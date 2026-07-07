"""
Analyzer module: extracts structured signals from both the job description
and the base resume to inform dynamic prompt generation.
"""

from .llm import chat_json

JD_ANALYSIS_PROMPT = """You are an expert technical recruiter and ATS specialist.
Analyze the following job description and extract structured signals for resume tailoring.

Job Description:
{jd}

Return a JSON object with this exact structure:
{{
  "job_title": "exact job title from JD",
  "company_name": "company name if mentioned, else null",
  "industry": "industry/domain",
  "role_level": "entry/mid/senior/lead/principal/director/vp",
  "employment_type": "full-time/part-time/contract/etc",
  "required_hard_skills": ["list of required technical skills, tools, languages, frameworks"],
  "preferred_hard_skills": ["list of preferred/nice-to-have technical skills"],
  "soft_skills": ["list of soft skills mentioned"],
  "ats_keywords": ["top 20 most important keywords for ATS matching, in priority order"],
  "key_responsibilities": ["top 5-7 core responsibilities as concise phrases"],
  "required_qualifications": ["must-have qualifications"],
  "preferred_qualifications": ["nice-to-have qualifications"],
  "years_experience_required": "number or range as string, e.g. '3-5' or '5+'",
  "education_requirement": "degree requirement if specified",
  "domain_knowledge": ["specific domain knowledge areas required"],
  "action_verbs": ["preferred action verbs used in the JD"],
  "company_values": ["values/culture keywords mentioned"],
  "red_flags": ["anything unusual or very specific to watch for"]
}}"""

RESUME_ANALYSIS_PROMPT = """You are an expert resume coach and career strategist.
Analyze the following resume and extract a structured profile.

Resume:
{resume}

Return a JSON object with this exact structure:
{{
  "candidate_name": "full name",
  "current_title": "current or most recent job title",
  "years_experience": "estimated total years of professional experience",
  "core_skills": ["list of all technical skills mentioned"],
  "soft_skills": ["soft skills evident from resume"],
  "industries": ["industries the candidate has worked in"],
  "education": ["education entries as strings"],
  "certifications": ["certifications and credentials"],
  "notable_achievements": ["top 5 quantified achievements or impact statements"],
  "work_history": [
    {{
      "title": "job title",
      "company": "company name",
      "duration": "date range",
      "key_bullets": ["2-3 most impactful bullet points"]
    }}
  ],
  "projects": [
    {{
      "name": "project name",
      "description": "brief description",
      "technologies": ["tech stack used"],
      "impact": "measurable outcome or impact if mentioned"
    }}
  ],
  "gaps_and_weaknesses": ["areas where resume may be weak or missing common expectations"],
  "strengths": ["clear strengths that stand out"],
  "resume_style": "chronological/functional/hybrid",
  "quantification_level": "low/medium/high (how well achievements are quantified)",
  "has_projects_section": true
}}"""

GAP_ANALYSIS_PROMPT = """You are a senior technical recruiter performing a gap analysis.

Job Description Analysis:
{jd_analysis}

Candidate Resume Analysis:
{resume_analysis}

Perform a detailed gap analysis and return a JSON object:
{{
  "match_percentage": 0-100 integer estimate of current match,
  "strong_matches": ["skills/experiences that strongly align with JD requirements"],
  "partial_matches": ["areas with partial overlap that can be strengthened"],
  "critical_gaps": ["required skills/experiences the candidate clearly lacks"],
  "improvable_gaps": ["gaps that can be addressed through better framing/wording"],
  "keyword_gaps": ["important ATS keywords missing from resume"],
  "positioning_strategy": "how to best position this candidate for this role",
  "transferable_skills": ["skills from resume that transfer to JD requirements even if not obvious"],
  "recommended_emphasis": ["what to emphasize most in the tailored resume"],
  "sections_to_strengthen": ["which resume sections need the most work"]
}}"""


def analyze_jd(jd_text: str) -> dict:
    """Analyze a job description and return structured signals."""
    messages = [
        {
            "role": "system",
            "content": "You are an expert technical recruiter. Return only valid JSON."
        },
        {
            "role": "user",
            "content": JD_ANALYSIS_PROMPT.format(jd=jd_text)
        }
    ]
    return chat_json(messages, temperature=0.1)


def analyze_resume(resume_text: str) -> dict:
    """Analyze a resume and return structured profile including projects."""
    messages = [
        {
            "role": "system",
            "content": "You are an expert resume coach. Return only valid JSON."
        },
        {
            "role": "user",
            "content": RESUME_ANALYSIS_PROMPT.format(resume=resume_text)
        }
    ]
    return chat_json(messages, temperature=0.1)


def analyze_gaps(jd_analysis: dict, resume_analysis: dict) -> dict:
    """Perform gap analysis between JD requirements and resume."""
    import json
    messages = [
        {
            "role": "system",
            "content": "You are a senior technical recruiter. Return only valid JSON."
        },
        {
            "role": "user",
            "content": GAP_ANALYSIS_PROMPT.format(
                jd_analysis=json.dumps(jd_analysis, indent=2),
                resume_analysis=json.dumps(resume_analysis, indent=2)
            )
        }
    ]
    return chat_json(messages, temperature=0.1)
