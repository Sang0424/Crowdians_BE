# app/services/report_service.py

from app.models.report import Report
from app.schemas.report import ReportCreateRequest


async def create_report(reporter_id: str, request: ReportCreateRequest) -> Report:
    """새로운 신고를 접수합니다."""
    
    # 이미 같은 유저가 동일한 대상을 동일한 사유로 미해결 (pending) 상태로 남긴 게 있다면 중복 방지 (선택 사항)
    existing_report = await Report.find_one({
        "reporter_id": reporter_id,
        "target_type": request.targetType,
        "target_id": request.targetId,
        "status": "pending"
    })
    
    if existing_report:
        raise ValueError("동일한 대상에 대한 신고 접수 건이 이미 처리 대기 중입니다.")
        
    report = Report(
        reporter_id=reporter_id,
        target_type=request.targetType,
        target_id=request.targetId,
        reason=request.reason,
        details=request.details,
    )
    
    await report.insert()
    return report

