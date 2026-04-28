"""SQLite persistence pra Fase A.

Schema:
- `alunos`: phone → nome, turma, escola, estado FSM
- `turmas`: identificação da turma (suporta agregação Fase B)
- `interactions`: 1 linha por foto recebida (pipeline completo)

Path default: `data/whatsapp/redato.db` (relativo ao backend).
Override via env `REDATO_WHATSAPP_DB`.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

BACKEND = Path(__file__).resolve().parents[2]


def _db_path() -> Path:
    override = os.getenv("REDATO_WHATSAPP_DB")
    if override:
        return Path(override)
    return BACKEND / "data" / "whatsapp" / "redato.db"


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


_SCHEMA_TABLES = """
CREATE TABLE IF NOT EXISTS alunos (
    phone TEXT PRIMARY KEY,
    nome TEXT,
    turma_id TEXT,
    escola TEXT,
    estado TEXT NOT NULL DEFAULT 'NEW',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(turma_id) REFERENCES turmas(turma_id)
);

CREATE TABLE IF NOT EXISTS turmas (
    turma_id TEXT PRIMARY KEY,
    escola TEXT NOT NULL,
    nome TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aluno_phone TEXT NOT NULL,
    turma_id TEXT,
    missao_id TEXT NOT NULL,
    activity_id TEXT NOT NULL,
    foto_path TEXT,
    foto_hash TEXT,           -- SHA256 dos bytes da imagem (detecção de duplicata)
    texto_transcrito TEXT,
    ocr_quality_issues TEXT,  -- JSON array
    ocr_metrics TEXT,         -- JSON dict (brilho, laplacian_var, n_chars)
    redato_output TEXT,       -- JSON dict
    resposta_aluno TEXT,
    elapsed_ms INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(aluno_phone) REFERENCES alunos(phone),
    FOREIGN KEY(turma_id) REFERENCES turmas(turma_id)
);

CREATE INDEX IF NOT EXISTS idx_interactions_turma
    ON interactions(turma_id, created_at);
CREATE INDEX IF NOT EXISTS idx_interactions_aluno
    ON interactions(aluno_phone, created_at);
