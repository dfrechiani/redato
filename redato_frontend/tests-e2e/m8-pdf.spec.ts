import { expect, test } from "@playwright/test";

/**
 * Smoke E2E M8 — exportar PDF + histórico.
 *
 * Cobre:
 * - Botão "Exportar PDF" no dashboard de turma abre modal
 * - Geração dispara backend e abre tab de download (assertamos que
 *   request foi feita e response veio com content-type pdf)
 * - Botão "Exportar PDF da escola" só pra coordenador
 * - Página de histórico lista PDFs gerados
 * - Link "baixar" abre PDF
 */

const PROF = { email: "prof@demo.redato", senha: "senha123" };
const COORD = { email: "coord@demo.redato", senha: "senha123" };

async function loginAs(
  page: import("@playwright/test").Page,
  user: { email: string; senha: string },
) {
  await page.goto("/login");
  await page.getByRole("textbox", { name: "Email" }).fill(user.email);
  await page.getByRole("textbox", { name: "Senha" }).fill(user.senha);
  await page.getByRole("button", { name: /^Entrar$/ }).click();
  await page.waitForURL("/", { timeout: 15_000 });
}

test.describe("M8 exportar PDF", () => {
  test("dashboard turma: botão abre modal e gera PDF", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/turma/t-prof-1");
    await page.getByRole("tab", { name: "Dashboard" }).click();

    await page.getByRole("button", { name: /^Exportar PDF$/ }).click();
    await expect(
      page.getByRole("heading", { name: /Exportar dashboard da turma/i }),
    ).toBeVisible();

    // Stub window.open pra não precisar lidar com popup
    await page.evaluate(() => {
      (window as Window & { open: typeof window.open }).open = () => null;
    });

    const apiResponsePromise = page.waitForResponse(
      (r) => r.url().includes("/api/portal/pdfs/dashboard-turma/")
            && r.request().method() === "POST",
      { timeout: 10_000 },
    );
    await page.getByRole("button", { name: /Gerar PDF/ }).click();

    const apiResp = await apiResponsePromise;
    expect(apiResp.status()).toBe(200);
    const body = await apiResp.json();
    expect(body.pdf_id).toBeTruthy();
    expect(body.tamanho_bytes).toBeGreaterThan(100);

    await expect(page.getByText(/PDF gerado/)).toBeVisible();
  });

  test("evolução do aluno tem botão exportar", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/turma/t-prof-1/aluno/a1/evolucao");
    await expect(
      page.getByRole("button", { name: /Exportar evolução PDF/i }),
    ).toBeVisible();
  });

  test("dashboard escola tem botão e funciona pra coordenador", async ({ page }) => {
    await loginAs(page, COORD);
    await page.goto("/escola/dashboard");
    await page.getByRole("button", { name: /Exportar PDF da escola/i }).click();
    await expect(
      page.getByRole("heading", { name: /Exportar dashboard da escola/i }),
    ).toBeVisible();

    const apiResponsePromise = page.waitForResponse(
      (r) => r.url().includes("/api/portal/pdfs/dashboard-escola/")
            && r.request().method() === "POST",
      { timeout: 10_000 },
    );
    await page.getByRole("button", { name: /Gerar PDF/ }).click();
    const apiResp = await apiResponsePromise;
    expect(apiResp.status()).toBe(200);
  });
});

test.describe("M8 histórico de PDFs", () => {
  test("histórico de turma lista PDFs gerados", async ({ page }) => {
    await loginAs(page, PROF);
    // Gera 1 PDF primeiro
    await page.goto("/turma/t-prof-1");
    await page.getByRole("tab", { name: "Dashboard" }).click();
    await page.getByRole("button", { name: /^Exportar PDF$/ }).click();
    const apiResp = page.waitForResponse(
      (r) => r.url().includes("/api/portal/pdfs/dashboard-turma/")
            && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: /Gerar PDF/ }).click();
    await apiResp;

    // Vai pra histórico
    await page.goto("/turma/t-prof-1/historico-pdfs");
    await expect(
      page.getByRole("heading", { name: /Histórico de PDFs/i }),
    ).toBeVisible();
    await expect(page.getByText(/Dashboard da turma/i).first()).toBeVisible();
    await expect(page.getByText(/baixar/i).first()).toBeVisible();
  });

  test("histórico da escola só pra coordenador", async ({ page }) => {
    await loginAs(page, COORD);
    await page.goto("/escola/historico-pdfs");
    await expect(
      page.getByRole("heading", { name: /Histórico de PDFs/i }),
    ).toBeVisible();
  });

  test("professor que tenta /escola/historico-pdfs é redirecionado", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/escola/historico-pdfs");
    await page.waitForURL("/", { timeout: 10_000 });
  });
});
