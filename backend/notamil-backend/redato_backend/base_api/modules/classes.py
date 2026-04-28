from redato_backend.shared.logger import logger

from redato_backend.shared.bigquery import BigQueryClient
from typing import List, Dict, Any
from redato_backend.base_api.modules.utils import round_to_twenty
from redato_backend.base_api.modules.queries import (
    GET_PROFESSOR_GENERAL_PERFORMANCE_QUERY,
    GET_PROFESSOR_COMPETENCY_PERFORMANCE_QUERY,
    GET_CLASS_COMPETENCY_PERFORMANCE_QUERY,
    GET_CLASS_STUDENTS_QUERY,
)

bigquery_client = BigQueryClient()


def get_class_students(class_id: str) -> List[Dict[str, Any]]:
    query = GET_CLASS_STUDENTS_QUERY.format(class_id=class_id)

    try:
        result = bigquery_client.select(query)
        students_dict = {}

        for row in result:
            user_id = row["login_id"]
            if user_id not in students_dict:
                students_dict[user_id] = {
                    "student_user_id": user_id,
                    "name": row["name"],
                    "average_grade": round_to_twenty(float(row["average_grade"])),
                }

        return list(students_dict.values())
    except Exception as e:
        logger.error(f"Erro ao obter alunos da turma {class_id}: {e}")
        raise e


def get_professor_competency_performance(user_id: str) -> List[Dict[str, Any]]:
    try:
        query = GET_PROFESSOR_COMPETENCY_PERFORMANCE_QUERY.format(user_id=user_id)
        data = bigquery_client.select(query)
        result = [dict(row) for row in data]
        unique_entries = {}

        for row in result:
            if not row["competency_name"]:
                continue

            row["average_grade"] = str(round_to_twenty(float(row["average_grade"])))
            unique_key = f"{row['id']}_{row['competency_name']}"

            if unique_key not in unique_entries:
                row["competency"] = row["competency_name"]
                del row["competency_name"]
                unique_entries[unique_key] = row

        return list(unique_entries.values())
    except Exception as e:
        logger.error(f"Error getting data from professors table, user_id: {user_id}: {e}")
        raise e


def get_professor_general_performance(user_id: str) -> List[Dict[str, Any]]:
    try:
        query = GET_PROFESSOR_GENERAL_PERFORMANCE_QUERY.format(user_id=user_id)
        data = bigquery_client.select(query)
        result = [dict(row) for row in data]
        for row in result:
            row["average_grade"] = str(round_to_twenty(float(row["average_grade"])))

        return result
    except Exception as e:
        logger.error(f"Error getting data from professors table, user_id: {user_id}: {e}")
        raise e


def get_class_competency_performance(class_id: str) -> List[Dict[str, Any]]:
    try:
        query = GET_CLASS_COMPETENCY_PERFORMANCE_QUERY.format(class_id=class_id)
        data = bigquery_client.select(query)
        result = [dict(row) for row in data]
        unique_entries = {}

        for row in result:
            if not row["competency_name"]:
                continue

            row["average_grade"] = str(round_to_twenty(float(row["average_grade"])))
            unique_key = f"{row['id']}_{row['competency_name']}"

            if unique_key not in unique_entries:
                row["competency"] = row["competency_name"]
                del row["competency_name"]
                unique_entries[unique_key] = row

        return list(unique_entries.values())
    except Exception as e:
        logger.error(f"Error getting data for class_id {class_id}: {e}")
        raise e
