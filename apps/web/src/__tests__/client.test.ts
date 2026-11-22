// Typed API client: parameters, error contract and cancellation (RT-02).
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError } from "../api/client";

afterEach(() => vi.restoreAllMocks());

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }),
  );
}

describe("api client", () => {
  it("serialises filters as comma-separated lists and skips empty ones", async () => {
    const spy = mockFetch(200, { data: [] });
    await api.risk({ periodId: "2024-wd-1824", unitType: "cell", levels: ["high", "medium"], districtIds: [] });
    const url = String(spy.mock.calls[0][0]);
    expect(url).toContain("/api/v1/risk?");
    expect(url).toContain("period_id=2024-wd-1824");
    expect(url).toContain("levels=high%2Cmedium");
    expect(url).not.toContain("district_ids");
  });

  it("raises the contract error code", async () => {
    mockFetch(404, { error: { code: "UNKNOWN_PERIOD", message: "nope", details: {} } });
    await expect(api.periods()).rejects.toMatchObject({ status: 404, code: "UNKNOWN_PERIOD" });
    await expect(api.periods()).rejects.toBeInstanceOf(ApiError);
  });

  it("forwards the abort signal so stale period requests are cancelled", async () => {
    const spy = mockFetch(200, {});
    const controller = new AbortController();
    await api.compareTemporal("cell", "F1-C1", ["a", "b"], controller.signal);
    expect((spy.mock.calls[0][1] as RequestInit).signal).toBe(controller.signal);
  });
});
