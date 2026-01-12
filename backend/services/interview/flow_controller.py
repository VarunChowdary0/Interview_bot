from typing import Optional
from datetime import datetime
from uuid import uuid4
import json
import random
import re
import time
from pathlib import Path

from models.interview import InterviewSession, InterviewState, ChatMessage, ChatRole


def extract_json_from_response(response: str) -> str:
    """Extract JSON from LLM response, handling markdown code blocks and various formats."""
    if not response:
        return ""

    # Clean up common issues
    response = response.strip()

    # Try to find JSON in code blocks first (```json ... ``` or ``` ... ```)
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    matches = re.findall(code_block_pattern, response)
    if matches:
        # Get the first match and clean it
        json_content = matches[0].strip()
        if json_content:
            return json_content

    # If response starts with { or [, it might be raw JSON
    if response.startswith('{') or response.startswith('['):
        return response

    # Try to find JSON object pattern (handles nested braces)
    # Look for outermost { ... }
    brace_start = response.find('{')
    if brace_start != -1:
        brace_count = 0
        for i, char in enumerate(response[brace_start:], brace_start):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    return response[brace_start:i+1]

    # Try to find JSON array pattern
    bracket_start = response.find('[')
    if bracket_start != -1:
        bracket_count = 0
        for i, char in enumerate(response[bracket_start:], bracket_start):
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    return response[bracket_start:i+1]

    # Return as-is if no patterns found
    return response


from models.llm import (
    LLM_Response,
    QuestionAction,
    PrePlanner,
    Question,
    QuestionEvaluation,
)
from models.common import DifficultyLevel
from services.llm.base import LLMProvider, LLMMessage, LLMCallLog
from services.llm.prompts import (
    PREPLAN_TOPICS_PROMPT,
    GENERATE_GREETING_PROMPT,
    EVALUATE_RESPONSE_PROMPT,
    GENERATE_CONCLUSION_PROMPT,
    GENERATE_QUESTION_PROMPT,
    CODING_FORMAT_INSTRUCTIONS,
    CONCEPTUAL_FORMAT_INSTRUCTIONS,
    CODING_OUTPUT_FORMAT,
    CONCEPTUAL_OUTPUT_FORMAT,
)
from services.interview.state_machine import transition_state


