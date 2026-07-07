"""
PDF Generator: converts a plain-text tailored resume into a
professionally formatted, ATS-compatible PDF using WeasyPrint.
"""

import os
import re
import uuid
from pathlib import Path

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except Exception:
    WEASYPRINT_AVAILABLE = False

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

RESUME_CSS = """
@page {
    margin: 0.75in 0.8in;
    size: letter;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: 'Georgia', 'Times New Roman', serif;
    font-size: 10.5pt;
    line-height: 1.45;
    color: #1a1a1a;
    background: white;
}

/* ── Header ─────────────────────────────────────── */
.resume-header {
    text-align: center;
    border-bottom: 2px solid #2c3e50;
    padding-bottom: 10px;
    margin-bottom: 14px;
}

.resume-header h1 {
    font-size: 22pt;
    font-weight: bold;
    color: #2c3e50;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 4px;
}

.resume-header .contact-line {
    font-size: 9.5pt;
    color: #555;
    font-family: 'Arial', sans-serif;
}

.resume-header .contact-line a {
    color: #2980b9;
    text-decoration: none;
}

/* ── Section Headers ─────────────────────────────── */
.section {
    margin-bottom: 14px;
}

.section-title {
    font-size: 11pt;
    font-weight: bold;
    color: #2c3e50;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    border-bottom: 1px solid #bdc3c7;
    padding-bottom: 2px;
    margin-bottom: 8px;
    font-family: 'Arial', sans-serif;
}

/* ── Summary ─────────────────────────────────────── */
.summary p {
    font-size: 10.5pt;
    color: #333;
    text-align: justify;
}

/* ── Skills ──────────────────────────────────────── */
.skills-grid {
    display: table;
    width: 100%;
}

.skills-row {
    display: table-row;
}

.skills-label {
    display: table-cell;
    font-weight: bold;
    font-size: 10pt;
    width: 130px;
    padding: 2px 8px 2px 0;
    vertical-align: top;
    font-family: 'Arial', sans-serif;
    color: #2c3e50;
}

.skills-value {
    display: table-cell;
    font-size: 10pt;
    padding: 2px 0;
    color: #333;
}

/* ── Experience ──────────────────────────────────── */
.job {
    margin-bottom: 12px;
}

.job-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 1px;
}

.job-title-company {
    font-weight: bold;
    font-size: 10.5pt;
    color: #1a1a1a;
}

.job-company {
    font-style: italic;
    color: #555;
}

.job-dates {
    font-size: 9.5pt;
    color: #666;
    font-family: 'Arial', sans-serif;
    white-space: nowrap;
    margin-left: 8px;
}

.job-location {
    font-size: 9.5pt;
    color: #666;
    font-family: 'Arial', sans-serif;
}

.job ul {
    margin-top: 4px;
    padding-left: 16px;
}

.job ul li {
    font-size: 10pt;
    margin-bottom: 2px;
    color: #333;
}

/* ── Education ───────────────────────────────────── */
.edu-entry {
    margin-bottom: 8px;
}

.edu-degree {
    font-weight: bold;
    font-size: 10.5pt;
}

.edu-school {
    font-style: italic;
    color: #555;
}

.edu-dates {
    font-size: 9.5pt;
    color: #666;
    font-family: 'Arial', sans-serif;
}

/* ── Certifications ──────────────────────────────── */
.cert-list {
    list-style: none;
    padding: 0;
}

.cert-list li {
    font-size: 10pt;
    padding: 1px 0;
    color: #333;
}

.cert-list li::before {
    content: "▪ ";
    color: #2c3e50;
}

/* ── Projects ────────────────────────────────────── */
.project {
    margin-bottom: 8px;
}

.project-title {
    font-weight: bold;
    font-size: 10.5pt;
}

.project ul {
    padding-left: 16px;
    margin-top: 3px;
}

.project ul li {
    font-size: 10pt;
    margin-bottom: 2px;
    color: #333;
}
"""


def parse_resume_to_html(resume_text: str) -> str:
    """
    Parse plain-text resume into structured HTML for PDF rendering.
    Handles common resume section patterns.
    """
    lines = resume_text.strip().split('\n')
    html_parts = []
    in_section = False
    current_section = None
    job_buffer = []
    i = 0

    # Detect name (first non-empty line)
    name = ""
    contact_lines = []
    content_start = 0

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if not name:
            name = stripped
            content_start = idx + 1
        elif idx < content_start + 5 and not is_section_header(stripped):
            contact_lines.append(stripped)
            content_start = idx + 1
        else:
            content_start = idx
            break

    # Build header
    contact_html = " &nbsp;|&nbsp; ".join(contact_lines) if contact_lines else ""
    html_parts.append(f"""<div class="resume-header">
  <h1>{name}</h1>
  <div class="contact-line">{contact_html}</div>
</div>""")

    # Parse remaining content
    remaining_lines = lines[content_start:]
    sections = split_into_sections(remaining_lines)

    for section_name, section_lines in sections:
        section_html = render_section(section_name, section_lines)
        html_parts.append(section_html)

    return "\n".join(html_parts)


