"""Dev offline mode — in-memory stubs for Firebase / BigQuery / Firestore / Cloud
Functions so the backend can run locally with no external dependencies.

Activate with ``REDATO_DEV_OFFLINE=1``. When active, ``apply_patches()`` must
run BEFORE any other ``redato_backend`` modules are imported.

What this module fakes:

* ``FirebaseService`` — token verification always succeeds; tokens are the
  JSON payload encoded as ``dev:<base64>``. Seed users are preloaded.
* ``BigQueryClient`` — an in-memory dict keyed by table id. Queries are
  matched by keyword against the known templates in ``base_api/modules/queries.py``
  and ``base_api/functions/queries.py``.
* ``firestore.Client`` — simple in-memory document store.
* ``call_cloud_function`` — writes deterministic graded-essay / OCR rows and
  returns 200. Tutor returns a canned educational reply.

This is pedagogical infrastructure — not a production fake. It covers the
correction / feedback / tutor flow end-to-end so you can validate the UI
without GCP access.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import pickle
import re
import sys
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4


# Logger pro caminho FT do OF14 (commit fix(of14)). Os print()s
# legados de outras partes do módulo NÃO foram migrados — Railway
# captura print() em dynos novos, mas a migração pra logger acontece
# por demanda (quando algum print silencia em prod).
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Global in-memory state with opt-in disk persistence
# ---------------------------------------------------------------------------
#
# uvicorn --reload restarts the Python process on every file change, which
# wipes the in-memory store. To keep submitted essays / feedback across
# reloads, we pickle the store to a file on every mutation and reload on
# startup. Disable with REDATO_DEV_PERSIST=0 if you want a clean slate.

_LOCK = threading.RLock()

_PERSIST_PATH = Path(__file__).resolve().parent.parent / ".dev_offline_state.pkl"
_PERSIST_ENABLED = os.getenv("REDATO_DEV_PERSIST", "1") != "0"


class _Store:
    def __init__(self) -> None:
        self.tables: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # firestore path ("collection/doc" or nested) -> doc dict
        self.firestore_docs: Dict[str, Dict[str, Any]] = {}
        # firebase users keyed by uid
        self.firebase_users: Dict[str, Dict[str, Any]] = {}
        # firebase users keyed by email (index)
        self.firebase_email_index: Dict[str, str] = {}


_STORE = _Store()


def _persist() -> None:
    """Dump the store to disk. Must be called under _LOCK."""
    if not _PERSIST_ENABLED:
        return
    try:
        tmp = _PERSIST_PATH.with_suffix(".pkl.tmp")
        with open(tmp, "wb") as f:
            pickle.dump(
                {
                    "tables": dict(_STORE.tables),
                    "firestore_docs": _STORE.firestore_docs,
                    "firebase_users": _STORE.firebase_users,
                    "firebase_email_index": _STORE.firebase_email_index,
                },
                f,
            )
        os.replace(tmp, _PERSIST_PATH)
    except Exception as exc:  # noqa: BLE001
        print(f"[dev_offline] persist failed: {exc!r}")


def _load_from_disk() -> bool:
    """Load the store from disk if a snapshot exists. Returns True on success."""
    if not _PERSIST_ENABLED or not _PERSIST_PATH.exists():
        return False
    try:
        with open(_PERSIST_PATH, "rb") as f:
            snapshot = pickle.load(f)
        _STORE.tables = defaultdict(list, snapshot.get("tables") or {})
        _STORE.firestore_docs = snapshot.get("firestore_docs") or {}
        _STORE.firebase_users = snapshot.get("firebase_users") or {}
        _STORE.firebase_email_index = snapshot.get("firebase_email_index") or {}
        print(f"[dev_offline] restored state from {_PERSIST_PATH.name}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[dev_offline] load failed ({exc!r}); starting fresh")
        return False


# ---------------------------------------------------------------------------
# Seed data — deterministic so the UI has something to render
# ---------------------------------------------------------------------------

SCHOOL_ID = "school-demo"
CLASS_ID = "class-demo"
THEME_ID = "theme-demo"
PROFESSOR_UID = "prof-demo-uid"
STUDENT_UID = "student-demo-uid"
ADMIN_UID = "admin-demo-uid"

STUDENT_EMAIL = "aluno@demo.redato"
PROFESSOR_EMAIL = "professor@demo.redato"
ADMIN_EMAIL = "admin@demo.redato"

# Same password for all demo users in offline mode.
DEMO_PASSWORD = "redato123"


def _seed() -> None:
    """Populate seed rows — idempotent, runs once at patch time."""
    from redato_backend.shared.constants import (
        CLASSES_TABLE,
        PROFESSORS_TABLE,
        SCHOOLS_TABLE,
        STUDENTS_TABLE,
        THEMES_TABLE,
        USERS_TABLE,
        COMPETENCIES_TABLE,
        COMPETENCIES,
    )

    now = datetime.now(timezone.utc).isoformat()

    # Users
    _STORE.tables[USERS_TABLE] = [
        {
            "login_id": STUDENT_UID,
            "name": "Aluno Demo",
            "email": STUDENT_EMAIL,
            "role": "student",
            "created_at": now,
        },
        {
            "login_id": PROFESSOR_UID,
            "name": "Professor Demo",
            "email": PROFESSOR_EMAIL,
            "role": "professor",
            "created_at": now,
        },
        {
            "login_id": ADMIN_UID,
            "name": "Admin Demo",
            "email": ADMIN_EMAIL,
            "role": "school_admin",
            "created_at": now,
        },
    ]

    # Firebase users (mirrors)
    for row in _STORE.tables[USERS_TABLE]:
        _STORE.firebase_users[row["login_id"]] = {
            "uid": row["login_id"],
            "email": row["email"],
            "role": row["role"],
            "name": row["name"],
        }
        _STORE.firebase_email_index[row["email"]] = row["login_id"]

    # School
    _STORE.tables[SCHOOLS_TABLE] = [
        {
            "id": SCHOOL_ID,
            "name": "Escola Demo",
            "user_id": ADMIN_UID,
            "created_at": now,
        }
    ]

    # Class
    _STORE.tables[CLASSES_TABLE] = [
        {
            "id": CLASS_ID,
            "name": "Turma Demo — 3º ano",
            "school_id": SCHOOL_ID,
            "professor_id": PROFESSOR_UID,
            "created_at": now,
        }
    ]

    # Students
    _STORE.tables[STUDENTS_TABLE] = [
        {
            "id": STUDENT_UID,
            "user_id": STUDENT_UID,
            "class_id": CLASS_ID,
            "school_id": SCHOOL_ID,
            "created_at": now,
        }
    ]

    # Professors
    _STORE.tables[PROFESSORS_TABLE] = [
        {
            "id": PROFESSOR_UID,
            "user_id": PROFESSOR_UID,
            "school_id": SCHOOL_ID,
            "created_at": now,
        }
    ]

    # Themes
    _STORE.tables[THEMES_TABLE] = [
        {
            "id": THEME_ID,
            "name": "O impacto das redes sociais na saúde mental dos jovens",
            "description": "Discuta os efeitos do uso contínuo de redes sociais no bem-estar emocional dos adolescentes brasileiros.",
            "class_id": CLASS_ID,
            "created_at": now,
        }
    ]

    # Competencies (the UI maps by id → friendly name via COMPETENCIES dict,
    # but some queries join on the competencies table — populate it too).
    _STORE.tables[COMPETENCIES_TABLE] = [
        {"id": comp_id, "name": name}
        for comp_id, name in COMPETENCIES.items()
    ]


# ---------------------------------------------------------------------------
# Fake Firebase
# ---------------------------------------------------------------------------


def _encode_dev_token(payload: Dict[str, Any]) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return f"dev:{raw}"


def _decode_dev_token(token: str) -> Dict[str, Any]:
    if not token.startswith("dev:"):
        raise ValueError("Not a dev token")
    raw = token.split(":", 1)[1]
    # Browser-side ``btoa`` output has its '=' padding stripped by our encoder
    # for URL safety. urlsafe_b64decode requires padding, so pad back to a
    # multiple of 4.
    raw += "=" * (-len(raw) % 4)
    return json.loads(base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8"))


class FakeFirebaseService:
    """Stand-in for the real FirebaseService.

    Public surface mirrors the subset the app actually calls.
    """

    def __init__(self) -> None:
        pass

    def initialize_firebase(self) -> None:
        return None

    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        from fastapi import HTTPException

        try:
            claims = _decode_dev_token(token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid dev token.") from exc
        uid = claims.get("uid")
        if not uid:
            raise HTTPException(status_code=401, detail="Dev token missing uid.")
        return {
            "uid": uid,
            "email": claims.get("email"),
            "role": claims.get("role"),
            "name": claims.get("name"),
        }

    @staticmethod
    def create_user(email: str, password: str, role: str = "student") -> Dict[str, Any]:
        uid = hashlib.sha1(email.encode("utf-8")).hexdigest()[:24]
        with _LOCK:
            _STORE.firebase_users[uid] = {
                "uid": uid,
                "email": email,
                "role": role,
                "name": email.split("@")[0],
            }
            _STORE.firebase_email_index[email] = uid
        return {"email": email, "uid": uid, "role": role}

    @staticmethod
    def send_password_reset_email(email: str) -> Dict[str, str]:
        return {"message": "Dev: password reset skipped.", "email": email}

    @staticmethod
    def send_account_creation_email(email: str, name: str, password: str) -> Dict[str, str]:
        return {"message": "Dev: account creation email skipped.", "email": email}

    @staticmethod
    def edit_user(user_id: str, username: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
        with _LOCK:
            user = _STORE.firebase_users.get(user_id)
            if user and username:
                user["name"] = username
        return {"message": "updated", "user_id": user_id, "display_name": username}

    @staticmethod
    def delete_user(uid: str) -> None:
        with _LOCK:
            user = _STORE.firebase_users.pop(uid, None)
            if user:
                _STORE.firebase_email_index.pop(user["email"], None)


# ---------------------------------------------------------------------------
# Fake BigQuery client
# ---------------------------------------------------------------------------


def _extract_first_quoted(query: str, marker: str) -> Optional[str]:
    """Find the first single-quoted token after a given marker."""
    idx = query.find(marker)
    if idx == -1:
        return None
    m = re.search(r"'([^']*)'", query[idx:])
    return m.group(1) if m else None


def _extract_param(query: str, name: str, params: Iterable[Any]) -> Optional[str]:
    """Resolve a @param name into its scalar value from the params list."""
    for p in params or []:
        pname = getattr(p, "name", None)
        if pname == name:
            return getattr(p, "value", None)
    return None


class _FakeSelectResults:
    """Emulates the iterable rows returned by the real BigQuery client.

    Each row is an object with attribute access (``row.foo``) plus ``dict`` -
    like behaviour for code that unpacks with ``**row``.
    """

    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def __iter__(self):
        for row in self._rows:
            yield _FakeRow(row)


class _FakeRow(dict):
    def __init__(self, data: Dict[str, Any]):
        super().__init__(data)

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    # ``keys`` works automatically via dict; having ``items`` too helps ``**row``.


class FakeBigQueryClient:
    """Replaces BigQueryClient for dev mode."""

    def __init__(self) -> None:
        pass

    # -- SELECT -------------------------------------------------------------

    def select(self, query: str) -> _FakeSelectResults:
        rows = self._dispatch_select(query, params=None)
        return _FakeSelectResults(rows)

    def select_with_params(self, query: str, query_params: List[Any]) -> _FakeSelectResults:
        rows = self._dispatch_select(query, params=query_params)
        return _FakeSelectResults(rows)

    # -- INSERT (streaming) ------------------------------------------------

    def insert(self, table_id: str, rows_to_insert: List[Dict[str, Any]]) -> None:
        with _LOCK:
            _STORE.tables[table_id].extend(rows_to_insert)
            _persist()

    # -- DML (INSERT/UPDATE/DELETE/MERGE via SQL) --------------------------

    def execute_query(self, query: str, query_params: Optional[List[Any]] = None) -> None:
        self._dispatch_dml(query, params=query_params)
        with _LOCK:
            _persist()

    # ------------------------------------------------------------------
    # Dispatch helpers — matches on keywords in the query string
    # ------------------------------------------------------------------

    def _dispatch_select(self, query: str, params: Optional[Iterable[Any]]) -> List[Dict[str, Any]]:
        from redato_backend.shared.constants import (
            CLASSES_TABLE,
            COMPETENCIES,
            ESSAYS_DETAILED_TABLE,
            ESSAYS_ERRORS_TABLE,
            ESSAYS_GRADED_TABLE,
            ESSAYS_OCR_TABLE,
            ESSAYS_RAW_TABLE,
            PROFESSOR_CORRECTIONS_TABLE,
            PROFESSORS_TABLE,
            SCHOOLS_TABLE,
            STUDENTS_TABLE,
            THEMES_TABLE,
            USERS_TABLE,
        )

        q = query
        with _LOCK:
            # --- professor feedback (parameterized) ---
            if PROFESSOR_CORRECTIONS_TABLE in q:
                essay_id = _extract_param(q, "essay_id", params)
                return [
                    r for r in _STORE.tables[PROFESSOR_CORRECTIONS_TABLE]
                    if r.get("essay_id") == essay_id
                ]

            # --- essay analysis join ---
            if ESSAYS_GRADED_TABLE in q and ESSAYS_DETAILED_TABLE in q and "WHERE eg.essay_id" in q:
                essay_id = _extract_first_quoted(q, "WHERE eg.essay_id")
                return _essay_analysis_rows(essay_id)

            # --- essay grading dedup by hash ---
            if ESSAYS_GRADED_TABLE in q and "eg.hash" in q:
                hash_value = _extract_first_quoted(q, "eg.hash")
                return [
                    {"essay_id": r["essay_id"]}
                    for r in _STORE.tables[ESSAYS_GRADED_TABLE]
                    if r.get("hash") == hash_value
                ]

            # --- essay raw content ---
            if ESSAYS_RAW_TABLE in q and "SELECT" in q.upper() and "WHERE id" in q:
                essay_id = _extract_first_quoted(q, "WHERE id")
                return [
                    r for r in _STORE.tables[ESSAYS_RAW_TABLE]
                    if r.get("id") == essay_id
                ]

            # --- OCR row ---
            if ESSAYS_OCR_TABLE in q and "ocr_id" in q:
                ocr_id = _extract_first_quoted(q, "ocr_id")
                return [
                    r for r in _STORE.tables[ESSAYS_OCR_TABLE]
                    if r.get("ocr_id") == ocr_id
                ]

            # --- user lookup by email ---
            if USERS_TABLE in q and "email" in q.lower() and "SELECT login_id" in q:
                email = _extract_first_quoted(q, "email")
                return [
                    {"login_id": r["login_id"], "name": r["name"]}
                    for r in _STORE.tables[USERS_TABLE]
                    if r.get("email") == email
                ]

            # --- school id by admin login ---
            if SCHOOLS_TABLE in q and "user_id" in q:
                user_id = _extract_first_quoted(q, "user_id")
                return [
                    {"school_id": r["id"]}
                    for r in _STORE.tables[SCHOOLS_TABLE]
                    if r.get("user_id") == user_id
                ]

            # --- class id of a student ---
            if STUDENTS_TABLE in q and "SELECT" in q and "class_id" in q and "user_id" in q and CLASSES_TABLE not in q:
                user_id = _extract_first_quoted(q, "user_id")
                return [
                    {"class_id": r["class_id"]}
                    for r in _STORE.tables[STUDENTS_TABLE]
                    if r.get("user_id") == user_id
                ]

            # --- themes for a class ---
            if THEMES_TABLE in q and "class_id" in q and "SELECT" in q:
                class_id = _extract_first_quoted(q, "class_id")
                return [
                    r for r in _STORE.tables[THEMES_TABLE]
                    if r.get("class_id") == class_id
                ]

            # --- list professors ---
            if PROFESSORS_TABLE in q and USERS_TABLE in q and "school_id" in q and "SELECT p.user_id" in q:
                school_id = _extract_first_quoted(q, "school_id")
                prof_ids = {p["user_id"] for p in _STORE.tables[PROFESSORS_TABLE] if p.get("school_id") == school_id}
                return [
                    {"user_id": u["login_id"], "name": u["name"], "email": u["email"]}
                    for u in _STORE.tables[USERS_TABLE]
                    if u["login_id"] in prof_ids
                ]

            # --- list classes for a school ---
            if CLASSES_TABLE in q and "school_id" in q and "professor_id" in q:
                school_id = _extract_first_quoted(q, "school_id")
                return _list_classes_rows(school_id)

            # --- list students for a school ---
            if STUDENTS_TABLE in q and CLASSES_TABLE in q and "school_id" in q:
                school_id = _extract_first_quoted(q, "school_id")
                return _list_students_rows(school_id)

            # --- user dashboard ---
            if "latest_15_essays" in q:
                login_id = _extract_first_quoted(q, "u.login_id")
                return _user_dashboard_rows(login_id)

            # --- class students with averages ---
            if "class_id" in q and "AVG(eg.overall_grade)" in q and CLASSES_TABLE in q and STUDENTS_TABLE in q:
                class_id = _extract_first_quoted(q, "c.id")
                return _class_students_rows(class_id)

            # --- professor general / competency performance: return empty
            # by default (not critical for correction flow validation) ---
            if "professor_classes" in q:
                return []

            # Fallback — log so the user can see unmatched queries
            print(f"[dev_offline] unmatched SELECT:\n{query[:200]}...")
            return []

    def _dispatch_dml(self, query: str, params: Optional[Iterable[Any]]) -> None:
        from redato_backend.shared.constants import (
            CLASSES_TABLE,
            PROFESSORS_TABLE,
            PROFESSOR_CORRECTIONS_TABLE,
            STUDENTS_TABLE,
            THEMES_TABLE,
        )

        q = query
        with _LOCK:
            # MERGE for professor_corrections (parameterized)
            if "MERGE" in q and PROFESSOR_CORRECTIONS_TABLE in q:
                essay_id = _extract_param(q, "essay_id", params)
                professor_id = _extract_param(q, "professor_id", params)
                feedback_text = _extract_param(q, "feedback_text", params)
                now = datetime.now(timezone.utc)
                table = _STORE.tables[PROFESSOR_CORRECTIONS_TABLE]
                existing = next((r for r in table if r.get("essay_id") == essay_id), None)
                if existing:
                    existing["feedback_text"] = feedback_text
                    existing["professor_id"] = professor_id
                    existing["updated_at"] = now
                else:
                    table.append({
                        "id": str(uuid4()),
                        "essay_id": essay_id,
                        "professor_id": professor_id,
                        "feedback_text": feedback_text,
                        "created_at": now,
                        "updated_at": now,
                    })
                return

            # INSERT INTO themes / professors / classes (template substitution)
            if q.strip().upper().startswith("INSERT INTO"):
                _handle_insert(q)
                return

            # UPDATE classes SET professor_id = '...' WHERE id = '...'
            if q.strip().upper().startswith("UPDATE") and CLASSES_TABLE in q:
                professor_id = _extract_first_quoted(q, "professor_id =")
                class_id = _extract_first_quoted(q, "WHERE id")
                for row in _STORE.tables[CLASSES_TABLE]:
                    if row.get("id") == class_id:
                        row["professor_id"] = professor_id
                return

            # DELETE
            if q.strip().upper().startswith("DELETE"):
                _handle_delete(q)
                return

            print(f"[dev_offline] unmatched DML:\n{query[:200]}...")


# ---------------------------------------------------------------------------
# SELECT row builders
# ---------------------------------------------------------------------------


def _essay_analysis_rows(essay_id: Optional[str]) -> List[Dict[str, Any]]:
    from redato_backend.shared.constants import (
        ESSAYS_DETAILED_TABLE,
        ESSAYS_ERRORS_TABLE,
        ESSAYS_GRADED_TABLE,
    )

    graded = next(
        (r for r in _STORE.tables[ESSAYS_GRADED_TABLE] if r.get("essay_id") == essay_id),
        None,
    )
    if not graded:
        return []
    details = [r for r in _STORE.tables[ESSAYS_DETAILED_TABLE] if r.get("essay_id") == essay_id]
    errors = [r for r in _STORE.tables[ESSAYS_ERRORS_TABLE] if r.get("essay_id") == essay_id]

    rows: List[Dict[str, Any]] = []
    for detail in details:
        detail_errors = [
            e for e in errors if e.get("competency") == detail.get("competency")
        ]
        if not detail_errors:
            rows.append({
                "essay_id": graded["essay_id"],
                "overall_grade": graded["overall_grade"],
                "competency": detail["competency"],
                "feedback": graded.get("feedback"),
                "grade": detail["grade"],
                "justification": detail.get("justification"),
                "description": None,
                "snippet": None,
                "error_type": None,
                "suggestion": None,
                "error_competency": None,
            })
            continue
        for err in detail_errors:
            rows.append({
                "essay_id": graded["essay_id"],
                "overall_grade": graded["overall_grade"],
                "competency": detail["competency"],
                "feedback": graded.get("feedback"),
                "grade": detail["grade"],
                "justification": detail.get("justification"),
                "description": err.get("description"),
                "snippet": err.get("snippet"),
                "error_type": err.get("error_type"),
                "suggestion": err.get("suggestion"),
                "error_competency": err.get("competency"),
            })
    return rows


def _list_classes_rows(school_id: Optional[str]) -> List[Dict[str, Any]]:
    from redato_backend.shared.constants import (
        CLASSES_TABLE,
        PROFESSORS_TABLE,
        USERS_TABLE,
    )

    rows = []
    for c in _STORE.tables[CLASSES_TABLE]:
        if c.get("school_id") != school_id:
            continue
        prof_id = c.get("professor_id")
        prof_user = None
        if prof_id:
            prof_user = next(
                (u for u in _STORE.tables[USERS_TABLE] if u["login_id"] == prof_id),
                None,
            )
        rows.append({
            "id": c["id"],
            "name": c["name"],
            "created_at": c["created_at"],
            "professor_id": prof_id,
            "professor_name": prof_user["name"] if prof_user else None,
            "professor_email": prof_user["email"] if prof_user else None,
        })
    return rows


def _list_students_rows(school_id: Optional[str]) -> List[Dict[str, Any]]:
    from redato_backend.shared.constants import (
        CLASSES_TABLE,
        STUDENTS_TABLE,
        USERS_TABLE,
    )

    rows = []
    for s in _STORE.tables[STUDENTS_TABLE]:
        if s.get("school_id") != school_id:
            continue
        user = next(
            (u for u in _STORE.tables[USERS_TABLE] if u["login_id"] == s["user_id"]),
            None,
        )
        klass = next(
            (c for c in _STORE.tables[CLASSES_TABLE] if c["id"] == s["class_id"]),
            None,
        )
        rows.append({
            "user_id": s["user_id"],
            "name": user["name"] if user else s["user_id"],
            "email": user["email"] if user else "",
            "class_id": s["class_id"],
            "class_name": klass["name"] if klass else None,
            "created_at": s["created_at"],
        })
    return rows


def _user_dashboard_rows(login_id: Optional[str]) -> List[Dict[str, Any]]:
    from redato_backend.shared.constants import (
        COMPETENCIES,
        ESSAYS_DETAILED_TABLE,
        ESSAYS_GRADED_TABLE,
        ESSAYS_RAW_TABLE,
    )

    graded = [r for r in _STORE.tables[ESSAYS_GRADED_TABLE] if r.get("user_id") == login_id]
    graded.sort(key=lambda r: r.get("graded_at", ""), reverse=True)
    graded = graded[:15]

    rows: List[Dict[str, Any]] = []
    for g in graded:
        raw = next((r for r in _STORE.tables[ESSAYS_RAW_TABLE] if r.get("id") == g["essay_id"]), {})
        details = [d for d in _STORE.tables[ESSAYS_DETAILED_TABLE] if d.get("essay_id") == g["essay_id"]]
        if not details:
            rows.append({
                "essay_id": g["essay_id"],
                "graded_at": g["graded_at"],
                "theme": raw.get("theme"),
                "overall_grade": g["overall_grade"],
                "competency": None,
                "competency_name": None,
                "grade": None,
            })
            continue
        for d in details:
            rows.append({
                "essay_id": g["essay_id"],
                "graded_at": g["graded_at"],
                "theme": raw.get("theme"),
                "overall_grade": g["overall_grade"],
                "competency": d["competency"],
                "competency_name": COMPETENCIES.get(d["competency"], d["competency"]),
                "grade": d["grade"],
            })
    return rows


def _class_students_rows(class_id: Optional[str]) -> List[Dict[str, Any]]:
    from redato_backend.shared.constants import (
        ESSAYS_GRADED_TABLE,
        STUDENTS_TABLE,
        USERS_TABLE,
    )

    rows = []
    for s in _STORE.tables[STUDENTS_TABLE]:
        if s.get("class_id") != class_id:
            continue
        user = next(
            (u for u in _STORE.tables[USERS_TABLE] if u["login_id"] == s["user_id"]),
            None,
        )
        grades = [
            g["overall_grade"]
            for g in _STORE.tables[ESSAYS_GRADED_TABLE]
            if g.get("user_id") == s["user_id"]
        ]
        avg = sum(grades) / len(grades) if grades else 0
        rows.append({
            "login_id": s["user_id"],
            "name": user["name"] if user else s["user_id"],
            "average_grade": avg,
        })
    return rows


# ---------------------------------------------------------------------------
# DML handlers
# ---------------------------------------------------------------------------


def _handle_insert(query: str) -> None:
    """Parse INSERT INTO … VALUES (…) statements from the known templates."""
    from redato_backend.shared.constants import (
        CLASSES_TABLE,
        PROFESSORS_TABLE,
        THEMES_TABLE,
    )

    now = datetime.now(timezone.utc).isoformat()

    if THEMES_TABLE in query:
        values = _extract_values(query)
        if len(values) >= 5:
            _STORE.tables[THEMES_TABLE].append({
                "id": values[0],
                "created_at": values[1],
                "name": values[2],
                "description": values[3],
                "class_id": values[4],
            })
        return

    if PROFESSORS_TABLE in query:
        values = _extract_values(query)
        if len(values) >= 4:
            _STORE.tables[PROFESSORS_TABLE].append({
                "id": values[0],
                "user_id": values[1],
                "created_at": values[2],
                "school_id": values[3],
            })
        return

    if CLASSES_TABLE in query:
        values = _extract_values(query)
        if len(values) >= 5:
            _STORE.tables[CLASSES_TABLE].append({
                "id": values[0],
                "name": values[1],
                "school_id": values[2],
                "professor_id": None if values[3].upper() == "NULL" else values[3],
                "created_at": values[4],
            })
        return


def _extract_values(query: str) -> List[str]:
    """Grab the VALUES (…) tuple. Handles quoted values and NULL."""
    m = re.search(r"VALUES\s*\((.*)\)", query, re.DOTALL | re.IGNORECASE)
    if not m:
        return []
    raw = m.group(1)
    # Split respecting quotes. Very small parser.
    values: List[str] = []
    current = []
    in_quote = False
    depth = 0
    for ch in raw:
        if ch == "'" and not in_quote:
            in_quote = True
            continue
        if ch == "'" and in_quote:
            in_quote = False
            continue
        if ch == "(" and not in_quote:
            depth += 1
            current.append(ch)
            continue
        if ch == ")" and not in_quote:
            depth -= 1
            current.append(ch)
            continue
        if ch == "," and not in_quote and depth == 0:
            values.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    if current:
        values.append("".join(current).strip())
    # strip wrapping TIMESTAMP('...') around timestamps, leaving the inner string
    cleaned: List[str] = []
    for v in values:
        ts_m = re.match(r"TIMESTAMP\('(.*)'\)", v)
        if ts_m:
            cleaned.append(ts_m.group(1))
        else:
            cleaned.append(v)
    return cleaned


def _handle_delete(query: str) -> None:
    from redato_backend.shared.constants import (
        CLASSES_TABLE,
        PROFESSORS_TABLE,
        STUDENTS_TABLE,
        THEMES_TABLE,
    )

    target_id = None
    key = "id"
    for table, column in [
        (CLASSES_TABLE, "id"),
        (PROFESSORS_TABLE, "user_id"),
        (THEMES_TABLE, "id"),
        (STUDENTS_TABLE, "user_id"),
    ]:
        if table in query:
            target_id = _extract_first_quoted(query, f"WHERE {column}")
            if target_id is None:
                target_id = _extract_first_quoted(query, "WHERE")
            key = column
            _STORE.tables[table] = [
                r for r in _STORE.tables[table]
                if r.get(key) != target_id
            ]
            return


# ---------------------------------------------------------------------------
# Fake Firestore
# ---------------------------------------------------------------------------


class _FakeDocSnapshot:
    def __init__(self, path: str, data: Optional[Dict[str, Any]]):
        self._path = path
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> Optional[Dict[str, Any]]:
        return None if self._data is None else dict(self._data)


class _FakeDocRef:
    def __init__(self, path: str):
        self._path = path

    def get(self) -> _FakeDocSnapshot:
        with _LOCK:
            data = _STORE.firestore_docs.get(self._path)
        return _FakeDocSnapshot(self._path, data)

    def set(self, data: Dict[str, Any], merge: bool = False) -> None:
        with _LOCK:
            if merge and self._path in _STORE.firestore_docs:
                _STORE.firestore_docs[self._path].update(data)
            else:
                _STORE.firestore_docs[self._path] = dict(data)
            _persist()

    def create(self, data: Dict[str, Any]) -> None:
        from google.api_core import exceptions as gcp_exceptions

        with _LOCK:
            if self._path in _STORE.firestore_docs:
                raise gcp_exceptions.AlreadyExists(self._path)
            _STORE.firestore_docs[self._path] = dict(data)
            _persist()

    def delete(self) -> None:
        with _LOCK:
            _STORE.firestore_docs.pop(self._path, None)
            _persist()

    def collection(self, name: str) -> "_FakeCollection":
        return _FakeCollection(f"{self._path}/{name}")


class _FakeCollection:
    def __init__(self, path: str):
        self._path = path

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(f"{self._path}/{doc_id}")


class FakeFirestoreClient:
    def __init__(self, database: Optional[str] = None, project: Optional[str] = None) -> None:
        self._database = database

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(name)


# ---------------------------------------------------------------------------
# Fake Cloud Function caller
# ---------------------------------------------------------------------------


async def fake_call_cloud_function(function_url: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate the 3 Cloud Functions used by the app.

    For essay grading and tutor chat, if ``ANTHROPIC_API_KEY`` is set we call
    the real Claude API locally; otherwise we return deterministic fake data.
    OCR always returns a canned transcription (doing real OCR locally would
    require Vision / Claude image APIs — out of scope for dev mode).

    The Claude calls are synchronous (SDK blocks), so we run them in a thread
    via ``asyncio.to_thread`` to avoid blocking the FastAPI event loop while
    a grading call is in flight (which can be 30-60s).
    """
    import asyncio
    import os

    from redato_backend.shared.constants import (
        ESSAY_OCR_CLOUD_FUNCTION,
        ESSAYS_ANALYZER_CLOUD_FUNCTION,
        TUTOR_CLOUD_FUNCTION,
    )

    use_claude = bool(os.getenv("ANTHROPIC_API_KEY"))

    if function_url == ESSAYS_ANALYZER_CLOUD_FUNCTION or "essay_handler" in function_url:
        try:
            if use_claude:
                # Run the quick preview + full grading concurrently. The preview
                # streams text into Firestore within seconds; the full grading
                # takes 30-40s. Total wall time == full grading time.
                await asyncio.gather(
                    asyncio.to_thread(_stream_quick_preview, data),
                    asyncio.to_thread(_claude_grade_essay, data),
                )
            else:
                _fake_grade_essay(data)
        except Exception as exc:  # noqa: BLE001
            print(f"[dev_offline] grading failed ({exc!r}); falling back to stub")
            _fake_grade_essay(data)
        return {"status_code": 200, "text": "ok", "json": {"message": "graded"}}

    if function_url == ESSAY_OCR_CLOUD_FUNCTION or "ocr_handler" in function_url:
        _fake_ocr(data)
        return {"status_code": 200, "text": "ok", "json": {"message": "ocr done"}}

    if function_url == TUTOR_CLOUD_FUNCTION or "chat_tutor" in function_url:
        try:
            if use_claude:
                response = await asyncio.to_thread(_claude_tutor_reply, data)
            else:
                response = _fake_tutor_reply(data)
        except Exception as exc:  # noqa: BLE001
            print(f"[dev_offline] tutor failed ({exc!r}); falling back to stub")
            response = _fake_tutor_reply(data)
        return {
            "status_code": 200,
            "text": "ok",
            "json": {"response": response},
        }

    return {"status_code": 200, "text": "ok", "json": {}}


