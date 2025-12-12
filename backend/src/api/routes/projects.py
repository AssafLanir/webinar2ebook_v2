"""Project CRUD endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from src.api.response import error_response, success_response
from src.models.project import CreateProjectRequest, UpdateProjectRequest
from src.services import project_service

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("")
async def list_projects() -> JSONResponse:
    """List all projects."""
    projects = await project_service.list_projects()
    return JSONResponse(
        content=success_response([p.model_dump(mode="json") for p in projects])
    )


@router.get("/{project_id}")
async def get_project(project_id: str) -> JSONResponse:
    """Get a project by ID."""
    project = await project_service.get_project(project_id)
    return JSONResponse(
        content=success_response(project.model_dump(mode="json"))
    )


@router.post("", status_code=201)
async def create_project(request: Request) -> JSONResponse:
    """Create a new project."""
    try:
        body = await request.json()
        create_request = CreateProjectRequest(**body)
    except PydanticValidationError as e:
        return JSONResponse(
            status_code=400,
            content=error_response("VALIDATION_ERROR", str(e)),
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content=error_response("VALIDATION_ERROR", str(e)),
        )

    project = await project_service.create_project(create_request)
    return JSONResponse(
        status_code=201,
        content=success_response(project.model_dump(mode="json")),
    )


@router.put("/{project_id}")
async def update_project(project_id: str, request: Request) -> JSONResponse:
    """Update a project by ID."""
    try:
        body = await request.json()
        update_request = UpdateProjectRequest(**body)
    except PydanticValidationError as e:
        return JSONResponse(
            status_code=400,
            content=error_response("VALIDATION_ERROR", str(e)),
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content=error_response("VALIDATION_ERROR", str(e)),
        )

    project = await project_service.update_project(project_id, update_request)
    return JSONResponse(
        content=success_response(project.model_dump(mode="json")),
    )


@router.delete("/{project_id}")
async def delete_project(project_id: str) -> JSONResponse:
    """Delete a project by ID."""
    await project_service.delete_project(project_id)
    return JSONResponse(
        content=success_response({"deleted": True}),
    )
