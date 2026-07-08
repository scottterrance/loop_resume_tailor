"""
Loop Resume Tailor — Flask Application
Iterative AI-powered resume tailoring with ATS scoring and PDF export.
"""

import os
import json
import uuid
import threading
from pathlib import Path
from flask import Flask, request, jsonify, send_file, Response, render_template
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# In-memory job store for SSE streaming
_jobs: dict[str, dict] = {}
_job_events: dict[str, list] = {}
_job_locks: dict[str, threading.Event] = {}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload-resume", methods=["POST"])
def upload_resume():
    """Upload a PDF resume and extract its text."""
    from core.extractor import extract_text_from_pdf, clean_resume_text

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    file_bytes = file.read()
    filename = file.filename.lower()

    try:
        if filename.endswith(".pdf"):
            text = extract_text_from_pdf(file_bytes)
        else:
            text = file_bytes.decode("utf-8", errors="ignore")

        text = clean_resume_text(text)
        return jsonify({"text": text, "length": len(text)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tailor", methods=["POST"])
def start_tailor():
    """
    Start the iterative tailoring loop.
    Returns a job_id for SSE streaming.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    resume_text = data.get("resume", "").strip()
    jd_text = data.get("jd", "").strip()
    api_key = data.get("api_key", "").strip()
    max_iterations = data.get("max_iterations")
    score_target = data.get("score_target")

    if not resume_text:
        return jsonify({"error": "Resume text is required"}), 400
    if not jd_text:
        return jsonify({"error": "Job description is required"}), 400

    # Set API key from request if provided
    if api_key:
        os.environ["LLM_API_KEY"] = api_key
        # Reset client so it picks up new key
        import core.llm as llm_module
        llm_module._clients = {}

    # Update loop settings if provided
    if max_iterations:
        os.environ["MAX_ITERATIONS"] = str(max_iterations)
    if score_target:
        os.environ["SCORE_TARGET"] = str(score_target)

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "running", "events": []}
    _job_events[job_id] = []
    _job_locks[job_id] = threading.Event()

    def run_job():
        from core.tailor import run_tailor_loop
        try:
            for event in run_tailor_loop(resume_text, jd_text):
                _job_events[job_id].append(event)
                if event.get("type") == "complete":
                    _jobs[job_id]["status"] = "complete"
                    _jobs[job_id]["result"] = event
                elif event.get("type") == "error":
                    _jobs[job_id]["status"] = "error"
                    _jobs[job_id]["error"] = event.get("message")
        except Exception as e:
            _job_events[job_id].append({"type": "error", "message": str(e)})
            _jobs[job_id]["status"] = "error"
        finally:
            _job_locks[job_id].set()

    thread = threading.Thread(target=run_job, daemon=True)
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/api/stream/<job_id>")
def stream_job(job_id: str):
    """
    SSE endpoint: stream job progress events.
    """
    if job_id not in _jobs:
        return jsonify({"error": "Job not found"}), 404

    def generate():
        sent_index = 0
        import time
        while True:
            events = _job_events.get(job_id, [])
            while sent_index < len(events):
                event = events[sent_index]
                sent_index += 1
                data = json.dumps(event)
                yield f"data: {data}\n\n"

                if event.get("type") in ("complete", "error"):
                    return

            job = _jobs.get(job_id, {})
            if job.get("status") in ("complete", "error") and sent_index >= len(_job_events.get(job_id, [])):
                return

            time.sleep(0.3)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@app.route("/api/generate-pdf", methods=["POST"])
def generate_pdf_endpoint():
    """Generate a PDF from the tailored resume text."""
    from core.pdf_generator_v2 import generate_pdf

    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    resume_text = data.get("resume", "").strip()
    candidate_name = data.get("name", "resume")
    job_title = data.get("job_title", "")

    if not resume_text:
        return jsonify({"error": "Resume text is required"}), 400

    try:
        import logging
        logging.basicConfig(level=logging.INFO)
        logging.info(f"Generating PDF for {candidate_name} - {job_title}")
        
        pdf_path = generate_pdf(resume_text, candidate_name, job_title)
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file was not created at {pdf_path}")
            
        # Return just the filename since it now contains all info
        return jsonify({"filename": Path(pdf_path).name})
    except Exception as e:
        import traceback
        error_msg = f"PDF Error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({"error": str(e), "details": traceback.format_exc()}), 500


@app.route("/api/download/<filename>")
def download_pdf(filename: str):
    """Download a generated PDF file."""
    # Security: only allow alphanumeric + underscore + dash + dot
    import re
    if not re.match(r'^[\w\-\.]+\.pdf$', filename):
        return jsonify({"error": "Invalid filename"}), 400

    pdf_path = OUTPUT_DIR / filename
    if not pdf_path.exists():
        return jsonify({"error": "File not found"}), 404

    return send_file(
        str(pdf_path),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )


@app.route("/api/job/<job_id>")
def get_job(job_id: str):
    """Get job status and result."""
    if job_id not in _jobs:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(_jobs[job_id])


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "model": os.environ.get("LLM_MODEL", "deepseek-chat")})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
