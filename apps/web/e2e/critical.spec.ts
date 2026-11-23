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
  await page.getByRole("radio", { name: "2021" }).first().click();
  await req;
  await expect(page.locator(".statusbar")).toContainText("2021");
});

test("E2E-03 RF-02 RF-08 HU-06 HU-07: unit detail with index, level, record and provenance", async ({ page }) => {
  await ready(page);
  await clickUnit(page, 1500);
  const detail = page.getByLabel("Detalle de la unidad seleccionada");
  await expect(detail).toContainText("Índice de riesgo");
  await expect(detail).toContainText("Registro histórico observado");
  await expect(detail).toContainText("Fuentes del periodo");
  await expect(detail).toContainText("estimado por el modelo");
  await detail.getByRole("button", { name: "Cerrar detalle" }).click();
  await expect(detail).toBeHidden();
});

test("E2E-04 RF-04 HU-13 HU-16: level filter applies and clears in one action", async ({ page }) => {
  await ready(page);
  const req = page.waitForRequest((r) => r.url().includes("levels=high"));
  await page.getByRole("checkbox", { name: /Alto/ }).check();
  await req;
  await expect(page.getByText(/Filtros: Alto/)).toBeVisible();
  await page.getByRole("button", { name: "Quitar filtros" }).click();
  await expect(page.getByRole("checkbox", { name: /Alto/ })).not.toBeChecked();
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
  await expect(page.getByText("Mejora relativa (M-05)")).toBeVisible();
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
