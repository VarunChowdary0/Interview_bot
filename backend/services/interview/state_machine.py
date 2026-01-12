from typing import Optional

from models.interview import InterviewState, InterviewSession
from models.llm import QuestionAction


# Define valid state transitions
VALID_TRANSITIONS: dict[InterviewState, set[InterviewState]] = {
    InterviewState.NOT_STARTED: {InterviewState.GREETING, InterviewState.CANCELLED},
    InterviewState.GREETING: {InterviewState.PREPLANNING, InterviewState.CANCELLED},
    InterviewState.PREPLANNING: {InterviewState.QUESTIONING, InterviewState.CANCELLED},
    InterviewState.QUESTIONING: {
        InterviewState.FOLLOW_UP,
        InterviewState.TRANSITIONING,
        InterviewState.CONCLUDING,
        InterviewState.CANCELLED,
    },
    InterviewState.FOLLOW_UP: {
        InterviewState.FOLLOW_UP,  # Can have multiple follow-ups
        InterviewState.TRANSITIONING,
        InterviewState.CONCLUDING,
        InterviewState.CANCELLED,
    },
    InterviewState.TRANSITIONING: {
        InterviewState.QUESTIONING,
        InterviewState.CONCLUDING,
        InterviewState.CANCELLED,
    },
    InterviewState.CONCLUDING: {InterviewState.COMPLETED},
    InterviewState.COMPLETED: set(),  # Terminal state
    InterviewState.CANCELLED: set(),  # Terminal state
}


class StateMachineError(Exception):
    """Error raised for invalid state transitions."""

    def __init__(self, current_state: InterviewState, target_state: InterviewState):
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(
            f"Invalid state transition: {current_state.value} -> {target_state.value}"
        )


def can_transition(current_state: InterviewState, target_state: InterviewState) -> bool:
    """Check if a state transition is valid.

    Args:
        current_state: The current state.
        target_state: The target state.

    Returns:
        True if transition is valid, False otherwise.
    """
    valid_targets = VALID_TRANSITIONS.get(current_state, set())
    return target_state in valid_targets


def transition_state(session: InterviewSession, target_state: InterviewState) -> InterviewSession:
    """Transition session to a new state.

    Args:
        session: The interview session.
        target_state: The target state.

    Returns:
        Updated session.

    Raises:
        StateMachineError: If transition is invalid.
    """
    if not can_transition(session.state, target_state):
        raise StateMachineError(session.state, target_state)

    session.state = target_state
    return session


def get_next_state_from_action(
    session: InterviewSession,
    action: QuestionAction,
) -> InterviewState:
    """Determine the next state based on LLM action.

    Args:
        session: The interview session.
        action: The action from LLM response.

    Returns:
        The next state.
    """
    if action == QuestionAction.ASK_FOLLOWUP:
        return InterviewState.FOLLOW_UP

    elif action == QuestionAction.MOVE_TO_NEXT_QUESTION:
        # Check if we have more topics
        if session.current_topic_index + 1 < len(session.preplanned_topics):
            return InterviewState.TRANSITIONING
        else:
            return InterviewState.CONCLUDING

    elif action == QuestionAction.END_INTERVIEW:
        return InterviewState.CONCLUDING

    # Default fallback
    return InterviewState.QUESTIONING


def is_terminal_state(state: InterviewState) -> bool:
    """Check if a state is terminal (no further transitions possible).

    Args:
        state: The state to check.

    Returns:
        True if terminal, False otherwise.
    """
    return state in (InterviewState.COMPLETED, InterviewState.CANCELLED)


def is_active_state(state: InterviewState) -> bool:
    """Check if a state represents an active interview.

    Args:
        state: The state to check.

    Returns:
        True if interview is active, False otherwise.
    """
    return state in (
        InterviewState.GREETING,
        InterviewState.PREPLANNING,
        InterviewState.QUESTIONING,
        InterviewState.FOLLOW_UP,
        InterviewState.TRANSITIONING,
        InterviewState.CONCLUDING,
    )
