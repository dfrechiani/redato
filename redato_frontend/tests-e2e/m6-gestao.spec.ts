import { expect, test } from "@playwright/test";

/**
 * Smoke E2E M6 — gestão (turmas, atividades, alunos, perfil).
 *
 * Roda contra mock-backend.mjs. Cada teste reseta a sessão fazendo
 * login via UI (não compartilha cookies — Playwright dá contexto novo
 * por teste por default).
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

test.describe("M6 home", () => {
  test("professor vê lista de turmas após login", async ({ page }) => {
    await loginAs(page, PROF);
    await expect(page.getByRole("heading", { name: /Suas turmas/i }))
      .toBeVisible();
    await expect(page.getByRole("heading", { name: /^1A$/ })).toBeVisible();
  });

  test("coordenador vê turmas agrupadas por professor", async ({ page }) => {
    await loginAs(page, COORD);
    await expect(page.getByRole("heading", { name: /Turmas da escola/i }))
      .toBeVisible();
    // 2 grupos (Maria + Outro Professor)
    await expect(page.getByRole("heading", { name: /Maria Professora/ }))
      .toBeVisible();
    await expect(page.getByRole("heading", { name: /Outro Professor/ }))
      .toBeVisible();
  });
});

test.describe("M6 turma detail", () => {
  test("abre detalhe + copia código", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await loginAs(page, PROF);
    await page.getByRole("link", { name: /1A/ }).first().click();
    await page.waitForURL(/\/turma\//);
    await expect(page.getByRole("heading", { name: /Turma 1A/ })).toBeVisible();
    await expect(page.getByText("TURMA-DEMO-1A-2026")).toBeVisible();
    await page.getByRole("button", { name: /Copiar código/i }).click();
    // Toast tem "!", o estado do botão muda pra "Copiado" (sem !).
    await expect(page.getByText("Copiado!")).toBeVisible();
  });

  test("expande lista de alunos e remove um", async ({ page, request }) => {
    await loginAs(page, PROF);
    // Garante que Bruno (a2) está ativo no estado do mock antes
    // do teste — outros testes paralelos podem ter inativado.
    const cookies = await page.context().cookies();
    const cookieHeader = cookies
      .map((c) => `${c.name}=${c.value}`).join("; ");
    await request.patch(
      "/api/portal/turmas/t-prof-1/alunos/a2",
      { data: { ativo: true }, headers: { Cookie: cookieHeader } },
    );
    await page.goto("/turma/t-prof-1");
    await page.getByRole("button", { name: /Alunos cadastrados/ }).click();
    await expect(page.getByText("Bruno Aluno")).toBeVisible();
    await page.getByRole("button", { name: /Remover Bruno Aluno/ }).click();
    await page.getByRole("button", { name: /Marcar inativo/ }).click();
    await expect(page.getByText(/marcado como inativo/i)).toBeVisible();
  });

  test("coordenador NÃO vê botão ativar missão", async ({ page }) => {
    await loginAs(page, COORD);
    await page.goto("/turma/t-prof-1");
    await expect(
      page.getByRole("button", { name: /\+ Ativar missão/ }),
    ).toHaveCount(0);
  });
});

test.describe("M6 ativar missão", () => {
  test("modal abre, lista missões, cria atividade", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/turma/t-prof-1");
    await page.getByRole("button", { name: /\+ Ativar missão/ }).click();
    await expect(page.getByRole("heading", { name: /^Ativar missão$/ }))
      .toBeVisible();
    // Selecionar missão diferente da já existente (m1)
    await page.locator('select').selectOption("m2");
    await page.getByRole("button", { name: /^Ativar$/ }).click();
    // Após criar, navega pra /atividade/{id}
    await page.waitForURL(/\/atividade\//, { timeout: 10_000 });
    // Após o fix UX: dropdown mostra título humano "Conectivos
    // Argumentativos" (corresponde a foco_c4) em vez do código cru.
    await expect(page.getByText(/Conectivos Argumentativos/)).toBeVisible();
  });

  test("aviso de duplicata aparece e permite continuar", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/turma/t-prof-1");
    await page.getByRole("button", { name: /\+ Ativar missão/ }).click();
    // m1 já tem atividade ativa — deve disparar duplicate_warning
    await page.locator('select').selectOption("m1");
    await page.getByRole("button", { name: /^Ativar$/ }).click();
    await expect(page.getByText(/Já existe uma atividade aberta/i))
      .toBeVisible();
    await page.getByRole("button", { name: /Criar mesmo assim/ }).click();
    await page.waitForURL(/\/atividade\//, { timeout: 10_000 });
  });
});

test.describe("M6 atividade detail + feedback aluno", () => {
  test("abre atividade com agregados", async ({ page, request }) => {
    await loginAs(page, PROF);
    // Reativa Bruno (a2) caso teste anterior tenha inativado ele
    const cookies = await page.context().cookies();
    const cookieHeader = cookies
      .map((c) => `${c.name}=${c.value}`).join("; ");
    await request.patch(
      "/api/portal/turmas/t-prof-1/alunos/a2",
      { data: { ativo: true }, headers: { Cookie: cookieHeader } },
    );
    await page.goto("/atividade/atv-1");
    await expect(page.getByRole("heading", { name: /Jogo Dissertativo/ }))
      .toBeVisible();
    await expect(page.getByText(/Distribuição de notas/)).toBeVisible();
    // Tabela (desktop) tem cell com nome; ignora a versão mobile escondida.
    await expect(page.getByRole("cell", { name: "Ana Aluna" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Bruno Aluno" })).toBeVisible();
  });

  test("clica em envio com feedback abre tela do aluno", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/atividade/atv-1");
    await page.getByRole("link", { name: /Ver feedback/ }).first().click();
    await page.waitForURL(/\/aluno\//);
    await expect(page.getByRole("heading", { name: /Ana Aluna/ }))
      .toBeVisible();
    await expect(page.getByText(/Nota total/i)).toBeVisible();
    await expect(page.locator("p", { hasText: /^720/ })).toBeVisible();
  });

  test("encerra atividade", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/atividade/atv-1");
    const encerrarBtn = page.getByRole("button", { name: /^Encerrar$/ });
    if (await encerrarBtn.isVisible()) {
      await encerrarBtn.click();
      await page.getByRole("button", { name: /^Encerrar$/ }).last().click();
      await expect(page.getByText("Atividade encerrada.")).toBeVisible();
    }
  });
});

test.describe("M6 perfil", () => {
  test("acessa perfil pelo dropdown e muda senha", async ({ page }) => {
    await loginAs(page, PROF);
    await page.getByRole("button", { name: /Maria/ }).first().click();
    await page.getByRole("menuitem", { name: /Perfil/ }).click();
    await page.waitForURL(/\/perfil/);
    await expect(page.getByRole("heading", { name: /^Perfil$/ }))
      .toBeVisible();

    await page.getByRole("button", { name: /Mudar senha/ }).click();
    await page.getByRole("textbox", { name: "Senha atual" }).fill("senha123");
    await page.getByRole("textbox", { name: "Nova senha", exact: true })
      .fill("nova-senha-456");
    await page.getByRole("textbox", { name: "Confirmar nova senha" })
      .fill("nova-senha-456");
    await page.getByRole("button", { name: /Salvar nova senha/ }).click();
    await expect(page.getByText(/Senha alterada/i)).toBeVisible();
  });

  test("senha atual incorreta mostra erro", async ({ page }) => {
    await loginAs(page, PROF);
    await page.goto("/perfil");
    await page.getByRole("button", { name: /Mudar senha/ }).click();
    await page.getByRole("textbox", { name: "Senha atual" }).fill("errada");
    await page.getByRole("textbox", { name: "Nova senha", exact: true })
      .fill("nova-senha-456");
    await page.getByRole("textbox", { name: "Confirmar nova senha" })
      .fill("nova-senha-456");
    await page.getByRole("button", { name: /Salvar nova senha/ }).click();
    await expect(page.getByText(/Senha atual incorreta/i)).toBeVisible();
  });
});
