from typing import TypedDict, Optional, Dict
from dataclasses import dataclass


class CompetencyDetail(TypedDict):
    grade: int


class EssayData(TypedDict):
    graded_at: str
    theme: Optional[str]
    overall_grade: int
    competencies: Dict[str, CompetencyDetail]


class DashboardData(TypedDict):
    essays: Dict[str, EssayData]
    total_essays: int
    average_grade: float
    competency_averages: Dict[str, float]


@dataclass
class EssayRow:
    essay_id: str
    graded_at: str
    theme: str
    overall_grade: int
    competency: Optional[str]
    competency_name: Optional[str]
    grade: Optional[int]
