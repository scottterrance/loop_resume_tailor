# Loop Resume Tailor

> **World-class AI-powered resume tailoring with iterative ATS optimization.**
> Powered by DeepSeek · Outputs recruiter-ready PDF · Scores ~100/100

---

## What It Does

Loop Resume Tailor implements a **closed-loop AI optimization cycle** that:

1. **Analyzes** your base resume and the target job description independently
2. **Performs gap analysis** — identifying missing keywords, skill mismatches, and positioning opportunities
3. **Generates a custom tailoring prompt** specific to your resume + JD pair (not a generic template)
4. **Generates a tailored resume** using that prompt
5. **Scores the resume** across 5 ATS/recruiter dimensions (0–100)
6. **Diagnoses weaknesses** and refines the prompt automatically
7. **Repeats** until the score reaches ~95–100 (configurable)
8. **Exports a professional PDF** ready to submit

The result: a resume that ranks **#1 in ATS systems** and immediately impresses human recruiters.

---

## Scoring Dimensions

| Dimension | Weight | What It Measures |
|---|---|---|
| Keyword Match (ATS) | 25 pts | Presence of JD-critical keywords in the resume |
| Skills Alignment | 25 pts | How well the candidate's skills match JD requirements |
| Role / Level Fit | 20 pts | Seniority signals, scope, and responsibility alignment |
| Impact & Quantification | 15 pts | Metrics, achievements, and measurable outcomes |
| Formatting & Readability | 15 pts | ATS-parseable structure, clarity, and professionalism |
| **Total** | **100 pts** | |

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/scottterrance/loop_resume_tailor.git
cd loop_resume_tailor
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your DeepSeek API key
```

```env
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_API_KEY=your_deepseek_api_key_here
MAX_ITERATIONS=5
SCORE_TARGET=95
```

### 3. Run

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## Usage

1. **Enter your DeepSeek API key** in the key field (stored in session only)
2. **Paste your base resume** or upload a PDF
3. **Paste the full job description**
4. Optionally adjust **Max Iterations** and **Score Target**
5. Click **Start AI Tailoring Loop**
6. Watch the live progress — analysis, prompt generation, iterations, and scoring
7. View the **final score dashboard** with dimension breakdown
8. **Download the PDF** and apply

---

## Project Structure

```
loop_resume_tailor/
├── app.py                  # Flask application entry point
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── core/
│   ├── llm.py              # DeepSeek API client
│   ├── analyzer.py         # JD + Resume analysis
│   ├── prompt_engine.py    # Dynamic prompt generation & refinement
│   ├── tailor.py           # Iterative tailoring loop (main orchestrator)
│   ├── scorer.py           # Resume scoring engine
│   ├── pdf_generator.py    # HTML→PDF rendering (WeasyPrint)
│   └── extractor.py        # PDF/text resume extraction
├── templates/
│   └── index.html          # Single-page application
└── static/
    ├── style.css            # Dark-mode UI styles
    └── app.js               # Frontend logic + SSE streaming
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/upload-resume` | Upload PDF resume → returns extracted text |
| `POST` | `/api/tailor` | Start tailoring loop → returns `job_id` |
| `GET`  | `/api/stream/<job_id>` | SSE stream of progress events |
| `POST` | `/api/generate-pdf` | Convert resume text → PDF |
| `GET`  | `/api/download/<filename>` | Download generated PDF |
| `GET`  | `/api/health` | Health check |

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `LLM_API_KEY` | — | DeepSeek API key (required) |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | LLM API base URL |
| `LLM_MODEL` | `deepseek-chat` | Model name |
| `MAX_ITERATIONS` | `5` | Maximum optimization iterations |
| `SCORE_TARGET` | `95` | Stop when score reaches this value |
| `PORT` | `5000` | Flask server port |

---

## Requirements

- Python 3.10+
- DeepSeek API key ([platform.deepseek.com](https://platform.deepseek.com))
- WeasyPrint system dependencies (pre-installed on most Linux systems)

---

## License

MIT License — see [LICENSE](LICENSE)