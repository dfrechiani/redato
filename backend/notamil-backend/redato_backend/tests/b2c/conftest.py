"""Fixtures do B2C — fake repo em memória + fakes de OCR/grader/Asaas.

Segue o idioma da casa (testes de `portal_link`/`missions`): a lógica é
exercitada com o data layer monkeypatchado, sem Postgres. Aqui o
`repo` inteiro é substituído por um `FakeStore` em memória, e
`correction`/`billing` por fakes determinísticos.
"""
from __future__ import annotations

import itertools
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest

from redato_backend.b2c.repo import AlunoDTO, AssinaturaDTO, ParceiroDTO


class FakeStore:
    def __init__(self) -> None:
        self.parceiros: Dict[str, ParceiroDTO] = {}
        self.codigo_index: Dict[str, str] = {}
        self.alunos: Dict[str, AlunoDTO] = {}          # telefone -> aluno
        self.alunos_by_id: Dict[str, AlunoDTO] = {}
        self.assinaturas: Dict[str, AssinaturaDTO] = {}  # aluno_id -> sub
        self.sub_index: Dict[str, str] = {}            # sub_id -> aluno_id
        self.envios: List[Dict[str, Any]] = []
        self.eventos: Dict[str, Dict[str, Any]] = {}   # dedupe_key -> evento
        self.degradadas: List[Dict[str, Any]] = []
        self._ids = itertools.count(1)

    def _nid(self, prefix: str) -> str:
        return f"{prefix}_{next(self._ids)}"

    # seeding helpers ----------------------------------------------------
    def add_parceiro(self, **kw: Any) -> ParceiroDTO:
        pid = kw.pop("id", self._nid("par"))
        p = ParceiroDTO(
            id=pid,
            slug=kw.get("slug", "demo"),
            codigo_entrada=kw.get("codigo_entrada", "DEMO"),
            nome_publico=kw.get("nome_publico", "Correção DEMO"),
            nome_professor=kw.get("nome_professor", "Prof. Demo"),
            wallet_id_asaas=kw.get("wallet_id_asaas"),
            share_pct=kw.get("share_pct"),
            preco_centavos=kw.get("preco_centavos", 3990),
            ativo=kw.get("ativo", True),
            branding=kw.get("branding", {}),
        )
        self.parceiros[pid] = p
        self.codigo_index[p.codigo_entrada.upper()] = pid
        return p

    def add_aluno(self, telefone: str, parceiro_id: str, **kw: Any) -> AlunoDTO:
        aid = kw.pop("id", self._nid("alu"))
        a = AlunoDTO(
            id=aid, telefone_e164=telefone, nome=kw.get("nome"),
            parceiro_id=parceiro_id, estado=kw.get("estado", "novo"),
            cpf=kw.get("cpf"),
            correcoes_gratis_usadas=kw.get("correcoes_gratis_usadas", 0),
            consent_lgpd_at=kw.get("consent_lgpd_at"),
            consent_version=kw.get("consent_version"),
            ultima_inbound_at=kw.get("ultima_inbound_at"),
            ultimo_tema_sorteado=kw.get("ultimo_tema_sorteado"),
            ultimo_tema_sorteado_at=kw.get("ultimo_tema_sorteado_at"),
        )
        self.alunos[telefone] = a
        self.alunos_by_id[aid] = a
        return a

    # repo API -----------------------------------------------------------
    def get_parceiro_por_codigo(self, codigo: str) -> Optional[ParceiroDTO]:
        pid = self.codigo_index.get((codigo or "").strip().upper())
        p = self.parceiros.get(pid) if pid else None
        return p if (p and p.ativo) else None

    def get_parceiro_por_slug(self, slug: str) -> Optional[ParceiroDTO]:
        return next((p for p in self.parceiros.values() if p.slug == slug), None)

    def get_parceiro_por_id(self, pid: str) -> Optional[ParceiroDTO]:
        return self.parceiros.get(pid)

    def get_aluno_por_telefone(self, tel: str) -> Optional[AlunoDTO]:
        return self.alunos.get(tel)

    def get_aluno_por_id(self, aid: str) -> Optional[AlunoDTO]:
        return self.alunos_by_id.get(aid)

    def criar_aluno(self, telefone, parceiro_id, estado="novo") -> AlunoDTO:
        return self.add_aluno(telefone, parceiro_id, estado=estado)

    def atualizar_aluno(self, telefone, **campos) -> Optional[AlunoDTO]:
        a = self.alunos.get(telefone)
        if a is None:
            return None
        for k, v in campos.items():
            setattr(a, k, v)
        return a

    def incrementar_gratis(self, telefone) -> Optional[AlunoDTO]:
        a = self.alunos.get(telefone)
        if a is None:
            return None
        a.correcoes_gratis_usadas += 1
        return a

    def registrar_envio(self, aluno_id, parceiro_id, **kw) -> str:
        eid = self._nid("env")
        kw.setdefault("status", "corrigido")
        self.envios.append({
            "id": eid, "aluno_id": aluno_id, "parceiro_id": parceiro_id,
            "created_at": datetime.now(timezone.utc), **kw,
        })
        return eid

    def _by_id(self, eid):
        return next((e for e in self.envios if e["id"] == eid), None)

    def contar_envios_hoje(self, aluno_id, agora=None) -> int:
        return sum(1 for e in self.envios
                   if e["aluno_id"] == aluno_id and e.get("status") == "corrigido")

    def contar_corrigidos(self, aluno_id) -> int:
        return sum(1 for e in self.envios
                   if e["aluno_id"] == aluno_id and e.get("status") == "corrigido")

    def ultimas_notas(self, aluno_id, limite=5) -> List[int]:
        notas = [e["nota_total"] for e in self.envios
                 if e["aluno_id"] == aluno_id and e.get("nota_total") is not None]
        return notas[-limite:]

    def listar_notas_competencias(self, aluno_id, limite=20) -> List[Dict[str, Any]]:
        return [e["notas_competencias"] for e in self.envios
                if e["aluno_id"] == aluno_id and e.get("notas_competencias")][-limite:]

    # tema pendente ----------------------------------------------------
    def get_envio_pendente(self, aluno_id):
        pend = [e for e in self.envios
                if e["aluno_id"] == aluno_id and e.get("status") == "aguardando_tema"]
        if not pend:
            return None
        e = pend[-1]
        return {"id": e["id"], "texto_ocr": e.get("texto_ocr"),
                "tema": e.get("tema"), "gratis": bool(e.get("gratis"))}

    def substituir_envio_pendente(self, aluno_id, parceiro_id, *,
                                  texto_ocr, gratis=False, tema=None) -> str:
        self.envios = [e for e in self.envios
                       if not (e["aluno_id"] == aluno_id
                               and e.get("status") == "aguardando_tema")]
        return self.registrar_envio(
            aluno_id, parceiro_id, texto_ocr=texto_ocr, texto_final=texto_ocr,
            tema=tema, gratis=gratis, status="aguardando_tema",
        )

    def corrigir_envio_pendente(self, envio_id, *, tema, nota_total,
                                notas_competencias, custo_estimado_centavos=None,
                                tempo_processamento_ms=None) -> None:
        e = self._by_id(envio_id)
        if e is None:
            return
        e.update(status="corrigido", tema=tema, nota_total=nota_total,
                 notas_competencias=notas_competencias,
                 custo_estimado_centavos=custo_estimado_centavos,
                 tempo_processamento_ms=tempo_processamento_ms)

    def atualizar_tema_pendente(self, envio_id, tema) -> None:
        e = self._by_id(envio_id)
        if e is not None and e.get("status") == "aguardando_tema":
            e["tema"] = tema

    def registrar_envio_bloqueado(self, aluno_id, parceiro_id) -> str:
        return self.registrar_envio(aluno_id, parceiro_id, status="bloqueado")

    # régua ------------------------------------------------------------
    def iniciar_overdue(self, sub_id, quando) -> None:
        aid = self.sub_index.get(sub_id)
        sub = self.assinaturas.get(aid) if aid else None
        if sub is None:
            return
        sub.status = "atrasada"
        if sub.overdue_desde is None:
            sub.overdue_desde = quando
        if sub.regua_estagio < 1:
            sub.regua_estagio = 1

    def avancar_regua(self, sub_id, novo_estagio) -> None:
        aid = self.sub_index.get(sub_id)
        sub = self.assinaturas.get(aid) if aid else None
        if sub and novo_estagio > sub.regua_estagio:
            sub.regua_estagio = novo_estagio

    def zerar_regua(self, sub_id) -> None:
        aid = self.sub_index.get(sub_id)
        sub = self.assinaturas.get(aid) if aid else None
        if sub:
            sub.overdue_desde = None
            sub.regua_estagio = 0

    def listar_atrasadas_para_tick(self):
        out = []
        for aid, sub in self.assinaturas.items():
            if sub.status == "atrasada" and sub.overdue_desde and sub.regua_estagio < 3:
                a = self.alunos_by_id.get(aid)
                if a:
                    out.append({
                        "sub_id": sub.asaas_subscription_id,
                        "overdue_desde": sub.overdue_desde,
                        "regua_estagio": sub.regua_estagio,
                        "aluno_id": a.id, "telefone": a.telefone_e164,
                        "nome": a.nome, "parceiro_id": a.parceiro_id,
                    })
        return out

    # métricas ---------------------------------------------------------
    def contar_fotos_bloqueadas(self, parceiro_id) -> int:
        return sum(1 for e in self.envios
                   if e["parceiro_id"] == parceiro_id and e.get("status") == "bloqueado")

    def contar_eventos_pendentes(self, parceiro_id) -> int:
        alunos_ids = {a.id for a in self.alunos.values() if a.parceiro_id == parceiro_id}
        return sum(1 for ev in self.eventos.values()
                   if ev.get("aluno_id") in alunos_ids and not ev.get("processado"))

    def registrar_notificacao_degradada(self, parceiro_id, template_key, *,
                                        aluno_id=None, telefone=None) -> None:
        self.degradadas.append({
            "parceiro_id": parceiro_id, "template_key": template_key,
            "aluno_id": aluno_id, "telefone": telefone,
        })

    def contar_notificacoes_degradadas(self, parceiro_id) -> int:
        return sum(1 for d in self.degradadas if d["parceiro_id"] == parceiro_id)

    def correcoes_por_assinante_ativo(self, parceiro_id) -> List[int]:
        ativos = {a.id for a in self.alunos.values()
                  if a.parceiro_id == parceiro_id
                  and a.estado in ("ativo", "aguardando_cancelamento")}
        contagem = {}
        for e in self.envios:
            if e["aluno_id"] in ativos and e.get("status") == "corrigido":
                contagem[e["aluno_id"]] = contagem.get(e["aluno_id"], 0) + 1
        return list(contagem.values())

    def get_assinatura_por_aluno(self, aluno_id) -> Optional[AssinaturaDTO]:
        return self.assinaturas.get(aluno_id)

    def get_assinatura_por_subscription(self, sub_id) -> Optional[AssinaturaDTO]:
        aid = self.sub_index.get(sub_id)
        return self.assinaturas.get(aid) if aid else None

    def upsert_assinatura(self, aluno_id, *, valor_centavos,
                          asaas_customer_id=None, asaas_subscription_id=None,
                          status="pendente", ciclo="MONTHLY",
                          proximo_vencimento=None) -> AssinaturaDTO:
        sub = self.assinaturas.get(aluno_id)
        if sub is None:
            sub = AssinaturaDTO(
                id=self._nid("sub"), aluno_id=aluno_id,
                asaas_customer_id=asaas_customer_id,
                asaas_subscription_id=asaas_subscription_id,
                status=status, valor_centavos=valor_centavos, ciclo=ciclo,
                proximo_vencimento=proximo_vencimento,
            )
            self.assinaturas[aluno_id] = sub
        sub.valor_centavos = valor_centavos
        if asaas_customer_id is not None:
            sub.asaas_customer_id = asaas_customer_id
        if asaas_subscription_id is not None:
            sub.asaas_subscription_id = asaas_subscription_id
        sub.status = status
        sub.ciclo = ciclo
        if proximo_vencimento is not None:
            sub.proximo_vencimento = proximo_vencimento
        if sub.asaas_subscription_id:
            self.sub_index[sub.asaas_subscription_id] = aluno_id
        return sub

    def atualizar_status_assinatura(self, sub_id, status,
                                    *, proximo_vencimento=None) -> Optional[AssinaturaDTO]:
        aid = self.sub_index.get(sub_id)
        sub = self.assinaturas.get(aid) if aid else None
        if sub is None:
            return None
        sub.status = status
        if proximo_vencimento is not None:
            sub.proximo_vencimento = proximo_vencimento
        return sub

    def registrar_evento_billing(self, dedupe_key, tipo,
                                 *, aluno_id=None, payload=None) -> bool:
        if dedupe_key in self.eventos:
            return False
        self.eventos[dedupe_key] = {
            "tipo": tipo, "aluno_id": aluno_id, "payload": payload,
            "processado": False,
        }
        return True

    def contar_eventos_tipo(self, aluno_id, tipo) -> int:
        return sum(1 for e in self.eventos.values()
                   if e["aluno_id"] == aluno_id and e["tipo"] == tipo)

    def marcar_evento_processado(self, dedupe_key) -> None:
        if dedupe_key in self.eventos:
            self.eventos[dedupe_key]["processado"] = True

    def contar_alunos_por_estado(self, parceiro_id) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for a in self.alunos.values():
            if a.parceiro_id == parceiro_id:
                out[a.estado] = out.get(a.estado, 0) + 1
        return out

    def metricas_envios(self, parceiro_id) -> Dict[str, Any]:
        envs = [e for e in self.envios if e["parceiro_id"] == parceiro_id
                and e.get("status") == "corrigido"]
        tempos = [e["tempo_processamento_ms"] for e in envs
                  if e.get("tempo_processamento_ms")]
        return {
            "total_correcoes": len(envs),
            "tempo_medio_ms": int(sum(tempos) / len(tempos)) if tempos else None,
            "custo_estimado_centavos": sum(e.get("custo_estimado_centavos") or 0
                                           for e in envs),
        }


