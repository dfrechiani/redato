/**
 * Testes manuais de diff-words.ts (Fase 2 passo 7a).
 *
 * Frontend ainda NÃO tem setup de jest/vitest (anotado como pendência
 * — ver commit 32d7162). Esses testes são scripts standalone que
 * Daniel roda manualmente:
 *
 *     cd redato_frontend
 *     npx tsx lib/diff-words.test.ts
 *
 * Exit code 0 = todos os asserts passaram. Saída textual mostra o
 * diff produzido pra cada cenário pra inspeção visual.
 *
 * Cobre:
 * - Cópia literal: diff = 1 segmento op=0, pctAutoral=0
 * - Reescrita autoral total: 1 op=-1 + 1 op=1 (sem op=0), pctAutoral=100
 * - Reescrita parcial: mistura de ops, pctAutoral entre 30-70
 * - Paráfrase superficial: poucos op=±1, pctAutoral baixo (~5-20)
 * - Edge cases: textos vazios, idênticos, só whitespace
 */

import { tokenize, diffByWords, pctAutoral } from "./diff-words";


/* eslint-disable no-console */


// ──────────────────────────────────────────────────────────────────────
// Mini-runner pra Daniel rodar via tsx sem jest
// ──────────────────────────────────────────────────────────────────────

let passed = 0;
let failed = 0;

function test(name: string, fn: () => void): void {
  try {
    fn();
    passed += 1;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    failed += 1;
    console.log(`  ✗ ${name}`);
    console.log(`    ${(err as Error).message}`);
  }
}

function assertEq<T>(actual: T, expected: T, msg = ""): void {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    throw new Error(
      `${msg}\n      actual:   ${a}\n      expected: ${e}`,
    );
  }
}

function assertTrue(cond: boolean, msg: string): void {
  if (!cond) throw new Error(msg);
}


// ──────────────────────────────────────────────────────────────────────
// tokenize
// ──────────────────────────────────────────────────────────────────────

console.log("\n=== tokenize ===");

test("tokenize separa palavras + espaços + pontuação", () => {
  const out = tokenize("oi mundo, tudo bem?");
  // Esperado: ["oi", " ", "mundo,", " ", "tudo", " ", "bem?"]
  assertEq(out, ["oi", " ", "mundo,", " ", "tudo", " ", "bem?"]);
});

test("tokenize preserva quebras de linha", () => {
  const out = tokenize("primeiro\n\nsegundo");
  assertEq(out, ["primeiro", "\n\n", "segundo"]);
});

test("tokenize string vazia retorna array vazio", () => {
  assertEq(tokenize(""), []);
});

test("tokenize só whitespace agrupado", () => {
  // 3 espaços viram 1 token de whitespace
  assertEq(tokenize("   "), ["   "]);
});


// ──────────────────────────────────────────────────────────────────────
// diffByWords — 4 cenários canônicos
// ──────────────────────────────────────────────────────────────────────

console.log("\n=== diffByWords ===");

test("cópia literal: tudo neutro, pctAutoral=0", () => {
  const t = "No Brasil, o estigma social persiste.";
  const diffs = diffByWords(t, t);
  // Espera 1 só segmento op=0 com o texto inteiro
  assertEq(diffs.length, 1, "deveria ter 1 só segmento");
  assertEq(diffs[0][0], 0, "op deveria ser 0 (igual)");
  assertEq(diffs[0][1], t, "texto do segmento deveria ser o texto inteiro");
  assertEq(pctAutoral(diffs), 0);
});

test("reescrita autoral total: tudo op=±1, pctAutoral próximo de 100", () => {
  const a = "No Brasil, estigma social persiste.";
  const b = "Educação financeira mostra-se essencial hoje.";
  const diffs = diffByWords(a, b);
  // Espera ZERO segmentos op=0 (textos não compartilham nada)
  const iguais = diffs.filter(([op]) => op === 0);
  assertEq(iguais.length, 0, "nenhum segmento deveria ser op=0");
  // pctAutoral = 100 (cada char de B é novo)
  assertEq(pctAutoral(diffs), 100);
});

