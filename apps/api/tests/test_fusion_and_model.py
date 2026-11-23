"""Unit tests of the fused pipeline and the CNN-LSTM contracts.

HT-05 (geocoding rules, grid), HT-06 (coverage offsets), HT-07/HT-08
(tensor shapes, causality: RM-02, RM-03).
"""

from __future__ import annotations

from datetime import date

import pytest
import torch
from shapely.geometry import LineString, box

from ml.fused.model import VARIANTS, SpatioTemporalModel, expected_observations
from pipelines.fusion.events import band_of, coverage_fraction, day_type_of
from pipelines.fusion.geocode import DistrictStreetIndex, candidate_streets
from pipelines.fusion.streets import Street, street_core
from pipelines.spatial.grid import District, build_grid


# ------------------------------------------------------------------ geocoding
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("AV LIMA ALT PLANTA BOMBA DE AGUA SEDAPAL SUR A NORTE", ["LIMA"]),
        (
            "AVENIDA DOCE DE OCTUBRE NO ESPECIFICA JIRON NEVADO CHANCHANI",
            ["12 OCTUBRE", "NEVADO CHANCHANI"],
        ),
        ("ICA CRUCE CON CANETE CANETE ALTURA DE LA IGLESIA", ["ICA", "CANETE"]),
        ("AVENIDA VENEZUELA CUADRA DIECISEIS", ["VENEZUELA"]),
        ("SIN NOMBRE COMITE UNO AA. HH. BELLA AURORA", ["COMITE"]),  # loose numbers dropped
    ],
)
def test_candidate_streets(text, expected):
    assert candidate_streets(text) == expected


def test_street_core_strips_type_and_stop_words():
    assert street_core("Avenida Túpac Amaru") == "TUPAC AMARU"
    assert street_core("Jirón de la Unión") == "UNION"


def _index():
    district = District("150101", "LIMA", box(0, 0, 1000, 1000))
    streets = [
        Street("ICA", ("Jirón Ica",), LineString([(0, 500), (1000, 500)])),
        Street("CANETE", ("Jirón Cañete",), LineString([(300, 0), (300, 1000)])),
        Street(
            "FERNANDO WIESSE", ("Avenida Fernando Wiesse",), LineString([(800, 0), (800, 1000)])
        ),
        Street("PRINCIPAL", ("Calle Principal",), LineString([(0, 100), (1000, 100)])),
    ]
    return DistrictStreetIndex(district, streets)


def test_intersection_yields_point_inside_district():
    result = _index().geocode("ICA CRUCE CON CANETE")
    assert result.precision == "intersection"
    assert (round(result.geometry.x), round(result.geometry.y)) == (300, 500)


def test_single_street_yields_line_not_invented_point():
    result = _index().geocode("AVENIDA WIESSE ALTURA DEL PARADERO")
    assert result.precision == "street"
    assert result.geometry.geom_type in {"LineString", "MultiLineString"}


def test_generic_or_unknown_reference_stays_at_district_level():
    idx = _index()
    assert idx.geocode("PRINCIPAL SIN REFERENCIA").precision == "district"
    assert idx.geocode("AVENIDA INEXISTENTE CUADRA 3").precision == "district"


# ------------------------------------------------------------------ grid & time
def test_grid_cells_belong_to_scope_and_fractions_sum_to_one():
    districts = [
        District("150101", "A", box(0, 0, 2000, 1000)),
        District("150102", "B", box(2000, 0, 3500, 1000)),
    ]
    spec, cells = build_grid(districts, 1000)
    assert len(cells) == 4  # 3.5 km x 1 km -> 4 columns
    for c in cells:
        assert abs(sum(c.district_fractions.values()) - 1) < 1e-6
        assert c.district_ubigeo in {"150101", "150102"}
    assert spec.cell_index(2500, 500) == (1, 3)
    assert spec.cell_index(-10, 500) is None


def test_coverage_offsets_follow_observation_windows():
    assert coverage_fraction("cenacom", 2016, "weekday") == 1.0
    assert 0.45 < coverage_fraction("cenacom", 2017, "weekday") < 0.55  # Jan-Jun only
    assert coverage_fraction("onsv", 2019, "weekday") == 0.0  # no source: not zero events
    assert coverage_fraction("onsv", 2025, "weekend") == 0.0  # open year excluded