def _fake_grade_essay(data: Dict[str, Any]) -> None:
    """Write a deterministic grading to the stubbed BQ tables."""
    from redato_backend.shared.constants import (
        COMPETENCIES,
        ESSAYS_DETAILED_TABLE,
        ESSAYS_ERRORS_TABLE,
        ESSAYS_GRADED_TABLE,
    )
    from redato_backend.shared.utils import generate_essay_hash

    essay_id = data["request_id"]
    content = data.get("content", "")
    user_id = data.get("user_id")
    now = datetime.now(timezone.utc).isoformat()

    # Simple deterministic grading: 160 / 200 per competency except C3 (120).
    comp_ids = list(COMPETENCIES.keys())
    fixed = {
        comp_ids[0]: 160,  # Domínio da Norma Culta
        comp_ids[1]: 160,  # Seleção e Organização das Informações
        comp_ids[2]: 120,  # Conhecimento dos Mecanismos Linguísticos
        comp_ids[3]: 160,  # Compreensão do Tema
        comp_ids[4]: 160,  # Proposta de Intervenção
    }
    total = sum(fixed.values())

    with _LOCK:
        _STORE.tables[ESSAYS_GRADED_TABLE].append({
            "essay_id": essay_id,
            "user_id": user_id,
            "overall_grade": total,
            "graded_at": now,
            "feedback": (
                "Boa redação! A estrutura argumentativa está clara e a proposta "
                "de intervenção atende aos cinco elementos. Pontos de atenção: "
                "uso de conectivos para transições mais fluidas entre parágrafos "
                "e variação de repertório sociocultural na introdução."
            ),
            "hash": generate_essay_hash(content),
        })

        justifications = {
            comp_ids[0]: "Texto com poucos desvios formais, boa clareza vocabular.",
            comp_ids[1]: "Tema abordado com propriedade; poderia variar o repertório.",
            comp_ids[2]: "Uso correto de conectivos no interior dos parágrafos, mas transições entre parágrafos podem melhorar.",
            comp_ids[3]: "Tema compreendido e desenvolvido com argumentos pertinentes.",
            comp_ids[4]: "Proposta contempla agente, ação, meio, finalidade e detalhamento.",
        }

        for comp_id, grade in fixed.items():
            _STORE.tables[ESSAYS_DETAILED_TABLE].append({
                "essay_id": essay_id,
                "competency": comp_id,
                "detailed_analysis": justifications[comp_id],
                "grade": grade,
                "justification": justifications[comp_id],
                "graded_at": now,
            })

        # One illustrative error on the linguistic-mechanisms competency
        _STORE.tables[ESSAYS_ERRORS_TABLE].append({
            "essay_id": essay_id,
            "competency": comp_ids[2],
            "snippet": content[:60] if content else "trecho demonstrativo",
            "error_type": "transição entre parágrafos",
            "description": "Transição direta entre parágrafos sem conectivo argumentativo.",
            "suggestion": "Considere iniciar o próximo parágrafo com 'Nesse sentido,' ou 'Diante disso,'.",
            "graded_at": now,
        })
        _persist()