"""


def init_db() -> None:
    with _conn() as c:
        # 1) Cria tabelas + índices base
        c.executescript(_SCHEMA_TABLES)
        # 2) Migration: adiciona colunas em DBs antigos
        cols = {r["name"] for r in c.execute(
            "PRAGMA table_info(interactions)"
        ).fetchall()}
        if "foto_hash" not in cols:
            c.execute("ALTER TABLE interactions ADD COLUMN foto_hash TEXT")
        if "invalidated_at" not in cols:
            # NULL = válida; ISO timestamp = invalidada (aluno disse "ocr errado")
            c.execute("ALTER TABLE interactions ADD COLUMN invalidated_at TEXT")
        # 3) Cria índice de hash (depois de garantir que a coluna existe)
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_interactions_hash "
            "ON interactions(aluno_phone, missao_id, foto_hash)"
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────
# Alunos
# ──────────────────────────────────────────────────────────────────────

def get_aluno(phone: str) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM alunos WHERE phone = ?", (phone,)
        ).fetchone()
        return dict(row) if row else None


def upsert_aluno(
    phone: str,
    *,
    nome: Optional[str] = None,
    turma_id: Optional[str] = None,
    escola: Optional[str] = None,
    estado: Optional[str] = None,
) -> Dict[str, Any]:
    """Cria ou atualiza aluno. Campos None são preservados."""
    now = _now()
    existing = get_aluno(phone)
    if existing is None:
        with _conn() as c:
            c.execute(
                "INSERT INTO alunos (phone, nome, turma_id, escola, estado, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (phone, nome, turma_id, escola, estado or "NEW", now, now),
            )
    else:
        with _conn() as c:
            c.execute(
                "UPDATE alunos SET "
                "nome = COALESCE(?, nome), "
                "turma_id = COALESCE(?, turma_id), "
                "escola = COALESCE(?, escola), "
                "estado = COALESCE(?, estado), "
                "updated_at = ? "
                "WHERE phone = ?",
                (nome, turma_id, escola, estado, now, phone),
            )
    return get_aluno(phone)  # type: ignore[return-value]


# ──────────────────────────────────────────────────────────────────────
# Turmas
# ──────────────────────────────────────────────────────────────────────

def upsert_turma(turma_id: str, escola: str, nome: str) -> None:
    now = _now()
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO turmas (turma_id, escola, nome, created_at) "
            "VALUES (?, ?, ?, ?)",
            (turma_id, escola, nome, now),
        )


# ──────────────────────────────────────────────────────────────────────
# Interactions
# ──────────────────────────────────────────────────────────────────────

def save_interaction(
    *,
    aluno_phone: str,
    turma_id: Optional[str],
    missao_id: str,
    activity_id: str,
    foto_path: Optional[str],
    foto_hash: Optional[str] = None,
    texto_transcrito: Optional[str],
    ocr_quality_issues: Optional[List[str]],
    ocr_metrics: Optional[Dict[str, Any]],
    redato_output: Optional[Dict[str, Any]],
    resposta_aluno: Optional[str],
    elapsed_ms: Optional[int],
) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO interactions ("
            "aluno_phone, turma_id, missao_id, activity_id, foto_path, "
            "foto_hash, texto_transcrito, ocr_quality_issues, ocr_metrics, "
            "redato_output, resposta_aluno, elapsed_ms, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                aluno_phone, turma_id, missao_id, activity_id, foto_path,
                foto_hash,
                texto_transcrito,
                json.dumps(ocr_quality_issues or [], ensure_ascii=False),
                json.dumps(ocr_metrics or {}, ensure_ascii=False),
                json.dumps(redato_output or {}, ensure_ascii=False, default=str),
                resposta_aluno,
                elapsed_ms,
                _now(),
            ),
        )
        return cur.lastrowid


def _hamming_distance_hex(h1: str, h2: str) -> int:
    """Hamming distance entre dois hashes em hex (mesmo length)."""
    return bin(int(h1, 16) ^ int(h2, 16)).count("1")


def find_duplicate_interaction(
    aluno_phone: str, missao_id: str, foto_hash: str,
    *, max_age_days: int = 30, max_hamming: int = 5,
) -> Optional[Dict[str, Any]]:
    """Retorna a interação mais recente do mesmo aluno + missão com
    foto perceptualmente similar (Hamming ≤ max_hamming sobre dHash 64 bits).

    Por que Hamming + dHash em vez de match exato com SHA256:
    WhatsApp/Twilio re-encoda a imagem em cada upload (diferentes bytes
    pra mesma foto visual). SHA256 detectava 0 duplicatas em uso real.
    dHash 8x8 (16 chars hex) é invariante a recompressão.
    """
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM interactions "
            "WHERE aluno_phone = ? AND missao_id = ? "
            "AND foto_hash IS NOT NULL "
            "AND resposta_aluno IS NOT NULL "
            "AND invalidated_at IS NULL "
            "AND created_at >= ? "
            "ORDER BY created_at DESC LIMIT 50",
            (aluno_phone, missao_id, cutoff),
        ).fetchall()

    target_len = len(foto_hash)
    for r in rows:
        candidate = r["foto_hash"]
        # Ignora hashes do formato antigo (SHA256, 64 chars) quando
        # foto_hash atual é dHash (16 chars). Sem upgrade automático.
        if not candidate or len(candidate) != target_len:
            continue
        try:
            if _hamming_distance_hex(candidate, foto_hash) <= max_hamming:
                return dict(r)
        except (ValueError, TypeError):
            continue
    return None


def compute_image_hash(image_path: str) -> str:
    """dHash perceptual (16 chars hex = 64 bits).

    Algoritmo: converte pra grayscale, redimensiona pra 9x8, compara
    cada pixel com o vizinho à direita (8 comparações × 8 linhas = 64
    bits). Estável a recompressão JPEG, mudanças mínimas de brilho/
    contraste e leve crop. NÃO estável a rotação 90°+ — o quality_check
    do OCR já normaliza orientação antes desta função ser chamada,
    porém a função recebe o path do arquivo bruto, então rotações
    diferentes geram dHashes diferentes (limitação aceita pra Fase A).
    """
    import numpy as np
    from PIL import Image, ImageOps
    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img)  # normaliza rotação EXIF se houver
    img = img.convert("L").resize((9, 8), Image.LANCZOS)
    arr = np.asarray(img, dtype=int)
    diff = arr[:, 1:] > arr[:, :-1]   # 8x8 boolean
    bits = diff.flatten()
    out = 0
    for bit in bits:
        out = (out << 1) | int(bit)
    return f"{out:016x}"  # 16 chars hex


def list_interactions_by_turma(
    turma_id: str, *, limit: int = 100,
) -> List[Dict[str, Any]]:
    """Lista interações de uma turma. Ordenado mais recente primeiro.
    Suporte pra agregação por turma (Fase B)."""
    with _conn() as c:
        rows = c.execute(
            "SELECT i.*, a.nome AS aluno_nome FROM interactions i "
            "LEFT JOIN alunos a ON a.phone = i.aluno_phone "
            "WHERE i.turma_id = ? "
            "ORDER BY i.created_at DESC LIMIT ?",
            (turma_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def list_interactions_by_aluno(
    phone: str, *, limit: int = 50,
) -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM interactions WHERE aluno_phone = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (phone, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_last_valid_interaction(
    aluno_phone: str,
) -> Optional[Dict[str, Any]]:
    """Retorna a interação mais recente do aluno que ainda não foi
    invalidada (e tem resposta_aluno preenchida)."""
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM interactions WHERE aluno_phone = ? "
            "AND resposta_aluno IS NOT NULL "
            "AND invalidated_at IS NULL "
            "ORDER BY created_at DESC LIMIT 1",
            (aluno_phone,),
        ).fetchone()
        return dict(row) if row else None


def invalidate_interaction(interaction_id: int) -> None:
    """Marca interaction como invalidada (aluno disse 'ocr errado')."""
    with _conn() as c:
        c.execute(
            "UPDATE interactions SET invalidated_at = ? WHERE id = ?",
            (_now(), interaction_id),
        )
