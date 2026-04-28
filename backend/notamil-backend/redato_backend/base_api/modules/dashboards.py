from typing import Optional

from redato_backend.base_api.modules.models import DashboardData
from redato_backend.base_api.modules.user_dashboard import UserDashboardService

from redato_backend.shared.bigquery import BigQueryClient


def get_user_dashboard(login_id: str) -> Optional[DashboardData]:
    """Convenience function for getting user dashboard data."""
    bq_client = BigQueryClient()
    dashboard_service = UserDashboardService(bq_client)
    return dashboard_service.get_dashboard(login_id)