def _fake_ocr(data: Dict[str, Any]) -> None:
    from redato_backend.shared.constants import ESSAYS_OCR_TABLE

    ocr_id = data["request_id"]
    now = datetime.now(timezone.utc).date().isoformat()

    transcription = (
        "A sociedade brasileira enfrenta um desafio contemporâneo relacionado ao uso "
        "<uncertain confidence='HIGH'>excessivo</uncertain> de redes sociais pelos jovens. "
        "Esse fenômeno tem impactos diretos na saúde mental, especialmente entre "
        "<uncertain confidence='MEDIUM'>adolescentes</uncertain>."
    )

    with _LOCK:
        _STORE.tables[ESSAYS_OCR_TABLE].append({
            "ocr_id": ocr_id,
            "content": transcription,
            "theme": "O impacto das redes sociais na saúde mental dos jovens",
            "accuracy": 0.86,
            "user_id": data.get("user_id"),
            "loaded_at": now,
        })
        _persist()


def _fake_tutor_reply(data: Dict[str, Any]) -> str:
    competency = data.get("competency", "")
    errors = data.get("errors") or []
    if errors:
        return (
            f"Vamos pensar juntos sobre esse trecho em '{competency}'. "
            f"O problema destacado é: {errors[0]}. Tente reescrever conectando "
            f"essa ideia ao argumento central do parágrafo usando um conectivo "
            f"como 'dessa maneira' ou 'logo'. Quer ver um exemplo?"
        )
    return (
        "Me conte em uma frase qual é a sua dúvida principal sobre este trecho — "
        "assim consigo te ajudar com mais precisão."
    )


# ---------------------------------------------------------------------------
# Real grading via Claude (activated by ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------
#
# Design choices (see DEV.md for rationale):
#   1. System prompt = Parte A of docs/redato/redato_system_prompt.md, loaded
#      from disk at module import time. Big prompt, high quality.
#   2. Prompt caching (cache_control=ephemeral) on the system block so the
#      ~11k-token prompt is only paid for on the first call; subsequent
#      calls within 5 min pay 10% of that cost and a couple seconds less.
#   3. tool_use with a strict JSON schema forces Claude to emit output the
#      backend can consume directly — no parse retries, no malformed JSON.
#   4. Output schema follows the Redato canonical ``correcao_completa``
#      (see Parte C of the markdown) then maps into the stubbed BQ tables.


# dev_offline.py lives at redato_hash/backend/notamil-backend/redato_backend/dev_offline.py;
# the v2 rubric lives at redato_hash/docs/redato/v2/rubrica_v2.md (3 dirs up).
#
# Em prod (Docker), o módulo está em /app/redato_backend/dev_offline.py.
# `parents[3]` estoura IndexError porque só há 2 níveis acima de /app.
# Por isso `_get_repo_root()` é defensivo — fallback /app é seguro:
# rubricas não existem no Docker (filtradas pelo .dockerignore via docs/),
# loaders já têm try/except interno e caem no _FALLBACK_SYSTEM_PROMPT.
def _get_repo_root() -> Path:
    """Raiz do repo em dev local; `/app` (placeholder) em Docker."""
    try:
        return Path(__file__).resolve().parents[3]
    except IndexError:
        return Path("/app")


# Path builders — lazy. Em Docker, calculados em runtime, não import-time.
def _rubric_v2_path() -> Path:
    return _get_repo_root() / "docs" / "redato" / "v2" / "rubrica_v2.md"


def _rubric_v1_path() -> Path:
    """Legacy v1 rubric — fallback if v2 missing."""
    return _get_repo_root() / "docs" / "redato" / "redato_system_prompt.md"


# v3 holística — REVERTIDA em 2026-04-26 (falha estrutural no eval, ver
# docs/redato/v3/_failed/README_FAILURE.md). Arquivos movidos pra _failed/
# pra preservação. Branch REDATO_RUBRICA=v3 continua funcional pra
# reprodutibilidade do experimento. Quando v4 chegar com paradigma novo,
# adicionar _rubric_v4_path() / _system_v4_path() análogos.
def _rubric_v3_path() -> Path:
    return _get_repo_root() / "docs" / "redato" / "v3" / "_failed" / "rubrica_v3.md"


def _system_v3_path() -> Path:
    return _get_repo_root() / "docs" / "redato" / "v3" / "_failed" / "system_prompt_v3.md"


_FALLBACK_SYSTEM_PROMPT = (
    "Você é a Redato, corretora automatizada de redações do ENEM. Avalie a "
    "redação segundo as 5 competências oficiais do INEP, usando a escala "
    "discreta 0/40/80/120/160/200. Na dúvida entre dois níveis, vá para o "
    "superior. Total é a soma das 5 competências (0-1000)."
)


_REDATO_PERSONA = """\
# REDATO — Identidade e modo de correção

Você é a **Redato**, corretora automatizada de redações do ENEM do programa
"Redação em Jogo" (MVT Educação, ensino médio brasileiro). Corrige com
fidelidade à rubrica oficial do INEP e aos critérios operacionais
documentados abaixo.

## Tom
- Direto, específico, construtivo. "Sua tese não apresenta posicionamento"
  é melhor do que "sua tese poderia estar mais clara".
- Técnico sem ser hermético. Use vocabulário da rubrica ENEM, mas explique
  quando o aluno mostra desconhecimento.
- Respeitoso com o esforço; nunca ironia ou humor às custas do texto.
- Honesto sobre a nota: se o texto é 80 em C3, dê 80 e explique como chegar
  a 120. Não suavize para agradar.
- Português brasileiro, segunda pessoa. "Você argumentou bem em…",
  "Seu parágrafo precisa de…".

## Modo de correção
Você opera por **contagem numérica** explícita, não por estimativa. Em C1,
conte desvios um a um. Em C2, verifique palavras-chave parágrafo por
parágrafo. Em C5, marque presença booleana de cada um dos 5 elementos
antes de fixar a nota. A ferramenta `submit_correction` força essa
auditoria através de campos obrigatórios — preencha todos, inclusive os
booleanos de threshold.

---

"""


def _load_rubric() -> str:
    """Load the v2 authoritative rubric. Falls back to v1 Parte A if missing.

    Em Docker, paths não existem — todas as tentativas falham e cai no
    `_FALLBACK_SYSTEM_PROMPT`. Aceitável: dev_offline não é usado em
    prod, mas o módulo precisa importar limpo pra que o guard de
    `apply_patches()` faça seu papel.
    """
    v1 = _rubric_v1_path()
    for path in (_rubric_v2_path(), v1):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        # v1 file has PARTE A/B/C; extract only Parte A.
        if path == v1:
            start = text.find("# PARTE A")
            end = text.find("# PARTE B")
            if start != -1 and end != -1 and end > start:
                text = text[start:end].strip()
        return _REDATO_PERSONA + text.strip()
    return _FALLBACK_SYSTEM_PROMPT


_SYSTEM_PROMPT_BASE = _load_rubric()


# ──────────────────────────────────────────────────────────────────────
# V3 HOLÍSTICA — A/B paralelo via REDATO_RUBRICA=v3
# ──────────────────────────────────────────────────────────────────────
# v3 rejeita filosofia mecânica da v2: notas são juízo qualitativo direto
# do LLM (não derivadas via Python), tool schema é simples (notas/flags/
# evidencias/audit_prose). Reusa _REDATO_PERSONA porque tom/registro são
# os mesmos; troca apenas a rubrica + critérios de gradação.

def _load_v3_system_prompt() -> str:
    """Constrói system prompt v3: persona Redato + system_prompt_v3.md
    (que internamente referencia rubrica_v3.md como fonte canônica)."""
    try:
        sys_v3 = _system_v3_path().read_text(encoding="utf-8").strip()
        # Anexa rubrica completa pra LLM ter referencial dos descritores.
        rubrica_v3 = _rubric_v3_path().read_text(encoding="utf-8").strip()
        return (
            _REDATO_PERSONA
            + sys_v3
            + "\n\n---\n\n## RUBRICA V3 COMPLETA (referência)\n\n"
            + rubrica_v3
        )
    except Exception as exc:
        # Fallback: se v3 não está disponível, registra mas não quebra.
        # Caller via REDATO_RUBRICA=v3 deve checar import-time.
        print(f"[dev_offline] WARN: v3 system prompt indisponível: {exc!r}")
        return _FALLBACK_SYSTEM_PROMPT


_SYSTEM_PROMPT_V3 = _load_v3_system_prompt()

# Short addendum tying the pedagogical prompt to the specific tool we ask
# Claude to call. Kept outside the cached block so we can iterate on it
# without invalidating the cache of the 11k-token Parte A.
_GRADING_TAIL_INSTRUCTION = """

---

## Formato de saída para esta chamada

Chame SEMPRE a ferramenta `submit_correction` com o JSON estruturado da
correção. Não responda em texto livre.

- `notas.c1`..`notas.c5`: notas INEP discretas (0, 40, 80, 120, 160 ou 200).
- `notas.total`: soma exata de c1..c5 (a ferramenta valida o total).
- `feedback_por_competencia.<cN>.resumo`: 1-2 frases resumindo a avaliação
  da competência.
- `feedback_por_competencia.<cN>.pontos_fortes`: 1-3 bullets positivos
  **estritamente da competência em questão** (ver regra de não-transbordamento
  na Seção 6.5.2).
- `feedback_por_competencia.<cN>.pontos_atencao`: 1-4 pontos de atenção,
  cada um com `trecho` literal copiado da redação, `problema` explicando
  o desvio e `sugestao` de como corrigir. Em C1, liste **todos** os desvios
  graves sem omitir nenhum. Deixe vazio apenas se realmente não houver.
- `tres_movimentos_seguintes`: exatamente 3 bullets acionáveis, priorizados.
  O 1º deve listar **TODOS** os desvios graves de C1 (não apenas exemplos)
  e declarar o ganho potencial real calculado pela matriz da Seção 6.5.2.
- `observacoes_gerais`: 2-3 frases gerais sobre o texto.

Use português brasileiro em todos os campos de texto.

## REGRAS DURAS de preenchimento dos audits

Antes da derivação mecânica, os audits precisam estar CORRETOS. Aplique:

### 1. Threshold_check de C1 — mecânico, sem "margem de segurança"

Depois de contar `desvios_gramaticais_count`, `erros_ortograficos_count`,
`desvios_crase_count`, `falhas_estrutura_sintatica_count` e `marcas_oralidade`,
aplique a tabela EXATAMENTE como está:

- **Nota 5** (`applies_nota_5=true`): total ≤ 2 desvios **E** ortográficos ≤ 1
  **E** crase ≤ 1 **E** falhas sintáticas ≤ 1 **E** zero oralidade.
- **Nota 4**: até 3 gramaticais, até 3 ortográficos, até 2 regência.
- **Nota 3**: até 5 gramaticais, estrutura regular.
- **Nota 2**: estrutura deficitária OU regular + muitos desvios.
- **Nota 1**: diversificados e frequentes (6+ desvios distintos).
- **Nota 0**: desconhecimento sistemático.

Marque **exatamente um** `applies_nota_N = true`. **Não marque nota_4 quando os
critérios de nota_5 estão satisfeitos**. Se você encontrou 0 ou 1 desvios e
não há marcas de oralidade, o texto é **nota 5 (200)**. Dar 160 "para ser
cauteloso" é **erro de calibração**, não conservadorismo.

### 2. Definição operacional de `has_explicit_thesis`

Tese = **posicionamento argumentativo** sobre o tema. Tem forma
"*X (causa/acarreta/gera) Y*" ou "*X é (problema/dever/urgência) por Z*".

São **tese explícita:**
- *"O uso das redes sociais tem comprometido a saúde mental da juventude,
  seja por X, seja por Y."* (posição + eixos)
- *"As redes sociais consolidaram uma cultura de comparação que adoece
  adolescentes."* (posição argumentativa)

**NÃO são tese** (marque `has_explicit_thesis=false`):
- *"As redes sociais têm diversas facetas e afetam os jovens de muitas
  maneiras distintas."* — descrição, não posição.
- *"Este é um tema que merece ser debatido com profundidade."* — metalinguagem.
- *"As redes sociais são um fenômeno amplo da contemporaneidade."* —
  generalidade.
- Qualquer abertura que apenas **apresenta o tema** sem tomar partido.

Se a introdução cita um autor (Han, Bauman) e depois descreve o tema sem
posicionar uma tese argumentativa, `has_explicit_thesis=false`.

### 3. Escopo de C1 — norma culta, NÃO coesão lexical

C1 avalia:
- Concordância (verbal, nominal)
- Crase
- Regência
- Ortografia, acentuação, pontuação
- Conjugação verbal
- Colocação pronominal
- Registro (formal × oralidade)

C1 **NÃO** avalia:
- Repetição de palavras ("saúde mental" 3x) → isso é **C4** (referenciação pobre).
- Uso excessivo do mesmo conectivo ("Além disso" 5x) → **C4**.
- Frases justapostas sem período composto → **C4** (articulação).
- Pronomes vagos ("isso" em cadeia) → **C4** (coesão referencial).

Se o texto tem 0 erros gramaticais mas repete palavras, `desvios_gramaticais_count=0`
e `threshold_check.applies_nota_5=true` → **C1=200**. A repetição vai para C4,
onde você marca `has_mechanical_repetition=true` e `most_used_connector_count`
ou `ambiguous_pronouns`, e o two-stage deriva C4 adequadamente.

## DERIVAÇÃO MECÂNICA das notas (não-negociável)

Depois de preencher os audits (c1_audit … c5_audit), as notas finais devem ser
**derivadas mecanicamente** dos audits, sem julgamento qualitativo. Aplique
cada regra como LOOKUP, não como estimativa:

**C1:**
- `c1_audit.threshold_check.applies_nota_N=true` → `c1.nota = N*40`.
  Só UM dos `applies_nota_*` pode ser true. Se você não consegue decidir,
  é porque ainda não contou os desvios com cuidado.

**C2:**
- `c2_audit.fuga_total_detected = true` → `c2.nota = 0`.
- `c2_audit.tangenciamento_detected = true` → `c2.nota = 40` (máximo).
  **Atenção sutil:** menção ao tema DENTRO de um nome próprio de obra
  (ex.: *"O Dilema das Redes"*) **NÃO conta** como palavra-chave presente.
  Menção ao art. 227 ou a uma pesquisa sobre o tema também NÃO substitui
  as palavras-chave do tema dissertado. Avalie se o texto discute LITERALMENTE
  "redes sociais / saúde mental / jovens" ou se disserta sobre conceito
  mais amplo (tecnologia, ambientes digitais, novas gerações) usando o tema
  como pretexto.
- `c2_audit.has_false_attribution = true` ou `has_wrong_legal_article = true`
  e abordagem completa → `c2.nota ≤ 120` (PDF nota 3).
- Caso contrário, aplique a rubrica normalmente.

**C5:**
- `c5_audit.elements_count = N` → `c5.nota = N*40`.
  Se `elements_count = 5` **e** `proposta_articulada_ao_tema = true`, `c5.nota = 200`.
  Se `elements_count = 4` **e** `proposta_articulada_ao_tema = false`, `c5.nota = 120`.
- Cada elemento só conta se existe trecho **literal** no texto. Não infira
  "meio implícito" de uma ação — marque `present: false` e `elements_count−1`.

**Anti-propagação:**
- A nota de uma competência depende APENAS do audit daquela competência.
- C1 baixo não rebaixa C2/C3/C4/C5. C5 baixo não rebaixa C1/C2/C3/C4.
- Se `c2_audit.repertoire_references` tem 5+ entradas legitimadas e produtivas
  em D1 e D2 com palavras-chave presentes, `c2.nota = 200` — mesmo que C3
  seja fraco, mesmo que C5 seja vago.

**Anti-criticismo:**
- Se NÃO encontrou desvios em C1 (`desvios_gramaticais_count ≤ 2`, `erros_ortograficos_count ≤ 1`, `desvios_crase_count ≤ 1`, `falhas_estrutura_sintatica_count ≤ 1`, sem oralidade), marque `applies_nota_5 = true` e dê **C1 = 200**. Não invente defeitos.
- Se uma competência está impecável, 200 é o valor correto. Dar 180 "para não exagerar" é criticismo obrigatório — **erro calibração**.

## CHECKLIST OBRIGATÓRIO antes de chamar a ferramenta

1. Contei cada desvio de C1 individualmente e o `threshold_check` reflete a
   contagem com EXATAMENTE um `applies_nota_N = true`?
2. Para C2, verifiquei parágrafo por parágrafo se as palavras-chave LITERAIS
   do tema (não sinônimos amplos, não menções em nomes próprios) estão
   presentes — ou se é tangenciamento?
3. Contei `c5_audit.elements_count` somando os booleanos `present`? Cada
   elemento tem `quote` literal ou `present = false`?
4. A nota de cada competência deriva APENAS do audit dela, sem puxão de C1/C3/C5 fracas?
5. Se o texto é impecável, **marquei 200**? Não subtrai por "rigor"?

Se qualquer resposta for "não", revise antes de enviar.
"""


