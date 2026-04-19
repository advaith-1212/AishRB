"""
Render cover_letter.md to cover_letter.pdf for a given user.

Usage:
    python render_cover_letter.py --user-id <ID>

Reads:  data/<user_id>/cover_letter.md + data/<user_id>/resume.yaml (for contact header)
Writes: data/<user_id>/cover_letter.pdf
"""

import argparse
import os
import re
import yaml
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATE_DIR = os.path.join(_DIR, 'templates')


def render_cover_letter_pdf(user_id: int) -> str:
    """Render cover_letter.md to PDF. Returns path to generated PDF."""
    user_dir = os.path.join(_DIR, 'data', str(user_id))
    md_path = os.path.join(user_dir, 'cover_letter.md')
    resume_path = os.path.join(user_dir, 'resume.yaml')
    pdf_path = os.path.join(user_dir, 'cover_letter.pdf')

    if not os.path.exists(md_path):
        raise FileNotFoundError(f"No cover letter found at {md_path}")

    # Read the markdown cover letter
    with open(md_path, 'r', encoding='utf-8') as f:
        raw = f.read()

    # Parse: strip salutation and signature, extract body paragraphs
    lines = raw.strip().splitlines()

    # Extract salutation ("Dear ..." line)
    salutation = 'Dear Hiring Manager,'
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip().lower().startswith('dear '):
            salutation = line.strip()
            body_start = i + 1
            break

    # Remove signature block ("Sincerely," onwards)
    body_end = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip().lower()
        if stripped.startswith('sincerely') or stripped.startswith('best') or stripped.startswith('regards'):
            body_end = i
            break

    # Extract paragraphs (split on blank lines)
    body_text = '\n'.join(lines[body_start:body_end]).strip()
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', body_text) if p.strip()]

    # Get contact info from resume YAML (only location, phone, email for cover letter)
    contact = {}
    name = 'Candidate'
    if os.path.exists(resume_path):
        with open(resume_path, 'r', encoding='utf-8') as f:
            resume = yaml.safe_load(f) or {}
        name = resume.get('name', 'Candidate')
        full_contact = resume.get('contact', {})
        contact = {
            'location': full_contact.get('location', ''),
            'phone': full_contact.get('phone', ''),
            'email': full_contact.get('email', ''),
        }

    # Format today's date
    date_str = datetime.now().strftime('%B %d, %Y')

    # Render HTML
    env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR))
    template = env.get_template('cover_letter.html')
    html_str = template.render(
        name=name,
        contact=contact,
        date=date_str,
        salutation=salutation,
        paragraphs=paragraphs,
    )

    # Write PDF
    HTML(string=html_str, base_url=_DIR).write_pdf(pdf_path)
    return pdf_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Render cover letter PDF')
    parser.add_argument('--user-id', type=int, required=True)
    args = parser.parse_args()

    path = render_cover_letter_pdf(args.user_id)
    print(f"PDF written to: {path}")
