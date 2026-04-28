from fastapi import APIRouter, HTTPException

from redato_backend.shared.logger import logger
from redato_backend.base_api.modules.dashboards import get_user_dashboard
from redato_backend.base_api.modules.classes import (
    get_class_students,
    get_class_competency_performance,
    get_professor_competency_performance,
    get_professor_general_performance,
)


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/user")
def user_dashboard(user_id: str):
    try:
        logger.info(f"Getting user dashboard for user_id {user_id}")

        dashboard = get_user_dashboard(user_id)

        return dashboard

    except Exception as e:
        logger.error(f"Error getting user dashboard for user_id {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/class")
def class_students(class_id: str):
    try:
        logger.info(f"Getting students for class_id {class_id}")

        students = get_class_students(class_id)

        return {"data": students}

    except Exception as e:
        logger.error(f"Error getting students for class_id {class_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/general/professor")
async def professor_general_performance(professor_id: str):
    try:
        logger.info(f"Getting general performance for professor_id {professor_id}")
        data = get_professor_general_performance(professor_id)
        return {"data": data}
    except Exception as e:
        logger.error(f"Error getting data for professor_id {professor_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/competency/professor")
async def professor_competency_performance(professor_id: str):
    try:
        logger.info(f"Getting competency performance for professor_id {professor_id}")
        data = get_professor_competency_performance(professor_id)

        # Log the first item to check competency format
        if data and len(data) > 0:
            logger.info(f"Sample competency data: {data[0]}")

        return {"data": data}
    except Exception as e:
        logger.error(f"Error getting data for professor_id {professor_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/competency/class")
async def class_competency_performance(class_id: str):
    try:
        logger.info(f"Getting competency performance for class_id {class_id}")
        data = get_class_competency_performance(class_id)

        # Log the first item to check competency format
        if data and len(data) > 0:
            logger.info(f"Sample competency data: {data[0]}")

        return {"data": data}
    except Exception as e:
        logger.error(f"Error getting data for class_id {class_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
