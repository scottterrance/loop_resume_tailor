"""
Dynamic Prompt Engine: generates tailoring prompts specific to each
resume + JD pair, and refines them based on scoring feedback.
"""

import json
from .llm import chat


INITIAL_PROMPT_TEMPLATE = """You are a world-class resume writer and ATS optimization expert.

## MISSION
Generate the ultimate tailored resume prompt for this specific candidate applying to this specific role.
The prompt will be used to instruct an AI to rewrite the resume for maximum ATS score and recruiter impact.

## JOB DESCRIPTION ANALYSIS
{jd_analysis}

## CANDIDATE RESUME ANALYSIS
{resume_analysis}

## GAP ANALYSIS
{gap_analysis}

## YOUR TASK
Generate a comprehensive, highly specific tailoring prompt that:
1. Addresses every critical gap identified
2. Maximizes keyword density for the specific ATS keywords
3. Repositions the candidate's experience to match the role
4. Instructs on quantification improvements
5. Specifies exact formatting requirements
6. Includes the candidate's actual experience details to preserve authenticity

The prompt should be detailed, actionable, and specific to THIS candidate and THIS role.
Write the prompt as if you are giving instructions to the best resume writer in the world.
The prompt must result in a resume that ranks #1 in the recruiter's applicant list.

Output ONLY the tailoring prompt text, no preamble or explanation."""


REFINEMENT_PROMPT_TEMPLATE = """You are a world-class resume optimization expert.

## CONTEXT
A tailored resume was generated using the following prompt:
{previous_prompt}

## SCORING RESULTS
{score_result}

## DIAGNOSIS
The resume scored {total_score}/100. Here is what needs improvement:
{diagnosis}

## YOUR TASK
Rewrite and improve the tailoring prompt to address ALL identified weaknesses.
Focus especially on:
{refinement_focus}

The new prompt must be more specific, more targeted, and must fix every identified gap.
Output ONLY the improved tailoring prompt text, no preamble or explanation."""


def generate_initial_prompt(jd_analysis: dict, resume_analysis: dict, gap_analysis: dict) -> str:
    """Generate the initial tailoring prompt based on analysis."""
    messages = [
        {
            "role": "system",
            "content": "You are the world's best resume optimization expert. You write precise, actionable prompts that produce ATS-perfect resumes."
        },
        {
            "role": "user",
            "content": INITIAL_PROMPT_TEMPLATE.format(
                jd_analysis=json.dumps(jd_analysis, indent=2),
                resume_analysis=json.dumps(resume_analysis, indent=2),
                gap_analysis=json.dumps(gap_analysis, indent=2)
            )
        }
    ]
    return chat(messages, temperature=0.4)


def refine_prompt(previous_prompt: str, score_result: dict, iteration: int) -> str:
    """Refine the tailoring prompt based on scoring feedback."""
    total_score = score_result.get("total", 0)
    diagnosis = score_result.get("diagnosis", "")
    refinement_instructions = score_result.get("refinement_instructions", "")

    # Build focused refinement areas from low-scoring dimensions
    focus_areas = []
    dimensions = [
        ("keyword_match", "keyword_match", "Improve ATS keyword density and placement"),
        ("skills_alignment", "skills_alignment", "Better align skills section with JD requirements"),
        ("role_level_fit", "role_level_fit", "Adjust seniority signals and scope of responsibilities"),
        ("impact_quantification", "impact_quantification", "Add more quantified achievements and metrics"),
        ("formatting_readability", "formatting_readability", "Improve formatting, structure, and ATS readability"),
    ]

    for key, _, label in dimensions:
        dim = score_result.get(key, {})
        if isinstance(dim, dict):
            score = dim.get("score", 0)
            max_score = dim.get("max", 25)
            if score < max_score * 0.85:
                focus_areas.append(f"- {label} (scored {score}/{max_score})")

    refinement_focus = "\n".join(focus_areas) if focus_areas else refinement_instructions

    messages = [
        {
            "role": "system",
            "content": "You are the world's best resume optimization expert. You iteratively improve resume prompts until they produce perfect results."
        },
        {
            "role": "user",
            "content": REFINEMENT_PROMPT_TEMPLATE.format(
                previous_prompt=previous_prompt,
                score_result=json.dumps(score_result, indent=2),
                total_score=total_score,
                diagnosis=diagnosis,
                refinement_focus=refinement_focus
            )
        }
    ]
    return chat(messages, temperature=0.3)