test("reescrita parcial: pctAutoral entre 30 e 70", () => {
  const a = "No Brasil, estigma social associado aos transtornos persiste.";
  const b = "No Brasil, o preconceito cultural sobre saúde mental persiste.";
  const diffs = diffByWords(a, b);
  // "No Brasil,", "persiste." mantidos; o resto trocado
  const pct = pctAutoral(diffs);
  assertTrue(pct >= 30 && pct <= 70,
    `pctAutoral=${pct}, esperado entre 30-70 (mistura)`);
  // Tem pelo menos 1 segmento neutro e pelo menos 1 op=±1
  assertTrue(
    diffs.some(([op]) => op === 0),
    "deveria ter pelo menos 1 segmento op=0",
  );
  assertTrue(
    diffs.some(([op]) => op !== 0),
    "deveria ter pelo menos 1 segmento op=±1",
  );
});

test("paráfrase superficial: pctAutoral baixo (~5-25)", () => {
  // Mesma frase com 1 palavra trocada
  const a = "No Brasil, o estigma social associado aos transtornos mentais persiste como questão central.";
  const b = "No Brasil, o estigma social ligado aos transtornos mentais persiste como questão central.";
  const diffs = diffByWords(a, b);
  const pct = pctAutoral(diffs);
  // Só "associado" → "ligado" mudou (1 palavra de ~14)
  assertTrue(pct > 0 && pct <= 25,
    `pctAutoral=${pct}, esperado >0 e <=25 (paráfrase superficial)`);
});


// ──────────────────────────────────────────────────────────────────────
// Edge cases
// ──────────────────────────────────────────────────────────────────────

console.log("\n=== edge cases ===");

test("texto B vazio: tudo é remoção, pctAutoral=0", () => {
  const diffs = diffByWords("texto montado completo", "");
  // Tudo op=-1 (removido)
  for (const [op] of diffs) {
    if (op === 1) {
      throw new Error("nenhum segmento deveria ser op=1");
    }
  }
  assertEq(pctAutoral(diffs), 0);
});

test("texto A vazio: tudo é adição, pctAutoral=100", () => {
  const diffs = diffByWords("", "tudo novo aqui");
  // Tudo op=1 (adicionado)
  for (const [op] of diffs) {
    if (op === -1) {
      throw new Error("nenhum segmento deveria ser op=-1");
    }
  }
  assertEq(pctAutoral(diffs), 100);
});

test("ambos vazios: array vazio, pctAutoral=0", () => {
  const diffs = diffByWords("", "");
  assertEq(diffs, []);
  assertEq(pctAutoral(diffs), 0);
});

test("acentuação preservada nos tokens", () => {
  const a = "saúde mental";
  const b = "saúde física";
  const diffs = diffByWords(a, b);
  // "saúde" mantido, "mental"/"física" trocado
  const segmentoIgual = diffs.find(([op]) => op === 0);
  assertTrue(
    segmentoIgual !== undefined,
    "deveria existir segmento op=0",
  );
  assertTrue(
    (segmentoIgual?.[1] || "").includes("saúde"),
    "segmento op=0 deveria conter 'saúde'",
  );
});


// ──────────────────────────────────────────────────────────────────────
// Smoke visual — print 1 cenário pra Daniel ver o output
// ──────────────────────────────────────────────────────────────────────

console.log("\n=== Smoke visual (cenário paráfrase) ===");
const smokeA = "No Brasil, estigma social associado aos transtornos mentais persiste.";
const smokeB = "No Brasil, o estigma cultural sobre saúde mental ainda persiste.";
const smokeDiffs = diffByWords(smokeA, smokeB);
for (const [op, text] of smokeDiffs) {
  const label = op === -1 ? "REMOVIDO" : op === 1 ? "ADICIONADO" : "IGUAL    ";
  // Substitui \n por marker visível pra o output não quebrar
  const visText = text.replace(/\n/g, "↵");
  console.log(`  [${label}] ${JSON.stringify(visText)}`);
}
console.log(`  → pctAutoral = ${pctAutoral(smokeDiffs)}%`);


// ──────────────────────────────────────────────────────────────────────
// Final
// ──────────────────────────────────────────────────────────────────────

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
