"""File upload, download, and delete endpoints."""

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from src.api.response import success_response
from src.services import project_service
from src.services.file_service import file_service

router = APIRouter(prefix="/projects/{project_id}/files", tags=["Files"])


@router.post("", status_code=201)
async def upload_file(
    project_id: str,
    file: Annotated[UploadFile, File(...)],
    label: Annotated[str | None, Form()] = None,
) -> JSONResponse:
    """Upload a file to a project as a resource.

    The file is validated for size (max 10MB) and type (PDF, PPT, PPTX, DOC, DOCX, JPG, JPEG, PNG).
    A new resource entry is created and added to the project.
    """
    from src.models.project import UpdateProjectRequest

    # Verify project exists first
    project = await project_service.get_project(project_id)

    # Read file content
    content = await file.read()

    # Upload file and get resource entry
    resource = await file_service.upload_file(
        project_id=project_id,
        filename=file.filename or "unnamed",
        content=content,
        content_type=file.content_type,
        label=label,
        resource_order=len(project.resources),
    )

    # Add the new resource to the project
    updated_resources = list(project.resources) + [resource]

    update_request = UpdateProjectRequest(
        name=project.name,
        webinarType=project.webinarType,
        transcriptText=project.transcriptText,
        outlineItems=project.outlineItems,
        resources=updated_resources,
        visuals=project.visuals,
        draftText=project.draftText,
        styleConfig=project.styleConfig,
        finalTitle=project.finalTitle,
        finalSubtitle=project.finalSubtitle,
        creditsText=project.creditsText,
    )

    await project_service.update_project(project_id, update_request)

    return JSONResponse(
        status_code=201,
        content=success_response(resource.model_dump(mode="json")),
    )


@router.get("/{file_id}")
async def download_file(project_id: str, file_id: str) -> FileResponse:
    """Download a file from a project.

    Returns the file with appropriate content-type and disposition headers.
    """
    # Verify project exists
    project = await project_service.get_project(project_id)

    # Find the resource with this file_id
    resource = None
    for res in project.resources:
        if res.fileId == file_id:
            resource = res
            break

    if resource is None or resource.fileName is None:
        from src.api.exceptions import FileNotFoundError
        raise FileNotFoundError(file_id, project_id)

    # Get file path
    file_path = file_service.get_file_path_for_download(
        project_id=project_id,
        file_id=file_id,
        filename=resource.fileName,
    )

    return FileResponse(
        path=file_path,
        filename=resource.fileName,
        media_type=resource.mimeType or "application/octet-stream",
    )


@router.delete("/{file_id}")
async def delete_file(project_id: str, file_id: str) -> JSONResponse:
    """Delete a file from a project.

    Removes both the file from disk and the resource entry from the project.
    """
    # Verify project exists and get current state
    project = await project_service.get_project(project_id)

    # Find the resource with this file_id
    resource = None
    resource_index = None
    for i, res in enumerate(project.resources):
        if res.fileId == file_id:
            resource = res
            resource_index = i
            break

    if resource is None or resource.fileName is None:
        from src.api.exceptions import FileNotFoundError
        raise FileNotFoundError(file_id, project_id)

    # Delete file from disk
    await file_service.delete_file(
        project_id=project_id,
        file_id=file_id,
        filename=resource.fileName,
    )

    # Remove resource from project and update
    from src.models.project import UpdateProjectRequest

    # Build updated resources list without the deleted file
    updated_resources = [r for i, r in enumerate(project.resources) if i != resource_index]

    # Reorder remaining resources
    for i, r in enumerate(updated_resources):
        # Create a new resource with updated order
        updated_resources[i] = r.model_copy(update={"order": i})

    # Update project with remaining resources
    update_request = UpdateProjectRequest(
        name=project.name,
        webinarType=project.webinarType,
        transcriptText=project.transcriptText,
        outlineItems=project.outlineItems,
        resources=updated_resources,
        visuals=project.visuals,
        draftText=project.draftText,
        styleConfig=project.styleConfig,
        finalTitle=project.finalTitle,
        finalSubtitle=project.finalSubtitle,
        creditsText=project.creditsText,
    )

    await project_service.update_project(project_id, update_request)

    return JSONResponse(
        content=success_response({"deleted": True}),
    )
