import { expect, test } from "@playwright/test";

/**
 * Smoke E2E do M5. Roda contra mock-backend.mjs (porta 8091).
 *
 * Notas sobre seletores:
 * - Usamos `getByRole("textbox", { name: "X" })` em vez de `getByLabel`
 *   pra evitar ambiguidade com o asterisco "required" do FormField e o
 *   botão "Mostrar senha" do PasswordInput (que tem aria-label contendo
 *   "senha").
 * - Preferimos `getByText(...)` sobre `getByRole('alert')` porque o
 *   Next.js injeta um `<div role="alert" id="__next-route-announcer__">`
 *   global que casa com o role.
 */

const PROF_EMAIL = "prof@demo.redato";
const PROF_SENHA = "senha123";

test.describe("auth", () => {
  test("/login renderiza formulário", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText(/Portal do Professor/i)).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Email" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Senha" })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Entrar$/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Esqueci minha senha/i }))
      .toBeVisible();
    await expect(page.getByRole("checkbox", { name: /Lembrar de mim/i }))
      .toBeVisible();
  });

  test("submit vazio mostra erro", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: /^Entrar$/ }).click();
    await expect(page.getByText("Preencha email e senha.")).toBeVisible();
  });

  test("credenciais erradas mostram erro 401", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("textbox", { name: "Email" }).fill("errado@demo.redato");
    await page.getByRole("textbox", { name: "Senha" }).fill("senhaerrada");
    await page.getByRole("button", { name: /^Entrar$/ }).click();
    await expect(page.getByText(/Email ou senha incorretos/i)).toBeVisible();
  });

  test("usuário inativo recebe mensagem específica", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("textbox", { name: "Email" }).fill("inativo@demo.redato");
    await page.getByRole("textbox", { name: "Senha" }).fill("senha123");
    await page.getByRole("button", { name: /^Entrar$/ }).click();
    await expect(page.getByText(/conta está inativa/i)).toBeVisible();
  });

  test("login válido redireciona pra home autenticada", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("textbox", { name: "Email" }).fill(PROF_EMAIL);
    await page.getByRole("textbox", { name: "Senha" }).fill(PROF_SENHA);
    await page.getByRole("button", { name: /^Entrar$/ }).click();
    await page.waitForURL("/", { timeout: 15_000 });
    await expect(
      page.getByRole("heading", { name: /Olá, Maria/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /Suas turmas/i }),
    ).toBeVisible();
  });

  test("middleware: não autenticado em / redireciona pra /login com from", async ({ page }) => {
    await page.goto("/turmas/abc");
    await page.waitForURL(/\/login\?from=/);
    expect(page.url()).toContain("from=%2Fturmas%2Fabc");
  });

  test("logout limpa sessão e volta pra /login", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("textbox", { name: "Email" }).fill(PROF_EMAIL);
    await page.getByRole("textbox", { name: "Senha" }).fill(PROF_SENHA);
    await page.getByRole("button", { name: /^Entrar$/ }).click();
    await page.waitForURL("/", { timeout: 15_000 });

    await page.getByRole("button", { name: /Maria/ }).first().click();
    await page.getByRole("menuitem", { name: /^Sair$/ }).click();

    await page.waitForURL(/\/login$/);
    await page.goto("/");
    await page.waitForURL(/\/login\?from=/);
  });
});

test.describe("primeiro-acesso", () => {
  test("token expirado mostra mensagem", async ({ page }) => {
    await page.goto("/primeiro-acesso?token=TOKEN_EXPIRADO");
    await expect(page.getByRole("heading", { name: /Link expirado/i }))
      .toBeVisible();
  });

  test("token inválido mostra mensagem", async ({ page }) => {
    await page.goto("/primeiro-acesso?token=TOKEN_INVALIDO");
    await expect(page.getByRole("heading", { name: /Link inválido/i }))
      .toBeVisible();
  });

  test("sem token mostra mensagem", async ({ page }) => {
    await page.goto("/primeiro-acesso");
    await expect(page.getByRole("heading", { name: /Link incompleto/i }))
      .toBeVisible();
  });

  test("token válido define senha e redireciona /login", async ({ page }) => {
    await page.goto("/primeiro-acesso?token=TOKEN_OK");
    await expect(page.getByRole("heading", { name: /Defina sua senha/i }))
      .toBeVisible();
    await page.getByRole("textbox", { name: "Nova senha" }).fill("senha-forte-123");
    await page.getByRole("textbox", { name: "Confirmar senha" }).fill("senha-forte-123");
    await page.getByRole("button", { name: /Definir senha/ }).click();
    await page.waitForURL(/\/login$/, { timeout: 10_000 });
  });

  test("senha fraca mostra erro local", async ({ page }) => {
    await page.goto("/primeiro-acesso?token=TOKEN_OK");
    await page.getByRole("textbox", { name: "Nova senha" }).fill("abc");
    await page.getByRole("textbox", { name: "Confirmar senha" }).fill("abc");
    await page.getByRole("button", { name: /Definir senha/ }).click();
    await expect(page.getByText(/pelo menos 8 caracteres/i)).toBeVisible();
  });

  test("senhas diferentes mostra erro", async ({ page }) => {
    await page.goto("/primeiro-acesso?token=TOKEN_OK");
    await page.getByRole("textbox", { name: "Nova senha" }).fill("senha-forte-123");
    await page.getByRole("textbox", { name: "Confirmar senha" }).fill("senha-diferente-123");
    await page.getByRole("button", { name: /Definir senha/ }).click();
    await expect(page.getByText(/não conferem/i)).toBeVisible();
  });
});

test.describe("reset-password", () => {
  test("sem token: solicita reset", async ({ page }) => {
    await page.goto("/reset-password");
    await expect(page.getByRole("heading", { name: /Esqueceu a senha/i }))
      .toBeVisible();
    await page.getByRole("textbox", { name: "Email" }).fill(PROF_EMAIL);
    await page.getByRole("button", { name: /Enviar link/ }).click();
    await expect(page.getByRole("heading", { name: /Verifique seu email/i }))
      .toBeVisible();
  });

  test("com token: confirma nova senha → redirect /login", async ({ page }) => {
    await page.goto("/reset-password?token=TOKEN_OK");
    await expect(page.getByRole("heading", { name: /^Nova senha$/i }))
      .toBeVisible();
    await page.getByRole("textbox", { name: "Nova senha" }).fill("senha-forte-123");
    await page.getByRole("textbox", { name: "Confirmar senha" }).fill("senha-forte-123");
    await page.getByRole("button", { name: /Redefinir senha/ }).click();
    await page.waitForURL(/\/login$/, { timeout: 10_000 });
  });

  test("token expirado mostra erro", async ({ page }) => {
    await page.goto("/reset-password?token=TOKEN_EXPIRADO");
    await page.getByRole("textbox", { name: "Nova senha" }).fill("senha-forte-123");
    await page.getByRole("textbox", { name: "Confirmar senha" }).fill("senha-forte-123");
    await page.getByRole("button", { name: /Redefinir senha/ }).click();
    await expect(page.getByText(/Este link expirou/i)).toBeVisible();
  });
});