_REPO_FNS = [
    "get_parceiro_por_codigo", "get_parceiro_por_slug", "get_parceiro_por_id",
    "get_aluno_por_telefone", "get_aluno_por_id", "criar_aluno",
    "atualizar_aluno", "incrementar_gratis", "registrar_envio",
    "contar_envios_hoje", "contar_corrigidos", "ultimas_notas",
    "listar_notas_competencias", "get_envio_pendente",
    "substituir_envio_pendente", "corrigir_envio_pendente",
    "atualizar_tema_pendente", "registrar_envio_bloqueado",
    "get_assinatura_por_aluno", "get_assinatura_por_subscription",
    "upsert_assinatura", "atualizar_status_assinatura",
    "iniciar_overdue", "avancar_regua", "zerar_regua",
    "listar_atrasadas_para_tick",
    "registrar_evento_billing", "contar_eventos_tipo",
    "marcar_evento_processado", "contar_alunos_por_estado", "metricas_envios",
    "contar_fotos_bloqueadas", "contar_eventos_pendentes",
    "correcoes_por_assinante_ativo",
    "registrar_notificacao_degradada", "contar_notificacoes_degradadas",
]


@pytest.fixture
def store(monkeypatch):
    """Instala o FakeStore no lugar do `repo` em todos os módulos que o
    importam (router, webhook, admin_api)."""
    from redato_backend.b2c import repo as repo_mod
    from redato_backend.billing import webhook as wh_mod
    from redato_backend.b2c import admin_api as admin_mod
    st = FakeStore()
    for name in _REPO_FNS:
        fn = getattr(st, name)
        monkeypatch.setattr(repo_mod, name, fn, raising=True)
        # webhook/admin importam `repo` como módulo, então patchar o módulo
        # basta; mas garantimos também referências diretas se houver.
    return st


