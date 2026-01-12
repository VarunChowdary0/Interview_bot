from typing import Optional
from datetime import datetime
from collections import defaultdict
import json

from models.interview import InterviewSession, ChatRole
from models.report import InterviewReport, SkillAssessment, InterviewSummary
from models.common import DifficultyLevel
from services.llm.base import LLMProvider, LLMMessage
from services.llm.prompts import GENERATE_REPORT_INSIGHTS_PROMPT


class ReportGenerator:
    """Generates interview reports from completed sessions."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm = llm_provider

    async def generate(self, session: InterviewSession) -> InterviewReport:
        """Generate a complete interview report.

        Args:
            session: The completed interview session.

        Returns:
            InterviewReport with all assessments and insights.
        """
        resume = session.resume_data or {}
        job = session.job_data or {}

        # Calculate skill assessments
        skill_assessments = self._calculate_skill_assessments(session)

        # Calculate summary
        summary = self._calculate_summary(session, skill_assessments, job)

        # Generate AI insights if LLM is available
        insights = await self._generate_insights(session, skill_assessments, summary)

        # Build conversation history for audit
        conversation_history = [
            {
                "id": msg.id,
                "role": msg.role.value,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "metadata": msg.metadata,
            }
            for msg in session.messages
        ]

        return InterviewReport(
            session_id=session.session_id,
            candidate_name=resume.get("name", "Unknown"),
            candidate_email=resume.get("email", ""),
            job_title=job.get("title", "Unknown Position"),
            company_name=job.get("company_name", "Unknown Company"),
            interview_date=session.started_at or session.created_at,
            skill_assessments=skill_assessments,
            summary=summary,
            conversation_history=conversation_history,
            all_evaluations=session.evaluations,
            strengths_summary=insights.get("strengths_summary", ""),
            areas_for_improvement=insights.get("areas_for_improvement", ""),
            hiring_recommendation=insights.get("hiring_recommendation", ""),
            detailed_feedback=insights.get("detailed_feedback"),
        )

    def _calculate_skill_assessments(self, session: InterviewSession) -> list[SkillAssessment]:
        """Calculate per-skill assessments from evaluations."""
        # Group evaluations by skill
        skill_evals: dict[str, list[dict]] = defaultdict(list)

        for eval_dict in session.evaluations:
            skill = eval_dict.get("skill", "General")
            skill_evals[skill].append(eval_dict)

        assessments = []

        for skill, evals in skill_evals.items():
            if not evals:
                continue

            # Calculate averages
            correctness_scores = [e.get("correctness_score", 0) for e in evals]
            depth_scores = [e.get("depth_score", 0) for e in evals]
            communication_scores = [e.get("communication_score", 0) for e in evals]

            avg_correctness = sum(correctness_scores) / len(correctness_scores)
            avg_depth = sum(depth_scores) / len(depth_scores)
            avg_communication = sum(communication_scores) / len(communication_scores)

            # Overall score (weighted average based on default rubric)
            overall = 0.5 * avg_correctness + 0.3 * avg_depth + 0.2 * avg_communication

            # Find max difficulty reached
            difficulties = []
            for e in evals:
                qref = e.get("question_ref", {})
                # Try to find difficulty from the question
                # For now, default to MEDIUM
                difficulties.append(DifficultyLevel.MEDIUM)

            max_difficulty = max(difficulties, key=lambda d: ["EASY", "MEDIUM", "HARD"].index(d.value))

            # Collect strengths and weaknesses from observed/missing concepts
            all_observed = []
            all_missing = []
            for e in evals:
                all_observed.extend(e.get("observed_concepts", []))
                all_missing.extend(e.get("missing_concepts", []))

            # Deduplicate and limit
            strengths = list(set(all_observed))[:5]
            weaknesses = list(set(all_missing))[:5]

            assessments.append(SkillAssessment(
                skill=skill,
                questions_asked=len(evals),
                average_correctness=round(avg_correctness, 2),
                average_depth=round(avg_depth, 2),
                average_communication=round(avg_communication, 2),
                overall_score=round(overall, 2),
                difficulty_reached=max_difficulty,
                strengths=strengths,
                weaknesses=weaknesses,
            ))

        return assessments

    def _calculate_summary(
        self,
        session: InterviewSession,
        skill_assessments: list[SkillAssessment],
        job: dict,
    ) -> InterviewSummary:
        """Calculate interview summary."""
        # Calculate duration
        if session.started_at and session.ended_at:
            duration = (session.ended_at - session.started_at).total_seconds() / 60
        else:
            duration = 0.0

        # Count followups
        total_followups = 0
        for msg in session.messages:
            if msg.metadata and msg.metadata.get("question_type") == "followup":
                total_followups += 1

        # Calculate overall score
        if skill_assessments:
            overall_score = sum(a.overall_score for a in skill_assessments) / len(skill_assessments)
        else:
            overall_score = 0.0

        # Check pass criteria
        pass_criteria = job.get("pass_criteria", {})
        min_score = pass_criteria.get("minimum_overall_score", 0.6)
        mandatory_skills = set(pass_criteria.get("mandatory_skills", []))

        # Check if mandatory skills are covered with passing score
        mandatory_passed = True
        if mandatory_skills:
            for assessment in skill_assessments:
                if assessment.skill in mandatory_skills:
                    if assessment.overall_score < min_score:
                        mandatory_passed = False
                        break

        pass_status = overall_score >= min_score and mandatory_passed

        # Determine recommendation
        if overall_score >= 0.85 and mandatory_passed:
            recommendation = "Strong Hire"
        elif overall_score >= 0.7 and mandatory_passed:
            recommendation = "Hire"
        elif overall_score >= 0.5:
            recommendation = "Maybe"
        else:
            recommendation = "No Hire"

        topics_covered = [a.skill for a in skill_assessments]

        return InterviewSummary(
            total_questions=session.questions_asked,
            total_followups=total_followups,
            duration_minutes=round(duration, 1),
            topics_covered=topics_covered,
            overall_score=round(overall_score, 2),
            pass_status=pass_status,
            recommendation=recommendation,
        )

    async def _generate_insights(
        self,
        session: InterviewSession,
        skill_assessments: list[SkillAssessment],
        summary: InterviewSummary,
    ) -> dict:
        """Generate AI-powered insights for the report."""
        if not self.llm:
            # Return default insights if no LLM
            return {
                "strengths_summary": "Unable to generate - LLM not available",
                "areas_for_improvement": "Unable to generate - LLM not available",
                "hiring_recommendation": summary.recommendation,
                "detailed_feedback": None,
            }

        resume = session.resume_data or {}
        job = session.job_data or {}
        pass_criteria = job.get("pass_criteria", {})

        # Format skill assessments for prompt
        skill_text = "\n".join([
            f"- {a.skill}: Score {a.overall_score:.0%}, "
            f"Correctness {a.average_correctness:.0%}, "
            f"Depth {a.average_depth:.0%}, "
            f"Communication {a.average_communication:.0%}"
            for a in skill_assessments
        ])

        prompt = GENERATE_REPORT_INSIGHTS_PROMPT.format(
            candidate_name=resume.get("name", "Candidate"),
            job_title=job.get("title", "Position"),
            company_name=job.get("company_name", "Company"),
            duration_minutes=summary.duration_minutes,
            total_questions=summary.total_questions,
            skill_assessments=skill_text,
            avg_correctness=f"{sum(a.average_correctness for a in skill_assessments) / max(len(skill_assessments), 1):.0%}",
            avg_depth=f"{sum(a.average_depth for a in skill_assessments) / max(len(skill_assessments), 1):.0%}",
            avg_communication=f"{sum(a.average_communication for a in skill_assessments) / max(len(skill_assessments), 1):.0%}",
            overall_score=f"{summary.overall_score:.0%}",
            min_score=f"{pass_criteria.get('minimum_overall_score', 0.6):.0%}",
            mandatory_skills=", ".join(pass_criteria.get("mandatory_skills", [])) or "None specified",
        )

        messages = [
            LLMMessage(role="system", content="You are an HR expert generating interview feedback."),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            response = await self.llm.generate(messages)
            data = json.loads(response)
            return {
                "strengths_summary": data.get("strengths_summary", ""),
                "areas_for_improvement": data.get("areas_for_improvement", ""),
                "hiring_recommendation": data.get("hiring_recommendation", summary.recommendation),
                "detailed_feedback": data.get("detailed_feedback"),
            }
        except (json.JSONDecodeError, Exception):
            return {
                "strengths_summary": f"Candidate demonstrated skills in: {', '.join(summary.topics_covered)}",
                "areas_for_improvement": "Review detailed evaluations for specific feedback.",
                "hiring_recommendation": summary.recommendation,
                "detailed_feedback": None,
            }