_FEW_SHOT_EXAMPLES = """
## Exemplos trabalhados (v2 — contagem numérica estrita)

Estes exemplos mostram a aplicação correta dos thresholds numéricos do PDF.
Imite o nível de detalhe, a contagem explícita e a disciplina de isolamento
entre competências — uma nota baixa em C1 ou C5 **não** puxa C2/C3/C4 para
baixo.

### Exemplo 1 — C1 com 11 desvios → nota 1 (40 pts)

ENTRADA (redação sobre redes sociais) contém:
- Crase: *"aplica as redes sociais"*, *"recorrendo à estímulos"*, *"exposto à um
  ciclo"*, *"à longo prazo"* — 4 desvios de crase.
- Concordância: *"os jovens brasileiro expõe"*, *"os jovem"*, *"os mecanismos
  potencializa"* — 3 desvios.
- Mau/mal: *"mau respeita"* — 1.
- Ortografia/pontuação: *"Isso por que"* — 1.
- Oralidade: *"Tipo assim, a gente vê"*, *"pra menores"* — 2.

Total: ≈11 desvios. Pelo PDF (C1), "desvios diversificados e frequentes"
enquadra como nota 1.

SAÍDA esperada (trechos-chave):

    c1_audit.desvios_gramaticais = [lista EXAUSTIVA com 11 itens]
    c1_audit.desvios_gramaticais_count = 11
    c1_audit.desvios_crase_count = 4
    c1_audit.marcas_oralidade = ["Tipo assim, a gente vê", "pra menores"]
    c1_audit.threshold_check.applies_nota_5 = false
    c1_audit.threshold_check.applies_nota_4 = false
    c1_audit.threshold_check.applies_nota_3 = false
    c1_audit.threshold_check.applies_nota_2 = false
    c1_audit.threshold_check.applies_nota_1 = true       ← ENQUADRA
    c1_audit.threshold_check.applies_nota_0 = false
    c1_audit.nota = 40

    c2_audit.nota = 200    ← Han/Bauman/OMS/documentário/art.227, palavras-chave em todos os parágrafos
    c3_audit.nota = 200    ← tese clara, eixos desenvolvidos, autoria
    c4_audit.nota = 200    ← conectivos variados, coesão funcional
    c5_audit.elements_count = 5 → nota = 200

Padrão demonstrado: nota alta em C2-C5 **não** puxa C1 para cima. Contagem
de 11 desvios → PDF nota 1 (40). Não estime "sofrimento leve" → "dou 80"; a
rubrica é numérica.

### Exemplo 2 — C2 com repertório falso + abordagem completa → nota 3 (120)

ENTRADA contém:
- *"Einstein já dizia que 'a tecnologia superou nossa humanidade'"* (apócrifo)
- *"Segundo pesquisas recentes..."* (sem fonte)
- *"artigo 5º da Constituição... proteção à infância"* (artigo errado — é 227)
- *"Filósofos antigos já discutiam..."* (menção vaga)

SAÍDA esperada (trechos-chave):

    c2_audit.repertoire_references = [
      { quote: "Einstein já dizia...", legitimacy: "false_attribution", ... },
      { quote: "Segundo pesquisas recentes...", legitimacy: "not_legitimated", ... },
      { quote: "artigo 5º... proteção à infância", legitimacy: "false_attribution",
        legitimacy_reason: "art. 5º trata de garantias gerais; proteção à infância está no 227." },
      { quote: "Filósofos antigos...", legitimacy: "not_legitimated", ... },
    ]
    c2_audit.has_reference_in_d1 = true
    c2_audit.has_reference_in_d2 = true
    c2_audit.tres_partes_completas = true
    c2_audit.nota = 120    ← PDF nota 3: "abordagem completa + repertório
                             não legitimado/não pertinente" ENQUADRA.

Padrão demonstrado: repertório não-verificado NÃO é nota 2 automaticamente.
Com abordagem completa e 3 partes, o PDF manda nota 3 (120). Apontar as 4
ocorrências individualmente no feedback.

### Exemplo 3 — Tangenciamento sutil (texto sobre "tecnologia" quando tema é "redes sociais") → C2 = 40

ENTRADA: texto que diz *"a tecnologia digital ocupa lugar central"*, *"os ambientes
digitais consolidaram uma cultura de comparação permanente"*, *"sistemas algorítmicos"*,
*"plataformas contemporâneas"*, *"problemas emocionais entre as novas gerações"*. Nenhum
parágrafo usa literalmente "redes sociais" nem "saúde mental". Menciona *"O Dilema das
Redes"* (nome de filme) e *"art. 227 da Constituição sobre proteção à infância"*.

SAÍDA esperada:

    c2_audit.theme_keywords_by_paragraph = [
      { paragraph_index: 1, keywords_found: [], synonyms_found: ["tecnologia", "novas gerações"], majority_keywords_present: false },
      { paragraph_index: 2, keywords_found: [], synonyms_found: ["ambientes digitais", "plataformas", "adolescentes"], majority_keywords_present: false },
      { paragraph_index: 3, keywords_found: [], synonyms_found: ["sistemas algorítmicos", "usuário"], majority_keywords_present: false },
      { paragraph_index: 4, keywords_found: [], synonyms_found: ["plataformas digitais", "menores"], majority_keywords_present: false },
    ]
    c2_audit.tangenciamento_detected = true
    c2_audit.fuga_total_detected = false
    c2_audit.nota = 40           ← REGRA MECÂNICA: tangenciamento → C2 ≤ 40

Padrão demonstrado:
- *"O Dilema das Redes"* é nome próprio de obra. Contém "Redes" mas NÃO é
  menção ao tema — é título de filme. NÃO conta como palavra-chave.
- *"art. 227 sobre proteção à infância"* é repertório jurídico, não discussão
  do tema. NÃO conta como palavra-chave.
- Sinônimos aceitos seriam *"mídias sociais"*, *"Instagram"*, *"TikTok"*,
  *"bem-estar psíquico"*, *"ansiedade"*, *"adolescentes brasileiros"*.
- *"tecnologia"*, *"ambientes digitais"*, *"sistemas algorítmicos"*,
  *"plataformas contemporâneas"*, *"novas gerações"* são **generalizações
  temáticas**, não sinônimos diretos. Nenhum parágrafo tem a maioria das
  palavras-chave → tangenciamento → C2 = 40 pelo PDF.

C3 pode ficar em 160 (texto bem organizado, só que sobre outro tema).
C1, C4, C5 avaliam normalmente (um texto pode ser impecável gramaticalmente
e ter uma boa proposta mesmo tangenciando o tema).

### Exemplo 4 — Texto IMPECÁVEL (controle) → 1000/1000, sem inventar defeitos

ENTRADA: texto com introdução posicionada ("o uso massivo compromete a saúde
mental"), 2 eixos desenvolvidos com repertório legitimado em D1 (Han, Bauman,
OMS) e D2 (O Dilema das Redes, art. 227), conectivos variados, proposta com
5 elementos detalhados. 0-1 desvios pontuais (nunca reincidentes).

SAÍDA esperada:

    c1_audit.desvios_gramaticais_count = 0 ou 1
    c1_audit.erros_ortograficos_count = 0 ou 1
    c1_audit.desvios_crase_count = 0
    c1_audit.falhas_estrutura_sintatica_count = 0
    c1_audit.marcas_oralidade = []
    c1_audit.threshold_check.applies_nota_5 = true    ← REGRA: 0-1 desvios → nota 5
    c1_audit.threshold_check.applies_nota_4 = false
    c1_audit.nota = 200

    c2_audit.tangenciamento_detected = false
    c2_audit.tres_partes_completas = true
    c2_audit.has_reference_in_d1 = true
    c2_audit.has_reference_in_d2 = true
    c2_audit.has_false_attribution = false
    c2_audit.repertoire_references = [ ≥3 itens legitimated + productive ]
    c2_audit.nota = 200

    c3_audit.has_explicit_thesis = true         ← posição argumentativa clara
    c3_audit.ponto_de_vista_claro = true
    c3_audit.ideias_progressivas = true
    c3_audit.planejamento_evidente = true
    c3_audit.autoria_markers = [≥2 trechos com análise autoral]
    c3_audit.conclusion_retakes_thesis = true
    c3_audit.argumentos_contraditorios = false
    c3_audit.limitado_aos_motivadores = false
    c3_audit.nota = 200

    c4_audit.connector_variety_count = ≥5
    c4_audit.most_used_connector_count = ≤2
    c4_audit.has_mechanical_repetition = false
    c4_audit.complex_periods_well_structured = true
    c4_audit.nota = 200

    c5_audit.elements_present = { agente, acao, modo_meio, finalidade, detalhamento TODOS com present=true e quote literal }
    c5_audit.elements_count = 5
    c5_audit.proposta_articulada_ao_tema = true
    c5_audit.nota = 200

    meta_checks.total_calculated = 1000
    feedback_text = "Redação exemplar..." (sem "poderia melhorar" obrigatório)

Padrão demonstrado: quando o texto é impecável em cada competência, **marque
200**. Não penalize em 180 "por rigor" — isso é criticismo obrigatório, não
calibração. O PDF reserva rigor para texto com defeitos reais.

### Exemplo 5 — C5 com 4 elementos genéricos mal articulados → nota 3 (120)

ENTRADA (P4): *"É necessário que o governo tome providências sobre o assunto,
criando políticas públicas eficientes para combater esse problema que afeta
tantos jovens. A sociedade também deve se conscientizar e as famílias precisam
acompanhar de perto o uso que seus filhos fazem das redes sociais. Somente
com a união de todos será possível resolver essa questão de forma adequada,
garantindo um futuro melhor para a juventude brasileira."*

SAÍDA esperada:

    c5_audit.elements_present = {
      agente:       { present: true, quote: "o governo",                    generic: true  },
      acao:         { present: true, quote: "tome providências",            generic: true  },
      modo_meio:    { present: true, quote: "criando políticas públicas",   generic: true  },
      finalidade:   { present: true, quote: "garantindo um futuro melhor", articulated_with_thesis: false },
      detalhamento: { present: false, quote: null, type: "absent" },
    }
    c5_audit.elements_count = 4
    c5_audit.proposta_articulada_ao_tema = false
    c5_audit.nota = 120    ← 4 elementos nominalmente presentes (genéricos) +
                             má articulação ao tema. PDF: contagem (4) → nota 4 (160)
                             mas "proposta mal articulada" puxa para nota 3 (120).

Padrão demonstrado: contar CADA elemento booleanamente primeiro. Marcar
`generic: true` quando o elemento está lá de forma vaga. O nota não é 40
só porque "parece vago" nem 160 porque "tem 4 elementos" — o PDF trata
articulação ao tema como critério que puxa para o nível inferior.
"""


def _competency_feedback_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "resumo": {
                "type": "string",
                "description": "1-2 frases resumindo a avaliação desta competência.",
            },
            "pontos_fortes": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "1-3 aspectos positivos ESTRITAMENTE desta competência. "
                    "Não inclua qualidades de outras competências (ex.: não "
                    "elogie estrutura sintática em C1 — isso é C3/C4)."
                ),
            },
            "pontos_atencao": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "trecho": {
                            "type": "string",
                            "description": "Trecho LITERAL copiado da redação.",
                        },
                        "problema": {
                            "type": "string",
                            "description": "O que está errado ou limitado no trecho.",
                        },
                        "sugestao": {
                            "type": "string",
                            "description": "Como reescrever ou melhorar.",
                        },
                    },
                    "required": ["trecho", "problema", "sugestao"],
                },
                "description": (
                    "Desvios e limites específicos com trecho literal. Em C1, "
                    "liste TODOS os desvios graves identificados (não apenas "
                    "alguns exemplos); cada item em formato errado → correto."
                ),
            },
        },
        "required": ["resumo", "pontos_fortes", "pontos_atencao"],
    }


_NOTA_ENUM = [0, 40, 80, 120, 160, 200]


def _preanulation_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "description": (
            "Checagens pré-correção. Qualquer flag TRUE em should_annul zera "
            "todas as 5 competências."
        ),
        "properties": {
            "fuga_total_ao_tema": {"type": "boolean"},
            "nao_dissertativo_argumentativo": {"type": "boolean"},
            "linhas_proprias_count": {
                "type": "integer",
                "minimum": 0,
                "description": "Linhas de produção própria (cópia de motivadores não conta).",
            },
            "abaixo_de_8_linhas_proprias": {"type": "boolean"},
            "copia_excessiva_sem_producao_propria": {"type": "boolean"},
            "improperios_presentes": {"type": "boolean"},
            "lingua_estrangeira_predominante": {"type": "boolean"},
            "texto_ilegivel": {"type": "boolean"},
            "should_annul": {"type": "boolean"},
            "annul_reason": {"type": ["string", "null"]},
        },
        "required": [
            "fuga_total_ao_tema",
            "nao_dissertativo_argumentativo",
            "linhas_proprias_count",
            "abaixo_de_8_linhas_proprias",
            "copia_excessiva_sem_producao_propria",
            "improperios_presentes",
            "lingua_estrangeira_predominante",
            "texto_ilegivel",
            "should_annul",
        ],
    }


def _c1_audit_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "description": (
            "Auditoria C1 por CONTAGEM NUMÉRICA (PDF). Liste cada desvio "
            "individualmente; a nota é determinada pelos thresholds."
        ),
        "properties": {
            "desvios_gramaticais": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "quote": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": [
                                "concordancia_verbal",
                                "concordancia_nominal",
                                "crase",
                                "regencia",
                                "mau_mal",
                                "ortografia",
                                "acentuacao",
                                "pontuacao",
                                "conjugacao",
                                "colocacao_pronominal",
                            ],
                        },
                        "correction": {"type": "string"},
                    },
                    "required": ["quote", "type", "correction"],
                },
                "description": "Lista EXAUSTIVA de TODOS os desvios. Não resuma.",
            },
            "desvios_gramaticais_count": {"type": "integer", "minimum": 0},
            "erros_ortograficos_count": {"type": "integer", "minimum": 0},
            "desvios_crase_count": {"type": "integer", "minimum": 0},
            "desvios_regencia_count": {"type": "integer", "minimum": 0},
            "falhas_estrutura_sintatica_count": {"type": "integer", "minimum": 0},
            "marcas_oralidade": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Trechos com oralidade/coloquialismo excessivo.",
            },
            "reincidencia_de_erro": {"type": "boolean"},
            "reading_fluency_compromised": {"type": "boolean"},
            "threshold_check": {
                "type": "object",
                "description": (
                    "Checagem booleana contra a TABELA DO PDF. Marque TRUE em "
                    "EXATAMENTE UM dos applies_nota_N (o que enquadra o texto)."
                ),
                "properties": {
                    "applies_nota_5": {
                        "type": "boolean",
                        "description": "≤2 desvios totais, ≤1 ortográfico, ≤1 crase, ≤1 falha sintática.",
                    },
                    "applies_nota_4": {
                        "type": "boolean",
                        "description": "Até 3 gramaticais, até 3 ortográficos, até 2 regência.",
                    },
                    "applies_nota_3": {
                        "type": "boolean",
                        "description": "Até 5 gramaticais, estrutura regular, sentido mantido.",
                    },
                    "applies_nota_2": {
                        "type": "boolean",
                        "description": "Estrutura deficitária OU regular + muitos desvios.",
                    },
                    "applies_nota_1": {
                        "type": "boolean",
                        "description": "Desvios diversificados e frequentes.",
                    },
                    "applies_nota_0": {
                        "type": "boolean",
                        "description": "Desconhecimento sistemático, erros em todas convenções.",
                    },
                },
                "required": [
                    "applies_nota_5",
                    "applies_nota_4",
                    "applies_nota_3",
                    "applies_nota_2",
                    "applies_nota_1",
                    "applies_nota_0",
                ],
            },
            "nota": {"type": "integer", "enum": _NOTA_ENUM},
        },
        "required": [
            "desvios_gramaticais",
            "desvios_gramaticais_count",
            "erros_ortograficos_count",
            "desvios_crase_count",
            "desvios_regencia_count",
            "falhas_estrutura_sintatica_count",
            "marcas_oralidade",
            "reincidencia_de_erro",
            "reading_fluency_compromised",
            "threshold_check",
            "nota",
        ],
    }


def _c2_audit_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "description": (
            "Auditoria C2. Inclui checagem de palavras-chave do tema PARÁGRAFO "
            "POR PARÁGRAFO — força detecção de tangenciamento."
        ),
        "properties": {
            "theme_keywords_by_paragraph": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "paragraph_index": {"type": "integer", "minimum": 1},
                        "keywords_found": {"type": "array", "items": {"type": "string"}},
                        "synonyms_found": {"type": "array", "items": {"type": "string"}},
                        "majority_keywords_present": {"type": "boolean"},
                    },
                    "required": [
                        "paragraph_index",
                        "keywords_found",
                        "majority_keywords_present",
                    ],
                },
            },
            "tangenciamento_detected": {"type": "boolean"},
            "fuga_total_detected": {"type": "boolean"},
            "repertoire_references": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "quote": {"type": "string"},
                        "category": {
                            "type": "string",
                            "enum": [
                                "filosofico",
                                "sociologico",
                                "historico",
                                "juridico",
                                "literario",
                                "cientifico",
                                "cinematografico",
                                "midiatico",
                                "artistico",
                            ],
                        },
                        "source_cited": {"type": "boolean"},
                        "legitimacy": {
                            "type": "string",
                            "enum": ["legitimated", "not_legitimated", "false_attribution"],
                        },
                        "productivity": {
                            "type": "string",
                            "enum": ["productive", "decorative", "copied_from_motivator"],
                        },
                        "paragraph_located": {"type": "integer", "minimum": 1, "maximum": 8},
                        "legitimacy_reason": {"type": "string"},
                    },
                    "required": [
                        "quote",
                        "category",
                        "source_cited",
                        "legitimacy",
                        "productivity",
                        "paragraph_located",
                        "legitimacy_reason",
                    ],
                },
            },
            "has_reference_in_d1": {"type": "boolean"},
            "has_reference_in_d2": {"type": "boolean"},
            "tres_partes_completas": {"type": "boolean"},
            "partes_embrionarias_count": {"type": "integer", "minimum": 0, "maximum": 3},
            "conclusao_com_frase_incompleta": {"type": "boolean"},
            "copia_motivadores_sem_aspas": {"type": "boolean"},
            "nota": {"type": "integer", "enum": _NOTA_ENUM},
        },
        "required": [
            "theme_keywords_by_paragraph",
            "tangenciamento_detected",
            "fuga_total_detected",
            "repertoire_references",
            "has_reference_in_d1",
            "has_reference_in_d2",
            "tres_partes_completas",
            "partes_embrionarias_count",
            "conclusao_com_frase_incompleta",
            "copia_motivadores_sem_aspas",
            "nota",
        ],
    }


def _c3_audit_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "has_explicit_thesis": {"type": "boolean"},
            "thesis_quote": {"type": ["string", "null"]},
            "ponto_de_vista_claro": {"type": "boolean"},
            "ideias_progressivas": {"type": "boolean"},
            "planejamento_evidente": {"type": "boolean"},
            "autoria_markers": {"type": "array", "items": {"type": "string"}},
            "encadeamento_sem_saltos": {"type": "boolean"},
            "saltos_tematicos": {"type": "array", "items": {"type": "string"}},
            "argumentos_contraditorios": {"type": "boolean"},
            "informacoes_irrelevantes_ou_repetidas": {"type": "boolean"},
            "limitado_aos_motivadores": {"type": "boolean"},
            "nota": {"type": "integer", "enum": _NOTA_ENUM},
        },
        "required": [
            "has_explicit_thesis",
            "ponto_de_vista_claro",
            "ideias_progressivas",
            "planejamento_evidente",
            "autoria_markers",
            "encadeamento_sem_saltos",
            "saltos_tematicos",
            "argumentos_contraditorios",
            "informacoes_irrelevantes_ou_repetidas",
            "limitado_aos_motivadores",
            "nota",
        ],
    }


