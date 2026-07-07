"""Cliente Asaas — assinatura recorrente com split pro parceiro.

Duas implementações com a MESMA interface:
- `RealAsaasClient`  : HTTP real (requests) contra sandbox/prod.
- `MockAsaasClient`  : em memória, sem rede — default em dev/testes.

O payload da assinatura é montado por `build_subscription_payload`
(função pura) — tanto o cliente real quanto o mock usam ela, então o
teste do split (critério #7) assere sobre o payload determinístico.

Letras miúdas respeitadas (spec §5): split % incide sobre o líquido;
cartão liquida D+32 (nenhuma copy promete repasse imediato); estorno
reverte split (tratado no webhook, não aqui).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Protocol


# ──────────────────────────────────────────────────────────────────────
# Payload builder (puro)
# ──────────────────────────────────────────────────────────────────────

def build_subscription_payload(
    *,
    customer_id: str,
    valor_centavos: int,
    wallet_id: Optional[str],
    share_pct: Optional[float],
    ciclo: str = "MONTHLY",
    billing_type: str = "UNDEFINED",
    descricao: str = "Assinatura Correção de Redação",
) -> Dict[str, Any]:
    """Monta o corpo do POST /subscriptions do Asaas.

    Só inclui `splits` quando há walletId E share_pct — parceiro sem
    wallet configurada não gera split (assinatura fica 100% Redato até o
    parceiro fornecer o walletId)."""
    payload: Dict[str, Any] = {
        "customer": customer_id,
        "billingType": billing_type,
        "value": round(valor_centavos / 100, 2),
        "cycle": ciclo,
        "description": descricao,
    }
    if wallet_id and share_pct is not None:
        payload["split"] = [
            {"walletId": wallet_id, "percentualValue": float(share_pct)},
        ]
    return payload


# ──────────────────────────────────────────────────────────────────────
# Interface
# ──────────────────────────────────────────────────────────────────────

class AsaasClient(Protocol):
    def create_customer(self, nome: str,
                         cpf: Optional[str] = None) -> Dict[str, Any]: ...

    def create_subscription(
        self, *, customer_id: str, valor_centavos: int,
        wallet_id: Optional[str], share_pct: Optional[float],
        ciclo: str = "MONTHLY",
    ) -> Dict[str, Any]: ...

    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]: ...


# ──────────────────────────────────────────────────────────────────────
# Mock (default em dev/testes) — sem rede
# ──────────────────────────────────────────────────────────────────────

class MockAsaasClient:
    """Guarda as chamadas em memória. Ids determinísticos por contador
    pra facilitar asserts. `subscriptions` guarda o payload enviado —
    é onde o teste do split olha."""

    def __init__(self) -> None:
        self.customers: List[Dict[str, Any]] = []
        self.subscriptions: List[Dict[str, Any]] = []
        self.canceled: List[str] = []

    def create_customer(self, nome: str,
                         cpf: Optional[str] = None) -> Dict[str, Any]:
        cid = f"cus_mock_{len(self.customers) + 1}"
        rec = {"id": cid, "name": nome, "cpfCnpj": cpf}
        self.customers.append(rec)
        return rec

    def create_subscription(
        self, *, customer_id: str, valor_centavos: int,
        wallet_id: Optional[str], share_pct: Optional[float],
        ciclo: str = "MONTHLY",
    ) -> Dict[str, Any]:
        payload = build_subscription_payload(
            customer_id=customer_id, valor_centavos=valor_centavos,
            wallet_id=wallet_id, share_pct=share_pct, ciclo=ciclo,
        )
        sid = f"sub_mock_{len(self.subscriptions) + 1}"
        self.subscriptions.append({"id": sid, "payload": payload})
        return {
            "id": sid,
            "invoiceUrl": f"https://sandbox.asaas.com/i/{sid}",
            "status": "PENDING",
            **payload,
        }

    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        self.canceled.append(subscription_id)
        return {"id": subscription_id, "deleted": True}


# ──────────────────────────────────────────────────────────────────────
# Real (HTTP)
# ──────────────────────────────────────────────────────────────────────

class RealAsaasClient:
    """Cliente HTTP. NÃO deve ser instanciado sem ASAAS_API_KEY."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> Dict[str, str]:
        return {
            "access_token": self.api_key,
            "Content-Type": "application/json",
        }

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        import requests
        resp = requests.post(
            f"{self.base_url}{path}", json=body,
            headers=self._headers(), timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def create_customer(self, nome: str,
                         cpf: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"name": nome}
        if cpf:
            body["cpfCnpj"] = cpf
        return self._post("/customers", body)

    def create_subscription(
        self, *, customer_id: str, valor_centavos: int,
        wallet_id: Optional[str], share_pct: Optional[float],
        ciclo: str = "MONTHLY",
    ) -> Dict[str, Any]:
        payload = build_subscription_payload(
            customer_id=customer_id, valor_centavos=valor_centavos,
            wallet_id=wallet_id, share_pct=share_pct, ciclo=ciclo,
        )
        return self._post("/subscriptions", payload)

    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        import requests
        resp = requests.delete(
            f"{self.base_url}/subscriptions/{subscription_id}",
            headers=self._headers(), timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


# ──────────────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────────────

_client_singleton: Optional[Any] = None


def get_asaas_client() -> AsaasClient:
    """Real quando há ASAAS_API_KEY e não estamos offline; mock caso
    contrário. Cacheado por processo."""
    global _client_singleton
    api_key = os.getenv("ASAAS_API_KEY", "").strip()
    offline = os.getenv("REDATO_DEV_OFFLINE") == "1"
    if not api_key or offline:
        if not isinstance(_client_singleton, MockAsaasClient):
            _client_singleton = MockAsaasClient()
        return _client_singleton
    base_url = os.getenv(
        "ASAAS_BASE_URL", "https://sandbox.asaas.com/api/v3",
    )
    return RealAsaasClient(api_key=api_key, base_url=base_url)


def reset_client_for_tests() -> None:
    global _client_singleton
    _client_singleton = None
