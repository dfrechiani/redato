from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any
from redato_backend.base_api.functions.handle_bq import (
    insert_theme_into_bq,
    insert_class_into_bq,
    delete_class_from_bq,
    get_professors_from_bq,
    insert_professor_into_bq,
    delete_professor_from_bq,
    delete_theme_from_bq,
    get_classes_from_bq,
    get_students_from_bq,
    delete_student_from_bq,
    update_professor_in_class,
)
from redato_backend.shared.logger import logger
from redato_backend.base_api.api_routes.deps import require_admin
from redato_backend.base_api.api_routes.models import ThemeCreate
from redato_backend.base_api.functions.models import ClassCreate, ProfessorCreate
from redato_backend.shared.firebase import FirebaseService


router = APIRouter(
    prefix="/manager",
    tags=["manager"],
    dependencies=[Depends(require_admin)],
)


@router.post("/theme")
def create_themes(theme: ThemeCreate):
    try:
        insert_theme_into_bq(theme.name, theme.description, theme.class_id)
        return {"message": "Theme created successfully"}
    except Exception as e:
        logger.error(f"Error when creating theme: {e}")
        raise HTTPException(status_code=500, detail="Failed to create theme.")


@router.post("/class")
async def create_class(class_data: ClassCreate):
    try:
        class_id = insert_class_into_bq(class_data)
        return {"message": "Class created successfully", "class_id": class_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/class/{class_id}")
async def delete_class(class_id: str):
    try:
        delete_class_from_bq(class_id)
        return {"message": f"Class with ID {class_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list-professors", response_model=Dict[str, Any])
async def list_professors(
    school_id: str = Query(..., description="The school ID to filter professors by")
):
    try:
        professors = get_professors_from_bq(school_id)
        return {"data": professors}
    except Exception:
        raise HTTPException(status_code=500, detail="Error fetching professors list.")


@router.post("/professor")
def create_professor(professor_data: ProfessorCreate):

    try:
        professor_id = insert_professor_into_bq(professor_data)

        return {"professor_id": professor_id}
    except Exception as e:
        logger.error(f"Erro ao criar professor: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao criar o professor.")


@router.delete("/professors/{professor_id}")
async def delete_professor(professor_id: str):
    try:
        firebase_service = FirebaseService()

        delete_professor_from_bq(professor_id, firebase_service)
        return {"message": f"Professor {professor_id} deleted successfully"}
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/theme/{theme_id}")
async def delete_theme(theme_id: str):
    try:
        delete_theme_from_bq(theme_id)
        return {"message": f"Theme {theme_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list-classes", response_model=Dict[str, Any])
async def list_classes(school_id: str):
    try:
        classes = get_classes_from_bq(school_id)
        return {"data": classes}
    except Exception:
        raise HTTPException(status_code=500, detail="Error fetching classes list.")


@router.get("/list-students", response_model=Dict[str, Any])
async def list_students(school_id: str):
    try:
        students = get_students_from_bq(school_id)
        return {"data": students}
    except Exception:
        raise HTTPException(status_code=500, detail="Error fetching students list.")


@router.delete("/student/{student_id}")
async def delete_student(student_id: str):
    try:
        firebase_service = FirebaseService()

        delete_student_from_bq(student_id, firebase_service)
        return {"message": f"Student {student_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/class/{class_id}")
async def update_class(class_id: str, professor_id: str):
    try:
        update_professor_in_class(class_id, professor_id)
        return {"message": f"Class {class_id} updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
