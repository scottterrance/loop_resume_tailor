"""
Modern PDF Generator using WeasyPrint and HTML/CSS.
Replaces the legacy fpdf-based generator with a professional, ATS-friendly design.

Features:
- Clean, semantic HTML structure for better ATS parsing
- Modern typography (sans-serif fonts)
- Professional visual hierarchy
- Deterministic text layer for AI/LLM filtering
- Page-break-aware section rendering
"""

import os
import re
from pathlib import Path
from jinja2 import Template
try:
    from weasyprint import HTML
    HAS_WEASYPRINT = True
except (ImportError, OSError):
    HAS_WEASYPRINT = False
from io import BytesIO

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Resume Parsing Helpers ────────────────────────────────────────────────────

def parse_resume_text(resume_text: str) -> dict:
    """
    Parse plain-text resume into structured sections.
    Handles the standard format output by the LLM.
    """
    lines = resume_text.strip().split('\n')
    
    # Extract header (first 3 lines)
    candidate_name = ""
    professional_title = ""
    contact_info = ""
    
    header_end = 0
    for i, line in enumerate(lines):
        if i < 3:
            if i == 0:
                candidate_name = line.strip()
            elif i == 1:
                professional_title = line.strip()
            elif i == 2:
                contact_info = line.strip()
        else:
            header_end = i
            break
    
    # Known primary section headers to prevent misidentifying sub-skills or languages
    VALID_HEADERS = {
        "PROFESSIONAL SUMMARY", "SUMMARY", "OBJECTIVE", "PROFILE",
        "TECHNICAL SKILLS", "SKILLS", "CORE COMPETENCIES", "TECHNOLOGIES",
        "WORK EXPERIENCE", "EXPERIENCE", "EMPLOYMENT HISTORY",
        "PROJECTS", "PERSONAL PROJECTS", "ACADEMIC PROJECTS",
        "EDUCATION", "ACADEMIC BACKGROUND",
        "CERTIFICATIONS", "AWARDS", "LANGUAGES", "VOLUNTEER EXPERIENCE"
    }

    # Parse sections
    sections = {}
    current_section = None
    current_content = []
    
    for line in lines[header_end:]:
        stripped = line.strip()
        
        if not stripped:
            continue
        
        # Check if this is a section header
        # A valid header is ALL CAPS and either:
        # 1. Is in our VALID_HEADERS list
        # 2. Is ALL CAPS, short, has no digits, AND doesn't look like a skill line (no colons)
        is_header = False
        clean_header = stripped.replace(':', '').strip()
        
        if clean_header in VALID_HEADERS:
            is_header = True
        elif stripped.isupper() and len(stripped) < 50 and not any(c.isdigit() for c in stripped) and ":" not in stripped:
            is_header = True

        if is_header:
            # Save previous section
            if current_section and current_content:
                sections[current_section] = current_content
            
            current_section = clean_header
            current_content = []
        else:
            if current_section:
                current_content.append(stripped)
    
    # Save last section
    if current_section and current_content:
        sections[current_section] = current_content
    
    return {
        "candidate_name": candidate_name,
        "professional_title": professional_title,
        "contact_info": contact_info,
        "sections": sections
    }


def extract_summary(sections: dict) -> str:
    """Extract summary/objective from sections."""
    for key in ["PROFESSIONAL SUMMARY", "SUMMARY", "OBJECTIVE", "PROFILE"]:
        if key in sections and sections[key]:
            return " ".join(sections[key])
    return ""


def extract_work_experience(sections: dict) -> list:
    """Extract work experience entries."""
    jobs = []
    
    for key in ["WORK EXPERIENCE", "EXPERIENCE", "PROFESSIONAL EXPERIENCE", "EMPLOYMENT HISTORY"]:
        if key not in sections:
            continue
        
        content = sections[key]
        current_job = None
        
        for line in content:
            # Job title line (not a bullet)
            if not line.startswith('-') and current_job is None:
                current_job = {
                    "title": line,
                    "company": "",
                    "dates": "",
                    "bullets": []
                }
            # Company/date line (contains pipe or date pattern)
            elif current_job and ('|' in line or re.search(r'\d{4}', line)):
                # Parse company | location | dates format
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 2:
                    current_job["company"] = " | ".join(parts[:-1])
                    current_job["dates"] = parts[-1]
                else:
                    current_job["company"] = line
            # Bullet point
            elif line.startswith('-'):
                if current_job:
                    bullet = line.lstrip('-').strip()
                    current_job["bullets"].append(bullet)
            # End of job entry (blank line or new job)
            elif current_job and line and not line.startswith('-'):
                jobs.append(current_job)
                current_job = {
                    "title": line,
                    "company": "",
                    "dates": "",
                    "bullets": []
                }
        
        # Add last job
        if current_job:
            jobs.append(current_job)
    
    return jobs


