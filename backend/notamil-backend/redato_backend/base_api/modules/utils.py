import re


def is_uuid(value: str) -> bool:
    """Check if a string is in UUID format"""
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )
    return bool(uuid_pattern.match(value))


def round_to_twenty(grade: float) -> float:
    """
    Rounds a grade to the nearest multiple of 20.
    Example: 717 -> 720, 736 -> 740, 831 -> 840
    """
    return round(grade / 20) * 20
