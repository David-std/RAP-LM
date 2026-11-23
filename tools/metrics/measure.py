"""Measure product quality metrics against the running stack (WBS 4.3; Tables 34-35).

Usage::

    python -m tools.metrics.measure --api http://127.0.0.1:8000 \
        --dataset artifacts/datasets/fused-v1.0.0 --run artifacts/runs/<run_id> \
        [--rerun artifacts/runs/<rerun_id>] --out evidence/metrics

Each metric writes ``<id>.json`` with numerator, denominator, value, target,
run, environment and timestamp. A metric that cannot be computed is written
as ``not_measured`` with its reason; an empty denominator never counts as met.

* M-01 spatial correspondence: ONSV reference coordinates (independent of the
  geocoder) must fall inside the geometry served by /units for the unit that
  holds the event.
* M-02 result completeness: every result served by /risk for every published
  period carries unit, period, value, level and legend (or explicit no_result).
* M-03 source/version traceability: a sample of results resolved through
  /provenance returns sources and dataset version.
* M-04 pipeline reproducibility: two runs with the same data/code/config are
  aligned by (unit, period); value within 1 % (0 when reference is 0) and
  identical level.
* M-05 relative error improvement: read from the run's frozen test evaluation.
* M-08 query correctness: API values vs results.csv for single-unit queries,
  level/district filters and comparisons (golden cases).
* M-09 API p95 latency of /risk and /comparisons under sequential load.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import random
import statistics
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from shapely.geometry import Point, shape

TARGETS = {
    "M-01": ">= 95 %",
    "M-02": ">= 95 %",
    "M-03": ">= 95 %",
    "M-04": ">= 95 % values within tolerance; 100 % unit/period/level match",
    "M-05": "> 0 %",
    "M-08": ">= 95 % overall, 100 % critical",
    "M-09": "p95 <= 2 s",
}


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def get(self, path: str, **params) -> tuple[int, dict, float]:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.base}{path}{'?' + query if query else ''}"
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                body = json.loads(r.read())
                status = r.status
        except urllib.error.HTTPError as e:
            body, status = json.loads(e.read() or b"{}"), e.code
        return status, body, time.perf_counter() - start


def write(out: Path, metric: str, payload: dict, run_id: str) -> None:
    payload = {
        "metric": metric,
        "target": TARGETS.get(metric),
        "run_id": run_id,
        "measured_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "machine": platform.machine(),
            "os": platform.system(),
        },
        **payload,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{metric}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        metric,
        json.dumps({k: payload.get(k) for k in ("numerator", "denominator", "value", "status")}),
    )


def ratio(num: int, den: int) -> float | None:
    return round(num / den * 100, 4) if den else None


def m01(api: Api, dataset: Path, harmonized: Path | None, out: Path, run_id: str) -> None:
    if not harmonized:
        write(out, "M-01", {"status": "not_measured", "reason": "--harmonized not given"}, run_id)
        return
    units = api.get("/api/v1/units", unit_type="cell")[1]
    geoms = {f["properties"]["unit_id"]: shape(f["geometry"]) for f in units["features"]}
    alloc = {}
    with (dataset / "events.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["precision"] == "point":
                alloc[r["event_id"]] = next(iter(json.loads(r["allocation"])))
    num = den = 0
    failures = []
    with harmonized.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            uid = alloc.get(r["event_id"])
            if not uid:
                continue
            den += 1
            point = Point(float(r["longitude"]), float(r["latitude"]))
            if geoms[uid].buffer(1e-7).contains(point):
                num += 1
            elif len(failures) < 10:
                failures.append({"event_id": r["event_id"], "unit_id": uid})
    write(
        out,
        "M-01",
        {
            "numerator": num,
            "denominator": den,
            "value": ratio(num, den),
            "reference": "ONSV coordinates validated inside the declared district",
            "failures_sample": failures,
        },
        run_id,
    )


def m02_m03(api: Api, out: Path, run_id: str) -> None:
    periods = api.get("/api/v1/periods")[1]["data"]
    num = den = 0
    missing: list[str] = []
    sample: list[tuple[str, str, str]] = []
    for unit_type in ("cell", "district"):
        for p in periods:
            body = api.get("/api/v1/risk", period_id=p["period_id"], unit_type=unit_type)[1]
            legend_ok = bool(body["meta"]["legend"]["bands"])
            for r in body["data"]:
                den += 1
                ok = (
                    legend_ok
                    and r["unit"]["unit_id"]
                    and r["period"]["period_id"] == p["period_id"]
                    and r["run_id"] == run_id
                    and (
                        (
                            r["availability"] == "estimated"
                            and r["risk_level"]
                            and r["risk_index"] is not None
                            and r["indicator_value"] is not None
                        )
                        or (r["availability"] != "estimated" and r["risk_level"] is None)
                    )
                )
                num += bool(ok)
                if not ok and len(missing) < 10:
                    missing.append(f"{r['unit']['unit_id']}/{p['period_id']}")
                sample.append((unit_type, r["unit"]["unit_id"], p["period_id"]))
    write(
        out,
        "M-02",
        {
            "numerator": num,
            "denominator": den,
            "value": ratio(num, den),
            "scope": "all units x all published periods, cell and district views (API DTO)",
            "failures_sample": missing,
        },
        run_id,
    )
    random.seed(20261122)
    picked = random.sample(sample, min(200, len(sample)))
    ok3 = 0
    for unit_type, uid, pid in picked:
        _, body, _ = api.get("/api/v1/provenance", unit_type=unit_type, unit_id=uid, period_id=pid)
        if (
            body.get("run", {}).get("run_id") == run_id
            and body["meta"]["run"]["dataset_version_id"]
            and any(s["incorporated"] for s in body["sources"])
            and body["result_context"]["observing_sources"]
        ):
            ok3 += 1
    write(
        out,
        "M-03",
        {
            "numerator": ok3,
            "denominator": len(picked),
            "value": ratio(ok3, len(picked)),
            "sampling": "200 random (unit, period) pairs, seed 20261122",
        },
        run_id,
    )


def read_results(path: Path) -> dict[tuple[str, str, str], dict]:
    with path.open(encoding="utf-8") as f:
        return {
            (r["representation_id"], r["unit_id"], r["period_id"]): r for r in csv.DictReader(f)
        }


def m04(run: Path, rerun: Path | None, out: Path, run_id: str) -> None:
    if not rerun:
        write(out, "M-04", {"status": "not_measured", "reason": "--rerun not given"}, run_id)
        return
    ref, new = read_results(run / "results.csv"), read_results(rerun / "results.csv")
    keys = set(ref) | set(new)
    aligned = within = level_match = 0
    for k in keys:
        a, b = ref.get(k), new.get(k)
        if not a or not b:
            continue
        aligned += 1
        va, vb = float(a["indicator_value"] or 0), float(b["indicator_value"] or 0)
        ok = (vb == 0) if va == 0 else abs(vb - va) / abs(va) <= 0.01
        within += ok
        level_match += a["risk_level"] == b["risk_level"]
    write(
        out,
        "M-04",
        {
            "numerator": within,
            "denominator": len(keys),
            "value": ratio(within, len(keys)),
            "unit_period_alignment_pct": ratio(aligned, len(keys)),
            "level_match_pct": ratio(level_match, len(keys)),
            "reference_run": run.name,
            "rerun": rerun.name,
        },
        run_id,
    )


def m05(run: Path, out: Path, run_id: str, extra: list[Path]) -> None:
    rows = []
    for r in [run, *extra]:
        m = json.loads((r / "metrics.json").read_text(encoding="utf-8"))
        for t in m["test"]:
            rows.append(
                {
                    "run": r.name,
                    "variant": m["selected_variant"],
                    "family": t["family"],
                    "year": t["year"],
                    "E_baseline": t["baseline"] and t["baseline"]["district_mae"],
                    "E_model": t["model"]["district_mae"],
                    "improvement_pct": t["relative_improvement_pct"],
                }
            )
    write(
        out,
        "M-05",
        {
            "evaluations": rows,
            "value": rows[0]["improvement_pct"] if rows else None,
            "formula": "(E_baseline - E_model) / E_baseline * 100, E = district x subperiod MAE",
        },
        run_id,
    )


def m08(api: Api, run: Path, out: Path, run_id: str) -> None:
    ref = read_results(run / "results.csv")
    cases: list[tuple[str, bool, bool]] = []  # (name, passed, critical)
    random.seed(7)
    keys = random.sample(sorted(ref), 150)
    for rep, uid, pid in keys:
        unit_type = "cell" if rep == "grid-1km" else "district"
        body = api.get("/api/v1/risk", period_id=pid, unit_type=unit_type, unit_id=uid)[1]
        got = body["data"][0]
        exp = ref[(rep, uid, pid)]
        ok = (
            got["unit"]["unit_id"] == uid
            and got["period"]["period_id"] == pid
            and abs(got["indicator_value"] - float(exp["indicator_value"]))
            <= 1e-6 * max(1, float(exp["indicator_value"]))
            and got["risk_level"] == exp["risk_level"]
        )
        cases.append((f"detail {uid} {pid}", ok, True))
    periods = sorted({k[2] for k in ref})
    for pid in random.sample(periods, 6):
        for level in ("high", "low"):
            body = api.get("/api/v1/risk", period_id=pid, unit_type="cell", levels=level)[1]
            expected = {
                k[1]
                for k, v in ref.items()
                if k[0] == "grid-1km" and k[2] == pid and v["risk_level"] == level
            }
            cases.append(
                (
                    f"filter level={level} {pid}",
                    {r["unit"]["unit_id"] for r in body["data"]} == expected,
                    True,
                )
            )
        body = api.get("/api/v1/risk", period_id=pid, unit_type="district", district_ids="150132")[
            1
        ]
        cases.append(
            (
                f"filter district {pid}",
                [r["unit"]["unit_id"] for r in body["data"]] == ["150132"],
                True,
            )
        )
    cell_ids = sorted({k[1] for k in ref if k[0] == "grid-1km"})
    for _ in range(10):
        pid = random.choice(periods)
        units = random.sample(cell_ids, 3)
        body = api.get(
            "/api/v1/comparisons", mode="spatial", unit_ids=",".join(units), period_id=pid
        )[1]
        ok = all(
            it["result"]["unit"]["unit_id"] == u
            and it["result"]["period"]["period_id"] == pid
            and it["result"]["risk_level"] == ref[("grid-1km", u, pid)]["risk_level"]
            for it, u in zip(body["items"], units, strict=True)
        )
        cases.append((f"spatial compare {pid}", ok, True))
        uid = random.choice(cell_ids)
        ps = random.sample(periods, 3)
        body = api.get(
            "/api/v1/comparisons", mode="temporal", unit_id=uid, period_ids=",".join(ps)
        )[1]
        ok = all(
            it["result"]["period"]["period_id"] == p
            and it["result"]["unit"]["unit_id"] == uid
            and it["result"]["risk_level"] == ref[("grid-1km", uid, p)]["risk_level"]
            for it, p in zip(body["items"], ps, strict=True)
        )
        cases.append((f"temporal compare {uid}", ok, True))
    passed = sum(c[1] for c in cases)
    crit = [c for c in cases if c[2]]
    write(
        out,
        "M-08",
        {
            "numerator": passed,
            "denominator": len(cases),
            "value": ratio(passed, len(cases)),
            "critical_pass_pct": ratio(sum(c[1] for c in crit), len(crit)),
            "expected_source": "results.csv exported before publication",
            "failed_cases": [c[0] for c in cases if not c[1]][:20],
        },
        run_id,
    )


def _m09_requests(api: Api, run: Path, n: int, seed: int) -> list:
    """Mixed workload: full-map /risk (2,899 cells) and 4-unit /comparisons."""
    ref = read_results(run / "results.csv")
    periods = sorted({k[2] for k in ref})
    cells = sorted({k[1] for k in ref if k[0] == "grid-1km"})
    rnd = random.Random(seed)
    calls = []
    for i in range(n):
        pid = rnd.choice(periods)
        if i % 2 == 0:
            calls.append(("/api/v1/risk", {"period_id": pid, "unit_type": "cell"}))
        else:
            calls.append(
                (
                    "/api/v1/comparisons",
                    {
                        "mode": "spatial",
                        "unit_ids": ",".join(rnd.sample(cells, 4)),
                        "period_id": pid,
                    },
                )
            )
    return calls


def _m09_summary(results: list[tuple[int, dict, float]]) -> dict:
    timings = sorted(t for _s, _b, t in results)
    return {
        "requests": len(timings),
        "errors": sum(s != 200 for s, _b, _t in results),
        "p95": round(timings[int(0.95 * len(timings)) - 1], 4),
        "median": round(statistics.median(timings), 4),
        "max": round(timings[-1], 4),
    }


def m09(api: Api, run: Path, out: Path, run_id: str, n: int = 200, workers: int = 10) -> None:
    """p95 latency sequentially and with ``workers`` simultaneous clients (audit P2)."""
    from concurrent.futures import ThreadPoolExecutor

    calls = _m09_requests(api, run, n, seed=11)
    sequential = _m09_summary([api.get(path, **params) for path, params in calls])
    with ThreadPoolExecutor(max_workers=workers) as pool:
        concurrent = _m09_summary(list(pool.map(lambda c: api.get(c[0], **c[1]), calls)))
    met = all(x["p95"] <= 2 and x["errors"] == 0 for x in (sequential, concurrent))
    write(
        out,
        "M-09",
        {
            "value": max(sequential["p95"], concurrent["p95"]),
            "unit": "seconds",
            "requests": n,
            "errors": sequential["errors"] + concurrent["errors"],
            "sequential": sequential,
            "concurrent": concurrent | {"clients": workers},
            "load": "mixed full-map /risk (2,899 cells) and 4-unit /comparisons; sequential, then "
            f"{workers} simultaneous clients",
            "status": "met" if met else "not_met",
        },
        run_id,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--rerun", type=Path)
    ap.add_argument("--extra-eval", type=Path, action="append", default=[])
    ap.add_argument("--harmonized", type=Path)
    ap.add_argument("--out", type=Path, default=Path("evidence/metrics"))
    args = ap.parse_args()
    api = Api(args.api)
    run_id = api.get("/api/v1/periods")[1]["meta"]["run"]["run_id"]
    m01(api, args.dataset, args.harmonized, args.out, run_id)
    m02_m03(api, args.out, run_id)
    m04(args.run, args.rerun, args.out, run_id)
    m05(args.run, args.out, run_id, args.extra_eval)
    m08(api, args.run, args.out, run_id)
    m09(api, args.run, args.out, run_id)


if __name__ == "__main__":
    main()
