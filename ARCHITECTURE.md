# Loop Resume Tailor — Architecture Design

## Overview

A single-page web application (Python/Flask backend + vanilla HTML/CSS/JS frontend) that:
1. Accepts a base resume (text or PDF) and a job description
2. Dynamically generates tailored prompts based on the specific resume + JD pair
3. Iteratively generates, scores, and refines the tailored resume via DeepSeek LLM
4. Outputs a professionally formatted, ATS-optimized PDF resume

## Stack

| Layer | Technology | Reason |
|---|---|---|
| Backend | Python 3 + Flask | Lightweight, easy to extend, Python ecosystem for PDF/NLP |
| LLM | DeepSeek Chat (deepseek-chat) | User-provided API key, cost-effective, strong reasoning |
| PDF Generation | WeasyPrint | HTML→PDF, professional formatting, CSS control |
| Frontend | Vanilla HTML/CSS/JS (Single Page) | Zero build step, simple, fast |
| Resume Parsing | pdfminer.six / plain text | Handle both PDF and text input |

## Core Workflow (The Loop)

```
Input: base_resume + job_description
  │
  ▼
[Step 1] Analyze JD → extract: required skills, keywords, role level, industry, ATS signals
  │
  ▼
[Step 2] Analyze Resume → extract: candidate profile, gaps vs JD, strengths
  │
  ▼
[Step 3] Generate dynamic tailoring prompt (specific to this resume+JD pair)
  │
  ▼
[Step 4] Generate tailored resume using the prompt
  │
  ▼
[Step 5] Score the tailored resume (0-100) across 5 dimensions:
         - Keyword Match (ATS)       : 25pts
         - Skills Alignment          : 25pts
         - Role/Level Fit            : 20pts
         - Impact & Quantification   : 15pts
         - Formatting & Readability  : 15pts
  │
  ▼
[Step 6] If score < 95: diagnose gaps → refine prompt → go to Step 4
         If score >= 95: finalize resume
  │
  ▼
[Step 7] Render to professional PDF → download
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | /api/analyze | Analyze JD + resume, return extracted signals |
| POST | /api/tailor | Run full iterative loop, stream progress via SSE |
| GET  | /api/download/<id> | Download generated PDF |
| POST | /api/upload-resume | Upload PDF resume for text extraction |

## Scoring Dimensions

The scoring engine uses a dedicated LLM call with a structured JSON response:

```json
{
  "keyword_match": { "score": 23, "max": 25, "missing": ["..."] },
  "skills_alignment": { "score": 22, "max": 25, "gaps": ["..."] },
  "role_level_fit": { "score": 18, "max": 20, "notes": "..." },
  "impact_quantification": { "score": 12, "max": 15, "suggestions": ["..."] },
  "formatting_readability": { "score": 14, "max": 15, "notes": "..." },
  "total": 89,
  "diagnosis": "...",
  "refinement_instructions": "..."
}
```

## File Structure

```
loop_resume_tailor/
├── app.py                  # Flask application entry point
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── core/
│   ├── __init__.py
│   ├── llm.py              # DeepSeek API client wrapper
│   ├── analyzer.py         # JD + Resume analysis
│   ├── prompt_engine.py    # Dynamic prompt generation
│   ├── tailor.py           # Iterative tailoring loop
│   ├── scorer.py           # Resume scoring engine
│   └── pdf_generator.py    # HTML→PDF rendering
├── templates/
│   ├── index.html          # Main SPA
│   └── resume.html         # PDF resume template
├── static/
│   ├── style.css           # App styles
│   └── app.js              # Frontend logic
└── README.md
```
