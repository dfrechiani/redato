import { expect, test } from "@playwright/test";

/**
 * Smoke E2E M7 — dashboards de turma, escola e evolução do aluno.
 *
 * Roda contra mock-backend.mjs estendido. Cobre:
 * - Aba "Dashboard" na turma renderiza 5 elementos
 * - Toggle de modo (Foco/Completo/Todos)
 * - Estado vazio em turma sem envios
 * - Dashboard escola só pra coordenador (professor não vê item no menu)
 * - Comparação de turmas com ≥ 2 turmas populada
 * - Evolução do aluno com chart populado
 * - Aluno sem envios → estado vazio elegante
 * - Link "em risco" navega pra evolução do aluno
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

test.describe("M7 dashboard turma", () => {
  test("aba Dashboard renderiza 5 elementos principais", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/turma/t-prof-1");
    await page.getByRole("tab", { name: "Dashboard" }).click();
    // 1. Distribuição
    await expect(page.getByText(/Distribuição de notas/i)).toBeVisible();
    // 2. Top detectores (canônico humanizado)
    await expect(page.getByText(/Proposta de intervenção vaga/)).toBeVisible();
    // 3. Alunos em risco (Ana com 3 missoes baixas)
    await expect(page.getByText("Ana Aluna").first()).toBeVisible();
    await expect(page.getByText(/3 missões abaixo/)).toBeVisible();
    // 4. Evolução (≥ 3 missões → chart visível)
    await expect(page.getByText(/Evolução da turma/)).toBeVisible();
    // 5. Resumo (n_envios_total)
    await expect(page.getByText(/10\s+envios/)).toBeVisible();
  });

  test("toggle de modo filtra entre Foco / Completo / Todos", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/turma/t-prof-1");
    await page.getByRole("tab", { name: "Dashboard" }).click();
    // Default = Todos: ambas seções aparecem
    await expect(page.getByText(/Foco \(0-200\)/i)).toBeVisible();
    // Click em "Foco" — agora só foco
    await page.getByRole("tab", { name: "Foco" }).click();
    await expect(page.getByText(/Foco \(0-200\)/i)).toHaveCount(0);
    // Click em "Completo"
    await page.getByRole("tab", { name: "Completo" }).click();
    await expect(page.getByText(/161-200/)).toHaveCount(0);
  });

  test("turma vazia mostra estado vazio elegante", async ({ page }) => {
    await loginAs(page, PROF);
    // Mock retorna vazio pra turma_id "t-vazia"
    await page.goto("/turma/t-vazia");
    await page.getByRole("tab", { name: "Dashboard" }).click();
    await expect(page.getByText(/Sem envios ainda/i)).toBeVisible();
  });

  test("outros detectores aparecem como contagem agregada", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/turma/t-prof-1");
    await page.getByRole("tab", { name: "Dashboard" }).click();
    // Mock retorna outros_detectores=2
    await expect(page.getByText(/\+2 outros/)).toBeVisible();
  });
});

test.describe("M7 dashboard escola", () => {
  test("coordenador acessa via dropdown e vê dashboard completo", async ({ page }) => {
    await loginAs(page, COORD);
    await page.getByRole("button", { name: /Carla/ }).first().click();
    await page.getByRole("menuitem", { name: /Dashboard escola/ }).click();
    await page.waitForURL(/\/escola\/dashboard/);
    await expect(
      page.getByRole("heading", { name: /Dashboard da escola/i }),
    ).toBeVisible();
    // Comparação populada (2 turmas)
    await expect(page.getByText(/Comparação entre turmas/i)).toBeVisible();
    // Top detectores escola
    await expect(page.getByText(/Top detectores da escola/i)).toBeVisible();
    // Card 1A no resumo
    await expect(page.getByRole("heading", { name: /^1A$/ })).toBeVisible();
  });

  test("professor não vê 'Dashboard escola' no menu", async ({ page }) => {
    await loginAs(page, PROF);
    await page.getByRole("button", { name: /Maria/ }).first().click();
    await expect(
      page.getByRole("menuitem", { name: /Dashboard escola/ }),
    ).toHaveCount(0);
  });

  test("professor que tenta /escola/dashboard direto é redirecionado", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/escola/dashboard");
    // O server-side da página chama /auth/me e redireciona pra "/"
    await page.waitForURL("/", { timeout: 10_000 });
  });
});

test.describe("M7 evolução do aluno", () => {
  test("aluno com envios tem chart e missões realizadas", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/turma/t-prof-1/aluno/a1/evolucao");
    await expect(page.getByRole("heading", { name: /Ana Aluna/ }))
      .toBeVisible();
    await expect(page.getByText(/Evolução das notas/i)).toBeVisible();
    await expect(page.getByText(/Jogo Dissertativo/)).toBeVisible();
    // "Jogo de Redação" é o título humano da missão completo do 1S
    await expect(page.getByText(/Jogo de Redação/).first()).toBeVisible();
    // 1 missão pendente no mock
    await expect(page.getByText(/Missões pendentes/i)).toBeVisible();
  });

  test("aluno sem envios mostra estado vazio", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/turma/t-prof-1/aluno/a-pendente/evolucao");
    await expect(
      page.getByText(/Aluno ainda não realizou missões/i),
    ).toBeVisible();
  });

  test("link em 'alunos em risco' navega pra evolução", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/turma/t-prof-1");
    await page.getByRole("tab", { name: "Dashboard" }).click();
    // Click no link da Ana (em risco)
    await page.getByRole("link", { name: /Ana Aluna/ }).first().click();
    await page.waitForURL(/\/evolucao$/);
    await expect(page.getByRole("heading", { name: /Ana Aluna/ }))
      .toBeVisible();
  });
});
