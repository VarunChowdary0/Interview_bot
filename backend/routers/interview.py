from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from typing import Optional

from models.interview import InterviewState
from schemas.requests import CreateInterviewRequest, CandidateResponseRequest, EndInterviewRequest
from schemas.responses import (
    InterviewSessionResponse,
    InterviewMessageResponse,
    InterviewStatusResponse,
    InterviewEndResponse,
)
from services.interview.session_manager import SessionManager, get_session_manager
from services.interview.flow_controller import InterviewFlowController
from services.interview.state_machine import is_terminal_state, is_active_state
from services.llm import get_llm_provider, LLMProvider
from config import get_settings

router = APIRouter(prefix="/api/interview", tags=["Interview"])


def get_flow_controller(
    llm: LLMProvider = Depends(get_llm_provider),
) -> InterviewFlowController:
    """Dependency to get flow controller with LLM."""
    return InterviewFlowController(llm)


@router.post("/create", response_model=InterviewSessionResponse)
async def create_interview(
    request: CreateInterviewRequest,
    session_manager: SessionManager = Depends(get_session_manager),
):
    """Create a new interview session.

    Requires either a resume_session_id (from prior upload) or resume_data directly,
    along with job_data defining the interview parameters.

    Returns:
        InterviewSessionResponse with the new session_id.
    """
    # Get resume data
    resume_data = None

    if request.resume_session_id:
        resume_data = session_manager.get_resume(request.resume_session_id)
        if not resume_data:
            raise HTTPException(
                status_code=404,
                detail="Resume session not found. Please upload resume first.",
            )
    elif request.resume_data:
        resume_data = request.resume_data
    else:
        raise HTTPException(
            status_code=400,
            detail="Either resume_session_id or resume_data is required.",
        )

    # Create interview session
    job_data_dict = request.job_data.model_dump()
    session = session_manager.create_session(
        resume_data=resume_data,
        job_data=job_data_dict,
    )

    return InterviewSessionResponse(
        session_id=session.session_id,
        state=session.state,
        created_at=session.created_at,
    )


@router.post("/{session_id}/start", response_model=InterviewMessageResponse)
async def start_interview(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
    flow_controller: InterviewFlowController = Depends(get_flow_controller),
):
    """Start an interview session.

    Generates the greeting and first question.

    Returns:
        InterviewMessageResponse with greeting and first question.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if session.state != InterviewState.NOT_STARTED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start interview in state: {session.state.value}",
        )

    # Start interview
    message = await flow_controller.start_interview(session)
    session_manager.update_session(session)

    return InterviewMessageResponse(
        session_id=session.session_id,
        state=session.state,
        message=message,
        progress=session.get_progress(),
        is_complete=False,
    )


@router.post("/{session_id}/respond", response_model=InterviewMessageResponse)
async def submit_response(
    session_id: str,
    request: CandidateResponseRequest,
    session_manager: SessionManager = Depends(get_session_manager),
    flow_controller: InterviewFlowController = Depends(get_flow_controller),
):
    """Submit a candidate response to the current question.

    Evaluates the response and returns the next question or conclusion.

    Returns:
        InterviewMessageResponse with next question or closing message.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if not is_active_state(session.state):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot respond in state: {session.state.value}",
        )

    # Process response
    message = await flow_controller.process_response(session, request.response)
    session_manager.update_session(session)

    return InterviewMessageResponse(
        session_id=session.session_id,
        state=session.state,
        message=message,
        progress=session.get_progress(),
        is_complete=is_terminal_state(session.state),
    )


@router.get("/{session_id}/status", response_model=InterviewStatusResponse)
async def get_status(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
):
    """Get the current status of an interview session.

    Returns:
        InterviewStatusResponse with current state and progress.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Calculate duration if interview is active
    duration_seconds = None
    if session.started_at:
        end_time = session.ended_at or datetime.utcnow()
        duration_seconds = (end_time - session.started_at).total_seconds()

    return InterviewStatusResponse(
        session_id=session.session_id,
        state=session.state,
        progress=session.get_progress(),
        started_at=session.started_at,
        duration_seconds=duration_seconds,
        messages_count=len(session.messages),
    )


@router.post("/{session_id}/end", response_model=InterviewEndResponse)
async def end_interview(
    session_id: str,
    request: Optional[EndInterviewRequest] = None,
    session_manager: SessionManager = Depends(get_session_manager),
    flow_controller: InterviewFlowController = Depends(get_flow_controller),
):
    """End an interview early.

    Can be used to cancel an in-progress interview.

    Returns:
        InterviewEndResponse with final state.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if is_terminal_state(session.state):
        raise HTTPException(
            status_code=400,
            detail=f"Interview already ended in state: {session.state.value}",
        )

    reason = request.reason if request else None
    await flow_controller.end_interview_early(session, reason)
    session_manager.update_session(session)

    return InterviewEndResponse(
        session_id=session.session_id,
        state=session.state,
        ended_at=session.ended_at or datetime.utcnow(),
        report_available=len(session.evaluations) > 0,
    )


@router.get("/{session_id}/history")
async def get_history(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
):
    """Get the conversation history for an interview.

    Returns:
        List of messages in the conversation.
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    messages = [
        {
            "id": msg.id,
            "role": msg.role.value,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
            "metadata": msg.metadata,
        }
        for msg in session.messages
    ]

    return {
        "session_id": session_id,
        "state": session.state.value,
        "messages": messages,
    }