def test_day_type_and_band():
    assert day_type_of(date(2024, 11, 23)) == "weekend"
    assert day_type_of(date(2024, 11, 22)) == "weekday"
    assert band_of("18:30") == 3 and band_of("00:00") == 0 and band_of("") is None


# ------------------------------------------------------------------ model contracts
@pytest.mark.parametrize("variant", VARIANTS)
def test_model_output_shape(variant):
    torch.manual_seed(0)
    model = SpatioTemporalModel(in_channels=5, subperiods=8, families=2, hidden=8, variant=variant)
    out = model(torch.randn(6, 5, 7, 9))
    assert out.shape == (6, 8, 7, 9)


@pytest.mark.parametrize("variant", ["cnn_lstm", "convlstm", "lstm_only"])
def test_recurrence_never_reads_the_future(variant):  # RM-03
    torch.manual_seed(0)
    model = SpatioTemporalModel(
        in_channels=3, subperiods=8, families=2, hidden=8, variant=variant
    ).eval()
    x = torch.randn(5, 3, 6, 6)
    altered = x.clone()
    altered[3:] += 10.0  # change only years 3 and 4
    with torch.no_grad():
        a, b = model(x), model(altered)
    assert torch.allclose(a[:3], b[:3])
    assert not torch.allclose(a[3:], b[3:])


def test_cnn_uses_spatial_neighbourhood():  # RM-02
    torch.manual_seed(0)
    model = SpatioTemporalModel(
        in_channels=2, subperiods=8, families=2, hidden=8, variant="cnn_lstm"
    ).eval()
    x = torch.zeros(2, 2, 7, 7)
    y = x.clone()
    y[:, :, 3, 4] = 5.0  # neighbour of cell (3, 3)
    with torch.no_grad():
        assert not torch.allclose(model(x)[:, :, 3, 3], model(y)[:, :, 3, 3])


def test_observation_operator_conserves_thinning():
    log_lambda = torch.zeros(1, 1, 2, 2)  # lambda = 1 in each of 4 cells
    valid = torch.ones(2, 2)
    frac = torch.ones(1, 2, 2)  # one district covering all cells
    cover = torch.ones(2, 1, 1)
    located = torch.tensor([[0.75], [0.5]])
    mu_c, mu_d = expected_observations(log_lambda, torch.zeros(2), cover, located, frac, valid)
    total = mu_c.sum(dim=(3, 4)) + mu_d.sum(dim=3)
    assert torch.allclose(total, torch.full_like(total, 4.0))


def test_git_sha_is_resolved_without_git_executable():  # RNF-02, incident I-10
    from pipelines.lineage import git_sha

    sha = git_sha()
    assert len(sha) == 40 and all(c in "0123456789abcdef" for c in sha)


def test_gradient_influence_matches_receptive_field():  # Grad-CAM style maps (D-09)
    from ml.fused.saliency import influence

    torch.manual_seed(0)
    x = torch.randn(4, 3, 9, 9)
    valid = torch.ones(9, 9)
    target = torch.zeros(9, 9)
    target[4, 4] = 1
    reach = {}
    for variant in ("lstm_only", "cnn_lstm"):
        model = SpatioTemporalModel(
            in_channels=3, subperiods=8, families=2, hidden=8, dropout=0.0, variant=variant
        ).eval()
        reach[variant] = int((influence([model], x, valid, 3, target) > 1e-9).sum())
    assert reach == {"lstm_only": 1, "cnn_lstm": 25}  # 1x1 kernels vs two 3x3 convolutions


def test_gradcam_is_non_negative_and_localised():  # Grad-CAM, HiResCAM variant
    from ml.fused.saliency import gradcam

    torch.manual_seed(0)
    model = SpatioTemporalModel(
        in_channels=3, subperiods=8, families=2, hidden=8, dropout=0.0, variant="convlstm"
    ).eval()
    target = torch.zeros(9, 9)
    target[4, 4] = 1
    cam = gradcam([model], torch.randn(4, 3, 9, 9), torch.ones(9, 9), 3, target)
    assert cam.shape == (9, 9)
    assert (cam >= 0).all() and cam.max() > 0
    # Four steps of 3x3 gates reach at most 3 cells away: the border stays at zero.
    assert cam[0, :].sum() == 0 and cam[:, 0].sum() == 0


