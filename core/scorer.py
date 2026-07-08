"""
Resume Scoring Engine: evaluates a tailored resume against a job description
across 5 dimensions from an ATS and recruiter perspective.
"""

import json
from .llm import chat_json

SCORING_PROMPT = """You are a senior ATS system analyst and expert technical recruiter.
Score the following tailored resume against the job description.

## JOB DESCRIPTION
{jd_text}

## JOB DESCRIPTION ANALYSIS (extracted signals)
{jd_analysis}

## TAILORED RESUME
{tailored_resume}

## SCORING INSTRUCTIONS
Score across exactly 5 dimensions. Be strict and precise. A score of 100 means this resume
would rank #1 in any ATS system and immediately impress a human recruiter.

Return a JSON object with this EXACT structure:
{{
  "keyword_match": {{
    "score": <0-25 integer>,
    "max": 25,
    "matched_keywords": ["keywords found in resume"],
    "missing_keywords": ["important keywords NOT in resume"],
    "notes": "brief explanation"
  }},
  "skills_alignment": {{
    "score": <0-25 integer>,
    "max": 25,
    "aligned_skills": ["skills that match JD requirements"],
    "missing_skills": ["required skills not demonstrated"],
    "notes": "brief explanation"
  }},
  "role_level_fit": {{
    "score": <0-20 integer>,
    "max": 20,
    "signals_present": ["seniority/scope signals found"],
    "signals_missing": ["expected signals not found"],
    "notes": "brief explanation"
  }},
  "impact_quantification": {{
    "score": <0-15 integer>,
    "max": 15,
    "strong_bullets": ["examples of well-quantified achievements"],
    "weak_bullets": ["bullets that lack metrics or impact"],
    "notes": "brief explanation"
  }},
  "formatting_readability": {{
    "score": <0-15 integer>,
    "max": 15,
    "strengths": ["formatting strengths"],
    "issues": ["formatting issues"],
    "notes": "brief explanation"
  }},
  "total": <sum of all scores, 0-100>,
  "grade": "<A+/A/A-/B+/B/B-/C/D based on total>",
  "recruiter_verdict": "one sentence verdict from a recruiter's perspective",
  "ats_verdict": "one sentence verdict from an ATS system perspective",
  "diagnosis": "detailed paragraph explaining why the score is what it is and what the biggest issues are",
  "refinement_instructions": "specific, actionable instructions for improving the resume to score higher"
}}"""


def score_resume(tailored_resume: str, jd_text: str, jd_analysis: dict) -> dict:
    """
    Score a tailored resume against the job description.
    Returns a structured scoring result with diagnosis and refinement instructions.
    Uses DeepSeek-R1 for superior reasoning and stricter evaluation.
    """
    messages = [
        {
            "role": "system",
            "content": "You are a strict ATS scoring system and expert recruiter. Score resumes precisely. Always respond with valid JSON."
        },
        {
            "role": "user",
            "content": SCORING_PROMPT.format(
                jd_text=jd_text,
                jd_analysis=json.dumps(jd_analysis, indent=2),
                tailored_resume=tailored_resume
            )
        }
    ]
    # Use DeepSeek-R1 for scoring to ensure adversarial validation
    result = chat_json(messages, temperature=0.1, model="deepseek-reasoner")

    # Ensure total is computed correctly
    computed_total = (
        result.get("keyword_match", {}).get("score", 0) +
        result.get("skills_alignment", {}).get("score", 0) +
        result.get("role_level_fit", {}).get("score", 0) +
        result.get("impact_quantification", {}).get("score", 0) +
        result.get("formatting_readability", {}).get("score", 0)
    )
    result["total"] = computed_total

    # Assign grade
    if computed_total >= 95:
        result["grade"] = "A+"
    elif computed_total >= 90:
        result["grade"] = "A"
    elif computed_total >= 85:
        result["grade"] = "A-"
    elif computed_total >= 80:
        result["grade"] = "B+"
    elif computed_total >= 75:
        result["grade"] = "B"
    elif computed_total >= 70:
        result["grade"] = "B-"
    elif computed_total >= 60:
        result["grade"] = "C"
    else:
        result["grade"] = "D"

    return result
