from typing import Any, List

from google.cloud import bigquery
from redato_backend.shared.constants import GCP_PROJECT_ID


class BigQueryClient:
    def __init__(self) -> None:
        self._client = bigquery.Client(project=GCP_PROJECT_ID)

    def select(self, query: str) -> Any:
        query_job = self._client.query(query)
        results = query_job.result()
        return results

    def select_with_params(
        self,
        query: str,
        query_params: List[Any],
    ) -> Any:
        job_config = bigquery.QueryJobConfig()
        job_config.query_parameters = query_params
        query_job = self._client.query(query, job_config=job_config)
        results = query_job.result()
        return results

    def insert(self, table_id: str, rows_to_insert: List[Any]) -> None:
        insert_errors = self._client.insert_rows_json(table_id, rows_to_insert)
        if insert_errors:
            raise ValueError(f"Encountered errors while inserting rows: {insert_errors}")

    def execute_query(self, query: str, query_params: List[Any] = None) -> None:
        job_config = bigquery.QueryJobConfig()
        if query_params:
            job_config.query_parameters = query_params
        # Executa a query (pode ser DELETE, INSERT, UPDATE)
        query_job = self._client.query(query, job_config=job_config)
        query_job.result()
