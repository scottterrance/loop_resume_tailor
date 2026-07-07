"""
Iterative Resume Tailoring Loop.
Orchestrates the full workflow: analyze → prompt → generate → score → refine → repeat.
"""

import os
import json
from typing import Generator
from .llm import chat
from .analyzer import analyze_jd, analyze_resume, analyze_gaps
from .prompt_engine import generate_initial_prompt, refine_prompt
from .scorer import score_resume

RESUME_GENERATION_SYSTEM = """You are the world's best professional resume writer.
You create ATS-optimized, recruiter-approved resumes that get candidates to the top of the list.
Your resumes are:
- Perfectly formatted with clear sections
- Rich in relevant keywords naturally integrated
- Full of quantified achievements and impact statements
- Tailored precisely to the target role
- Professional, concise, and compelling

Always output the complete resume in clean plain text format with clear section headers."""

SCORE_TARGET = int(os.environ.get("SCORE_TARGET", "95"))
MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", "5"))


def generate_resume(base_resume: str, tailoring_prompt: str) -> str:
    """Generate a tailored resume using the provided prompt."""
    messages = [
        {"role": "system", "content": RESUME_GENERATION_SYSTEM},
        {
            "role": "user",
            "content": f"""Using the following tailoring instructions, rewrite the base resume into a perfectly tailored version.

## TAILORING INSTRUCTIONS
{tailoring_prompt}

## BASE RESUME
{base_resume}

Generate the complete tailored resume now. Output ONLY the resume content, no explanations."""
        }
    ]
    return chat(messages, temperature=0.2)


def run_tailor_loop(
    base_resume: str,
    jd_text: str,
    progress_callback=None
) -> Generator[dict, None, None]:
    """
    Run the full iterative tailoring loop.
    Yields progress events as dicts for SSE streaming.

    Event types:
    - {"type": "progress", "step": str, "message": str}
    - {"type": "analysis", "jd_analysis": dict, "resume_analysis": dict, "gap_analysis": dict}
    - {"type": "iteration", "iteration": int, "prompt": str, "resume": str, "score": dict}
    - {"type": "complete", "final_resume": str, "final_score": dict, "final_prompt": str, "iterations": list}
    - {"type": "error", "message": str}
    """

    def emit(event: dict):
        if progress_callback:
            progress_callback(event)
        return event

    try:
        # ── Step 1: Analyze JD ──────────────────────────────────────────────
        yield emit({"type": "progress", "step": "analyze_jd", "message": "Analyzing job description..."})
        jd_analysis = analyze_jd(jd_text)
        yield emit({"type": "progress", "step": "analyze_jd_done",
                    "message": f"JD analyzed: {jd_analysis.get('job_title', 'Role')} at {jd_analysis.get('company_name', 'Company')}"})

        # ── Step 2: Analyze Resume ──────────────────────────────────────────
        yield emit({"type": "progress", "step": "analyze_resume", "message": "Analyzing your resume..."})
        resume_analysis = analyze_resume(base_resume)
        yield emit({"type": "progress", "step": "analyze_resume_done",
                    "message": f"Resume analyzed: {resume_analysis.get('candidate_name', 'Candidate')} — {resume_analysis.get('years_experience', '?')} years experience"})

        # ── Step 3: Gap Analysis ────────────────────────────────────────────
        yield emit({"type": "progress", "step": "gap_analysis", "message": "Performing gap analysis..."})
        gap_analysis = analyze_gaps(jd_analysis, resume_analysis)
        initial_match = gap_analysis.get("match_percentage", 0)
        yield emit({"type": "progress", "step": "gap_analysis_done",
                    "message": f"Gap analysis complete. Initial match: {initial_match}%"})

        yield emit({
            "type": "analysis",
            "jd_analysis": jd_analysis,
            "resume_analysis": resume_analysis,
            "gap_analysis": gap_analysis
        })

        # ── Step 4: Generate Initial Prompt ────────────────────────────────
        yield emit({"type": "progress", "step": "generate_prompt", "message": "Generating tailored prompt..."})
        current_prompt = generate_initial_prompt(jd_analysis, resume_analysis, gap_analysis)
        yield emit({"type": "progress", "step": "generate_prompt_done", "message": "Initial tailoring prompt generated."})

        # ── Steps 5–7: Iterative Loop ───────────────────────────────────────
        iterations = []
        final_resume = ""
        final_score = {}
        best_score = 0
        best_resume = ""
        best_prompt = current_prompt

        for iteration in range(1, MAX_ITERATIONS + 1):
            yield emit({
                "type": "progress",
                "step": f"iteration_{iteration}_generate",
                "message": f"Iteration {iteration}/{MAX_ITERATIONS}: Generating tailored resume..."
            })

            tailored_resume = generate_resume(base_resume, current_prompt)

            yield emit({
                "type": "progress",
                "step": f"iteration_{iteration}_score",
                "message": f"Iteration {iteration}/{MAX_ITERATIONS}: Scoring resume..."
            })

            score = score_resume(tailored_resume, jd_text, jd_analysis)
            total = score.get("total", 0)

            iteration_data = {
                "iteration": iteration,
                "prompt": current_prompt,
                "resume": tailored_resume,
                "score": score
            }
            iterations.append(iteration_data)

            yield emit({
                "type": "iteration",
                **iteration_data
            })

            yield emit({
                "type": "progress",
                "step": f"iteration_{iteration}_result",
                "message": f"Iteration {iteration} score: {total}/100 ({score.get('grade', '?')}) — {score.get('recruiter_verdict', '')}"
            })

            # Track best result
            if total > best_score:
                best_score = total
                best_resume = tailored_resume
                best_prompt = current_prompt
                final_resume = tailored_resume
                final_score = score

            # Check if target reached
            if total >= SCORE_TARGET:
                yield emit({
                    "type": "progress",
                    "step": "target_reached",
                    "message": f"Target score {SCORE_TARGET} reached with {total}/100! Finalizing..."
                })
                break

            # Refine prompt for next iteration
            if iteration < MAX_ITERATIONS:
                yield emit({
                    "type": "progress",
                    "step": f"iteration_{iteration}_refine",
                    "message": f"Refining prompt based on score feedback..."
                })
                current_prompt = refine_prompt(current_prompt, score, iteration)

        # Use best result if final wasn't set
        if not final_resume:
            final_resume = best_resume
            final_score = score
            best_prompt = current_prompt

        yield emit({
            "type": "complete",
            "final_resume": final_resume,
            "final_score": final_score,
            "final_prompt": best_prompt,
            "iterations": iterations,
            "jd_analysis": jd_analysis,
            "resume_analysis": resume_analysis,
            "gap_analysis": gap_analysis
        })

    except Exception as e:
        import traceback
        yield emit({
            "type": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        })
