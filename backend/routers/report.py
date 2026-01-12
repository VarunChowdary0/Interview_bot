from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from io import BytesIO

from models.interview import InterviewState
from services.interview.session_manager import SessionManager, get_session_manager
from services.report.generator import ReportGenerator
from services.report.json_exporter import export_report_json, export_report_dict
from services.report.pdf_exporter import export_report_pdf
from services.llm import get_llm_provider, LLMProvider

router = APIRouter(prefix="/api/report", tags=["Report"])


async def get_report_generator(
    llm: LLMProvider = Depends(get_llm_provider),
) -> ReportGenerator:
    """Dependency to get report generator with LLM."""
    return ReportGenerator(llm)


@router.get("/{session_id}")
async def get_report(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
    report_generator: ReportGenerator = Depends(get_report_generator),
):
    """Get the interview report as JSON.

    Only available for completed or cancelled interviews.

    Returns:
        Complete interview report with assessments and insights.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.state not in (InterviewState.COMPLETED, InterviewState.CANCELLED):
        raise HTTPException(
            status_code=400,
            detail=f"Report not available. Interview state: {session.state.value}",
        )

    if not session.evaluations:
        raise HTTPException(
            status_code=400,
            detail="No evaluations available. Interview may have been cancelled early.",
        )

    report = await report_generator.generate(session)
    return export_report_dict(report)


@router.get("/{session_id}/json")
async def download_report_json(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
    report_generator: ReportGenerator = Depends(get_report_generator),
):
    """Download the interview report as a JSON file.

    Returns:
        JSON file download.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.state not in (InterviewState.COMPLETED, InterviewState.CANCELLED):
        raise HTTPException(
            status_code=400,
            detail=f"Report not available. Interview state: {session.state.value}",
        )

    report = await report_generator.generate(session)
    json_content = export_report_json(report, pretty=True)

    # Get candidate name for filename
    candidate_name = report.candidate_name.replace(" ", "_")
    filename = f"interview_report_{candidate_name}_{session_id[:8]}.json"

    return StreamingResponse(
        BytesIO(json_content.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{session_id}/pdf")
async def download_report_pdf(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
    report_generator: ReportGenerator = Depends(get_report_generator),
):
    """Download the interview report as a PDF file.

    Returns:
        PDF file download.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.state not in (InterviewState.COMPLETED, InterviewState.CANCELLED):
        raise HTTPException(
            status_code=400,
            detail=f"Report not available. Interview state: {session.state.value}",
        )

    report = await report_generator.generate(session)

    try:
        pdf_content = export_report_pdf(report)
    except ImportError as e:
        raise HTTPException(
            status_code=501,
            detail=str(e),
        )

    # Get candidate name for filename
    candidate_name = report.candidate_name.replace(" ", "_")
    filename = f"interview_report_{candidate_name}_{session_id[:8]}.pdf"

    return StreamingResponse(
        BytesIO(pdf_content),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