def is_section_header(line: str) -> bool:
    """Detect if a line is a section header."""
    upper = line.upper().strip()
    section_keywords = [
        "SUMMARY", "OBJECTIVE", "PROFILE", "EXPERIENCE", "WORK EXPERIENCE",
        "PROFESSIONAL EXPERIENCE", "EMPLOYMENT", "EDUCATION", "SKILLS",
        "TECHNICAL SKILLS", "CORE COMPETENCIES", "CERTIFICATIONS", "CERTIFICATES",
        "PROJECTS", "PUBLICATIONS", "AWARDS", "ACHIEVEMENTS", "LANGUAGES",
        "VOLUNTEER", "INTERESTS", "REFERENCES", "ADDITIONAL"
    ]
    for kw in section_keywords:
        if kw in upper and len(line.strip()) < 60:
            return True
    # All caps short line
    if line.strip() == line.strip().upper() and len(line.strip()) > 3 and len(line.strip()) < 50:
        return True
    return False


def split_into_sections(lines: list) -> list:
    """Split resume lines into (section_name, lines) tuples."""
    sections = []
    current_name = "SUMMARY"
    current_lines = []

    for line in lines:
        stripped = line.strip()
        if is_section_header(stripped) and stripped:
            if current_lines:
                sections.append((current_name, current_lines))
            current_name = stripped.rstrip(':').strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_name, current_lines))

    return sections


def render_section(section_name: str, lines: list) -> str:
    """Render a resume section as HTML."""
    clean_lines = [l for l in lines if l.strip()]
    if not clean_lines:
        return ""

    upper = section_name.upper()

    # Determine section type
    if any(kw in upper for kw in ["SUMMARY", "OBJECTIVE", "PROFILE", "ABOUT"]):
        content = " ".join(l.strip() for l in clean_lines)
        return f"""<div class="section summary">
  <div class="section-title">{section_name}</div>
  <p>{content}</p>
</div>"""

    elif any(kw in upper for kw in ["SKILL", "COMPETENC", "TECHNICAL", "EXPERTISE", "PROFICIENC"]):
        return render_skills_section(section_name, clean_lines)

    elif any(kw in upper for kw in ["EXPERIENCE", "EMPLOYMENT", "WORK HISTORY", "CAREER"]):
        return render_experience_section(section_name, clean_lines)

    elif any(kw in upper for kw in ["EDUCATION", "ACADEMIC", "DEGREE"]):
        return render_education_section(section_name, clean_lines)

    elif any(kw in upper for kw in ["CERTIF", "LICENSE", "CREDENTIAL"]):
        items = [l.strip().lstrip('-•*▪').strip() for l in clean_lines if l.strip()]
        items_html = "\n".join(f"<li>{item}</li>" for item in items)
        return f"""<div class="section">
  <div class="section-title">{section_name}</div>
  <ul class="cert-list">{items_html}</ul>
</div>"""

    elif any(kw in upper for kw in ["PROJECT"]):
        return render_projects_section(section_name, clean_lines)

    else:
        # Generic list section
        items = [l.strip().lstrip('-•*▪').strip() for l in clean_lines if l.strip()]
        items_html = "\n".join(f"<li>{item}</li>" for item in items)
        return f"""<div class="section">
  <div class="section-title">{section_name}</div>
  <ul class="cert-list">{items_html}</ul>
</div>"""


def render_skills_section(section_name: str, lines: list) -> str:
    """Render skills section with category detection."""
    rows = []
    for line in lines:
        stripped = line.strip().lstrip('-•*▪').strip()
        if not stripped:
            continue
        # Check for "Category: skills" pattern
        if ':' in stripped:
            parts = stripped.split(':', 1)
            label = parts[0].strip()
            value = parts[1].strip()
            rows.append(f"""<div class="skills-row">
    <div class="skills-label">{label}:</div>
    <div class="skills-value">{value}</div>
  </div>""")
        else:
            rows.append(f"""<div class="skills-row">
    <div class="skills-label"></div>
    <div class="skills-value">{stripped}</div>
  </div>""")

    rows_html = "\n".join(rows)
    return f"""<div class="section">
  <div class="section-title">{section_name}</div>
  <div class="skills-grid">{rows_html}</div>
</div>"""


def render_experience_section(section_name: str, lines: list) -> str:
    """Render work experience section."""
    jobs_html = []
    job_blocks = split_job_blocks(lines)

    for block in job_blocks:
        if not block:
            continue
        job_html = render_job_block(block)
        jobs_html.append(job_html)

    return f"""<div class="section">
  <div class="section-title">{section_name}</div>
  {"".join(jobs_html)}
</div>"""