def _c4_audit_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "connectors_used": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "connector": {"type": "string"},
                        "count": {"type": "integer", "minimum": 1},
                        "positions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["connector", "count"],
                },
            },
            "connector_variety_count": {"type": "integer", "minimum": 0},
            "most_used_connector": {"type": "string"},
            "most_used_connector_count": {"type": "integer", "minimum": 0},
            "has_mechanical_repetition": {"type": "boolean"},
            "referential_cohesion_examples": {"type": "array", "items": {"type": "string"}},
            "ambiguous_pronouns": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "quote": {"type": "string"},
                        "issue": {"type": "string"},
                    },
                    "required": ["quote", "issue"],
                },
            },
            "paragraph_transitions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "from_paragraph": {"type": "integer"},
                        "to_paragraph": {"type": "integer"},
                        "quality": {
                            "type": "string",
                            "enum": ["clear", "adequate", "abrupt", "absent"],
                        },
                    },
                    "required": ["from_paragraph", "to_paragraph", "quality"],
                },
            },
            "complex_periods_well_structured": {"type": "boolean"},
            "coloquialism_excessive": {"type": "boolean"},
            "nota": {"type": "integer", "enum": _NOTA_ENUM},
        },
        "required": [
            "connectors_used",
            "connector_variety_count",
            "most_used_connector",
            "most_used_connector_count",
            "has_mechanical_repetition",
            "referential_cohesion_examples",
            "ambiguous_pronouns",
            "paragraph_transitions",
            "complex_periods_well_structured",
            "coloquialism_excessive",
            "nota",
        ],
    }


def _c5_element_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "present": {"type": "boolean"},
            "quote": {"type": ["string", "null"]},
            "generic": {"type": "boolean"},
        },
        "required": ["present", "quote", "generic"],
    }


def _c5_finalidade_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "present": {"type": "boolean"},
            "quote": {"type": ["string", "null"]},
            "articulated_with_thesis": {"type": "boolean"},
        },
        "required": ["present", "quote", "articulated_with_thesis"],
    }


def _c5_detalhamento_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "present": {"type": "boolean"},
            "quote": {"type": ["string", "null"]},
            "type": {
                "type": "string",
                "enum": ["agent", "action", "means", "purpose", "example", "absent"],
            },
        },
        "required": ["present", "type"],
    }


def _c5_audit_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "description": (
            "Auditoria C5 por CONTAGEM DE ELEMENTOS (PDF). Marque cada "
            "booleano de presença antes de fixar a nota."
        ),
        "properties": {
            "elements_present": {
                "type": "object",
                "properties": {
                    "agente": _c5_element_schema(),
                    "acao": _c5_element_schema(),
                    "modo_meio": _c5_element_schema(),
                    "finalidade": _c5_finalidade_schema(),
                    "detalhamento": _c5_detalhamento_schema(),
                },
                "required": [
                    "agente",
                    "acao",
                    "modo_meio",
                    "finalidade",
                    "detalhamento",
                ],
            },
            "elements_count": {
                "type": "integer",
                "minimum": 0,
                "maximum": 5,
                "description": "Soma de elements_present.*.present = 1. Calcule EXPLICITAMENTE.",
            },
            "proposta_articulada_ao_tema": {"type": "boolean"},
            "respeita_direitos_humanos": {"type": "boolean"},
            "nota": {"type": "integer", "enum": _NOTA_ENUM},
        },
        "required": [
            "elements_present",
            "elements_count",
            "proposta_articulada_ao_tema",
            "respeita_direitos_humanos",
            "nota",
        ],
    }


def _priorization_entry_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "target_competency": {
                "type": "string",
                "enum": ["c1", "c2", "c3", "c4", "c5"],
            },
            "expected_gain_min": {"type": "integer", "minimum": 0, "maximum": 200},
            "expected_gain_max": {"type": "integer", "minimum": 0, "maximum": 200},
            "covers_all_identified_issues": {
                "type": "boolean",
                "description": (
                    "true se as ações abaixo cobrem TODAS as ocorrências da "
                    "competência alvo identificadas nos audits acima."
                ),
            },
            "actions": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "description": (
                    "Passos acionáveis. Em C1, liste TODOS os desvios graves "
                    "no formato errado → correto."
                ),
            },
        },
        "required": [
            "target_competency",
            "expected_gain_min",
            "expected_gain_max",
            "covers_all_identified_issues",
            "actions",
        ],
    }


# ──────────────────────────────────────────────────────────────────────
# Helpers pra schema flatten (Opus 4.7 falha em schema profundo da v2 — A/B
# 2026-04-26 mostrou 9/20 outputs vazios. Flatten reduz profundidade de
# nivel 4 (cN_audit.threshold_check.applies_nota_5) pra nivel 3
# (c1_threshold_check.applies_nota_5) movendo cN_audit.X → cN_X no
# top-level. Conteúdo da rubrica + system prompt continuam intactos.)
# ──────────────────────────────────────────────────────────────────────

def _flatten_audit_props(audit_schema: Dict[str, Any], prefix: str) -> Tuple[Dict[str, Any], List[str]]:
    """Achata audit_schema.properties.X em prefix_X. Retorna (props, required)."""
    flat_props: Dict[str, Any] = {}
    flat_required: List[str] = []
    for k, schema in (audit_schema.get("properties") or {}).items():
        flat_props[f"{prefix}_{k}"] = schema
    for r in audit_schema.get("required") or []:
        flat_required.append(f"{prefix}_{r}")
    return flat_props, flat_required


def _unflatten_v2_input(flat: Dict[str, Any]) -> Dict[str, Any]:
    """Converte tool input flat (cN_X) de volta pra estrutura nested
    (cN_audit.X) compatível com _derive_cN_nota e _persist_grading_to_bq."""
    out: Dict[str, Any] = {}
    for k in ("essay_analysis", "preanulation_checks", "meta_checks", "feedback_text"):
        if k in flat:
            out[k] = flat[k]

    for prefix in ("c1", "c2", "c3", "c4", "c5"):
        nested: Dict[str, Any] = {}
        offset = len(prefix) + 1
        for k, v in flat.items():
            if k.startswith(f"{prefix}_"):
                # Evita pegar "priority_*" que tem outro prefixo numérico
                if k.startswith("priority_"):
                    continue
                nested[k[offset:]] = v
        if nested:
            out[f"{prefix}_audit"] = nested

    priorization: Dict[str, Any] = {}
    for n in (1, 2, 3):
        entry: Dict[str, Any] = {}
        sub_prefix = f"priority_{n}_"
        for k, v in flat.items():
            if k.startswith(sub_prefix):
                entry[k[len(sub_prefix):]] = v
        if entry:
            priorization[f"priority_{n}"] = entry
    if priorization:
        out["priorization"] = priorization

    return out


_SUBMIT_CORRECTION_TOOL = {
    "name": "submit_correction",
    "description": (
        "Envia a correção ENEM estruturada (rubrica v2). Avalie preanulation_checks "
        "PRIMEIRO — se should_annul=true, todas as notas vão a 0 e as auditorias "
        "podem ser superficiais. Caso contrário, preencha cada auditoria pela "
        "CONTAGEM NUMÉRICA do PDF, não por estimativa."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "essay_analysis": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "theme_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Palavras-chave do tema identificadas.",
                    },
                    "word_count": {"type": "integer", "minimum": 0},
                    "paragraph_count": {"type": "integer", "minimum": 0},
                    "title_present": {"type": "boolean"},
                    "title_coherent_with_theme": {"type": ["boolean", "null"]},
                },
                "required": ["theme", "theme_keywords", "word_count", "paragraph_count", "title_present"],
            },
            "preanulation_checks": _preanulation_schema(),
            "c1_audit": _c1_audit_schema(),
            "c2_audit": _c2_audit_schema(),
            "c3_audit": _c3_audit_schema(),
            "c4_audit": _c4_audit_schema(),
            "c5_audit": _c5_audit_schema(),
            "priorization": {
                "type": "object",
                "properties": {
                    "priority_1": _priorization_entry_schema(),
                    "priority_2": _priorization_entry_schema(),
                    "priority_3": _priorization_entry_schema(),
                },
                "required": ["priority_1", "priority_2", "priority_3"],
            },
            "meta_checks": {
                "type": "object",
                "properties": {
                    "total_calculated": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 1000,
                    },
                    "total_matches_sum": {"type": "boolean"},
                    "no_competency_bleeding": {
                        "type": "boolean",
                        "description": (
                            "true se nenhuma competência puxou outra indevidamente. "
                            "C1 fraco NÃO rebaixa C2/C3/C4; C3 fraco NÃO rebaixa C2/C4."
                        ),
                    },
                    "preanulation_verified": {"type": "boolean"},
                    "keywords_verified_per_paragraph": {"type": "boolean"},
                    "c5_counted_elements": {"type": "boolean"},
                    "feedback_tone_constructive": {"type": "boolean"},
                },
                "required": [
                    "total_calculated",
                    "total_matches_sum",
                    "no_competency_bleeding",
                    "preanulation_verified",
                    "keywords_verified_per_paragraph",
                    "c5_counted_elements",
                    "feedback_tone_constructive",
                ],
            },
            "feedback_text": {
                "type": "string",
                "description": "Síntese final de 3-5 frases para o aluno, em português brasileiro.",
            },
        },
        "required": [
            "essay_analysis",
            "preanulation_checks",
            "c1_audit",
            "c2_audit",
            "c3_audit",
            "c4_audit",
            "c5_audit",
            "priorization",
            "meta_checks",
            "feedback_text",
        ],
    },
}


def _build_flat_v2_tool() -> Dict[str, Any]:
    """Versão flat do _SUBMIT_CORRECTION_TOOL: cN_audit.X → cN_X no top-level
    + priority_N.X → priority_N_X. Mesma rubrica v2, mesmo conteúdo, só
    estrutura achatada. Output do Claude passa por _unflatten_v2_input
    antes de seguir para derivação/persistência (compatibilidade total)."""
    flat_props: Dict[str, Any] = {}
    flat_required: List[str] = []

    # essay_analysis e preanulation_checks: shallow já, mantém nested
    base_props = _SUBMIT_CORRECTION_TOOL["input_schema"]["properties"]
    flat_props["essay_analysis"] = base_props["essay_analysis"]
    flat_props["preanulation_checks"] = base_props["preanulation_checks"]
    flat_required.extend(["essay_analysis", "preanulation_checks"])

    # cN_audit → cN_*  (corta 1 nível de profundidade)
    audit_builders = {
        "c1": _c1_audit_schema, "c2": _c2_audit_schema,
        "c3": _c3_audit_schema, "c4": _c4_audit_schema,
        "c5": _c5_audit_schema,
    }
    for prefix, builder in audit_builders.items():
        props, req = _flatten_audit_props(builder(), prefix)
        flat_props.update(props)
        flat_required.extend(req)

    # priorization.priority_N → priority_N_*
    pe = _priorization_entry_schema()
    for n in (1, 2, 3):
        props, req = _flatten_audit_props(pe, f"priority_{n}")
        flat_props.update(props)
        flat_required.extend(req)

    # meta_checks: shallow (apenas booleans + 1 int), mantém nested
    flat_props["meta_checks"] = base_props["meta_checks"]
    flat_props["feedback_text"] = base_props["feedback_text"]
    flat_required.extend(["meta_checks", "feedback_text"])

    return {
        "name": "submit_correction_flat",
        "description": (
            "Envia a correção ENEM estruturada (rubrica v2 — conteúdo idêntico, "
            "estrutura ACHATADA). cN_audit.X virou cN_X no top-level "
            "(c1_desvios_gramaticais, c1_threshold_check, c1_nota, etc.). "
            "Mesmas regras de gradação, mesma calibração da Seção 6. "
            "Avalie preanulation_checks PRIMEIRO — se should_annul=true, "
            "todas as notas vão a 0."
        ),
        "input_schema": {
            "type": "object",
            "properties": flat_props,
            "required": flat_required,
        },
    }


_SUBMIT_CORRECTION_FLAT_TOOL = _build_flat_v2_tool()


# V3 holística — schema simples: audit_prose + notas + flags + evidencias.
# Sem cN_audit, sem threshold_check, sem contagens. Notas vêm direto do
# juízo qualitativo do LLM. Mecanismo de auto-consistência é a flag set
# + audit_prose com quote literal por evidência.
_NOTA_ENUM = [0, 40, 80, 120, 160, 200]
_ANULACAO_ENUM = [
    "fuga_total",
    "nao_atende_tipo",
    "extensao_insuficiente",
    "improperio",
    "parte_desconectada",
    "lingua_estrangeira",
    "ilegivel",
]
_V3_FLAG_KEYS = [
    "tangenciamento",
    "copia_motivadores_recorrente",
    "repertorio_de_bolso",
    "argumentacao_previsivel",
    "limitacao_aos_motivadores",
    "proposta_vaga_ou_constatatoria",
    "proposta_desarticulada",
    "desrespeito_direitos_humanos",
]
_V3_EVID_ITEM = {
    "type": "object",
    "properties": {
        "trecho": {"type": "string", "description": "Quote literal do texto."},
        "categoria": {"type": "string"},
        "comentario": {"type": "string"},
    },
    "required": ["trecho", "comentario"],
}
_SUBMIT_CORRECTION_V3_TOOL = {
    "name": "submit_correction_v3",
    "description": (
        "Submete avaliação holística da redação ENEM segundo a rubrica v3. "
        "Atribua notas qualitativamente (sem contagem aritmética); use as "
        "flags para sinalizar disparadores de rebaixamento; preencha "
        "evidencias com quotes literais; redija audit_prose em voz de "
        "banca operativa (400-800 palavras)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "audit_prose": {
                "type": "string",
                "description": (
                    "Audit em prosa, 400-800 palavras, voz de banca INEP. "
                    "Cite trechos literais entre aspas como evidência. "
                    "Estruture por competência, na ordem de saliência."
                ),
            },
            "notas": {
                "type": "object",
                "properties": {
                    "c1": {"type": "integer", "enum": _NOTA_ENUM},
                    "c2": {"type": "integer", "enum": _NOTA_ENUM},
                    "c3": {"type": "integer", "enum": _NOTA_ENUM},
                    "c4": {"type": "integer", "enum": _NOTA_ENUM},
                    "c5": {"type": "integer", "enum": _NOTA_ENUM},
                },
                "required": ["c1", "c2", "c3", "c4", "c5"],
            },
            "flags": {
                "type": "object",
                "properties": {
                    "anulacao": {
                        "type": ["string", "null"],
                        "enum": _ANULACAO_ENUM + [None],
                        "description": (
                            "Se redação for anulada, especificar motivo; "
                            "caso contrário, null."
                        ),
                    },
                    **{k: {"type": "boolean"} for k in _V3_FLAG_KEYS},
                },
                "required": ["anulacao"] + _V3_FLAG_KEYS,
            },
            "evidencias": {
                "type": "object",
                "properties": {
                    "c1": {"type": "array", "items": _V3_EVID_ITEM},
                    "c2": {"type": "array", "items": _V3_EVID_ITEM},
                    "c3": {"type": "array", "items": _V3_EVID_ITEM},
                    "c4": {"type": "array", "items": _V3_EVID_ITEM},
                    "c5": {"type": "array", "items": _V3_EVID_ITEM},
                },
            },
        },
        "required": ["audit_prose", "notas", "flags", "evidencias"],
    },
}


# Map between canonical Redato keys (c1..c5) and the BigQuery competency UUIDs.
_REDATO_KEY_TO_UUID = {
    "c1": "d7d30def-7f7f-4cc4-ae92-b41228a9855e",  # Domínio da Norma Culta
    "c2": "a7c812b2-fefd-4757-8774-e08bcdba82cc",  # Compreensão do Tema
    "c3": "3334fd6a-adf0-4c43-8e83-630270c17f86",  # Seleção e Organização
    "c4": "5467abb2-bd17-44be-90bd-a5065d1e6ee0",  # Mecanismos Linguísticos
    "c5": "fd207ce5-b400-475b-a136-ce9c4d5cd00d",  # Proposta de Intervenção
}


