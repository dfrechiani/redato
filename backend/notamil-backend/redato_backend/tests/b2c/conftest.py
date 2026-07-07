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
        self.envios.append({
            "id": eid, "aluno_id": aluno_id, "parceiro_id": parceiro_id,
            "created_at": datetime.now(timezone.utc), **kw,
        })
        return eid

    def contar_envios_hoje(self, aluno_id, agora=None) -> int:
        return sum(1 for e in self.envios if e["aluno_id"] == aluno_id)

    def ultimas_notas(self, aluno_id, limite=5) -> List[int]:
        notas = [e["nota_total"] for e in self.envios
                 if e["aluno_id"] == aluno_id and e.get("nota_total") is not None]
        return notas[-limite:]

    def listar_notas_competencias(self, aluno_id, limite=20) -> List[Dict[str, Any]]:
        return [e["notas_competencias"] for e in self.envios
                if e["aluno_id"] == aluno_id and e.get("notas_competencias")][-limite:]

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
        envs = [e for e in self.envios if e["parceiro_id"] == parceiro_id]
        return {
            "total_correcoes": len(envs),
            "tempo_medio_ms": None,
            "custo_estimado_centavos": 0,
        }


_REPO_FNS = [
    "get_parceiro_por_codigo", "get_parceiro_por_slug", "get_parceiro_por_id",
    "get_aluno_por_telefone", "get_aluno_por_id", "criar_aluno",
    "atualizar_aluno", "incrementar_gratis", "registrar_envio",
    "contar_envios_hoje", "ultimas_notas", "listar_notas_competencias",
    "get_assinatura_por_aluno", "get_assinatura_por_subscription",
    "upsert_assinatura", "atualizar_status_assinatura",
    "registrar_evento_billing", "contar_eventos_tipo",
    "marcar_evento_processado", "contar_alunos_por_estado", "metricas_envios",
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

    def _corrigir(texto, grader=None):
        return C.ResultadoCorrecao(
            nota_total=880,
            notas={"c1": 200, "c2": 160, "c3": 160, "c4": 200, "c5": 160},
            ponto_forte="tese clara e bem delimitada",
            foco_melhoria="aprofundar o repertório na C2",
            raw={},
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