def split_job_blocks(lines: list) -> list:
    """Split experience lines into individual job blocks."""
    blocks = []
    current = []

    date_pattern = re.compile(
        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|June|July|August|September|October|November|December)\s+\d{4}|\d{4}\s*[-–]\s*(\d{4}|Present|Current)',
        re.IGNORECASE
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # New job block starts when we see a line with a date pattern that's not a bullet
        if date_pattern.search(stripped) and not stripped.startswith(('-', '•', '*', '▪')):
            if current:
                blocks.append(current)
            current = [stripped]
        else:
            current.append(stripped)

    if current:
        blocks.append(current)

    return blocks


def render_job_block(block: list) -> str:
    """Render a single job block as HTML."""
    if not block:
        return ""

    # First line: title/company/dates
    header = block[0]
    bullets = block[1:]

    # Try to parse title | company | dates
    date_pattern = re.compile(
        r'(\d{4}\s*[-–]\s*(?:\d{4}|Present|Current)|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\s*[-–]\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|Present|Current))',
        re.IGNORECASE
    )
    date_match = date_pattern.search(header)
    dates = date_match.group(0) if date_match else ""
    title_company = date_pattern.sub('', header).strip().strip('|–-').strip()

    # Split title from company
    separators = [' | ', ' at ', ' - ', ' – ', ', ']
    title = title_company
    company = ""
    for sep in separators:
        if sep in title_company:
            parts = title_company.split(sep, 1)
            title = parts[0].strip()
            company = parts[1].strip()
            break

    bullets_html = ""
    if bullets:
        bullet_items = []
        for b in bullets:
            b = b.strip().lstrip('-•*▪').strip()
            if b:
                bullet_items.append(f"<li>{b}</li>")
        if bullet_items:
            bullets_html = f"<ul>{''.join(bullet_items)}</ul>"

    company_html = f' <span class="job-company">— {company}</span>' if company else ""
    dates_html = f'<span class="job-dates">{dates}</span>' if dates else ""

    return f"""<div class="job">
  <div class="job-header">
    <span class="job-title-company">{title}{company_html}</span>
    {dates_html}
  </div>
  {bullets_html}
</div>"""


def render_education_section(section_name: str, lines: list) -> str:
    """Render education section."""
    entries_html = []
    blocks = []
    current = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(stripped)
    if current:
        blocks.append(current)

    for block in blocks:
        if not block:
            continue
        degree_line = block[0]
        rest = block[1:]
        rest_html = "<br>".join(l.lstrip('-•*▪').strip() for l in rest if l.strip())
        entries_html.append(f"""<div class="edu-entry">
    <span class="edu-degree">{degree_line}</span>
    {"<br>" + rest_html if rest_html else ""}
  </div>""")

    return f"""<div class="section">
  <div class="section-title">{section_name}</div>
  {"".join(entries_html)}
</div>"""


def render_projects_section(section_name: str, lines: list) -> str:
    """Render projects section."""
    projects_html = []
    blocks = []
    current = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append(current)
                current = []
        elif not stripped.startswith(('-', '•', '*', '▪')) and current:
            blocks.append(current)
            current = [stripped]
        else:
            current.append(stripped)
    if current:
        blocks.append(current)

    for block in blocks:
        if not block:
            continue
        title = block[0].lstrip('-•*▪').strip()
        bullets = [b.strip().lstrip('-•*▪').strip() for b in block[1:] if b.strip()]
        bullets_html = ""
        if bullets:
            bullets_html = "<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"
        projects_html.append(f"""<div class="project">
    <div class="project-title">{title}</div>
    {bullets_html}
  </div>""")

    return f"""<div class="section">
  <div class="section-title">{section_name}</div>
  {"".join(projects_html)}
</div>"""


def generate_pdf(resume_text: str, candidate_name: str = "resume") -> str:
    """
    Convert plain-text resume to a professionally formatted PDF.
    Returns the output file path.
    """
    file_id = str(uuid.uuid4())[:8]
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', candidate_name)[:30]
    output_path = OUTPUT_DIR / f"{safe_name}_{file_id}.pdf"

    resume_html = parse_resume_to_html(resume_text)

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{candidate_name} — Resume</title>
  <style>{RESUME_CSS}</style>
</head>
<body>
  {resume_html}
</body>
</html>"""

    if WEASYPRINT_AVAILABLE:
        HTML(string=full_html).write_pdf(str(output_path))
    else:
        # Fallback: save HTML and convert with alternative method
        html_path = output_path.with_suffix('.html')
        with open(html_path, 'w') as f:
            f.write(full_html)
        os.system(f"chromium --headless --disable-gpu --print-to-pdf={output_path} {html_path} 2>/dev/null")

    return str(output_path)


def get_output_path(file_id: str) -> str | None:
    """Find an output file by partial ID."""
    for f in OUTPUT_DIR.iterdir():
        if file_id in f.name and f.suffix == '.pdf':
            return str(f)
    return None