@pytest.fixture
def b2c_on(monkeypatch):
    monkeypatch.setenv("REDATO_B2C_ENABLED", "1")


@pytest.fixture
def sem_b2g(monkeypatch):
    """Telefone desconhecido ao fluxo escola (sem vínculo, sem estado)."""
    from redato_backend.b2c import router as R
    monkeypatch.setattr(R, "_tem_vinculo_b2g", lambda phone: False)
    monkeypatch.setattr(R, "_tem_estado_b2g", lambda phone: False)


@pytest.fixture
def fake_correcao(monkeypatch):
    """OCR e grader determinísticos — nota 880, C1..C5 fixas."""
    from redato_backend.b2c import correction as C

    class _Ocr:
        def __init__(self, text="Redação transcrita de teste.", rejected=False):
            self.text = text
            self.rejected = rejected
            self.quality_issues = []

    def _transcrever(image_path):
        return _Ocr()

    def _corrigir(texto, *, tema=None, grader=None):
        return C.ResultadoCorrecao(
            nota_total=880,
            notas={"c1": 200, "c2": 160, "c3": 160, "c4": 200, "c5": 160},
            ponto_forte="tese clara e bem delimitada",
            foco_melhoria="aprofundar o repertório na C2",
            raw={"_tema": tema},
        )

    monkeypatch.setattr(C, "transcrever", _transcrever)
    monkeypatch.setattr(C, "corrigir_texto", _corrigir)
    return C


@pytest.fixture
def mock_asaas(monkeypatch):
    from redato_backend.billing import asaas as A
    A.reset_client_for_tests()
    client = A.MockAsaasClient()
    monkeypatch.setattr(A, "get_asaas_client", lambda: client)
    # router importa get_asaas_client lazily de billing.asaas — o patch no
    # módulo cobre.
    return client
