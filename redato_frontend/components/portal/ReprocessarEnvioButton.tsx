"use client";

/**
 * Botão "Reprocessar avaliação" — só aparece quando o envio tem
 * correção falha (redato_output null/error ou nota_total null).
 *
 * Bug que motivou (2026-05-01): envios pelo WhatsApp podem falhar na
 * correção (timeout FT, parser fail, exception silenciada como o bug
 * google.cloud), gerando redato_output={"error":"..."} ou null. Antes,
 * professor não tinha como retentar — só pedia o aluno reenviar via
 * WhatsApp e torcer pra ele responder.
 *
 * Backend: POST /portal/envios/{envio_id}/reprocessar.
 */
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { ModalConfirm } from "@/components/ui/ModalConfirm";
import { reprocessarEnvio } from "@/lib/portal-client";

interface Props {
  envioId: string;
  /** Se true, render do botão; senão, retorna null (esconde). */
  shouldShow: boolean;
}

export function ReprocessarEnvioButton({ envioId, shouldShow }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  if (!shouldShow) return null;

  async function handleConfirm() {
    setLoading(true);
    try {
      const res = await reprocessarEnvio(envioId);
      if (res.ok) {
        toast.success(
          "Avaliação reprocessada. Atualizando…",
        );
        // Refetch do server component pra refletir o novo
        // redato_output. Sem `router.refresh()`, página continua
        // mostrando a falha porque é cache do RSC.
        router.refresh();
      } else {
        toast.error(
          `Reprocessar falhou: ${res.error ?? "erro desconhecido"}. ` +
          "Pode tentar de novo em alguns segundos.",
          { duration: 8000 },
        );
      }
    } catch (err) {
      toast.error(
        `Erro ao chamar API: ${(err as Error).message ?? err}`,
      );
    } finally {
      setLoading(false);
      setOpen(false);
    }
  }

  return (
    <>
      <Button
        variant="secondary"
        onClick={() => setOpen(true)}
        disabled={loading}
      >
        {loading ? "Reprocessando…" : "Reprocessar avaliação"}
      </Button>

      <ModalConfirm
        open={open}
        onClose={() => !loading && setOpen(false)}
        onConfirm={handleConfirm}
        title="Reprocessar essa avaliação?"
        description={
          <>
            Vai gerar uma nova correção pelo mesmo texto OCR que está
            persistido. A avaliação anterior será <strong>substituída</strong>{" "}
            (não há histórico da versão antiga).
            <br />
            <br />
            Use quando: a correção atual saiu com erro técnico, nota_total
            ficou em branco, ou alguma competência ficou sem feedback. Se
            o problema for no texto OCR, peça pro aluno mandar a foto de
            novo via WhatsApp em vez disso.
          </>
        }
        confirmLabel="Reprocessar"
        cancelLabel="Cancelar"
        confirmVariant="primary"
        loading={loading}
      />
    </>
  );
}
