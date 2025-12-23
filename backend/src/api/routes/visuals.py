"""Visual assets API routes.

Endpoints:
- POST /api/projects/{project_id}/visuals/assets/upload - Upload images
- GET /api/projects/{project_id}/visuals/assets/{asset_id}/content - Serve image
- DELETE /api/projects/{project_id}/visuals/assets/{asset_id} - Delete asset
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import JSONResponse, Response

from src.api.response import error_response, success_response
from src.services import project_service
from src.services.visual_asset_service import (
    MAX_ASSETS_PER_PROJECT,
    UploadValidationError,
    delete_asset_files,
    get_asset_content,
    process_and_store_asset,
    validate_asset_count,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/visuals", tags=["Visuals"])


@router.post("/assets/upload")
async def upload_assets(
    project_id: str,
    files: Annotated[list[UploadFile], File(description="Image files to upload")],
) -> JSONResponse:
    """Upload one or more images to the project's visual library.

    - Accepts PNG, JPEG, WebP
    - Max 10MB per file
    - Max 10 files per project total
    - Generates thumbnails automatically
    - Sets default caption from filename (without extension)

    Returns:
        {data: {assets: [VisualAsset, ...]}, error: null} on success
        {data: null, error: {code, message}} on validation failure
    """
    # Validate file count in single upload (check first - before hitting DB)
    if len(files) > 10:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "TOO_MANY_FILES",
                f"Maximum 10 files per upload, got {len(files)}",
            ),
        )

    # Verify project exists
    project = await project_service.get_project(project_id)

    # Get current asset count and validate we won't exceed the limit
    visual_plan = project.visualPlan
    current_count = len(visual_plan.assets) if visual_plan and visual_plan.assets else 0

    try:
        validate_asset_count(current_count, len(files))
    except UploadValidationError as e:
        return JSONResponse(
            status_code=400,
            content=error_response(e.code, e.message),
        )

    # Process each file
    assets = []
    for upload_file in files:
        try:
            # Read file content
            content = await upload_file.read()

            # Process and store
            asset = await process_and_store_asset(
                project_id=project_id,
                file_content=content,
                filename=upload_file.filename or "untitled",
                media_type=upload_file.content_type or "application/octet-stream",
            )
            assets.append(asset.model_dump())

        except UploadValidationError as e:
            # Return error for first validation failure
            return JSONResponse(
                status_code=400,
                content=error_response(e.code, e.message),
            )
        except ValueError as e:
            # Image processing error
            return JSONResponse(
                status_code=400,
                content=error_response(
                    "PROCESSING_ERROR",
                    f"Failed to process '{upload_file.filename}': {e}",
                ),
            )

    logger.info(f"Uploaded {len(assets)} assets to project {project_id}")

    return JSONResponse(
        status_code=200,
        content=success_response({"assets": assets}),
    )


@router.get("/assets/{asset_id}/content")
async def serve_asset_content(
    project_id: str,
    asset_id: str,
    size: Annotated[str, Query(description="Size variant: 'thumb' or 'full'")] = "thumb",
) -> Response:
    """Serve the binary content of an asset.

    - Verifies asset belongs to the project via GridFS metadata
    - Returns thumbnail by default, full size if size=full

    Note: We check project ownership via GridFS metadata (set during upload)
    rather than visualPlan.assets to allow serving immediately after upload,
    before the frontend saves the project state.

    Args:
        project_id: Project ID
        asset_id: Asset UUID
        size: 'thumb' (default) or 'full'

    Returns:
        Image binary with appropriate Content-Type header
    """
    # Get content from GridFS - this also verifies project ownership via metadata
    result = await get_asset_content(project_id, asset_id, variant=size)
    if result is None:
        return JSONResponse(
            status_code=404,
            content=error_response(
                "ASSET_NOT_FOUND",
                f"Asset '{asset_id}' not found for project",
            ),
        )

    content, media_type = result

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=86400",  # Cache for 1 day
        },
    )


@router.delete("/assets/{asset_id}")
async def delete_asset(
    project_id: str,
    asset_id: str,
) -> JSONResponse:
    """Delete an asset and its binary data from GridFS.

    Note: The frontend must also update visualPlan.assets and clear
    any assignments referencing this asset.

    Returns:
        {data: {deleted: true}, error: null} on success
        {data: null, error: {code, message}} on failure
    """
    # Verify project exists
    project = await project_service.get_project(project_id)

    # Verify asset belongs to project
    visual_plan = project.visualPlan
    if visual_plan and visual_plan.assets:
        asset_ids = {a.id for a in visual_plan.assets}
        if asset_id not in asset_ids:
            return JSONResponse(
                status_code=404,
                content=error_response(
                    "ASSET_NOT_FOUND",
                    f"Asset '{asset_id}' not found in project",
                ),
            )
    else:
        return JSONResponse(
            status_code=404,
            content=error_response(
                "ASSET_NOT_FOUND",
                f"Asset '{asset_id}' not found in project",
            ),
        )

    # Delete from GridFS
    deleted_count = await delete_asset_files(asset_id)

    logger.info(f"Deleted asset {asset_id} from project {project_id} ({deleted_count} files)")

    return JSONResponse(
        status_code=200,
        content=success_response({"deleted": True, "files_removed": deleted_count}),
    )
