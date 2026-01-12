"""Prompt templates for the interview bot LLM interactions.

Optimized for:
- Reduced token count (~40% reduction)
- Both resume AND job data consideration
- Creative LLM output (no fixed examples)
- Speech-friendly questions (coding questions limited to ~15%)
"""

# =============================================================================
# PREPLAN: Plans topics based on BOTH job requirements and candidate background
# =============================================================================
PREPLAN_TOPICS_PROMPT = """Plan interview topics matching job requirements to candidate background.

## Candidate Resume:
{resume_summary}

## Job Requirements:
Title: {job_title} at {company_name}
Level: {job_level}
Description: {job_description}
Primary Skills (MUST assess): {primary_skills}
Secondary Skills (if time permits): {secondary_skills}
Experience Required: {experience_required}

## Constraints:
- Max {max_questions} main questions
- Follow-ups handled separately (don't plan them)
- Each topic = one skill

## Planning Rules:
1. Prioritize PRIMARY skills that match candidate's experience
2. For each skill, find relevant candidate projects/experience to anchor questions
3. Skip skills candidate has zero background in (unless mandatory)
4. Order: strongest match first → weaker matches later

## Difficulty by Level:
- FRESHER: Start EASY, max MEDIUM
- JUNIOR: EASY or MEDIUM based on experience match
- SENIOR: Start MEDIUM, can reach HARD

## Output (JSON array only):
[{{"serial": 1, "skill": "SkillName", "difficulty": "EASY|MEDIUM|HARD"}}, ...]
"""


# =============================================================================
# GREETING: Warm opening mentioning role context
# =============================================================================
GENERATE_GREETING_PROMPT = """Generate a warm, natural interview greeting.

Candidate: {candidate_name}
Role: {job_title} at {company_name}

Requirements:
- Use first name naturally
- Mention the role briefly
- Set a relaxed, conversational tone
- 2-3 sentences max
- Plain text only (no markdown, no emojis)
- Be creative, avoid corporate scripts
"""


# =============================================================================
# QUESTION: Must consider BOTH job requirements AND candidate background
# =============================================================================
GENERATE_QUESTION_PROMPT = """Generate ONE focused interview question.

## Job Context:
Role: {job_title} | Level: {job_level}
Job Requirements: {job_requirements}

## Skill Being Assessed:
{skill} at {difficulty} difficulty

## Candidate Background (anchor questions here):
{candidate_context}

## Conversation So Far:
{conversation_history}

## Question Type: {question_type}
## Question Format: {question_format}

## QUESTION FORMAT INSTRUCTIONS:

{format_instructions}

## STRICT RULES:

1. **ANCHOR TO CANDIDATE**: Reference their actual project, role, or experience by name

2. **CONNECT TO JOB**: The question should assess skills relevant to {job_title}

3. **BANNED PATTERNS** (never use these):
   - "Tell me about..."
   - "What is..."
   - "Explain..."
   - "Describe..."
   - "Walk me through..."
   - Generic textbook questions

4. **DIFFICULTY CALIBRATION**:
   - EASY: Fundamentals in context of their work
   - MEDIUM: Problem-solving or debugging scenarios
   - HARD: Architecture decisions, trade-offs, scaling

5. **IF FOLLOWUP**: Must reference their last answer specifically, challenge or dig deeper

## Output (JSON only):
{output_format}
"""

# Format instructions based on whether it's a coding question or conceptual
CODING_FORMAT_INSTRUCTIONS = """This is a CODING QUESTION. You MUST:
- Set is_coding: true
- Provide problem_statement with clear requirements (displayed in UI)
- The "text" should be a brief verbal intro to the problem
- Keep problem_statement concise but complete"""

CONCEPTUAL_FORMAT_INSTRUCTIONS = """This is a CONCEPTUAL/DISCUSSION question for a speech-based interview.
- Set is_coding: false
- problem_statement: null
- Ask about concepts, trade-offs, debugging approaches, architecture decisions
- Questions should be answerable through discussion, not code"""

CODING_OUTPUT_FORMAT = """{{
  "id": "uuid",
  "text": "Brief verbal intro like: Here's a coding challenge based on your project...",
  "type": "{question_type}",
  "expected_concepts": ["concept1", "concept2"],
  "skill": "{skill}",
  "difficulty": "{difficulty}",
  "is_coding": true,
  "problem_statement": "**Problem**: Clear problem description\\n\\n**Input**: what they receive\\n**Output**: what to return\\n\\n**Constraints**: any limits"
}}"""

CONCEPTUAL_OUTPUT_FORMAT = """{{
  "id": "uuid",
  "text": "conversational question (spoken part)",
  "type": "{question_type}",
  "expected_concepts": ["concept1", "concept2"],
  "skill": "{skill}",
  "difficulty": "{difficulty}",
  "is_coding": false,
  "problem_statement": null
}}"""


# =============================================================================
# EVALUATE: Assess response ONLY (action decided by code)
# =============================================================================
EVALUATE_RESPONSE_PROMPT = """Score this interview response (0.0-1.0 each).

Q: {question_text}
Skill: {skill} | Expected: {expected_concepts}

Response: {candidate_response}

Output JSON only:
{{"question_ref": {{"question_id": "{question_id}", "parent_question_id": null, "question_type": "{question_type}"}}, "skill": "{skill}", "correctness_score": 0.0, "depth_score": 0.0, "communication_score": 0.0, "observed_concepts": [], "missing_concepts": [], "confidence_level": "LOW|MEDIUM|HIGH", "notes": ""}}
"""


# =============================================================================
# CONCLUSION: Professional closing
# =============================================================================
GENERATE_CONCLUSION_PROMPT = """Generate a professional interview closing.

Candidate: {candidate_name}
Role: {job_title}
Topics Covered: {topics_covered}
Total Questions: {total_questions}

Requirements:
- Thank them genuinely
- Confirm the interview is complete
- Mention next steps (report generation)
- Encouraging tone regardless of performance
- 2-3 sentences, plain text only
- Do NOT reveal any scores or decisions
"""


# =============================================================================
# REPORT: Generate insights based on data only
# =============================================================================
GENERATE_REPORT_INSIGHTS_PROMPT = """Interview report for {candidate_name} - {job_title}.
Score: {overall_score} (pass: {min_score}) | Skills: {skill_assessments}

Output JSON: {{"strengths_summary": "", "areas_for_improvement": "", "hiring_recommendation": "Strong Hire|Hire|Maybe|No Hire", "detailed_feedback": ""}}
"""
