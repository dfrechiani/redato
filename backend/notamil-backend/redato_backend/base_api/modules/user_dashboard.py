from typing import Dict, List, Optional

from redato_backend.base_api.modules.models import EssayRow, DashboardData
from redato_backend.base_api.modules.queries import USER_DASHBOARD_QUERY
from redato_backend.shared.bigquery import BigQueryClient
from redato_backend.shared.logger import logger
from redato_backend.shared.constants import COMPETENCIES
from redato_backend.base_api.modules.utils import round_to_twenty


class UserDashboardService:
    def __init__(self, bq_client: BigQueryClient):
        self.bq_client = bq_client

    @staticmethod
    def _initialize_dashboard_data() -> DashboardData:
        """Initializes an empty dashboard data structure."""
        return {
            "essays": {},
            "total_essays": 0,
            "average_grade": 0.0,
            "competency_averages": {
                comp_name: 0.0 for comp_id, comp_name in COMPETENCIES.items()
            },
        }

    @staticmethod
    def _process_competency_data(
        rows: List[EssayRow],
    ) -> tuple[Dict[str, int], Dict[str, int]]:
        """Processes competency data to calculate sums and counts."""
        competency_names = list(COMPETENCIES.values())
        competency_sums = {comp_name: 0 for comp_name in competency_names}
        competency_counts = {comp_name: 0 for comp_name in competency_names}

        for row in rows:
            if row.competency and row.grade is not None and row.competency_name:
                competency_sums[row.competency_name] += row.grade
                competency_counts[row.competency_name] += 1

        return competency_sums, competency_counts

    @staticmethod
    def _calculate_averages(
        dashboard_data: DashboardData,
        competency_sums: Dict[str, int],
        competency_counts: Dict[str, int],
    ) -> None:
        """Calculates average grades for overall and per competency."""
        total_grades = sum(
            essay["overall_grade"] for essay in dashboard_data["essays"].values()
        )

        if dashboard_data["total_essays"] > 0:
            raw_average = total_grades / dashboard_data["total_essays"]
            dashboard_data["average_grade"] = round_to_twenty(raw_average)

            competency_names = list(COMPETENCIES.values())
            for friendly in competency_names:
                if competency_counts[friendly] > 0:
                    raw_comp_average = (
                        competency_sums[friendly] / competency_counts[friendly]
                    )
                    dashboard_data["competency_averages"][friendly] = round_to_twenty(
                        raw_comp_average
                    )

    def get_dashboard(self, login_id: str) -> Optional[DashboardData]:  # noqa: C901
        try:
            query = USER_DASHBOARD_QUERY.format(login_id=login_id)
            rows = [EssayRow(**row) for row in self.bq_client.select(query)]

            if not rows:
                logger.warning(f"No essays found for login_id: {login_id}")
                return None

            dashboard_data = self._initialize_dashboard_data()

            # Process rows into dashboard structure
            for row in rows:
                if row.essay_id not in dashboard_data["essays"]:
                    dashboard_data["essays"][row.essay_id] = {
                        "graded_at": row.graded_at,
                        "theme": row.theme,
                        "overall_grade": round_to_twenty(row.overall_grade),
                        "competencies": {},
                    }
                    dashboard_data["total_essays"] += 1

                if row.competency and row.competency_name:
                    dashboard_data["essays"][row.essay_id]["competencies"][
                        row.competency_name
                    ] = {"grade": row.grade}

            # Calculate averages
            competency_sums, competency_counts = self._process_competency_data(rows)
            self._calculate_averages(dashboard_data, competency_sums, competency_counts)

            return dashboard_data

        except Exception as e:
            logger.error(f"Failed to retrieve dashboard data: {e}")
            raise
