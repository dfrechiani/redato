import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { formatPrazo } from "@/lib/format";
import type {
  CartaEscolhidaDetail, JogoRedatoOutput, ReescritaDetail,
} from "@/types/portal";


interface Props {
  data: ReescritaDetail;
}


/**
 * Tela do professor pra reescrita de um aluno (Fase 2 passo 6).
 *
 * Camadas (de cima pra baixo):
 * 1. Cabeçalho — aluno + atividade + grupo + tema + enviada em
 * 2. Banner DH (se flag desrespeito_direitos_humanos=true)
 * 3. Bloco principal — texto montado vs reescrita autoral (lado a lado)
 * 4. Notas + transformação (badge separado, decisão G.1.6)
 * 5. Cartas escolhidas + sugestões pedagógicas (decisão G.1.7)
 * 6. Análise da redação (feedback_professor: 4 blocos M9.4)
 *
 * Quando `redato_output=null` (Claude falhou no bot — timeout ou
 * erro genérico), camadas 4 e 6 mostram "avaliação pendente". Camadas
 * 3 e 5 ainda renderizam (texto + cartas existem independente da
 * avaliação).
 *
 * Não precisa "use client" — só tem JSX estático sem state. Server
 * component renderiza direto.
 */
export function ReescritaDetailView({ data }: Props) {
  const { partida, aluno, cartas_escolhidas: cartas, texto_montado,
    reescrita } = data;
  const r = reescrita.redato_output;
  const flagDH = r?.flags?.desrespeito_direitos_humanos === true;
  const avaliacaoDisponivel = r !== null;

  return (
    <div className="space-y-6">
      <header>
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
          Reescrita
        </p>
        <h1 className="font-display text-3xl mt-1">
          {aluno.nome}
        </h1>
        <p className="mt-1 text-sm text-ink-400">
          {partida.atividade_nome} ·{" "}
          <span className="font-medium">Grupo {partida.grupo_codigo}</span>
          {" · "}Tema:{" "}
          <span className="font-medium">{partida.nome_humano_tema}</span>
        </p>
        <p className="mt-1 text-xs text-ink-400">
          Enviada em {formatPrazo(reescrita.enviado_em)}
        </p>
      </header>

      {/* Banner DH — alerta no topo da página pra professor revisar
          antes de discutir com aluno. Cor vermelha pra contraste. */}
      {flagDH && (
        <div
          role="alert"
          className="rounded border-2 border-red-400 bg-red-50 px-4 py-3"
        >
          <p className="text-sm font-semibold text-red-900">
            ⚠️ Esta reescrita foi marcada por desrespeito a direitos
            humanos.
          </p>
          <p className="text-sm text-red-900 mt-1">
            Revise o conteúdo antes de discutir com o aluno. Pela
            cartilha INEP, a reescrita zera C1 e C5.
          </p>
        </div>
      )}

      {/* Bloco principal — texto montado vs reescrita autoral.
          Lado-a-lado simples (sem diff visual ainda — fica como
          pendência pra próxima iteração se professor pedir). */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
            Texto montado pelo grupo
          </p>
          <p className="text-sm leading-relaxed whitespace-pre-line font-body">
            {texto_montado || (
              <span className="text-ink-400 italic">
                (texto montado ainda não disponível)
              </span>
            )}
          </p>
        </Card>
        <Card>
          <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
            Reescrita autoral
          </p>
          <p className="text-sm leading-relaxed whitespace-pre-line font-body">
            {reescrita.texto}
          </p>
        </Card>
      </section>

      {/* Notas + transformação. Quando avaliação disponível, mostra 5
          competências + total + badge transformação. Senão, placeholder. */}
      {avaliacaoDisponivel ? (
        <BlocoNotas redato={r as JogoRedatoOutput} />
      ) : (
        <Card>
          <p className="text-sm text-amber-900">
            ⏳ Avaliação ainda não disponível. Ocorreu uma falha na
            geração do feedback. Você poderá reprocessar pela tela de
            partidas em breve.
          </p>
        </Card>
      )}

      {/* Cartas escolhidas + sugestões pedagógicas (decisão G.1.7).
          Sempre renderiza cartas; sugestões aparecem só se redato_output
          tiver itens. */}
      <BlocoCartas
        cartas={cartas}
        sugestoes={r?.sugestoes_cartas_alternativas ?? []}
      />

      {/* Análise da redação — feedback_professor M9.4 (4 blocos).
          Só renderiza quando avaliação disponível. */}
      {avaliacaoDisponivel && (
        <BlocoAnalise redato={r as JogoRedatoOutput} />
      )}
    </div>
  );
}


// ──────────────────────────────────────────────────────────────────────
// Sub-componentes
// ──────────────────────────────────────────────────────────────────────

function _faixaInep(nota: number): string {
  if (nota >= 200) return "excelente";
  if (nota >= 160) return "muito boa";
  if (nota >= 120) return "regular";
  if (nota >= 80) return "em desenvolvimento";
  if (nota >= 40) return "insuficiente";
  return "abaixo do esperado";
}


function _faixaBadgeVariant(
  nota: number,
): "ativa" | "lime" | "warning" | "encerrada" | "neutral" {
  if (nota >= 160) return "ativa";
  if (nota >= 120) return "lime";
  if (nota >= 80) return "warning";
  if (nota >= 40) return "encerrada";
  return "neutral";
}


function BlocoNotas({ redato }: { redato: JogoRedatoOutput }) {
  const { notas_enem, nota_total_enem, transformacao_cartas,
    flags } = redato;
  const competencias: Array<{ key: string; label: string; nota: number }> = [
    { key: "c1", label: "C1", nota: notas_enem.c1 },
    { key: "c2", label: "C2", nota: notas_enem.c2 },
    { key: "c3", label: "C3", nota: notas_enem.c3 },
    { key: "c4", label: "C4", nota: notas_enem.c4 },
    { key: "c5", label: "C5", nota: notas_enem.c5 },
  ];

  // Banda do badge de transformação — espelha o render WhatsApp
  // (whatsapp/render.py::_render_transformacao_badge). G.1.6 manda
  // visualmente separado da nota ENEM.
  const transfBanda = (() => {
    if (transformacao_cartas >= 91) return { emoji: "🏆", label: "autoria plena" };
    if (transformacao_cartas >= 71) return { emoji: "🎯", label: "autoria substancial" };
    if (transformacao_cartas >= 41) return { emoji: "🔄", label: "paráfrase com algum recorte" };
    if (transformacao_cartas >= 16) return { emoji: "📋", label: "esqueleto reconhecível" };
    return { emoji: "⚠️", label: "cópia das cartas" };
  })();

  // Lista de flags ativadas — útil pra professor entender por que a
  // nota foi capada. Excluímos `desrespeito_direitos_humanos` daqui
  // porque já tem banner vermelho dedicado no topo.
  const flagsLabels: Record<string, string> = {
    copia_literal_das_cartas: "cópia literal das cartas",
    cartas_mal_articuladas: "cartas mal articuladas",
    fuga_do_tema_do_minideck: "fuga do tema do minideck",
    tipo_textual_inadequado: "tipo textual inadequado",
  };
  const flagsAtivas = (Object.keys(flagsLabels) as Array<keyof typeof flagsLabels>)
    .filter((k) => (flags as Record<string, boolean>)[k]);

  return (
    <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <Card>
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
          Nota total
        </p>
        <p className="font-display text-5xl mt-1">
          {nota_total_enem}
          <span className="text-ink-400 text-2xl font-body">/1000</span>
        </p>
        {flagsAtivas.length > 0 && (
          <p className="mt-2 text-xs text-ink-400">
            <span className="font-semibold">Flags acionadas:</span>{" "}
            {flagsAtivas.map((k) => flagsLabels[k as string]).join(", ")}
          </p>
        )}
      </Card>

      <Card className="lg:col-span-1">
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
          Competências
        </p>
        <ul className="space-y-2">
          {competencias.map((c) => (
            <li key={c.key} className="flex items-center justify-between gap-2">
              <span className="font-mono text-sm">{c.label}</span>
              <span className="flex items-center gap-2">
                <Badge variant={_faixaBadgeVariant(c.nota)}>
                  {_faixaInep(c.nota)}
                </Badge>
                <span className="font-semibold tabular-nums w-10 text-right">
                  {c.nota}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </Card>

      {/* Badge separado de transformação — decisão G.1.6.
          Caixa visualmente distinta pro professor não confundir com a
          nota ENEM. */}
      <Card className="bg-muted/30">
        <p className="font-mono text-xs uppercase tracking-wider text-ink-400">
          Transformação das cartas
        </p>
        <p className="font-display text-4xl mt-1">
          {transfBanda.emoji} {transformacao_cartas}
          <span className="text-ink-400 text-xl font-body">/100</span>
        </p>
        <p className="mt-1 text-sm text-ink-400 italic">
          {transfBanda.label}
        </p>
        <p className="mt-2 text-xs text-ink-400">
          Score independente. Não compõe a nota ENEM (decisão G.1.6).
        </p>
      </Card>
    </section>
  );
}


function BlocoCartas({
  cartas, sugestoes,
}: {
  cartas: CartaEscolhidaDetail[];
  sugestoes: JogoRedatoOutput["sugestoes_cartas_alternativas"];
}) {
  const estruturais = cartas.filter((c) => c.tipo === "ESTRUTURAL");
  const lacunas = cartas.filter((c) => c.tipo !== "ESTRUTURAL");

  return (
    <Card>
      <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
        Cartas escolhidas pelo grupo
      </p>

      {estruturais.length > 0 && (
        <section className="mb-4">
          <h3 className="font-semibold text-sm mb-2 text-ink-400">
            Estruturais (esqueleto)
          </h3>
          <ul className="space-y-2">
            {estruturais.map((c) => (
              <li key={c.codigo} className="text-sm">
                <span className="font-mono text-xs bg-blue-50 text-blue-900 px-2 py-0.5 rounded mr-2">
                  {c.codigo}
                </span>
                {c.secao && (
                  <span className="text-xs text-ink-400 mr-2">
                    {c.secao}
                  </span>
                )}
                <span className="text-sm leading-relaxed">{c.conteudo}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {lacunas.length > 0 && (
        <section className="mb-4">
          <h3 className="font-semibold text-sm mb-2 text-ink-400">
            Lacunas temáticas
          </h3>
          <ul className="space-y-1.5">
            {lacunas.map((c) => (
              <li key={c.codigo} className="text-sm">
                <span className="font-mono text-xs bg-amber-50 text-amber-900 px-2 py-0.5 rounded mr-2">
                  {c.codigo}
                </span>
                <span className="text-xs text-ink-400 mr-2">
                  {c.tipo}
                </span>
                <span>{c.conteudo}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Sugestões pedagógicas (decisão G.1.7). Lista DINÂMICA — vazia
          é feedback positivo legítimo, então só renderiza quando há
          itens. */}
      {sugestoes.length > 0 && (
        <section>
          <h3 className="font-semibold text-sm mb-2 text-ink-400">
            Sugestões pedagógicas
          </h3>
          <ul className="space-y-2 text-sm">
            {sugestoes.map((s, i) => (
              <li
                key={i}
                className="rounded border border-border bg-muted/40 px-3 py-2"
              >
                <p className="font-mono text-xs">
                  <span className="text-ink-400">{s.codigo_original}</span>
                  {" → "}
                  <span className="font-semibold">{s.codigo_sugerido}</span>
                </p>
                <p className="text-sm leading-relaxed mt-1">
                  {s.motivo}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </Card>
  );
}


function BlocoAnalise({ redato }: { redato: JogoRedatoOutput }) {
  const fp = redato.feedback_professor;
  // Nada a renderizar se feedback_professor vier todo vazio (raro)
  if (
    !fp.pontos_fortes?.length &&
    !fp.pontos_fracos?.length &&
    !fp.padrao_falha &&
    !fp.transferencia_competencia
  ) {
    return null;
  }
  return (
    <Card>
      <p className="font-mono text-xs uppercase tracking-wider text-ink-400 mb-3">
        Análise da redação
      </p>

      {fp.pontos_fortes?.length > 0 && (
        <section className="mb-4">
          <h3 className="font-semibold text-sm mb-2">
            📌 Pontos fortes
          </h3>
          <ul className="space-y-1.5 list-disc list-inside text-sm leading-relaxed">
            {fp.pontos_fortes.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </section>
      )}

      {fp.pontos_fracos?.length > 0 && (
        <section className="mb-4">
          <h3 className="font-semibold text-sm mb-2">
            ⚠️ Pontos fracos
          </h3>
          <ul className="space-y-1.5 list-disc list-inside text-sm leading-relaxed">
            {fp.pontos_fracos.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </section>
      )}

      {fp.padrao_falha && (
        <section className="mb-4">
          <h3 className="font-semibold text-sm mb-2">
            🎯 Padrão de falha
          </h3>
          <p className="text-sm leading-relaxed">{fp.padrao_falha}</p>
        </section>
      )}

      {fp.transferencia_competencia && (
        <section>
          <h3 className="font-semibold text-sm mb-2">
            🔁 Transferência para outras competências
          </h3>
          <p className="text-sm leading-relaxed">
            {fp.transferencia_competencia}
          </p>
        </section>
      )}
    </Card>
  );
}