class InterviewFlowController:
    """Orchestrates the interview flow and LLM interactions."""

    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    def _log_llm_call(
        self,
        session: InterviewSession,
        call_type: str,
        messages: list[LLMMessage],
        response: str,
        usage: dict,
        latency_ms: int = 0,
    ) -> None:
        """Log an LLM call with prompt, response, and token usage to the session."""
        log = LLMCallLog(
            call_type=call_type,
            model=self.llm.config.model,
            prompt_messages=[{"role": m.role, "content": m.content} for m in messages],
            response=response,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_ms=latency_ms,
        )
        session.llm_logs.append(log.to_dict())

    async def start_interview(self, session: InterviewSession) -> ChatMessage:
        """Initialize and start the interview.

        Args:
            session: The interview session.

        Returns:
            Greeting message with first question.
        """
        # Transition to greeting state
        transition_state(session, InterviewState.GREETING)
        session.started_at = datetime.utcnow()

        # Generate greeting
        greeting = await self._generate_greeting(session)
        session.add_message(ChatRole.INTERVIEWER, greeting)

        # Transition to preplanning
        transition_state(session, InterviewState.PREPLANNING)

        # Generate topic plan
        preplanned = await self._generate_preplan(session)
        session.preplanned_topics = [p.model_dump() for p in preplanned]

        # Transition to questioning
        transition_state(session, InterviewState.QUESTIONING)

        # Generate first question
        first_question = await self._generate_first_question(session)
        session.current_question = first_question.model_dump()
        session.questions_asked = 1

        # Create combined message (greeting + first question)
        full_message = f"{greeting}\n\n{first_question.text}"
        message = session.add_message(
            ChatRole.INTERVIEWER,
            full_message,
            metadata={"question_id": first_question.id, "skill": first_question.skill},
        )

        return message

    async def process_response(
        self,
        session: InterviewSession,
        candidate_response: str,
    ) -> ChatMessage:
        """Process candidate's response and determine next action.

        Args:
            session: The interview session.
            candidate_response: The candidate's response text.

        Returns:
            Next interviewer message.
        """
        # Add candidate message
        session.add_message(ChatRole.CANDIDATE, candidate_response)

        # Check for explicit end request from candidate
        response_lower = candidate_response.strip().lower()
        explicit_end_phrases = ["end interview", "stop interview", "end the interview", "please end", "stop the interview"]
        if any(phrase in response_lower for phrase in explicit_end_phrases):
            print(f"[DEBUG] Candidate explicitly requested to end interview")
            return await self._conclude_interview(session)

        # Get max_questions from job policy
        job = session.job_data or {}
        question_policy = job.get("question_policy", {})
        max_questions = question_policy.get("max_questions", 10)

        # Check if we've already reached the question limit BEFORE asking more
        if session.questions_asked >= max_questions:
            print(f"[DEBUG] Max questions reached ({session.questions_asked}/{max_questions}), concluding interview")
            return await self._conclude_interview(session)

        # Get evaluation and next action from LLM
        llm_response = await self._evaluate_and_decide(session, candidate_response)

        # Store evaluation
        session.add_evaluation(llm_response.evaluation.model_dump())

        # Handle action
        if llm_response.action == QuestionAction.END_INTERVIEW:
            return await self._conclude_interview(session)

        if llm_response.action == QuestionAction.ASK_FOLLOWUP:
            transition_state(session, InterviewState.FOLLOW_UP)
            session.followups_for_current += 1

        elif llm_response.action == QuestionAction.MOVE_TO_NEXT_QUESTION:
            session.current_topic_index += 1
            session.followups_for_current = 0

            # Check if we've covered all topics
            if session.current_topic_index >= len(session.preplanned_topics):
                return await self._conclude_interview(session)

            # Move to next topic - transition through TRANSITIONING to QUESTIONING
            transition_state(session, InterviewState.TRANSITIONING)
            transition_state(session, InterviewState.QUESTIONING)

        # Update current question
        if llm_response.next_question:
            session.current_question = llm_response.next_question.model_dump()
            session.questions_asked += 1

            # Double-check we haven't exceeded the limit
            if session.questions_asked > max_questions:
                print(f"[DEBUG] Question limit exceeded after increment ({session.questions_asked}/{max_questions}), concluding")
                return await self._conclude_interview(session)

            message = session.add_message(
                ChatRole.INTERVIEWER,
                llm_response.next_question.text,
                metadata={
                    "question_id": llm_response.next_question.id,
                    "skill": llm_response.next_question.skill,
                },
            )
            return message

        # Fallback: generate next question if LLM didn't provide one
        # But first check if we've already reached the limit
        if session.questions_asked >= max_questions:
            print(f"[DEBUG] At question limit before fallback generation, concluding")
            return await self._conclude_interview(session)

        next_question = await self._generate_next_question(session)
        session.current_question = next_question.model_dump()
        session.questions_asked += 1

        message = session.add_message(
            ChatRole.INTERVIEWER,
            next_question.text,
            metadata={"question_id": next_question.id, "skill": next_question.skill},
        )
        return message

    async def end_interview_early(self, session: InterviewSession, reason: Optional[str] = None) -> ChatMessage:
        """End the interview early (cancelled by user).

        Args:
            session: The interview session.
            reason: Optional reason for ending.

        Returns:
            Closing message.
        """
        transition_state(session, InterviewState.CANCELLED)
        session.ended_at = datetime.utcnow()

        closing = "The interview has been ended. Thank you for your time."
        if reason:
            closing = f"The interview has been ended. Reason: {reason}. Thank you for your time."

        message = session.add_message(ChatRole.INTERVIEWER, closing)
        return message

    # Private helper methods

    async def _generate_greeting(self, session: InterviewSession) -> str:
        """Generate personalized greeting."""
        resume = session.resume_data or {}
        job = session.job_data or {}

        prompt = GENERATE_GREETING_PROMPT.format(
            candidate_name=resume.get("name", "Candidate"),
            job_title=job.get("title", "the position"),
            company_name=job.get("company_name", "our company"),
        )

        messages = [LLMMessage(role="user", content=prompt)]
        start = time.time()
        response, usage = await self.llm.generate_with_usage(messages)
        latency = int((time.time() - start) * 1000)
        self._log_llm_call("greeting", messages, response, usage, latency)
        return response

    async def _generate_preplan(self, session: InterviewSession) -> list[PrePlanner]:
        """Generate interview topic plan."""
        resume = session.resume_data or {}
        job = session.job_data or {}

        # Build resume summary
        resume_summary = self._build_resume_summary(resume)

        # Get job details
        question_policy = job.get("question_policy", {})
        max_questions = question_policy.get("max_questions", 10)

        prompt = PREPLAN_TOPICS_PROMPT.format(
            resume_summary=resume_summary,
            job_title=job.get("title", "Software Engineer"),
            company_name=job.get("company_name", "Company"),
            job_description=job.get("description", ""),
            job_level=job.get("level", "FRESHER"),
            primary_skills=", ".join(job.get("primary_skills", [])),
            secondary_skills=", ".join(job.get("secondary_have", [])),
            experience_required=job.get("expirence", "0-2 years"),
            max_questions=max_questions,
        )

        messages = [
            LLMMessage(role="system", content="You are an expert technical interviewer."),
            LLMMessage(role="user", content=prompt),
        ]

        # Get structured response
        start = time.time()
        response, usage = await self.llm.generate_with_usage(messages)
        latency = int((time.time() - start) * 1000)
        self._log_llm_call("preplan", messages, response, usage, latency)

        # Parse the response (extract JSON from possible markdown)
        try:
            cleaned = extract_json_from_response(response)
            data = json.loads(cleaned)
            if isinstance(data, list):
                return [PrePlanner(**item) for item in data]
            return []
        except (json.JSONDecodeError, ValueError):
            # Fallback: create default plan from primary skills
            primary_skills = job.get("primary_skills", ["General"])[:5]
            return [
                PrePlanner(
                    serial=i + 1,
                    skill=skill,
                    difficulty=DifficultyLevel.EASY,
                )
                for i, skill in enumerate(primary_skills)
            ]

    async def _generate_first_question(self, session: InterviewSession) -> Question:
        """Generate the first question based on preplanned topics."""
        if not session.preplanned_topics:
            # Fallback if no preplan
            return Question(
                id=str(uuid4()),
                text="Tell me about your experience and what interests you about this role.",
                type="main",
                expected_concepts=["experience", "motivation", "role_fit"],
                skill="General",
                difficulty=DifficultyLevel.EASY,
                is_coding=False,
                problem_statement=None,
            )

        first_topic = session.preplanned_topics[0]
        return await self._generate_question_for_topic(session, first_topic, "main")

    async def _generate_next_question(self, session: InterviewSession) -> Question:
        """Generate the next question based on current state."""
        if session.current_topic_index >= len(session.preplanned_topics):
            # No more topics - this shouldn't happen normally
            return Question(
                id=str(uuid4()),
                text="Is there anything else you'd like to share about your experience?",
                type="main",
                expected_concepts=["closing"],
                is_coding=False,
                problem_statement=None,
                skill="General",
                difficulty=DifficultyLevel.EASY,
            )

        current_topic = session.preplanned_topics[session.current_topic_index]
        question_type = "followup" if session.state == InterviewState.FOLLOW_UP else "main"

        return await self._generate_question_for_topic(session, current_topic, question_type)

    async def _generate_question_for_topic(
        self,
        session: InterviewSession,
        topic: dict,
        question_type: str,
        force_conceptual: bool = False,
    ) -> Question:
        """Generate a question for a specific topic.

        Args:
            session: The interview session.
            topic: The topic dict with skill and difficulty.
            question_type: "main" or "followup".
            force_conceptual: If True, always generate conceptual question (for follow-ups).
        """
        resume = session.resume_data or {}
        job = session.job_data or {}

        # Build conversation history (last 4 messages)
        history = ""
        for msg in session.messages[-4:]:
            role = "Interviewer" if msg.role == ChatRole.INTERVIEWER else "Candidate"
            history += f"{role}: {msg.content}\n"

        # Get difficulty value - handle both enum and string
        difficulty_raw = topic.get("difficulty", "EASY")
        if hasattr(difficulty_raw, 'value'):
            difficulty = difficulty_raw.value  # It's an enum
        elif isinstance(difficulty_raw, str) and difficulty_raw.startswith("DifficultyLevel."):
            difficulty = difficulty_raw.replace("DifficultyLevel.", "")
        else:
            difficulty = str(difficulty_raw)

        # Build job requirements summary
        job_requirements = self._build_job_requirements(job)

        # CODE-BASED DECISION: Determine if this should be a coding question
        # Only main questions can be coding questions, and only ~15% of the time
        # Follow-ups are always conceptual
        if force_conceptual or question_type == "followup":
            is_coding = False
        else:
            # 15% probability for coding questions on main questions
            is_coding = random.randint(0, 99) < 15

        # Select format instructions and output format based on is_coding decision
        if is_coding:
            question_format = "CODING"
            format_instructions = CODING_FORMAT_INSTRUCTIONS
            output_format = CODING_OUTPUT_FORMAT.format(
                question_type=question_type,
                skill=topic.get("skill", "General"),
                difficulty=difficulty,
            )
        else:
            question_format = "CONCEPTUAL"
            format_instructions = CONCEPTUAL_FORMAT_INSTRUCTIONS
            output_format = CONCEPTUAL_OUTPUT_FORMAT.format(
                question_type=question_type,
                skill=topic.get("skill", "General"),
                difficulty=difficulty,
            )

        prompt = GENERATE_QUESTION_PROMPT.format(
            job_title=job.get("title", "the position"),
            job_level=job.get("level", "FRESHER"),
            job_requirements=job_requirements,
            skill=topic.get("skill", "General"),
            difficulty=difficulty,
            question_type=question_type,
            question_format=question_format,
            format_instructions=format_instructions,
            output_format=output_format,
            candidate_context=self._build_resume_summary(resume),
            conversation_history=history or "No previous conversation.",
        )

        messages = [
            LLMMessage(role="system", content="You are a technical interviewer."),
            LLMMessage(role="user", content=prompt),
        ]

        start = time.time()
        response, usage = await self.llm.generate_with_usage(messages)
        latency = int((time.time() - start) * 1000)
        self._log_llm_call("question", messages, response, usage, latency)

        try:
            cleaned = extract_json_from_response(response)
            data = json.loads(cleaned)
            result = Question(**data)
            return result
        except json.JSONDecodeError as e:
            print(f"[DEBUG] Question JSON decode error: {e}")
        except Exception as e:
            print(f"[DEBUG] Question validation error: {type(e).__name__}: {e}")

        # Fallback question - try to be more contextual using resume data
        # Fallback questions are always conceptual (is_coding=False)
        skill = topic.get('skill', 'this technology')
        resume = session.resume_data or {}

        # Try to find a project to reference
        projects = resume.get("projects", [])
        if projects and isinstance(projects, list) and len(projects) > 0:
            project = projects[0]
            if isinstance(project, dict):
                project_name = project.get("name", "")
                if project_name:
                    return Question(
                        id=str(uuid4()),
                        text=f"I noticed you worked on {project_name}. How did {skill} concepts come into play in that project? What approach did you take?",
                        type=question_type,
                        expected_concepts=["experience", "practical_knowledge"],
                        skill=topic.get("skill", "General"),
                        difficulty=DifficultyLevel(topic.get("difficulty", "EASY")),
                        is_coding=False,
                        problem_statement=None,
                    )

        # Generic fallback if no project found
        return Question(
            id=str(uuid4()),
            text=f"Let's talk about {skill}. What's been your hands-on experience with it? Any interesting problems you've solved?",
            type=question_type,
            expected_concepts=["experience", "practical_knowledge"],
            skill=topic.get("skill", "General"),
            difficulty=DifficultyLevel(topic.get("difficulty", "EASY")),
            is_coding=False,
            problem_statement=None,
        )

    async def _evaluate_and_decide(
        self,
        session: InterviewSession,
        candidate_response: str,
    ) -> LLM_Response:
        """Evaluate response and decide next action.

        The evaluation is done by LLM, but action decision is made in code.
        """
        question = session.current_question or {}

        # Step 1: Get evaluation from LLM (evaluation only, no action decision)
        prompt = EVALUATE_RESPONSE_PROMPT.format(
            question_text=question.get("text", ""),
            skill=question.get("skill", "General"),
            expected_concepts=", ".join(question.get("expected_concepts", [])),
            candidate_response=candidate_response,
            question_id=question.get("id", str(uuid4())),
            question_type=question.get("type", "main"),
        )

        messages = [
            LLMMessage(role="system", content="You are an expert technical interviewer evaluating candidate responses."),
            LLMMessage(role="user", content=prompt),
        ]

        start = time.time()
        response, usage = await self.llm.generate_with_usage(messages)
        latency = int((time.time() - start) * 1000)
        self._log_llm_call("evaluate", messages, response, usage, latency)

        # Parse evaluation
        try:
            cleaned = extract_json_from_response(response)
            data = json.loads(cleaned)
            evaluation = QuestionEvaluation(**data)
        except (json.JSONDecodeError, Exception) as e:
            print(f"[DEBUG] Evaluation parse error: {type(e).__name__}: {e}")
            print(f"[DEBUG] Raw response: {response[:500]}...")
            # Fallback evaluation
            from models.llm import QuestionRef, ConfidenceLevel
            evaluation = QuestionEvaluation(
                question_ref=QuestionRef(
                    question_id=question.get("id", str(uuid4())),
                    parent_question_id=None,
                    question_type=question.get("type", "main"),
                ),
                skill=question.get("skill", "General"),
                correctness_score=0.5,
                depth_score=0.5,
                communication_score=0.5,
                observed_concepts=[],
                missing_concepts=[],
                confidence_level=ConfidenceLevel.LOW,
                notes="Fallback evaluation due to parsing error",
            )

        # Step 2: CODE-BASED ACTION DECISION
        action, reason, next_question = await self._decide_next_action(
            session, candidate_response, evaluation, question
        )

        return LLM_Response(
            action=action,
            evaluation=evaluation,
            next_question=next_question,
            reason=reason,
        )

    async def _decide_next_action(
        self,
        session: InterviewSession,
        candidate_response: str,
        evaluation: QuestionEvaluation,
        _question: dict,  # Unused, kept for potential future use
    ) -> tuple[QuestionAction, str, Question | None]:
        """Decide next action based on evaluation and interview state.

        This is the CODE-BASED decision logic, replacing LLM-based probability.

        Returns:
            Tuple of (action, reason, next_question or None)
        """
        job = session.job_data or {}
        question_policy = job.get("question_policy", {})
        max_questions = question_policy.get("max_questions", 10)
        max_followups = question_policy.get("max_followup_per_question", 2)

        # Check for explicit skip/end request from candidate
        response_lower = candidate_response.strip().lower()
        skip_phrases = ["skip", "next", "move on", "next question"]
        is_skip_request = any(phrase in response_lower for phrase in skip_phrases)

        # Calculate weighted score for quality assessment
        weights = job.get("evaluation_rubric", {})
        correctness_w = weights.get("correctness", 0.5)
        depth_w = weights.get("depth", 0.3)
        communication_w = weights.get("communication", 0.2)

        weighted_score = (
            evaluation.correctness_score * correctness_w +
            evaluation.depth_score * depth_w +
            evaluation.communication_score * communication_w
        )

        # Check if response is too short or unclear
        response_too_short = len(candidate_response.strip()) < 30
        response_unclear = evaluation.confidence_level.value == "LOW"

        # DECISION LOGIC (check in order):

        # 1. END_INTERVIEW - if question limit reached or all topics covered
        if session.questions_asked >= max_questions:
            return QuestionAction.END_INTERVIEW, "Question limit reached", None

        if session.current_topic_index >= len(session.preplanned_topics) - 1:
            # On last topic, only end if follow-up limit also reached
            if session.followups_for_current >= max_followups:
                return QuestionAction.END_INTERVIEW, "All topics covered", None

        # 2. MOVE_TO_NEXT_QUESTION - if any of these are true:
        #    - Candidate requested skip
        #    - Response too short/unclear
        #    - Follow-up limit reached
        #    - Skill sufficiently assessed (high score)
        if is_skip_request:
            return QuestionAction.MOVE_TO_NEXT_QUESTION, "Candidate requested to move on", None

        if session.followups_for_current >= max_followups:
            return QuestionAction.MOVE_TO_NEXT_QUESTION, "Follow-up limit reached", None

        if response_too_short or response_unclear:
            return QuestionAction.MOVE_TO_NEXT_QUESTION, "Response too brief to follow up on", None

        if weighted_score >= 0.85:
            return QuestionAction.MOVE_TO_NEXT_QUESTION, "Skill sufficiently demonstrated", None

        # 3. ASK_FOLLOWUP - 35% probability if conditions allow
        can_followup = session.followups_for_current < max_followups
        within_limit = session.questions_asked < max_questions
        response_worth_exploring = weighted_score >= 0.3 and weighted_score < 0.85

        if can_followup and within_limit and response_worth_exploring:
            # CODE-BASED 35% probability for follow-up
            if random.randint(0, 99) < 35:
                # Generate follow-up question (always conceptual)
                current_topic = session.preplanned_topics[session.current_topic_index]
                followup = await self._generate_question_for_topic(
                    session, current_topic, "followup", force_conceptual=True
                )
                return QuestionAction.ASK_FOLLOWUP, "Exploring response further", followup

        # Default: move to next question
        return QuestionAction.MOVE_TO_NEXT_QUESTION, "Moving to next topic", None

    def _create_fallback_response(
        self, session: InterviewSession, question: dict, candidate_response: str = ""
    ) -> LLM_Response:
        """Create a fallback LLM response when parsing fails."""
        from models.llm import QuestionRef, ConfidenceLevel

        job = session.job_data or {}
        question_policy = job.get("question_policy", {})
        max_followups = question_policy.get("max_followup_per_question", 2)

        # Decide action based on follow-up limits and randomness (35% follow-up chance)
        can_followup = session.followups_for_current < max_followups
        max_questions = question_policy.get("max_questions", 10)
        within_question_limit = session.questions_asked < max_questions
        followup_seed = random.randint(0, 99)

        # Check if response is meaningful (not gibberish or end request)
        response_lower = candidate_response.strip().lower()
        is_end_request = any(word in response_lower for word in ["end", "stop", "skip", "next", "move on"])
        response_is_meaningful = len(candidate_response.strip()) > 20 and not is_end_request

        if can_followup and within_question_limit and followup_seed < 35 and response_is_meaningful:
            action = QuestionAction.ASK_FOLLOWUP
            reason = "Fallback: asking follow-up to explore further"

            # Generate a simple contextual follow-up (always conceptual, not coding)
            skill = question.get("skill", "this topic")
            next_question = Question(
                id=str(uuid4()),
                text=f"Interesting! Can you walk me through a specific example where you applied that? What was the outcome?",
                type="followup",
                expected_concepts=["depth", "practical_application"],
                skill=skill,
                difficulty=DifficultyLevel(question.get("difficulty", "EASY")),
                is_coding=False,
                problem_statement=None,
            )
        else:
            action = QuestionAction.MOVE_TO_NEXT_QUESTION
            reason = "Fallback: moving to next question"
            next_question = None

        return LLM_Response(
            action=action,
            evaluation=QuestionEvaluation(
                question_ref=QuestionRef(
                    question_id=question.get("id", str(uuid4())),
                    parent_question_id=None,
                    question_type="main",
                ),
                skill=question.get("skill", "General"),
                correctness_score=0.5,
                depth_score=0.5,
                communication_score=0.5,
                observed_concepts=[],
                missing_concepts=[],
                confidence_level=ConfidenceLevel.LOW,
                notes="Fallback evaluation due to parsing error",
            ),
            next_question=next_question,
            reason=reason,
        )

    async def _conclude_interview(self, session: InterviewSession) -> ChatMessage:
        """Generate conclusion and end interview."""
        # Only transition if not already concluding
        if session.state != InterviewState.CONCLUDING:
            transition_state(session, InterviewState.CONCLUDING)

        resume = session.resume_data or {}
        job = session.job_data or {}

        # Get topics covered
        topics_covered = [t.get("skill", "Unknown") for t in session.preplanned_topics[:session.current_topic_index + 1]]

        prompt = GENERATE_CONCLUSION_PROMPT.format(
            candidate_name=resume.get("name", "Candidate"),
            job_title=job.get("title", "the position"),
            topics_covered=", ".join(topics_covered) if topics_covered else "various topics",
            total_questions=session.questions_asked,
        )

        messages = [LLMMessage(role="user", content=prompt)]
        start = time.time()
        conclusion, usage = await self.llm.generate_with_usage(messages)
        latency = int((time.time() - start) * 1000)
        self._log_llm_call("conclusion", messages, conclusion, usage, latency)

        transition_state(session, InterviewState.COMPLETED)
        session.ended_at = datetime.utcnow()

        message = session.add_message(ChatRole.INTERVIEWER, conclusion)

        # Save session data and LLM logs to JSON files
        self._save_session_to_file(session)
        self._save_llm_log_to_file(session)

        return message

    def _serialize_value(self, value):
        """Recursively serialize a value, handling enums and nested structures."""
        from enum import Enum

        if value is None:
            return None
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        if isinstance(value, (str, int, float, bool)):
            return value
        # Fallback: convert to string
        return str(value)

    def _save_session_to_file(self, session: InterviewSession) -> None:
        """Save completed session data to a JSON file for debugging/analysis."""
        try:
            # Create sessions directory if it doesn't exist
            sessions_dir = Path(__file__).parent.parent.parent / "session_logs"
            sessions_dir.mkdir(exist_ok=True)

            # Create filename with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            resume = session.resume_data or {}
            candidate_name = resume.get("name", "unknown").replace(" ", "_")
            filename = f"{timestamp}_{candidate_name}_{session.session_id[:8]}.json"

            # Build session data
            session_data = {
                "session_id": session.session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "candidate": {
                    "name": resume.get("name", "Unknown"),
                    "email": resume.get("email", ""),
                },
                "job": self._serialize_value(session.job_data),
                "state": session.state.value,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "duration_seconds": (
                    (session.ended_at - session.started_at).total_seconds()
                    if session.started_at and session.ended_at
                    else None
                ),
                "questions_asked": session.questions_asked,
                "preplanned_topics": self._serialize_value(session.preplanned_topics),
                "messages": [
                    {
                        "id": msg.id,
                        "role": msg.role.value,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "metadata": self._serialize_value(msg.metadata),
                    }
                    for msg in session.messages
                ],
                "evaluations": self._serialize_value(session.evaluations),
            }

            # Write to file
            filepath = sessions_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            print(f"[INFO] Session saved to: {filepath}")

        except Exception as e:
            print(f"[ERROR] Failed to save session to file: {e}")

    def _save_llm_log_to_file(self, session: InterviewSession) -> None:
        """Save LLM call logs to a separate JSON file for cost/usage analysis."""
        try:
            # Create llm_logs directory if it doesn't exist
            logs_dir = Path(__file__).parent.parent.parent / "llm_logs"
            logs_dir.mkdir(exist_ok=True)

            # Create filename with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            resume = session.resume_data or {}
            candidate_name = resume.get("name", "unknown").replace(" ", "_")
            filename = f"{timestamp}_{candidate_name}_{session.session_id[:8]}_llm.json"

            # Calculate totals
            total_input = sum(log.input_tokens for log in self.llm_logs)
            total_output = sum(log.output_tokens for log in self.llm_logs)
            total_latency = sum(log.latency_ms for log in self.llm_logs)

            # Build log data
            log_data = {
                "session_id": session.session_id,
                "timestamp": datetime.utcnow().isoformat(),
                "candidate_name": resume.get("name", "Unknown"),
                "model": self.llm.config.model,
                "summary": {
                    "total_calls": len(self.llm_logs),
                    "total_input_tokens": total_input,
                    "total_output_tokens": total_output,
                    "total_tokens": total_input + total_output,
                    "total_latency_ms": total_latency,
                    "avg_latency_ms": total_latency // len(self.llm_logs) if self.llm_logs else 0,
                },
                "calls": [log.to_dict() for log in self.llm_logs],
            }

            # Write to file
            filepath = logs_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)

            print(f"[INFO] LLM logs saved to: {filepath}")

        except Exception as e:
            print(f"[ERROR] Failed to save LLM logs to file: {e}")

    def _build_job_requirements(self, job: dict) -> str:
        """Build a concise job requirements summary for question context."""
        parts = []

        if job.get("description"):
            # Truncate description to key points
            desc = job["description"][:300]
            parts.append(f"Role: {desc}")

        primary = job.get("primary_skills", [])
        if primary:
            parts.append(f"Primary skills: {', '.join(primary[:5])}")

        secondary = job.get("secondary_have", [])
        if secondary:
            parts.append(f"Secondary skills: {', '.join(secondary[:3])}")

        if job.get("expirence"):
            parts.append(f"Experience: {job['expirence']}")

        return " | ".join(parts) if parts else "General software engineering role"

    def _build_resume_summary(self, resume: dict) -> str:
        """Build a detailed resume summary for prompts - includes project details and raw text excerpt."""
        parts = []

        # === STRUCTURED DATA SECTION ===
        parts.append("## STRUCTURED CANDIDATE INFO:")

        if resume.get("name"):
            parts.append(f"Name: {resume['name']}")

        if resume.get("role"):
            parts.append(f"Current Role: {resume['role']}")

        if resume.get("experience"):
            exp = resume["experience"]
            if isinstance(exp, dict):
                years = exp.get("total_years", 0)
                companies = exp.get("companies", [])
                parts.append(f"Experience: {years} years")
                if companies:
                    parts.append(f"Companies: {', '.join(companies[:3])}")

        if resume.get("skills"):
            skills = resume["skills"][:15]  # Top 15 skills
            parts.append(f"Skills: {', '.join(skills)}")

        if resume.get("education"):
            edu = resume["education"]
            if isinstance(edu, list) and edu:
                latest = edu[0]
                if isinstance(latest, dict):
                    degree = latest.get("degree", "")
                    college = latest.get("college_name", "")
                    parts.append(f"Education: {degree} from {college}")

        # Include detailed project information for contextual questions
        if resume.get("projects"):
            projects = resume["projects"]
            if isinstance(projects, list) and projects:
                parts.append("\n## PROJECTS (USE THESE FOR CONTEXTUAL QUESTIONS!):")
                for i, project in enumerate(projects[:5], 1):  # Up to 5 projects
                    if isinstance(project, dict):
                        name = project.get("name", f"Project {i}")
                        description = project.get("description", "")
                        tech = project.get("technologies", [])

                        parts.append(f"\n### Project {i}: {name}")
                        if description:
                            parts.append(f"Description: {description[:300]}")  # More description
                        if tech:
                            tech_list = tech if isinstance(tech, list) else [tech]
                            parts.append(f"Technologies: {', '.join(tech_list[:10])}")

        # Include work experience details
        if resume.get("work_experience"):
            work = resume["work_experience"]
            if isinstance(work, list) and work:
                parts.append("\n## WORK EXPERIENCE:")
                for i, job in enumerate(work[:3], 1):  # Up to 3 jobs
                    if isinstance(job, dict):
                        company = job.get("company", "Unknown")
                        role = job.get("role", job.get("title", "Unknown"))
                        parts.append(f"- {role} at {company}")

        # Include summary if available
        if resume.get("summary"):
            parts.append(f"\n## CANDIDATE SUMMARY:\n{resume['summary'][:500]}")

        # === RAW TEXT EXCERPT SECTION ===
        # Include condensed raw text for additional context the parser might have missed
        if resume.get("raw_text"):
            raw_text = resume["raw_text"]
            # Clean and condense the raw text
            condensed = self._condense_raw_text(raw_text, max_chars=1500)
            if condensed:
                parts.append("\n## RAW RESUME EXCERPT (for additional context):")
                parts.append(condensed)

        return "\n".join(parts) if parts else "No resume data available"

    def _condense_raw_text(self, raw_text: str, max_chars: int = 1500) -> str:
        """Condense raw resume text to extract the most relevant parts."""
        if not raw_text:
            return ""

        # Clean up the text
        lines = raw_text.split('\n')
        # Remove empty lines and very short lines (likely formatting artifacts)
        lines = [line.strip() for line in lines if line.strip() and len(line.strip()) > 5]

        # Join and truncate
        condensed = '\n'.join(lines)

        # If too long, try to get the most important parts
        if len(condensed) > max_chars:
            # Prioritize the first part (usually summary/intro) and middle part (usually experience/projects)
            first_part = condensed[:max_chars // 2]
            # Find a good break point
            last_newline = first_part.rfind('\n')
            if last_newline > max_chars // 3:
                first_part = first_part[:last_newline]

            # Get a middle section
            middle_start = len(condensed) // 3
            middle_part = condensed[middle_start:middle_start + max_chars // 2]
            first_newline = middle_part.find('\n')
            if first_newline > 0:
                middle_part = middle_part[first_newline + 1:]
            last_newline = middle_part.rfind('\n')
            if last_newline > 0:
                middle_part = middle_part[:last_newline]

            condensed = first_part + "\n...\n" + middle_part

        return condensed[:max_chars]
