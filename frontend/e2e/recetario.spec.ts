import { expect, test } from "@playwright/test";

const stamp = Date.now();

test("alta manual, edición, PDF y búsqueda en la estantería", async ({ page }) => {
  const title = `Tortilla e2e ${stamp}`;

  await page.goto("/nueva");
  await page.getByLabel("Título").fill(title);
  await page
    .getByLabel("Descripción")
    .fill("Receta escrita a mano para el flujo e2e.");
  await page.getByLabel("Cantidad").first().fill("4");
  await page
    .getByRole("textbox", { name: "Ingrediente 1", exact: true })
    .fill("patata");
  await page.getByRole("button", { name: "Añadir ingrediente" }).click();
  await page.getByLabel("Cantidad").nth(1).fill("5");
  await page
    .getByRole("textbox", { name: "Ingrediente 2", exact: true })
    .fill("huevo");
  await page
    .getByRole("textbox", { name: "Paso 1", exact: true })
    .fill("Pelar y cortar las patatas.");
  await page.getByRole("button", { name: "Añadir paso" }).click();
  await page
    .getByRole("textbox", { name: "Paso 2", exact: true })
    .fill("Batir los huevos y cuajar la tortilla.");

  await page.getByRole("button", { name: "Guardar en el recetario" }).click();

  await page.waitForURL(/\/recetas\/[0-9a-f-]+$/);
  await expect(page.getByText("Aprobada", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();

  await page.getByRole("button", { name: "Editar" }).click();
  const editedTitle = `${title} editada`;
  await page.getByLabel("Título").fill(editedTitle);
  await page.getByRole("button", { name: "Guardar cambios" }).click();
  await expect(
    page.getByText("Cambios guardados en esta página."),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: editedTitle })).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "PDF" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);

  await page.goto("/");
  await page
    .getByPlaceholder("Buscar por receta o ingrediente…")
    .fill(editedTitle);
  await expect(
    page.getByRole("link", { name: new RegExp(editedTitle) }),
  ).toBeVisible();
});

test("ingesta simulada: trabajo, revisión y aprobación", async ({ page }) => {
  await page.goto("/importar");

  await page.getByRole("tab", { name: "Pegar texto" }).click();
  await page
    .getByLabel("Caption del video")
    .fill("2 pechugas de pollo y 1 limón para una receta rápida");
  await page.getByRole("button", { name: "Extraer la receta" }).click();

  await expect(
    page.getByRole("heading", { name: "La página está lista" }),
  ).toBeVisible({ timeout: 45_000 });

  await page.getByRole("link", { name: "Abrir la receta" }).click();
  await page.waitForURL(/\/recetas\/[0-9a-f-]+$/);

  await expect(page.getByRole("button", { name: "Aprobar" })).toBeVisible();
  await page.getByRole("button", { name: "Aprobar" }).click();

  await expect(page.getByText("Aprobada", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Aprobar" })).toHaveCount(0);
});
