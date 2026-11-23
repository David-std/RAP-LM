// Each test is one critical scenario of the test plan (docs/pruebas/plan-de-pruebas.md).
import { expect, test, type Page } from "@playwright/test";

async function ready(page: Page) {
  await page.goto("/");
  await expect(page.getByText(/Corrida publicada|Datos de ejemplo/)).toBeVisible();
  await expect(page.locator(".leaflet-overlay-pane path").first()).toBeAttached();
}

async function clickUnit(page: Page, index: number) {
  await page.locator(".leaflet-overlay-pane path").nth(index).dispatchEvent("click");
}

test("E2E-01 RF-01 RF-07: map shows every unit of the scope with legend and active period", async ({ page }) => {
  await ready(page);
  const paths = await page.locator(".leaflet-overlay-pane path").count();
  expect(paths).toBeGreaterThan(2800); // 2,899 cells + 43 district outlines
  await expect(page.getByLabel("Leyenda del mapa")).toContainText("Sin resultado, no equivale a bajo");
  await expect(page.locator(".statusbar")).toContainText("Periodo:");
});

test("E2E-02 RF-03 HU-11: changing the period updates map and status together", async ({ page }) => {
  await ready(page);
  const req = page.waitForRequest((r) => r.url().includes("/api/v1/risk") && r.url().includes("period_id=2021-"));
  await page.getByLabel("Año").first().selectOption("2021");
  await req;
  await expect(page.locator(".statusbar")).toContainText("2021");
});

test("E2E-03 RF-02 RF-08 HU-06 HU-07 HU-23: zone panel with risk, network series, record and provenance", async ({ page }) => {
  await ready(page);
  await clickUnit(page, 1500);
  const panel = page.getByLabel("Panel de zona");
  await expect(panel).toContainText("Riesgo estimado");
  await expect(panel).toContainText("La red año a año");
  await expect(panel).toContainText("Registro histórico del periodo");
  await expect(panel).toContainText("no conteos ni probabilidades");
  await panel.getByText("Procedencia y limitaciones").click();
  await expect(panel).toContainText("Fuentes del periodo");
  await panel.getByRole("button", { name: "Cerrar panel" }).click();
  await expect(panel).toContainText("Seleccione una zona en el mapa");
});

test("E2E-04 RF-04 HU-13 HU-16: level filter applies and clears in one action", async ({ page }) => {
  await ready(page);
  const req = page.waitForRequest((r) => r.url().includes("levels=high"));
  const chip = page.getByRole("button", { name: /^Alto/ });
  await chip.click();
  await req;
  await expect(chip).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText(/Mostrando alto en los 43 distritos/)).toBeVisible();
  await page.getByRole("button", { name: "Quitar filtros" }).click();
  await expect(chip).toHaveAttribute("aria-pressed", "false");
});

test("E2E-05 RF-05 HU-17: compare two districts in the same period", async ({ page }) => {
  await ready(page);
  await page.getByRole("button", { name: "Comparar" }).first().click();
  await page.getByRole("radio", { name: "Distrito" }).click();
  await page.getByLabel("Añadir distrito").selectOption({ label: "Ate" });
  await page.getByLabel("Añadir distrito").selectOption({ label: "Miraflores" });
  const table = page.getByRole("table").filter({ hasText: "Dif. con A" });
  await expect(table.getByRole("row")).toHaveCount(3);
  await expect(page.getByText("Mismo periodo, corrida y escala")).toBeVisible();
});

test("E2E-06 RF-06 HU-20: compare one district between two periods", async ({ page }) => {
  await ready(page);
  await page.getByRole("button", { name: "Comparar" }).first().click();
  await page.getByRole("radio", { name: "Zona entre periodos" }).click();
  await page.getByRole("radio", { name: "Distrito" }).click();
  await page.locator("#temporal-unit").selectOption({ label: "Ate" });
  await expect(page.getByText("Variación")).toBeVisible();
  await expect(page.getByText("Serie de años")).toBeVisible();
});

test("E2E-07 RF-08 HU-24..HU-26: methodology lists sources, variables, limitations and evaluation", async ({ page }) => {
  await ready(page);
  await page.getByRole("button", { name: "Metodología y fuentes" }).click();
  await expect(page.getByRole("heading", { name: "Fuentes", exact: true })).toBeVisible();
  await expect(page.getByText("No incorporada").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Limitaciones" })).toBeVisible();
});

test("E2E-09 RM-01 RM-05: model view shows architecture, benchmark and high-level errors", async ({ page }) => {
  await ready(page);
  await page.getByRole("button", { name: "Modelo" }).click();
  await expect(page.getByRole("heading", { name: "Arquitectura" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Benchmark en la prueba independiente" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Errores del nivel alto" })).toBeVisible();
  await expect(page.getByText("Mejora frente al promedio histórico (M-05)")).toBeVisible();
});

test("E2E-10 D-09: corridors view ranks streets and opens a street detail", async ({ page }) => {
  await ready(page);
  await page.getByRole("button", { name: "Corredores" }).click();
  const first = page.getByLabel("Detalle de corredores").getByRole("button").first();
  await expect(first).toBeVisible();
  await first.click();
  await expect(page.getByText("Atropellos por año")).toBeVisible();
});

test("E2E-11 D-09: recorded density, continuous heat view and Grad-CAM layer", async ({ page }) => {
  await ready(page);
  await page.getByRole("radio", { name: /Atropellos registrados/ }).click();
  await expect(page.getByText("Atropellos registrados por km²")).toBeVisible();
  await page.getByRole("radio", { name: "Calor" }).click();
  await expect(page.getByLabel("Mapa de calor continuo")).toBeVisible();
  await page.getByRole("radio", { name: "Distritos" }).click();
  await page.getByRole("radio", { name: /Grad-CAM/ }).click();
  await page.locator(".leaflet-overlay-pane path").nth(10).dispatchEvent("click");
  await expect(page.getByText(/Grad-CAM: celdas/)).toBeVisible();
});

test("E2E-08 analyst ranking exports CSV with run and scope", async ({ page }) => {
  await ready(page);
  await page.getByRole("button", { name: "Análisis" }).click();
  await expect(page.getByRole("table").locator("tbody tr").first()).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exportar CSV" }).click();
  const file = await download;
  const text = await (await file.createReadStream()).toArray().then((c) => Buffer.concat(c).toString("utf8"));
  expect(text).toContain("# RAP-LM export; run ");
  expect(text).toContain("risk_index");
});

test("E2E-12 D-11: forecast view with ranking, ensemble range and 2024 validation", async ({ page }) => {
  await ready(page);
  await page.getByRole("button", { name: "Pronóstico" }).click();
  await expect(page.getByRole("heading", { name: /Riesgo esperado en \d{4}/ })).toBeVisible();
  await expect(page.getByText("¿Es confiable?")).toBeVisible();
  const first = page.getByLabel("Detalle del pronóstico").locator("tbody tr").first();
  await expect(first).toBeVisible();
  await first.click();
  await expect(page.getByLabel("Detalle del pronóstico").locator("tbody tr.on")).toHaveCount(1);
});