def _merge_ensemble_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Combine N audit runs into one via majority vote for booleans, median for
    counts, union (deduped) for lists of items. Used for `REDATO_ENSEMBLE` mode.
    """
    if not results:
        return {}
    if len(results) == 1:
        return results[0]

    import statistics

    def _is_placeholder(r: Dict[str, Any]) -> bool:
        """Detect Opus-style placeholder like {'$PARAMETER_NAME': ...}."""
        keys = list(r.keys()) if isinstance(r, dict) else []
        return any(k.startswith("$") for k in keys)

    valid = [r for r in results if isinstance(r, dict) and not _is_placeholder(r) and r]
    if not valid:
        # All runs returned placeholders — return first and let caller handle.
        return results[0]
    if len(valid) == 1:
        return valid[0]

    def _majority_bool(values: List[Any]) -> Optional[bool]:
        bool_vals = [bool(v) for v in values if v is not None]
        if not bool_vals:
            return None
        trues = sum(bool_vals)
        return trues > (len(bool_vals) / 2)

    def _median_int(values: List[Any]) -> Optional[int]:
        nums = [int(v) for v in values if isinstance(v, (int, float))]
        if not nums:
            return None
        return int(statistics.median(nums))

    def _merge_lists_of_dicts(lists: List[List[Any]], dedup_key: str = "quote") -> List[Dict[str, Any]]:
        """Union lists of dicts, deduping on dedup_key."""
        merged: Dict[str, Dict[str, Any]] = {}
        order: List[str] = []
        for lst in lists:
            if not isinstance(lst, list):
                continue
            for item in lst:
                if not isinstance(item, dict):
                    continue
                key = str(item.get(dedup_key, "")).strip().lower()
                if not key or key in merged:
                    continue
                merged[key] = item
                order.append(key)
        return [merged[k] for k in order]

    def _merge_value(values: List[Any]) -> Any:
        non_none = [v for v in values if v is not None]
        if not non_none:
            return None
        # All bools → majority vote
        if all(isinstance(v, bool) for v in non_none):
            return _majority_bool(non_none)
        # All numbers → median
        if all(isinstance(v, (int, float)) for v in non_none) and not any(
            isinstance(v, bool) for v in non_none
        ):
            return _median_int(non_none)
        # All strings → take the first non-empty
        if all(isinstance(v, str) for v in non_none):
            for v in non_none:
                if v.strip():
                    return v
            return non_none[0]
        # All lists of dicts → union
        if all(isinstance(v, list) for v in non_none):
            if all(
                all(isinstance(i, dict) for i in v) for v in non_none if v
            ):
                return _merge_lists_of_dicts(non_none)
            # List of strings → union preserving order
            merged_list: List[str] = []
            seen = set()
            for v in non_none:
                for item in v:
                    key = str(item)
                    if key not in seen:
                        merged_list.append(item)
                        seen.add(key)
            return merged_list
        # All dicts → recurse
        if all(isinstance(v, dict) for v in non_none):
            return _merge_dicts(non_none)
        # Fallback: first value.
        return non_none[0]

    def _merge_dicts(dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
        all_keys: List[str] = []
        seen = set()
        for d in dicts:
            for k in d:
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)
        out: Dict[str, Any] = {}
        for k in all_keys:
            values = [d.get(k) for d in dicts if isinstance(d, dict)]
            out[k] = _merge_value(values)
        return out

    merged = _merge_dicts(valid)

    # Tarefa 11: anexa metadata de confidence com base nas notas brutas do
    # audit de cada run individual (antes da derivação mecânica em
    # `_claude_grade_essay`). Mede variância da própria LLM entre runs.
    if len(valid) >= 2:
        from redato_backend.ensemble.confidence import calculate_confidence

        per_run_notas: List[Dict[str, Any]] = []
        for run in valid:
            notas: Dict[str, int] = {}
            for key in ("c1", "c2", "c3", "c4", "c5"):
                audit = run.get(f"{key}_audit") or {}
                nota = audit.get("nota") if isinstance(audit, dict) else None
                notas[key] = int(nota) if isinstance(nota, (int, float)) else 0
            notas["total"] = sum(notas[k] for k in ("c1", "c2", "c3", "c4", "c5"))
            per_run_notas.append({"notas": notas})

        merged["_confidence"] = calculate_confidence(per_run_notas).to_dict()

    return merged


def _call_claude_once(client, model: str, user_msg: str) -> Dict[str, Any]:
    """Single call — extracted so ensemble can parallelize."""
    return _call_claude_with_tool_inner(client, model, user_msg)


def _call_claude_with_tool(client, model: str, user_msg: str) -> Dict[str, Any]:
    """Main entry: single call or ensemble based on REDATO_ENSEMBLE env var."""
    import os
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        ensemble_n = max(1, int(os.getenv("REDATO_ENSEMBLE", "1") or "1"))
    except ValueError:
        ensemble_n = 1

    if ensemble_n == 1:
        return _call_claude_with_tool_inner(client, model, user_msg)

    print(f"[dev_offline] running ensemble n={ensemble_n} (majority vote)")
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=ensemble_n) as ex:
        futures = [
            ex.submit(_call_claude_with_tool_inner, client, model, user_msg)
            for _ in range(ensemble_n)
        ]
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except Exception as exc:
                print(f"[dev_offline] ensemble run failed: {exc!r}")
    return _merge_ensemble_results(results)


def _log_cache_metrics(stage: str, model: str, message: Any) -> None:
    """Loga métricas de prompt cache da resposta da Anthropic.

    Sem PII — só contadores de tokens e ratios. ``stage`` é ``grade`` ou
    ``critique``. Usa ``getattr`` com default 0 para não quebrar quando o SDK
    ainda não expõe os campos de cache.
    """
    usage = getattr(message, "usage", None)
    if usage is None:
        return
    cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    total_cached = cache_creation + cache_read
    hit_ratio = (cache_read / total_cached) if total_cached else 0.0
    print(
        f"[dev_offline] cache[{stage}] model={model} "
        f"create={cache_creation} read={cache_read} "
        f"input={input_tokens} output={output_tokens} "
        f"hit_ratio={hit_ratio:.2f}"
    )


def _call_claude_with_tool_inner(client, model: str, user_msg: str) -> Dict[str, Any]:
    """Run the grading call with prompt caching + forced tool_use, return the tool args.

    When ``REDATO_EXTENDED_THINKING=1`` is set, Claude thinks before emitting
    the tool call. This improves calibration on ambiguous cases (especially
    C5 aposition rules and C3 tese edge cases) at the cost of ~15-30s per
    grading. Worth enabling for simulados and production grading; not for
    quick iterations in dev.
    """
    import os

    rubrica = os.getenv("REDATO_RUBRICA", "v2")

    if rubrica == "v3":
        # Path holístico: prompt v3 isolado (sem few-shots da v2 nem grading tail
        # mecânico), tool schema simples (notas/flags/evidencias/audit_prose).
        kwargs: Dict[str, Any] = dict(
            model=model,
            max_tokens=8000,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT_V3,
                    # Único bloco cacheado (system v3 ~30k chars com persona +
                    # system_prompt_v3 + rubrica_v3 anexada).
                    "cache_control": {"type": "ephemeral", "ttl": "1h"},
                },
            ],
            tools=[_SUBMIT_CORRECTION_V3_TOOL],
            tool_choice={"type": "tool", "name": "submit_correction_v3"},
            messages=[{"role": "user", "content": user_msg}],
        )
        message = client.messages.create(**kwargs)
        _log_cache_metrics("grade-v3", model, message)
        for block in message.content:
            btype = getattr(block, "type", None)
            if btype == "tool_use" and getattr(block, "name", None) == "submit_correction_v3":
                out = dict(getattr(block, "input", {}) or {})
                out["_rubrica"] = "v3"
                return out
        raise RuntimeError(
            "Claude did not invoke submit_correction_v3. Response blocks: "
            + ", ".join(str(getattr(b, "type", "?")) for b in message.content)
        )

    # Path v2 — schema nested (default) ou flat (REDATO_SCHEMA_FLAT=1).
    # Flat reduce profundidade pra Opus 4.7 conseguir completar tool_use
    # em schemas que nested produzem 45% de outputs vazios.
    schema_flat = os.getenv("REDATO_SCHEMA_FLAT", "0") == "1"
    if schema_flat:
        tool = _SUBMIT_CORRECTION_FLAT_TOOL
        tool_name = "submit_correction_flat"
    else:
        tool = _SUBMIT_CORRECTION_TOOL
        tool_name = "submit_correction"

    kwargs: Dict[str, Any] = dict(
        model=model,
        max_tokens=8000,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT_BASE,
            },
            {
                "type": "text",
                "text": _FEW_SHOT_EXAMPLES,
                # Cache breakpoint #1: cobre base + fewshots (~40k chars).
                # TTL 1h em vez do default 5min — aulas duram 50min, simulado pode
                # passar de 1h. Custo de cache write 2× (vs 1.25× sem TTL),
                # compensa em rajadas longas.
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            },
            {
                "type": "text",
                "text": _GRADING_TAIL_INSTRUCTION,
                # Cache breakpoint #2: estende para incluir as regras de derivação
                # mecânica + checklist (~2-3k chars adicionais, também estável).
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            },
        ],
        tools=[tool],
        messages=[{"role": "user", "content": user_msg}],
    )

    if os.getenv("REDATO_EXTENDED_THINKING") == "1":
        # Thinking is incompatible with forcing a specific tool via tool_choice,
        # so we rely on the system/user instructions to get the tool call.
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": 4000}
    else:
        kwargs["tool_choice"] = {"type": "tool", "name": tool_name}

    message = client.messages.create(**kwargs)
    _log_cache_metrics("grade-flat" if schema_flat else "grade", model, message)

    for block in message.content:
        btype = getattr(block, "type", None)
        if btype == "tool_use" and getattr(block, "name", None) == tool_name:
            tool_input = dict(getattr(block, "input", {}) or {})
            # Flat → nested: derivação mecânica e _persist_grading_to_bq
            # esperam estrutura cN_audit. Conversão é pura forma; conteúdo
            # idêntico.
            if schema_flat:
                tool_input = _unflatten_v2_input(tool_input)
            return tool_input

    raise RuntimeError(
        f"Claude did not invoke {tool_name}. Response blocks: "
        + ", ".join(str(getattr(b, "type", "?")) for b in message.content)
    )


def _claude_grade_essay(data: Dict[str, Any]) -> Dict[str, Any]:
    """Grade the essay using the real Claude API + audit-first schema.

    Returns the full ``tool_args`` dict from Claude (the audit output) so
    callers like the calibration eval script can inspect the raw reasoning.
    """
    import os

    # Imports `shared.constants`/`shared.utils` movidos pra dentro dos
    # helpers que efetivamente usam (`_persist_grading_to_bq`). Imports
    # no topo de `_claude_grade_essay` puxavam `shared.utils` →
    # `shared.bigquery` → `from google.cloud import bigquery`, que
    # quebra em prod Railway (google-cloud-bigquery não está em
    # requirements.txt — apply_patches() só intercepta com
    # REDATO_DEV_OFFLINE=1, e prod tem REDATO_DEV_OFFLINE=0).
    # Bug pré-existente que ninguém pegou porque OF14 nunca foi
    # cadastrada em turma 1S ativa antes de 30/04/2026.
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError(
            "Anthropic SDK not installed. Add `anthropic` to requirements-dev.txt "
            "or unset ANTHROPIC_API_KEY to use the deterministic stub."
        ) from e

    essay_id = data["request_id"]
    content = (data.get("content") or "").strip()
    theme = (data.get("theme") or "").strip() or "Tema livre"
    user_id = data.get("user_id")
    activity_id = data.get("activity_id")

    # Roteamento REJ 1S: missões Foco e Completo Parcial usam pipelines
    # próprios em redato_backend.missions. Modo Completo Integral (OF14)
    # cai no fluxo v2 padrão abaixo, mas com preâmbulo REJ no user_msg.
    # Spec: docs/redato/v3/redato_1S_criterios.md.
    from redato_backend.missions import (
        MissionMode, resolve_mode, grade_mission,
    )
    from redato_backend.missions.prompts import (
        OF14_REJ_PREAMBLE, feedback_aluno_registro_block,
    )

    _mission_mode = resolve_mode(activity_id)
    if _mission_mode is not None and _mission_mode != MissionMode.COMPLETO_INTEGRAL:
        return grade_mission(data)

    # OF14 (completo_integral) usa GPT-FT BTBOS5VF como backend padrão desde
    # 2026-04-30 (commit feat(of14)). Decisão baseada em:
    #   - A/B 30/abr (commit 174ceab): FT 21.5% ±40 vs Sonnet 19.3%
    #   - Experimento prompt-enriched (commit 6080d4d): FT 28.5% ±40,
    #     100% parse_ok, $0.05/redação, 13.8s latência
    #   - Investigação MIGRATION_FT_OF14_AUDIT.md: gap = 0 campos ativos
    #     perdidos (frontend prod só consome cN_audit.nota)
    # Rollback rápido: REDATO_OF14_BACKEND=claude (1 env var, sem deploy).
    # Fallback automático: se FT falha (timeout, key missing, parser),
    # cai pro Claude path abaixo (graceful degradation).
    if (
        _mission_mode == MissionMode.COMPLETO_INTEGRAL
        and os.getenv("REDATO_OF14_BACKEND", "ft") == "ft"
    ):
        try:
            from redato_backend.missions.openai_ft_grader import (
                grade_of14_with_ft,
            )
            tool_args = grade_of14_with_ft(content=content, theme=theme)
            logger.info(
                "OF14 graded via FT BTBOS5VF (request_id=%s)", essay_id,
            )
            # _persist_grading_to_bq é defensive contra schema parcial
            # (_dict_or_empty em campos faltantes — priorization,
            # preanulation_checks, etc. não vêm do FT).
            _persist_grading_to_bq(
                tool_args=tool_args,
                essay_id=essay_id,
                user_id=user_id,
                content=content,
                activity_id=data.get("activity_id"),
            )
            try:
                from redato_backend.shared.job_tracker import EssayJobTracker
                tracker = EssayJobTracker()
                tracker._collection.document(essay_id).set(  # type: ignore[union-attr]
                    {"raw_audit": tool_args, "updated_at": datetime.now(timezone.utc)},
                    merge=True,
                )
            except (ImportError, ModuleNotFoundError) as exc:
                # google-cloud-firestore não instalado em Railway prod.
                # Esperado quando REDATO_DEV_OFFLINE=0; warning concise
                # pra não inundar logs (cada OF14 passaria por aqui).
                logger.warning(
                    "Firestore stash skipped for %s — google-cloud "
                    "unavailable (%s)", essay_id, exc,
                )
            except Exception:  # noqa: BLE001
                # Erro inesperado — stack completo (1º incidente prod
                # 01/05 mostrou que print(exc!r) silencia detalhes).
                logger.exception(
                    "could not stash raw_audit for %s", essay_id,
                )
            return tool_args
        except Exception:  # noqa: BLE001
            # Mantém literal "falling back to Claude" pro
            # test_dev_offline_tem_roteamento_of14_ft_com_rollback
            # detectar refactors que removem o fallback.
            logger.exception(
                "OF14 FT path failed for %s — falling back to Claude "
                "Sonnet 4.6 v2 (graceful degradation; set "
                "REDATO_OF14_BACKEND=claude to silence this fallback)",
                essay_id,
            )
            # Cai pro Claude path abaixo.

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.getenv("REDATO_CLAUDE_MODEL", "claude-sonnet-4-6")

    rej_preamble = (
        f"{OF14_REJ_PREAMBLE}\n---\n\n"
        if _mission_mode == MissionMode.COMPLETO_INTEGRAL
        else ""
    )

    # Calibração 2026-04-29: guideline central do registro de
    # feedback_aluno injetada em todos os modos. OF14 (pipeline v2)
    # também herda — schema v2 inclui `feedback_aluno` então a
    # guideline se aplica idêntica aos outros modos.
    registro_block = feedback_aluno_registro_block()

    user_msg = (
        f"{rej_preamble}"
        f"{registro_block}\n\n"
        f"---\n\n"
        f"TEMA: {theme}\n\n"
        f"REDAÇÃO DO ALUNO:\n\"\"\"\n{content}\n\"\"\"\n\n"
        "Avalie a redação acima pelas 5 competências ENEM, aplicando a "
        "calibração da Seção 6 (incluindo os adendos 6.5.1 C5 e 6.5.2 C1). "
        "Chame `submit_correction` preenchendo TODOS os campos de auditoria."
    )

    # Tarefa 9: pré-flag mecânico de repetição lexical. A/B 2026-04-25
    # (110 runs) mostrou REVERT — addendum infla C4 em textos onde a
    # repetição é só palavra-chave do tema (control_nota_1000, c5_three_elements,
    # c5_two_elements_only regrediram 1.00 → 0.00). Detector está promíscuo:
    # dispara em qualquer texto de 350+ palavras. Default OFF; setar
    # REDATO_REPETITION_FLAG=1 só pra reproduzir o experimento.
    # Resultados: scripts/ab_tests/results/repetition_ab_20260425_170025.json
    if os.getenv("REDATO_REPETITION_FLAG", "0") == "1":
        from redato_backend.audits.lexical_repetition_detector import (
            maybe_inject_repetition_addendum,
        )
        user_msg = maybe_inject_repetition_addendum(user_msg, content)

    tool_args = _call_claude_with_tool(client, model, user_msg)
    # _confidence é anexado por _merge_ensemble_results e precisa sobreviver
    # ao self-critique, que devolve um dict limpo da chamada de revisão.
    confidence_metadata = tool_args.get("_confidence") if isinstance(tool_args, dict) else None

    rubrica = os.getenv("REDATO_RUBRICA", "v2")
    is_v3 = rubrica == "v3"

    # V3 não passa por self-critique (rubrica holística não é compatível
    # com revisão estruturada do v2) nem por derivação mecânica (notas vêm
    # direto do juízo qualitativo do LLM em tool_args["notas"]).
    if not is_v3 and os.getenv("REDATO_SELF_CRITIQUE") == "1":
        tool_args = _run_self_critique(client, model, user_msg, tool_args)
        if confidence_metadata is not None and isinstance(tool_args, dict):
            tool_args["_confidence"] = confidence_metadata

    if not is_v3 and os.getenv("REDATO_TWO_STAGE", "1") != "0":
        derived = _derive_notas_mechanically(tool_args)
        for key in ("c1", "c2", "c3", "c4", "c5"):
            audit = tool_args.get(f"{key}_audit")
            if isinstance(audit, dict):
                old_nota = audit.get("nota")
                audit["nota"] = derived[key]
                if old_nota != derived[key]:
                    print(
                        f"[dev_offline] {key}: LLM said {old_nota}, mechanical={derived[key]}"
                    )

    # Persistência BQ é otimizada pra schema v2 (cN_audit, etc). V3 não tem
    # esses campos — pula persistência. Output do eval ainda persiste no
    # JSONL via run_validation_eval.py, suficiente pra análise.
    if not is_v3:
        _persist_grading_to_bq(
            tool_args=tool_args,
            essay_id=essay_id,
            user_id=user_id,
            content=content,
            activity_id=data.get("activity_id"),
        )

    # Store the raw audit in the Firestore job so the calibration eval and
    # debug UIs can fetch it later.
    try:
        from redato_backend.shared.job_tracker import EssayJobTracker
        tracker = EssayJobTracker()
        tracker._collection.document(essay_id).set(  # type: ignore[union-attr]
            {"raw_audit": tool_args, "updated_at": datetime.now(timezone.utc)},
            merge=True,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        # google-cloud-firestore não instalado em Railway prod.
        # Esperado com REDATO_DEV_OFFLINE=0; warning concise.
        logger.warning(
            "Firestore stash skipped for %s — google-cloud unavailable "
            "(%s)", essay_id, exc,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "could not stash raw_audit for %s", essay_id,
        )

    return tool_args


def _persist_grading_to_bq(
    *,
    tool_args: Dict[str, Any],
    essay_id: str,
    user_id: Optional[str],
    content: str,
    activity_id: Optional[str] = None,
) -> None:
    """Project the audit-first tool output into the existing BQ-stub tables.

    Defensive against Claude deviating from the schema — coerces any non-dict
    value to an empty dict rather than crashing the entire grading.

    No-op silencioso em prod Railway sem google-cloud-bigquery instalado.
    `apply_patches()` (REDATO_DEV_OFFLINE=1) registra fakes em
    `sys.modules` que tornam o import abaixo seguro; sem ele, o import
    explode com ModuleNotFoundError. Em vez de derrubar a correção
    inteira, persistir vira no-op + warning. O grading retorna o
    `tool_args` direto pro caller (FT ou Claude), que entrega ao
    aluno via render_aluno_whatsapp.
    """
    try:
        from redato_backend.shared.constants import (
            CORRECTION_REVIEW_TABLE,
            ESSAYS_DETAILED_TABLE,
            ESSAYS_ERRORS_TABLE,
            ESSAYS_GRADED_TABLE,
        )
        from redato_backend.shared.utils import generate_essay_hash
        from redato_backend.routing.correction_router import route_correction
    except (ImportError, ModuleNotFoundError) as exc:
        logger.warning(
            "BQ persist skipped for %s — google-cloud deps unavailable "
            "(%s). Esperado em Railway prod com REDATO_DEV_OFFLINE=0; "
            "a correção segue sem persistir em BQ-stub.",
            essay_id, exc,
        )
        return

    now = datetime.now(timezone.utc).isoformat()

    def _dict_or_empty(x: Any) -> Dict[str, Any]:
        return x if isinstance(x, dict) else {}

    # If preanulation was triggered, all competencies go to 0 regardless
    # of what the per-competency audits say.
    preanul = _dict_or_empty(tool_args.get("preanulation_checks"))
    annulled = bool(preanul.get("should_annul"))

    grades: Dict[str, int] = {}
    audits: Dict[str, Dict[str, Any]] = {}
    for key in ("c1", "c2", "c3", "c4", "c5"):
        audit = _dict_or_empty(tool_args.get(f"{key}_audit"))
        audits[key] = audit
        if annulled:
            grades[key] = 0
        else:
            try:
                grades[key] = _snap_to_inep(int(audit.get("nota", 0) or 0))
            except (TypeError, ValueError):
                grades[key] = 0

    total_sum = sum(grades.values())
    priorization = _dict_or_empty(tool_args.get("priorization"))
    feedback_text = str(tool_args.get("feedback_text") or "").strip()

    # Build the displayed feedback: the free-form synthesis + the 3 priorities
    # so the frontend shows concrete next-steps, not just a paragraph.
    feedback_parts: List[str] = []
    if feedback_text:
        feedback_parts.append(feedback_text)
    priority_lines: List[str] = []
    for idx, key in enumerate(("priority_1", "priority_2", "priority_3"), start=1):
        p = _dict_or_empty(priorization.get(key))
        actions = p.get("actions") or []
        if not actions:
            continue
        target = (p.get("target_competency") or "").upper()
        gain_min = p.get("expected_gain_min")
        gain_max = p.get("expected_gain_max")
        head = f"Prioridade {idx} — {target}"
        if isinstance(gain_min, int) and isinstance(gain_max, int):
            head += f" (ganho potencial: +{gain_min} a +{gain_max} pts)"
        priority_lines.append(head + ":")
        for action in actions[:10]:
            priority_lines.append(f"  • {action}")
    if priority_lines:
        feedback_parts.append("Próximos passos:")
        feedback_parts.extend(priority_lines)
    overall_feedback = "\n".join(feedback_parts).strip() or "(sem síntese)"

    # Tarefa 11: roteamento por confidence. Quando há ensemble (N>=2) e a
    # confiança é baixa (ou média em atividade de alto stake), enfileira pra
    # revisão do professor antes de mostrar ao aluno.
    confidence_metadata = tool_args.get("_confidence") if isinstance(tool_args, dict) else None
    routing = route_correction(
        {"_confidence": confidence_metadata},
        student_id=user_id or "",
        activity_id=activity_id or "",
    )

    with _LOCK:
        _STORE.tables[ESSAYS_GRADED_TABLE].append({
            "essay_id": essay_id,
            "user_id": user_id,
            "activity_id": activity_id,
            "overall_grade": total_sum,
            "graded_at": now,
            "feedback": overall_feedback,
            "hash": generate_essay_hash(content),
            "review_state": routing["state"],
            "visible_to_student": routing["visible_to_student"],
            "confidence_metadata": confidence_metadata,
        })

        if routing["review_record"]:
            _STORE.tables[CORRECTION_REVIEW_TABLE].append({
                "id": f"rev-{essay_id}",
                "correction_id": essay_id,
                "student_id": routing["review_record"]["student_id"],
                "teacher_id": None,
                "activity_id": routing["review_record"]["activity_id"],
                "state": routing["review_record"]["state"],
                "flags": routing["review_record"]["flags"],
                "confidence_level": routing["review_record"]["confidence_level"],
                "teacher_notes": None,
                "created_at": now,
                "reviewed_at": None,
            })

        for key in ("c1", "c2", "c3", "c4", "c5"):
            uuid = _REDATO_KEY_TO_UUID[key]
            justification = _build_competency_justification(key, audits[key])
            _STORE.tables[ESSAYS_DETAILED_TABLE].append({
                "essay_id": essay_id,
                "competency": uuid,
                "detailed_analysis": justification,
                "grade": grades[key],
                "justification": justification,
                "graded_at": now,
            })

            for err_row in _errors_from_audit(key, audits[key]):
                _STORE.tables[ESSAYS_ERRORS_TABLE].append({
                    "essay_id": essay_id,
                    "competency": uuid,
                    "snippet": str(err_row.get("snippet", ""))[:500],
                    "error_type": str(err_row.get("error_type", ""))[:100],
                    "description": str(err_row.get("description", ""))[:1000],
                    "suggestion": str(err_row.get("suggestion", ""))[:1000],
                    "graded_at": now,
                })
        _persist()


def _build_competency_justification(key: str, audit: Dict[str, Any]) -> str:
    """Turn a cN_audit dict (v2) into a human-readable justification string."""
    parts: List[str] = []
    if key == "c1":
        total = audit.get("desvios_gramaticais_count", 0)
        crase = audit.get("desvios_crase_count", 0)
        orto = audit.get("erros_ortograficos_count", 0)
        parts.append(
            f"{total} desvios gramaticais ({crase} de crase, {orto} ortográficos)."
        )
        tc = audit.get("threshold_check") or {}
        active = [k for k, v in tc.items() if v is True]
        if active:
            parts.append(f"Threshold: {active[0]}.")
    elif key == "c2":
        refs = audit.get("repertoire_references") or []
        legit = sum(1 for r in refs if isinstance(r, dict) and r.get("legitimacy") == "legitimated")
        parts.append(f"{len(refs)} referências ({legit} legitimadas).")
        flags = []
        if audit.get("tangenciamento_detected"):
            flags.append("tangenciamento")
        if audit.get("fuga_total_detected"):
            flags.append("fuga ao tema")
        if not audit.get("tres_partes_completas"):
            flags.append(f"{audit.get('partes_embrionarias_count', 0)} partes embrionárias")
        if flags:
            parts.append("Alertas: " + ", ".join(flags) + ".")
    elif key == "c3":
        thesis = "com tese explícita" if audit.get("has_explicit_thesis") else "sem tese clara"
        parts.append(f"Projeto {thesis}.")
        if audit.get("argumentos_contraditorios"):
            parts.append("Argumentos contraditórios.")
        if audit.get("limitado_aos_motivadores"):
            parts.append("Limitado aos motivadores.")
    elif key == "c4":
        variety = audit.get("connector_variety_count", 0)
        top = audit.get("most_used_connector") or ""
        top_count = audit.get("most_used_connector_count") or 0
        parts.append(f"{variety} conectivos distintos; '{top}' {top_count}x.")
        if audit.get("has_mechanical_repetition"):
            parts.append("Repetição mecânica.")
        if audit.get("coloquialism_excessive"):
            parts.append("Coloquialismo excessivo.")
    elif key == "c5":
        count = audit.get("elements_count", 0)
        parts.append(f"{count}/5 elementos presentes.")
        if not audit.get("proposta_articulada_ao_tema"):
            parts.append("Proposta mal articulada ao tema.")
    return " ".join(parts).strip() or "(sem detalhes)"


def _errors_from_audit(key: str, audit: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten the audit's structured findings into error-row dicts (v2 schema)."""
    rows: List[Dict[str, Any]] = []

    def _asdict(x: Any) -> Dict[str, Any]:
        return x if isinstance(x, dict) else {}

    if key == "c1":
        for err in audit.get("desvios_gramaticais") or []:
            err = _asdict(err)
            rows.append({
                "snippet": err.get("quote", ""),
                "error_type": f"C1 / {err.get('type', '')}",
                "description": f"Desvio: {err.get('type', '')}.",
                "suggestion": f"→ {err.get('correction', '')}",
            })
        for marker in audit.get("marcas_oralidade") or []:
            if not isinstance(marker, str):
                continue
            rows.append({
                "snippet": marker,
                "error_type": "C1 / oralidade",
                "description": "Marca de oralidade em texto dissertativo-argumentativo.",
                "suggestion": "Substituir por registro formal.",
            })
    elif key == "c2":
        for ref in audit.get("repertoire_references") or []:
            ref = _asdict(ref)
            legit = ref.get("legitimacy")
            if legit in ("not_legitimated", "false_attribution"):
                rows.append({
                    "snippet": ref.get("quote", ""),
                    "error_type": f"C2 / {legit}",
                    "description": ref.get("legitimacy_reason", ""),
                    "suggestion": "Substituir por repertório verificável.",
                })
    elif key == "c4":
        for amb in audit.get("ambiguous_pronouns") or []:
            amb = _asdict(amb)
            if not amb:
                continue
            rows.append({
                "snippet": amb.get("quote", ""),
                "error_type": "C4 / pronome ambíguo",
                "description": amb.get("issue", ""),
                "suggestion": "Especificar referente ou usar sinônimo.",
            })
        for trans in audit.get("paragraph_transitions") or []:
            trans = _asdict(trans)
            quality = trans.get("quality")
            if quality in ("abrupt", "absent"):
                rows.append({
                    "snippet": f"transição do parágrafo {trans.get('from_paragraph')} para o {trans.get('to_paragraph')}",
                    "error_type": f"C4 / transição {quality}",
                    "description": "Quebra de articulação entre parágrafos.",
                    "suggestion": "Adicionar conectivo ou retomada explícita.",
                })
    elif key == "c5":
        elements = audit.get("elements_present") or {}
        for name in ("agente", "acao", "modo_meio", "finalidade", "detalhamento"):
            elem = _asdict(elements.get(name))
            if not elem.get("present"):
                rows.append({
                    "snippet": name,
                    "error_type": f"C5 / {name} ausente",
                    "description": f"Elemento '{name}' não identificado na proposta.",
                    "suggestion": f"Adicionar {name} à proposta de intervenção.",
                })
            elif elem.get("generic"):
                rows.append({
                    "snippet": str(elem.get("quote", ""))[:200],
                    "error_type": f"C5 / {name} genérico",
                    "description": f"Elemento '{name}' presente mas genérico.",
                    "suggestion": f"Especificar {name} com termos concretos.",
                })
    return rows[:15]


