import hashlib


def compute_essay_hash(essay: str) -> str:
    normalized = essay.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
