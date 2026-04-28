from typing import Dict, Any


def get_errors_analysis(essay_analysis: Dict[str, Any]) -> Dict[str, Any]:
    essay_errors = {}
    for comp_data in essay_analysis["competencies"]:
        competency = comp_data["competency"]
        errors = comp_data["errors"]
        essay_errors[competency] = errors

    return essay_errors