def _snap_to_inep(grade: int) -> int:
    """Round a grade to the nearest valid INEP value (0, 40, 80, 120, 160, 200)."""
    valid = [0, 40, 80, 120, 160, 200]
    return min(valid, key=lambda v: abs(v - grade))


# ---------------------------------------------------------------------------
# Mechanical score derivation (two-stage mode — REDATO_TWO_STAGE=1)
# ---------------------------------------------------------------------------
# The LLM fills the audit (counts, booleans, element presence), Python computes
# the notas by applying the rubric as lookup. Eliminates LLM scoring bias
# (criticism, propagation) because each competency's nota depends ONLY on its
# own audit. Only caveat: if Claude fills the audit wrongly, the nota is wrong
# — but at least the error is isolated and diagnosable via the audit itself.


def _derive_c1_nota(audit: Dict[str, Any]) -> int:
    """C1: threshold_check booleans drive the nota; fall back to count if needed."""
    tc = audit.get("threshold_check") or {}
    if not isinstance(tc, dict):
        tc = {}
    # Apply in order from lowest to highest so we catch the correct nivel.
    if tc.get("applies_nota_0"):
        return 0
    if tc.get("applies_nota_1"):
        return 40
    if tc.get("applies_nota_2"):
        return 80
    if tc.get("applies_nota_3"):
        return 120
    if tc.get("applies_nota_4"):
        return 160
    if tc.get("applies_nota_5"):
        return 200

    # Fallback: derive from raw counts per PDF.
    total = int(audit.get("desvios_gramaticais_count") or 0)
    orto = int(audit.get("erros_ortograficos_count") or 0)
    crase = int(audit.get("desvios_crase_count") or 0)
    marcas = audit.get("marcas_oralidade") or []
    oral_count = len(marcas) if isinstance(marcas, list) else 0

    if total >= 9 or (total >= 6 and oral_count >= 2):
        return 40  # diversificados e frequentes
    if total >= 6:
        return 80
    if total >= 4:
        return 120
    if total >= 3 and orto <= 3 and crase <= 2:
        return 160
    if total <= 2 and orto <= 1 and crase <= 1 and oral_count == 0:
        return 200
    return 120


def _derive_c2_nota(audit: Dict[str, Any]) -> int:
    """C2: tangenciamento/fuga override; repertoire quality drives nota otherwise."""
    if audit.get("fuga_total_detected"):
        return 0
    if audit.get("tangenciamento_detected"):
        return 40

    refs = audit.get("repertoire_references") or []
    if not isinstance(refs, list):
        refs = []

    legit_productive = [
        r for r in refs
        if isinstance(r, dict)
        and r.get("legitimacy") == "legitimated"
        and r.get("productivity") == "productive"
    ]
    has_ref_d1 = bool(audit.get("has_reference_in_d1"))
    has_ref_d2 = bool(audit.get("has_reference_in_d2"))
    tres_completas = bool(audit.get("tres_partes_completas"))
    embrionarias = int(audit.get("partes_embrionarias_count") or 0)
    copia_sem_aspas = bool(audit.get("copia_motivadores_sem_aspas"))
    conclusao_incompleta = bool(audit.get("conclusao_com_frase_incompleta"))
    has_false = bool(audit.get("has_false_attribution"))
    has_unsourced = bool(audit.get("has_unsourced_data"))
    has_wrong_legal = bool(audit.get("has_wrong_legal_article"))

    # PDF nota 2: abordagem completa + problemas de tipo textual / cópia.
    if copia_sem_aspas or conclusao_incompleta or embrionarias >= 2:
        return 80
    # PDF nota 3: abordagem completa + repertório não legitimado / não pertinente.
    if has_false or has_wrong_legal or has_unsourced:
        return 120
    # PDF nota 4: informações pertinentes mas sem aprofundamento / repertório menos produtivo.
    if not has_ref_d1 or not has_ref_d2:
        return 160
    if not tres_completas:
        return 160
    # PDF nota 5: repertório produtivo e legitimado em D1 e D2, abordagem completa.
    nota = 160
    if len(legit_productive) >= 3 and has_ref_d1 and has_ref_d2 and tres_completas:
        nota = 200

    # Cap C2 (INVESTIGATION_baixas 2026-04-27): all-decorative repertoire.
    # Se há ≥2 referências e TODAS marcadas como não-productive (decorativas
    # ou copiadas), cap em 80 mesmo com 3 partes completas. INEP: repertório
    # decorativo não conta como produtivo.
    if len(refs) >= 2:
        productive_refs = [
            r for r in refs
            if isinstance(r, dict) and r.get("productivity") == "productive"
        ]
        if len(productive_refs) == 0:
            return min(nota, 80)

    return nota


def _derive_c3_nota(audit: Dict[str, Any]) -> int:
    """C3: structured scoring. Strong project (thesis + planning + POV) floors at 160."""
    has_thesis = bool(audit.get("has_explicit_thesis"))
    ponto_vista = bool(audit.get("ponto_de_vista_claro"))
    progressivas = bool(audit.get("ideias_progressivas"))
    planejamento = bool(audit.get("planejamento_evidente"))
    autoria = audit.get("autoria_markers") or []
    autoria_count = len(autoria) if isinstance(autoria, list) else 0
    encadeamento = bool(audit.get("encadeamento_sem_saltos"))
    contraditorios = bool(audit.get("argumentos_contraditorios"))
    irrelevantes = bool(audit.get("informacoes_irrelevantes_ou_repetidas"))
    limitado = bool(audit.get("limitado_aos_motivadores"))
    conclusion_retakes = bool(audit.get("conclusion_retakes_thesis"))

    # Nota 2 only with very strong negative pattern.
    if not has_thesis and contraditorios and not ponto_vista:
        return 80
    if not has_thesis and limitado and not progressivas:
        return 80

    # Cap C3 (INVESTIGATION_baixas 2026-04-27): sem tese explícita, cap 120.
    # Sem tese E sem ponto de vista claro → cap 80.
    # INEP exige projeto de texto evidenciando estratégia argumentativa
    # legível; sem tese, "configuração de autoria" não é atendida.
    if not has_thesis:
        if not ponto_vista:
            return 80
        # Mesmo com progressivas+planejamento positivos, sem tese cap em 120.
        return 120

    # --- has_thesis = true below ---

    # Strong-project floor: thesis + planning + clear POV + no contradictions.
    # When these fundamentals are in place, C3 is AT LEAST 160.
    #
    # Note: Claude tends to flag lexical repetition (a C4 problem) as
    # "informações repetidas" in C3, which contaminates the derivation.
    # We use it as a tiebreaker (drops 200→160), not as a hard penalty.
    strong_project = has_thesis and planejamento and ponto_vista and not contraditorios

    if strong_project:
        extras = sum([
            progressivas,
            encadeamento,
            conclusion_retakes,
            autoria_count >= 1,
        ])
        # If Claude flagged multiple secondary issues, demote.
        secondary_issues = sum([irrelevantes, limitado])
        if secondary_issues >= 2:
            return 120  # downgraded heavily
        if extras >= 2 and not irrelevantes:
            return 200
        if extras >= 1:
            return 160
        return 160

    # Weak-project path (thesis present but planning OR POV missing).
    positives = sum([
        progressivas,
        planejamento,
        encadeamento,
        conclusion_retakes,
        autoria_count >= 1,
        ponto_vista,
    ])
    if contraditorios:
        positives = max(positives - 2, 0)
    if irrelevantes:
        positives = max(positives - 1, 0)
    if limitado and autoria_count == 0:
        positives = max(positives - 2, 0)

    if positives >= 5:
        return 200
    if positives >= 3:
        return 160
    if positives >= 1:
        return 120
    return 80