def extract_skills(sections: dict) -> dict:
    """Extract skills and organize by category."""
    skills = {}
    
    for key in ["SKILLS", "TECHNICAL SKILLS", "CORE COMPETENCIES", "COMPETENCIES", "KEY SKILLS"]:
        if key not in sections:
            continue
        
        content = sections[key]
        for line in content:
            # Handle "Category: item1, item2" format
            if ':' in line:
                parts = line.split(':', 1)
                category = parts[0].strip()
                items = parts[1].strip()
                skills[category] = items
            else:
                # Fallback: treat entire line as a skill group
                if line and not line.startswith('-'):
                    skills["Skills"] = line
    
    return skills


def extract_education(sections: dict) -> list:
    """Extract education entries."""
    education = []
    
    for key in ["EDUCATION", "ACADEMIC BACKGROUND", "ACADEMIC HISTORY"]:
        if key not in sections:
            continue
        
        content = sections[key]
        current_edu = None
        
        for line in content:
            if not line.startswith('-'):
                # Degree line
                if current_edu:
                    education.append(current_edu)
                
                current_edu = {
                    "degree": line,
                    "school": "",
                    "graduation_date": ""
                }
            elif current_edu and line.startswith('-'):
                # Details (school, date)
                detail = line.lstrip('-').strip()
                if not current_edu["school"]:
                    current_edu["school"] = detail
                else:
                    current_edu["graduation_date"] = detail
        
        if current_edu:
            education.append(current_edu)
    
    return education


def extract_projects(sections: dict) -> list:
    """Extract projects."""
    projects = []
    
    for key in ["PROJECTS", "KEY PROJECTS", "PERSONAL PROJECTS", "NOTABLE PROJECTS", "SIDE PROJECTS"]:
        if key not in sections:
            continue
        
        content = sections[key]
        current_project = None
        
        for line in content:
            if not line.startswith('-'):
                # Project name
                if current_project:
                    projects.append(current_project)
                
                current_project = {
                    "name": line,
                    "technologies": "",
                    "description": ""
                }
            elif current_project and line.startswith('-'):
                # Details
                detail = line.lstrip('-').strip()
                if not current_project["technologies"] and any(tech in detail.lower() for tech in ["python", "javascript", "java", "c++", "react", "node", "django", "flask"]):
                    current_project["technologies"] = detail
                else:
                    current_project["description"] = detail
        
        if current_project:
            projects.append(current_project)
    
    return projects


def extract_certifications(sections: dict) -> list:
    """Extract certifications."""
    certs = []
    
    for key in ["CERTIFICATIONS", "CERTIFICATES", "LICENSES", "CREDENTIALS"]:
        if key not in sections:
            continue
        
        content = sections[key]
        for line in content:
            if not line.startswith('-'):
                cert_entry = {"name": line, "issuer": ""}
                certs.append(cert_entry)
            else:
                # Issuer info
                if certs:
                    certs[-1]["issuer"] = line.lstrip('-').strip()
    
    return certs


# ── PDF Generation ────────────────────────────────────────────────────────────

def generate_pdf(resume_text: str, candidate_name: str = "resume", job_title: str = "") -> str:
    """
    Generate a professional PDF from plain-text resume.
    Uses WeasyPrint if available, otherwise falls back to legacy fpdf generator.
    """
    if not HAS_WEASYPRINT:
        print("WeasyPrint dependencies not found. Falling back to legacy fpdf generator.")
        from .pdf_generator import generate_pdf as legacy_generate_pdf
        return legacy_generate_pdf(resume_text, candidate_name, job_title)

    # Parse resume
    parsed = parse_resume_text(resume_text)
    sections = parsed["sections"]
    
    # Extract structured data
    summary = extract_summary(sections)
    work_experience = extract_work_experience(sections)
    skills = extract_skills(sections)
    education = extract_education(sections)
    projects = extract_projects(sections)
    certifications = extract_certifications(sections)
    
    # Prepare template context
    context = {
        "candidate_name": parsed["candidate_name"] or candidate_name,
        "professional_title": parsed["professional_title"] or job_title,
        "contact_info": parsed["contact_info"],
        "summary": summary,
        "work_experience": work_experience,
        "skills": skills,
        "education": education,
        "projects": projects,
        "certifications": certifications,
    }
    
    # Load and render template
    template_path = Path(__file__).parent.parent / "templates" / "resume_template.html"
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    template = Template(template_content)
    html_content = template.render(**context)
    
    # Generate PDF using WeasyPrint
    html = HTML(string=html_content)
    
    # Generate filename
    safe_name = re.sub(r'[^\w\s-]', '', parsed["candidate_name"] or candidate_name).strip().replace(' ', '_')
    safe_title = re.sub(r'[^\w\s-]', '', job_title).strip().replace(' ', '_') if job_title else "Resume"
    filename = f"{safe_name}_{safe_title}.pdf"
    
    pdf_path = OUTPUT_DIR / filename
    
    # Render to PDF
    html.write_pdf(str(pdf_path))
    
    return str(pdf_path)
