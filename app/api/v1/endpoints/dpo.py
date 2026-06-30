# app/api/v1/endpoints/dpo.py
import io
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.core.security import CurrentUser
from app.services import dpo_service

router = APIRouter(prefix="/dpo", tags=["DPO"])


@router.get("/export")
async def export_dpo(
    current_user: CurrentUser,
    format: Optional[str] = Query("json", pattern="^(json|jsonl)$", description="Format to export: 'json' or 'jsonl'")
):
    """
    Export the DPO training dataset after PII masking.
    Only accessible by users with the 'admin' role.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can export the DPO dataset."
        )

    try:
        dataset = await dpo_service.export_dpo_dataset()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export DPO dataset: {str(e)}"
        )

    if format == "jsonl":
        # Convert the dataset into JSONL format
        output = io.StringIO()
        for item in dataset:
            output.write(json.dumps(item, ensure_ascii=False) + "\n")
        output.seek(0)

        # Return as a file stream for download
        return StreamingResponse(
            io.BytesIO(output.read().encode("utf-8")),
            media_type="application/x-jsonlines",
            headers={"Content-Disposition": "attachment; filename=dpo_dataset.jsonl"}
        )

    return dataset