def _derive_c4_nota(audit: Dict[str, Any]) -> int:
    """C4: mechanical repetition penalises; variety + referential cohesion rewards."""
    most_used_count = int(audit.get("most_used_connector_count") or 0)
    variety = int(audit.get("connector_variety_count") or 0)
    mechanical = bool(audit.get("has_mechanical_repetition"))
    complex_periods = bool(audit.get("complex_periods_well_structured"))
    coloquial = bool(audit.get("coloquialism_excessive"))
    ambiguous = audit.get("ambiguous_pronouns") or []
    ambiguous_count = len(ambiguous) if isinstance(ambiguous, list) else 0
    transitions = audit.get("paragraph_transitions") or []
    abrupt_transitions = sum(
        1 for t in transitions
        if isinstance(t, dict) and t.get("quality") in ("abrupt", "absent")
    )

    # Cap C4 (INVESTIGATION_baixas 2026-04-27, ajustado pra ≥3 flags em
    # 2026-04-27 após teste com ≥2 mostrar deflate em 401-799 e 800-940):
    # Conjunto de 3+ problemas estruturais simultâneos → cap 80.
    # Threshold mais conservador pra não punir redações com 2 flags
    # isoladas que o gold INEP ainda considera nota mediana.
    negative_flags = sum([
        mechanical,
        not complex_periods,
        ambiguous_count >= 2,
        most_used_count >= 4,
    ])
    if negative_flags >= 3:
        return 80

    # Mechanical repetition (5+ same connector) = nota 3 direct.
    if mechanical and most_used_count >= 4:
        return 120

    # Severe issues = nota 2.
    if (ambiguous_count >= 4 or abrupt_transitions >= 2 or coloquial):
        return 80

    # Variety + structure = nota 5. Slightly relaxed: accepts up to 3
    # occurrences of the most-used connector (typical of well-written texts).
    if (
        variety >= 5
        and most_used_count <= 3
        and not mechanical
        and ambiguous_count == 0
        and abrupt_transitions == 0
    ):
        return 200

    # Nota 4: good variety with minor flaws (some ambiguity or one abrupt transition).
    if variety >= 4 and most_used_count <= 3 and not mechanical:
        return 160

    # Nota 3: mediana.
    return 120


def _derive_c5_nota(audit: Dict[str, Any]) -> int:
    """C5: element count + articulation + direitos humanos."""
    if not audit.get("respeita_direitos_humanos", True):
        return 0

    # Use the explicit elements_present booleans, not just the count field
    # (Claude sometimes miscalculates the count).
    elems = audit.get("elements_present") or {}
    if not isinstance(elems, dict):
        elems = {}

    def _present(name: str) -> bool:
        elem = elems.get(name)
        return isinstance(elem, dict) and bool(elem.get("present"))

    count = sum(
        _present(n) for n in ("agente", "acao", "modo_meio", "finalidade", "detalhamento")
    )

    articulated = bool(audit.get("proposta_articulada_ao_tema"))

    if count == 5 and articulated:
        return 200
    if count == 5 and not articulated:
        return 160
    if count == 4:
        return 160 if articulated else 120
    if count == 3:
        return 120
    if count == 2:
        return 80
    if count == 1:
        return 40
    return 0


def _derive_notas_mechanically(tool_args: Dict[str, Any]) -> Dict[str, int]:
    """Compute the 5 notas from the audit fields, bypassing Claude's own nota fields.

    Returns a dict {c1, c2, c3, c4, c5}. Used when REDATO_TWO_STAGE=1.
    """
    def _audit(key: str) -> Dict[str, Any]:
        val = tool_args.get(f"{key}_audit")
        return val if isinstance(val, dict) else {}

    return {
        "c1": _derive_c1_nota(_audit("c1")),
        "c2": _derive_c2_nota(_audit("c2")),
        "c3": _derive_c3_nota(_audit("c3")),
        "c4": _derive_c4_nota(_audit("c4")),
        "c5": _derive_c5_nota(_audit("c5")),
    }


_PREVIEW_SYSTEM_PROMPT = (
    "Você é a Redato. Leia a redação e escreva em DUAS frases curtas (total "
    "≤ 180 caracteres) a primeira impressão: 1 ponto forte + 1 alerta. "
    "Responda em português brasileiro, direto, sem introdução, sem "
    "cabeçalho, sem negrito, sem rótulos como 'Primeira impressão:'."
)


_SELF_CRITIQUE_INSTRUCTION = """\
Revisão crítica de calibração.

Abaixo está uma correção já produzida por você para uma redação ENEM. Reavalie-a
aplicando rigorosamente:

- A rubrica das 5 competências (Seção 5 do system prompt).
- A calibração operacional da Seção 6, em especial:
  - 6.1: na dúvida entre dois níveis, vá para o nível superior.
  - 6.5.1: o adendo do detalhamento em C5 — reconheça TODAS as 5 modalidades
    (agente, ação, meio/modo, finalidade articulada à tese, exemplificação).
    NÃO penalize detalhamento que recai sobre a finalidade ou exemplificação.

Se a correção anterior apresentar falsos-negativos (sobretudo em C5, C3), ajuste
as notas e o feedback. Se já estiver bem calibrada, MANTENHA. Em qualquer caso,
chame `submit_correction` com o JSON final revisado.

Critérios de ajuste:
- Se o aluno aplicou detalhamento válido em qualquer uma das 5 modalidades e
  você deu menos de 200 em C5 SEM justificativa pedagógica clara, reavalie.
- Se o aluno construiu autoria com repertório produtivo e você deu 160 em C3
  por "tema previsível", reavalie.
- Se há desvios pontuais não-reincidentes em C1 e você deu 120, reavalie.

Correção anterior a revisar (JSON):
"""


def _run_self_critique(
    client,
    model: str,
    original_user_msg: str,
    initial_tool_args: Dict[str, Any],
) -> Dict[str, Any]:
    """Run a 2nd pass asking Claude to re-check its own grading against the rubric."""
    import json as _json

    critique_msg = (
        original_user_msg
        + "\n\n---\n\n"
        + _SELF_CRITIQUE_INSTRUCTION
        + _json.dumps(initial_tool_args, ensure_ascii=False, indent=2)
    )

    schema_flat = os.getenv("REDATO_SCHEMA_FLAT", "0") == "1"
    if schema_flat:
        crit_tool = _SUBMIT_CORRECTION_FLAT_TOOL
        crit_tool_name = "submit_correction_flat"
    else:
        crit_tool = _SUBMIT_CORRECTION_TOOL
        crit_tool_name = "submit_correction"

    try:
        message = client.messages.create(
            model=model,
            max_tokens=8000,
            system=[
                {"type": "text", "text": _SYSTEM_PROMPT_BASE},
                {
                    "type": "text",
                    "text": _FEW_SHOT_EXAMPLES,
                    "cache_control": {"type": "ephemeral", "ttl": "1h"},
                },
                {
                    "type": "text",
                    "text": _GRADING_TAIL_INSTRUCTION,
                    "cache_control": {"type": "ephemeral", "ttl": "1h"},
                },
            ],
            tools=[crit_tool],
            tool_choice={"type": "tool", "name": crit_tool_name},
            messages=[{"role": "user", "content": critique_msg}],
        )
        _log_cache_metrics("critique-flat" if schema_flat else "critique", model, message)
        for block in message.content:
            if (
                getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == crit_tool_name
            ):
                revised = dict(getattr(block, "input", {}) or {})
                if schema_flat:
                    revised = _unflatten_v2_input(revised)
                # Log if anything changed
                if revised.get("notas") != initial_tool_args.get("notas"):
                    print(
                        f"[dev_offline] self-critique adjusted notas: "
                        f"{initial_tool_args.get('notas')} -> {revised.get('notas')}"
                    )
                return revised
    except Exception as exc:  # noqa: BLE001
        print(f"[dev_offline] self-critique failed ({exc!r}); keeping original")

    return initial_tool_args


def _stream_quick_preview(data: Dict[str, Any]) -> None:
    """Run a fast streaming call to emit a ~5s preview of the feedback.

    Writes chunks to the job tracker as they arrive so the frontend sees
    text appearing while the full grading is still in flight. This call is
    independent from the structured grading — its output is a plain text
    preview, not a nota.
    """
    import os

    try:
        import anthropic
    except ImportError:
        return

    from redato_backend.shared.job_tracker import EssayJobTracker

    request_id = data.get("request_id")
    content = (data.get("content") or "").strip()
    if not request_id or not content:
        return

    tracker = EssayJobTracker()
    user_msg = (
        f"TEMA: {data.get('theme') or 'Tema livre'}\n\n"
        f"REDAÇÃO:\n\"\"\"\n{content}\n\"\"\"\n\n"
        "Escreva apenas o parágrafo de primeira impressão."
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    # Haiku is plenty for a short preview and much faster / cheaper than Sonnet.
    model = os.getenv("REDATO_PREVIEW_MODEL", "claude-haiku-4-5")

    try:
        with client.messages.stream(
            model=model,
            max_tokens=200,
            system=_PREVIEW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        ) as stream:
            for text in stream.text_stream:
                if text:
                    tracker.append_preview(request_id, text)
    except Exception as exc:  # noqa: BLE001
        print(f"[dev_offline] preview stream failed ({exc!r}); skipping preview")


_TUTOR_SYSTEM_PROMPT = """\
Você é a Redato, tutora pedagógica de escrita para o ENEM. Ajude o aluno a
entender e corrigir um trecho específico da redação dele. Seja socrática,
concisa (2-4 frases) e em português brasileiro.
"""


def _claude_tutor_reply(data: Dict[str, Any]) -> str:
    import os

    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("Anthropic SDK not installed.") from e

    competency = data.get("competency", "")
    errors = data.get("errors") or []
    message = data.get("message", "")

    context_parts = []
    if competency:
        context_parts.append(f"Competência: {competency}")
    if errors:
        context_parts.append(f"Trecho/erro em foco: {errors[0]}")
    context_parts.append(f"Pergunta do aluno: {message}")
    user_msg = "\n".join(context_parts)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.getenv("REDATO_CLAUDE_MODEL", "claude-sonnet-4-6")

    resp = client.messages.create(
        model=model,
        max_tokens=500,
        system=_TUTOR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    ).strip() or "Desculpe, não consegui formular uma resposta agora."


# ---------------------------------------------------------------------------
# Helper: issue a dev token (used by /auth/login stub)
# ---------------------------------------------------------------------------


def issue_dev_token(email: str, role: Optional[str] = None) -> str:
    """Look up (or invent) a seed user and return a dev token for them."""
    with _LOCK:
        uid = _STORE.firebase_email_index.get(email)
        if not uid:
            uid = hashlib.sha1(email.encode("utf-8")).hexdigest()[:24]
            _STORE.firebase_users[uid] = {
                "uid": uid,
                "email": email,
                "role": role or "student",
                "name": email.split("@")[0],
            }
            _STORE.firebase_email_index[email] = uid
        user = _STORE.firebase_users[uid]

    return _encode_dev_token({
        "uid": user["uid"],
        "email": user["email"],
        "role": role or user.get("role", "student"),
        "name": user.get("name"),
    })


# ---------------------------------------------------------------------------
# Patching entry point
# ---------------------------------------------------------------------------


def apply_patches() -> None:
    """Swap the real services for in-memory stubs. Idempotent.

    Works by installing synthetic modules into ``sys.modules`` BEFORE Python
    ever imports the real ones. This way the app runs even when the real
    ``google-cloud-*`` / ``firebase-admin`` packages are not installed.

    No-op em produção (REDATO_DEV_OFFLINE != "1"). Importante: o módulo
    pode até ser importado em prod (ex.: pelo unified_app antigo), mas
    nada é stubado. Anthropic/Twilio/SendGrid reais continuam ativos.
    """
    if os.getenv("REDATO_DEV_OFFLINE") != "1":
        return
    if getattr(apply_patches, "_applied", False):
        return

    # Force-load .env with override so a pre-existing empty ANTHROPIC_API_KEY
    # in the shell environment doesn't block the real key in the .env file.
    # Only active in dev-offline mode (this function is only called then).
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
    except Exception:
        pass

    # 1. Firebase — synthetic module that only exposes FakeFirebaseService.
    firebase_mod = ModuleType("redato_backend.shared.firebase")
    firebase_mod.FirebaseService = FakeFirebaseService  # type: ignore[attr-defined]
    sys.modules["redato_backend.shared.firebase"] = firebase_mod

    # 2. BigQuery — synthetic module with the fake client and a minimal shim
    #    for ``bigquery.ScalarQueryParameter`` used by the professor-feedback
    #    MERGE query.
    bq_mod = ModuleType("redato_backend.shared.bigquery")
    bq_mod.BigQueryClient = FakeBigQueryClient  # type: ignore[attr-defined]
    sys.modules["redato_backend.shared.bigquery"] = bq_mod

    # Stub google.cloud.bigquery so ``from google.cloud import bigquery``
    # succeeds for ScalarQueryParameter.
    gc_bq = ModuleType("google.cloud.bigquery")
    gc_bq.ScalarQueryParameter = _ScalarQueryParameter  # type: ignore[attr-defined]
    _register_google_cloud_module("bigquery", gc_bq)

    # 3. Firestore — stub ``google.cloud.firestore`` and google.api_core.exceptions.
    gc_fs = ModuleType("google.cloud.firestore")
    gc_fs.Client = FakeFirestoreClient  # type: ignore[attr-defined]
    _register_google_cloud_module("firestore", gc_fs)

    # 3b. google.cloud.logging — the shared logger imports this at module top.
    #     Stub with no-op Client and empty handler classes.
    gc_log = ModuleType("google.cloud.logging")

    class _NoopLogClient:
        def setup_logging(self) -> None:
            return None

    gc_log.Client = _NoopLogClient  # type: ignore[attr-defined]
    _register_google_cloud_module("logging", gc_log)

    gc_log_handlers = ModuleType("google.cloud.logging.handlers")

    class _NoopLogHandler:  # pragma: no cover
        pass

    gc_log_handlers.AppEngineHandler = _NoopLogHandler  # type: ignore[attr-defined]
    gc_log_handlers.CloudLoggingHandler = _NoopLogHandler  # type: ignore[attr-defined]
    gc_log_handlers.ContainerEngineHandler = _NoopLogHandler  # type: ignore[attr-defined]
    sys.modules["google.cloud.logging.handlers"] = gc_log_handlers
    gc_log.handlers = gc_log_handlers  # type: ignore[attr-defined]

    api_core_mod = sys.modules.get("google.api_core")
    if api_core_mod is None:
        api_core_mod = ModuleType("google.api_core")
        api_core_mod.__path__ = []  # type: ignore[attr-defined]
        sys.modules["google.api_core"] = api_core_mod
        _bind_submodule(sys.modules["google"], "api_core", api_core_mod)
    exc_mod = ModuleType("google.api_core.exceptions")
    exc_mod.AlreadyExists = _AlreadyExists  # type: ignore[attr-defined]
    sys.modules["google.api_core.exceptions"] = exc_mod
    api_core_mod.exceptions = exc_mod  # type: ignore[attr-defined]

    # 4. Cloud Function caller — replace the async function on a synthetic
    #    module. We also expose a minimal ``get_id_token_async`` in case the
    #    rest of the code imports it (defensive).
    caller_mod = ModuleType("redato_backend.base_api.caller")
    caller_mod.call_cloud_function = fake_call_cloud_function  # type: ignore[attr-defined]

    async def _noop_token(url: str) -> str:  # pragma: no cover
        return "dev"

    caller_mod.get_id_token_async = _noop_token  # type: ignore[attr-defined]
    sys.modules["redato_backend.base_api.caller"] = caller_mod

    # 5. Seed the in-memory store. If a persisted snapshot exists from a
    #    previous run, load that instead (keeps submitted essays across
    #    uvicorn --reload restarts).
    if not _load_from_disk():
        _seed()

    apply_patches._applied = True  # type: ignore[attr-defined]


class _ScalarQueryParameter(SimpleNamespace):
    """Minimal drop-in for ``google.cloud.bigquery.ScalarQueryParameter``."""

    def __init__(self, name: str, type_: str, value: Any):
        super().__init__(name=name, type_=type_, value=value)


class _AlreadyExists(Exception):
    """Minimal drop-in for ``google.api_core.exceptions.AlreadyExists``."""


def _register_google_cloud_module(name: str, module: ModuleType) -> None:
    """Insert ``google.cloud.<name>`` so ``from google.cloud import <name>`` works."""
    full = f"google.cloud.{name}"
    sys.modules[full] = module

    gc = sys.modules.get("google.cloud")
    if gc is None:
        gc = ModuleType("google.cloud")
        gc.__path__ = []  # mark as package  # type: ignore[attr-defined]
        sys.modules["google.cloud"] = gc

    g = sys.modules.get("google")
    if g is None:
        g = ModuleType("google")
        g.__path__ = []  # type: ignore[attr-defined]
        sys.modules["google"] = g
    _bind_submodule(g, "cloud", gc)
    _bind_submodule(gc, name, module)


def _bind_submodule(parent: ModuleType, name: str, child: ModuleType) -> None:
    setattr(parent, name, child)
