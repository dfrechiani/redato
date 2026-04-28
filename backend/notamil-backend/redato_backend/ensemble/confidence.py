"""
Calcula metadata de confiança a partir dos resultados do ensemble.

Usado em _merge_ensemble_results para anexar _confidence ao output final.
"""
from dataclasses import dataclass, field, asdict
from typing import Literal


@dataclass
class CompetencyAgreement:
    competency: Literal["c1", "c2", "c3", "c4", "c5"]
    notes_per_run: list[int]
    agreement: float  # 0-1: % de runs que concordam com a moda
    spread: int       # max - min em pontos
    modal_note: int
    is_unanimous: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConfidenceMetadata:
    ensemble_n: int
    per_competency: list[CompetencyAgreement]
    overall_agreement: float
    total_spread: int
    confidence_level: Literal["high", "medium", "low"]
    flags: list[str] = field(default_factory=list)
    needs_human_review: bool = False

    def to_dict(self) -> dict:
        return {
            "ensemble_n": self.ensemble_n,
            "per_competency": [c.to_dict() for c in self.per_competency],
            "overall_agreement": self.overall_agreement,
            "total_spread": self.total_spread,
            "confidence_level": self.confidence_level,
            "flags": self.flags,
            "needs_human_review": self.needs_human_review,
        }


def calculate_confidence(ensemble_results: list[dict]) -> ConfidenceMetadata:
    """
    Recebe lista de results de runs do ensemble (cada um com `notas: {c1..c5, total}`)
    e retorna metadata de confidence.

    Regras de classificação:
        high:   overall_agreement >= 0.85 AND total_spread <= 80
        medium: overall_agreement >= 0.65 AND total_spread <= 160
        low:    qualquer outro caso

    needs_human_review = True quando confidence_level == 'low'
    """
    if len(ensemble_results) < 2:
        return ConfidenceMetadata(
            ensemble_n=len(ensemble_results),
            per_competency=[],
            overall_agreement=1.0,
            total_spread=0,
            confidence_level="high",
            flags=["single_run"],
            needs_human_review=False,
        )

    competencias = ["c1", "c2", "c3", "c4", "c5"]
    per_comp: list[CompetencyAgreement] = []

    for comp in competencias:
        notes = [int(r["notas"][comp]) for r in ensemble_results]
        counts: dict[int, int] = {}
        for n in notes:
            counts[n] = counts.get(n, 0) + 1
        modal_note, modal_count = max(counts.items(), key=lambda kv: kv[1])

        per_comp.append(CompetencyAgreement(
            competency=comp,
            notes_per_run=notes,
            agreement=modal_count / len(notes),
            spread=max(notes) - min(notes),
            modal_note=modal_note,
            is_unanimous=(modal_count == len(notes)),
        ))

    overall_agreement = sum(c.agreement for c in per_comp) / len(per_comp)
    totals = [int(r["notas"]["total"]) for r in ensemble_results]
    total_spread = max(totals) - min(totals)

    flags: list[str] = []
    for c in per_comp:
        if c.spread >= 80:
            flags.append(f"high_spread_{c.competency}")
        if c.agreement < 0.5:
            flags.append(f"disagreement_{c.competency}")
    if total_spread >= 200:
        flags.append("high_total_spread")
    if overall_agreement < 0.6:
        flags.append("low_overall_agreement")

    if overall_agreement >= 0.85 and total_spread <= 80:
        confidence_level: Literal["high", "medium", "low"] = "high"
    elif overall_agreement >= 0.65 and total_spread <= 160:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    return ConfidenceMetadata(
        ensemble_n=len(ensemble_results),
        per_competency=per_comp,
        overall_agreement=round(overall_agreement, 3),
        total_spread=total_spread,
        confidence_level=confidence_level,
        flags=flags,
        needs_human_review=(confidence_level == "low"),
    )