def test_cenacom_vehicle_codes_follow_each_edition():  # D-12: questionnaire changed by edition
    from pipelines.fusion.vehicles import CENACOM_VEHICLE

    assert sorted(CENACOM_VEHICLE) == [17, 18, 19]
    for n, codes in CENACOM_VEHICLE.items():
        assert sorted(codes) == list(range(1, n + 1))
    # Moto lineal, motocar/mototaxi and bicicleta sit at different codes per edition.
    assert (CENACOM_VEHICLE[17][12], CENACOM_VEHICLE[17][13], CENACOM_VEHICLE[17][15]) == (
        "moto",
        "mototaxi",
        "bicicleta",
    )
    assert (CENACOM_VEHICLE[18][13], CENACOM_VEHICLE[18][14], CENACOM_VEHICLE[18][16]) == (
        "moto",
        "mototaxi",
        "bicicleta",
    )
    assert (CENACOM_VEHICLE[19][14], CENACOM_VEHICLE[19][15], CENACOM_VEHICLE[19][17]) == (
        "moto",
        "mototaxi",
        "bicicleta",
    )


def test_vehicle_shares_sum_to_one_event():  # several vehicles split one event
    from pipelines.fusion.vehicles import _split

    assert _split([]) == {"no_identificado": 1.0}
    shares = _split(["auto", "mototaxi", "auto"])
    assert abs(sum(shares.values()) - 1) < 1e-6 and shares["auto"] > shares["mototaxi"]


def test_cenacom_factor_codes_follow_each_edition():  # D-12: AT109 list changed by edition
    from pipelines.fusion.vehicles import CENACOM_FACTOR, _onsv_factor

    assert sorted(CENACOM_FACTOR) == [12, 15, 18, 19]
    for n, codes in CENACOM_FACTOR.items():
        assert sorted(codes) == list(range(1, n + 1))
        assert codes[1] == "velocidad"
    assert "senalizacion" not in CENACOM_FACTOR[12].values()  # 2012 had no such code
    assert CENACOM_FACTOR[15][12] == CENACOM_FACTOR[18][12] == "senalizacion"
    assert CENACOM_FACTOR[18][18] == CENACOM_FACTOR[19][18] == "sin_causa"
    assert _onsv_factor("EN PROCESO DE INVESTIGACION", "NO CUENTA CON CAUSA ESPECIFICA") == [
        "sin_causa"
    ]
    assert _onsv_factor("IMPRUDENCIA DEL PEATON", "ESTADO DE EBRIEDAD Y/O DROGADICCION") == [
        "peaton_alcohol"
    ]


def test_context_profile_percentiles():  # D-12: zone environment against the rest of Lima
    import numpy as np

    from pipelines.publication.context_profile import MIN_STREET_KM, _profiles

    ids = ["a", "b", "c", "d"]
    totals = {
        "street_km": np.array([10.0, 10.0, 10.0, 0.1]),
        "traffic_lights": np.array([1.0, 5.0, 10.0, 3.0]),
        "osm_signals": np.zeros(4),
        "pedestrian_crossings": np.zeros(4),
        "osm_crossings": np.zeros(4),
        "footway_km": np.zeros(4),
        "arterial_km": np.zeros(4),
        "poi_commerce": np.zeros(4),
        "poi_education": np.zeros(4),
        "poi_health": np.zeros(4),
        "transit_stops": np.zeros(4),
        "population": np.array([100.0, 200.0, 300.0, 400.0]),
    }
    out = _profiles(ids, totals, np.ones(4))
    signals = {u: dict((k, (v, p)) for k, v, p in out[u]).get("signals_per_street_km") for u in ids}
    assert signals["a"][1] < signals["b"][1] < signals["c"][1]
    assert signals["d"] is None and MIN_STREET_KM > 0.1  # too little street for a per-km ratio


def test_ranking_metrics():  # P1-05: precision measured with a budget, AP and validation threshold
    import numpy as np

    from ml.fused.classification import _average_precision, _ranking, best_threshold

    positive = np.array([True, False, True, False, False])
    perfect = np.array([0.9, 0.1, 0.8, 0.2, 0.3])
    assert _average_precision(perfect, positive) == 1.0
    worst = -perfect
    assert _average_precision(worst, positive) < 0.5
    r = _ranking(perfect, positive, 0.5)
    assert r["k"] == 2 and r["precision_at_k"] == 1.0
    assert r["at_validation_threshold"]["recall"] == 1.0
    assert best_threshold(perfect, positive) == 0.8
