# app/api/v1/endpoints/reports.py

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.models.user import User
from app.schemas.report import ReportCreateRequest, ReportResponse
from app.services.report_service import create_report

router = APIRouter()


@router.post(
    "/reports",
    response_model=ReportResponse,
    summary="악성 콘텐츠/응답 신고 (Report) 생성",
    description="유저 컨텐츠나 문제가 있는 AI의 응답을 관리자에게 신고합니다.",
)
async def submit_report(
    request: ReportCreateRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        r = await create_report(current_user.uid, request)
        
        return ReportResponse(
            id=str(r.id),
            reporterId=r.reporter_id,
            targetType=r.target_type,
            targetId=r.target_id,
            reason=r.reason,
            status=r.status,
            createdAt=r.created_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
