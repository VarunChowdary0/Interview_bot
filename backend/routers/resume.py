from fastapi import APIRouter, UploadFile, File, HTTPException
from datetime import datetime
from uuid import uuid4
import tempfile
import os

from services.parser import parse_resume
from services.interview.session_manager import get_session_manager
from schemas.responses import ResumeUploadResponse

router = APIRouter(prefix="/api/resume", tags=["Resume"])


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(...)):
    """Upload and parse a resume file.

    Accepts PDF, DOCX, or TXT files.

    Returns:
        ResumeUploadResponse with session_id and parsed resume data.
    """
    # Validate file type
    allowed_extensions = {".pdf", ".docx", ".txt"}
    file_ext = os.path.splitext(file.filename or "")[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
        )

    # Save to temp file
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Parse resume
        resume_data = parse_resume(tmp_path)

        # Store in session manager
        session_id = str(uuid4())
        session_manager = get_session_manager()
        session_manager.store_resume(session_id, resume_data)

        return ResumeUploadResponse(
            session_id=session_id,
            resume_data=resume_data,
            parsed_at=datetime.utcnow(),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse resume: {str(e)}",
        )

    finally:
        # Cleanup temp file
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/{session_id}")
async def get_resume(session_id: str):
    """Get parsed resume data by session ID.

    Args:
        session_id: The resume session ID from upload.

    Returns:
        Parsed resume data.
    """
    session_manager = get_session_manager()
    resume_data = session_manager.get_resume(session_id)

    if not resume_data:
        raise HTTPException(
            status_code=404,
            detail="Resume not found. It may have expired.",
        )

    return {"session_id": session_id, "resume_data": resume_data}
