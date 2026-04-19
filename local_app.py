from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from functools import wraps
import traceback
import yaml
import os
import sys
import json
import glob
import logging
import re as _re
from datetime import datetime
from jinja2 import Environment, FileSystemLoader


def _md_bold(text):
    """Convert **word** to <strong>word</strong> for inline bold in YAML."""
    if not text:
        return text
    return _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', str(text))
from weasyprint import HTML

from models import (
    init_db, create_user, authenticate_user, get_user_by_id,
    get_user_dir, get_user_versions_dir, get_user_settings,
    update_user_settings, verify_user_password, delete_user,
    is_onboarding_complete, mark_onboarding_complete,
    DEFAULT_SECTION_NAMES, DATA_DIR,
    generate_mcp_api_key, get_mcp_api_key,
    save_user_api_config, get_user_api_config, delete_user_api_config,
)
from services.crypto import encrypt_api_key, decrypt_api_key
from parsers.pdf import (extract_style_from_pdf,
                         extract_text_local, parse_resume_from_extracted,
                         _smart_parse_section, _normalize_section_key)
from parsers.confidence import score_parsed_resume
import sandbox as daytona_sandbox
import parsers.smart as sp
import services.parser as parser_service
from services.resume import save_current_resume as _save_resume
import services.jd as jd_service
import agents.jd_resume as jd_resume_agent
import agents.jd_finder as jd_finder_agent
import agents.cover_letter as cover_letter_agent

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# --- Logging setup ---
# gunicorn captures stderr; line-buffered stdout ensures prints flush immediately.
# Flask's logger is set to INFO so app.logger.info() calls are visible.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(line_buffering=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stderr,
    force=True,
)
app.logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

# Initialize database on startup
try:
    init_db()
    print(">>> DB init OK", flush=True)
except Exception:
    print(">>> FATAL: init_db() failed:", flush=True)
    traceback.print_exc()
    raise

# --- Auth helpers ---

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def get_current_user_id():
    return session.get('user_id')


def get_current_user_header():
    """Get the header (name + contact) for the current user from settings."""
    settings = get_user_settings(get_current_user_id())
    return settings.get('header', {})


def get_current_section_names():
    """Get section name mappings for the current user."""
    settings = get_user_settings(get_current_user_id())
    return settings.get('section_names', DEFAULT_SECTION_NAMES.copy())


def get_current_custom_sections():
    """Get custom sections for the current user."""
    settings = get_user_settings(get_current_user_id())
    return settings.get('custom_sections', [])


def merge_header(partial_data, header):
    """Merges user header into resume data."""
    if isinstance(partial_data, str):
        try:
            partial_data = yaml.safe_load(partial_data) or {}
        except Exception:
            partial_data = {}
    if not isinstance(partial_data, dict):
        partial_data = {}
    full_data = partial_data.copy()
    full_data.update(header)
    return full_data


def strip_header(full_data, header):
    """Removes header keys from resume data."""
    if isinstance(full_data, str):
        try:
            full_data = yaml.safe_load(full_data) or {}
        except Exception:
            full_data = {}
    if not isinstance(full_data, dict):
        return {}
    partial_data = full_data.copy()
    for key in header:
        if key in partial_data:
            del partial_data[key]
    return partial_data


def _resolve_ai_credentials(request_data: dict, user_id: int) -> tuple:
    """Return (provider, api_key, model) from request body or DB.

    Request body values override DB-stored config. Raises ValueError if
    no API key is available from either source.
    """
    provider = (request_data.get('provider') or request_data.get('ai_provider') or '').strip()
    api_key = (request_data.get('api_key') or request_data.get('ai_api_key') or '').strip()
    model = (request_data.get('model') or request_data.get('ai_model') or '').strip() or None

    if not api_key:
        config = get_user_api_config(user_id)
        if config and config.get('ai_api_key_encrypted'):
            api_key = decrypt_api_key(config['ai_api_key_encrypted'])
            provider = provider or config.get('provider') or 'anthropic'
            model = model or config.get('model')

    if not api_key:
        raise ValueError("No API key configured. Set one in Settings or pass it in the request.")

    return provider or 'anthropic', api_key, model


BUILTIN_KEYS = {'name', 'contact', 'summary', 'education', 'technical_skills',
                 'experience', 'projects', 'extracurricular'}


def _infer_render_type(data):
    """Infer whether a parsed section is bullets, entries, or skills."""
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            if 'category' in data[0] and 'skills' in data[0]:
                return 'skills'
            # Sections whose items are dicts with any recognised structural key
            # are treated as 'entries' (title+bullets, experience-style, etc.)
            _ENTRY_KEYS = ('company', 'role', 'institution', 'degree', 'date',
                           'name', 'event', 'award', 'title', 'description',
                           'organization', 'position', 'location')
            if any(k in data[0] for k in _ENTRY_KEYS):
                return 'entries'
        return 'bullets'
    if isinstance(data, dict) and 'bullets' in data:
        return 'bullets'
    return 'bullets'


def _has_meaningful_content(parsed: dict) -> bool:
    """Return True if a parsed resume dict contains real editable content.

    'name' and 'contact' are always stripped into the header before the YAML
    editor is shown, so a parser that only returns those fields produces a
    blank YAML and empty preview.  We require at least one *non-header* field
    to have real text before accepting an AI parse result.
    """
    if not isinstance(parsed, dict) or not parsed:
        return False

    # Keys that are always moved to the header or are internal metadata —
    # they don't appear in the editable YAML, so they don't count.
    _HEADER_KEYS = {'name', 'contact', '_section_headings', '_date_parsed'}

    def _entry_has_text(entry):
        if isinstance(entry, dict):
            return any(str(v).strip() for v in entry.values() if v)
        if isinstance(entry, str):
            return bool(entry.strip())
        return False

    for key, val in parsed.items():
        if key in _HEADER_KEYS:
            continue
        if isinstance(val, list) and any(_entry_has_text(e) for e in val):
            return True
        if isinstance(val, dict):
            if val.get('bullets') and any(str(b).strip() for b in val['bullets'] if b):
                return True
            if any(str(v).strip() for v in val.values() if v):
                return True
        if isinstance(val, str) and val.strip():
            return True

    return False


# ---------------------------------------------------------------------------
# Post-processing: clean up common AI parser artifacts
# ---------------------------------------------------------------------------

_CONTACT_PAT = _re.compile(
    r'@|mailto:|tel:|tel\.|linkedin\.com|github\.com|https?://|www\.'
    r'|\+\d[\d\s\-()]{6,}',
    _re.IGNORECASE,
)
_EDU_KEYWORDS = _re.compile(
    r'university|college|school|institute|academy|polytechnic|iit|iim|'
    r'nit|srm|vit|bits|mit|stanford|harvard|purdue|nyu|ucla|usc|oxford|cambridge',
    _re.IGNORECASE,
)
_BULLET_PREFIX = _re.compile(r'^[\u2022\u2023\u25e6\-\*]\s*')


def _clean_flat_list(items: list) -> list:
    """Strip leading bullet characters and re-join orphaned continuation lines.

    Some parsers emit list items like:
        ["• Led a team of 100+ as CRM for", "Techno-Management fest AARUUSH."]
    where the second item is a continuation, not a new bullet.  We detect
    bullet-prefix lists (≥40 % of items start with a bullet char) and merge
    items that lack the prefix back onto the previous item.
    """
    if not items or not all(isinstance(i, str) for i in items):
        return items

    stripped = [i.strip() for i in items]
    bullet_count = sum(1 for s in stripped if _BULLET_PREFIX.match(s))
    is_bullet_list = bullet_count >= max(1, len(stripped) * 0.4)

    cleaned: list[str] = []
    for s in stripped:
        if not s:
            continue
        if is_bullet_list:
            if _BULLET_PREFIX.match(s):
                cleaned.append(_BULLET_PREFIX.sub('', s).strip())
            else:
                # Continuation — glue onto previous item
                if cleaned:
                    cleaned[-1] = cleaned[-1].rstrip() + ' ' + s
                else:
                    cleaned.append(s)
        else:
            cleaned.append(s)
    return [s for s in cleaned if s]


def _clean_parsed_resume(parsed: dict) -> dict:
    """Remove common AI parser artifacts from a parsed resume dict.

    1. Drop education entries that are really the contact/header block
       (empty degree + description contains email / URL / phone).
    2. Strip leading bullet chars and merge continuation lines in every
       flat list-of-strings section (including bullets / description
       sub-lists inside list-of-dict sections).
    """
    if not isinstance(parsed, dict):
        return parsed

    result = dict(parsed)

    # 1. Clean education: remove spurious contact-info entries
    edu = result.get('education')
    if isinstance(edu, list):
        kept = []
        for entry in edu:
            if not isinstance(entry, dict):
                kept.append(entry)
                continue
            degree = (entry.get('degree') or '').strip()
            institution = (entry.get('institution') or '').strip()
            desc = entry.get('description') or []
            desc_text = ' '.join(str(d) for d in desc) if isinstance(desc, list) else str(desc)

            # Looks like contact info masquerading as an education entry?
            if _CONTACT_PAT.search(desc_text) or _CONTACT_PAT.search(institution):
                if not _EDU_KEYWORDS.search(institution):
                    continue   # skip it
            # Empty degree with no recognisable institution is also suspicious
            if not degree and not _EDU_KEYWORDS.search(institution):
                continue
            kept.append(entry)
        result['education'] = kept

    # 2. Strip bullet prefixes & merge continuations everywhere
    for key, val in result.items():
        if isinstance(val, list) and val:
            if isinstance(val[0], str):
                # Flat list of strings
                result[key] = _clean_flat_list(val)
            elif isinstance(val[0], dict):
                # List of dicts — clean their bullets/description sub-lists
                for item in val:
                    if not isinstance(item, dict):
                        continue
                    for subkey in ('bullets', 'description'):
                        if isinstance(item.get(subkey), list):
                            item[subkey] = _clean_flat_list(item[subkey])
        elif isinstance(val, dict):
            # Top-level dict (e.g. {bullets: [...], description: [...]})
            for subkey in ('bullets', 'description'):
                if isinstance(val.get(subkey), list):
                    val[subkey] = _clean_flat_list(val[subkey])

    return result


def _build_raw_text(extracted_data):
    """Build a plain-text representation from extracted data for display."""
    parts = []
    for page in extracted_data.get('pages', []):
        for line in page.get('lines', []):
            text = line.get('text', '').strip()
            if text:
                parts.append(text)
    return '\n'.join(parts)


def load_yaml(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return yaml.safe_load(f) or {}


# --- Auth routes ---

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')

    if not name or not email or not password:
        return render_template('signup.html', error='All fields are required.')
    if len(password) < 6:
        return render_template('signup.html', error='Password must be at least 6 characters.')

    user_id = create_user(name, email, password)
    if user_id is None:
        return render_template('signup.html', error='An account with this email already exists.')

    session['user_id'] = user_id
    return redirect(url_for('onboarding'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')

    user = authenticate_user(email, password)
    if not user:
        return render_template('login.html', error='Invalid email or password.')

    session['user_id'] = user['id']
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- Onboarding ---

@app.route('/onboarding')
@login_required
def onboarding():
    user_id = get_current_user_id()
    if is_onboarding_complete(user_id):
        return redirect(url_for('index'))
    user = get_user_by_id(user_id)
    return render_template('onboarding.html', user=user)


@app.route('/api/upload_resume', methods=['POST'])
@login_required
def upload_resume():
    """Upload and parse a PDF during onboarding. Returns parsed data as JSON.

    Pipeline (in priority order):
      1. Extract text (Daytona sandbox if available, else local)
      2. Parse:
         a. Locked smart parser (stored code) — if user has confirmed one
         b. Smart parser — LLM generates + runs a custom parse() in Daytona
         c. AI two-phase (legacy) — if api key provided but no smart parser creds
         d. Heuristic fallback — always works, no key required
      3. Return YAML + header + confidence + style
    """
    user_id = get_current_user_id()
    if is_onboarding_complete(user_id):
        return jsonify({"status": "error", "message": "Onboarding already completed."}), 400

    pdf_file = request.files.get('resume_pdf')
    if not pdf_file or not pdf_file.filename or not pdf_file.filename.lower().endswith('.pdf'):
        return jsonify({"status": "error", "message": "Please upload a valid PDF file."}), 400

    # Resolve AI credentials from form data or DB-stored config
    form_data = {
        'ai_provider': request.form.get('ai_provider', ''),
        'ai_api_key': request.form.get('ai_api_key', ''),
        'ai_model': request.form.get('ai_model', ''),
    }
    try:
        ai_provider, ai_api_key, ai_model = _resolve_ai_credentials(form_data, user_id)
    except ValueError:
        ai_provider, ai_api_key, ai_model = '', '', ''

    user_dir = get_user_dir(user_id)
    os.makedirs(user_dir, exist_ok=True)
    os.makedirs(os.path.join(user_dir, 'versions'), exist_ok=True)
    pdf_path = os.path.join(user_dir, 'onboarding_upload.pdf')
    pdf_file.save(pdf_path)

    try:
        extracted_style = extract_style_from_pdf(pdf_path)

        # Step 1: Extract text with font metadata
        sandbox_logs = []
        extracted_data, sandbox_logs = daytona_sandbox.extract_text_in_sandbox(pdf_path)
        extraction_source = 'sandbox'
        if not extracted_data:
            extracted_data = extract_text_local(pdf_path)
            extraction_source = 'local'
            sandbox_logs.append("Falling back to local extraction")

        if not extracted_data or not extracted_data.get('pages'):
            return jsonify({"status": "error",
                            "message": "Could not extract text from PDF. The file may be image-only or corrupted."}), 500

        # Build flat line list for smart parser
        flat_lines = []
        for page in extracted_data.get('pages', []):
            flat_lines.extend(page.get('lines', []))

        raw_text = _build_raw_text(extracted_data)

        # Resolve smart-parser credentials (user key > env var > None)
        sp_provider, sp_api_key, sp_model = sp.resolve_parser_credentials(
            ai_provider, ai_api_key, ai_model
        )

        # Step 2: Parse into structured data
        ai_error_info = None
        parser_used = 'heuristic'
        generated_parser_code = None

        # 2a. Check for an ACTIVE or LOCKED parser via parser_service
        best_parser = parser_service.get_best_parser(user_id)
        if best_parser:
            parser_state = best_parser['state']
            app.logger.info(f"[SmartParser] Using {parser_state} parser (id={best_parser['id']}) for user {user_id}")
            if parser_state == 'LOCKED':
                # Privacy-preserving path: extract + run + verify all inside one sandbox.
                # Raw lines never leave the Daytona container.
                verify_result, verify_logs = daytona_sandbox.extract_and_test_parser(
                    pdf_path, best_parser['code']
                )
                sandbox_logs.extend(verify_logs)
                _locked_parsed = verify_result.get('parsed') if verify_result else None
                if _has_meaningful_content(_locked_parsed):
                    parsed = sp.normalize_dates(_locked_parsed)
                    parser_used = 'smart_locked'
                    cov = verify_result.get('coverage_score', 0)
                    app.logger.info(f"[SmartParser] Locked parser coverage: {cov}%")
                else:
                    # LOCKED parser returned empty/sparse result — fall through to generation
                    app.logger.warning("[SmartParser] Locked parser returned no content, regenerating...")
                    best_parser = None
            if best_parser and parser_state == 'ACTIVE':
                result, final_code, sp_logs = parser_service.run_parser(
                    best_parser['id'], user_id, flat_lines,
                    provider=sp_provider, api_key=sp_api_key, model=sp_model
                )
                sandbox_logs.extend(sp_logs)
                if _has_meaningful_content(result):
                    parsed = sp.normalize_dates(result)
                    parser_used = 'smart_active'
                else:
                    app.logger.warning("[SmartParser] Active parser returned no content, falling back to heuristic")
                    parsed = parse_resume_from_extracted(extracted_data)

        # 2b. Generate a new smart parser (if credentials available and no usable parser)
        if not best_parser and sp_provider and sp_api_key:
            app.logger.info(f"[SmartParser] Generating new parser for user {user_id}")
            try:
                with open(pdf_path, 'rb') as _pf:
                    _pdf_bytes = _pf.read()
                parser_id, code, gen_logs = parser_service.generate_and_store_parser(
                    user_id, flat_lines, sp_provider, sp_api_key, sp_model,
                    pdf_bytes=_pdf_bytes
                )
                sandbox_logs.extend(gen_logs)
                result, final_code, sp_logs = parser_service.run_parser(
                    parser_id, user_id, flat_lines,
                    provider=sp_provider, api_key=sp_api_key, model=sp_model
                )
                sandbox_logs.extend(sp_logs)
                _HEADER_KEYS = {'name', 'contact', '_section_headings', '_date_parsed'}
                _result_keys = [k for k in (result or {}) if k not in _HEADER_KEYS and (result or {}).get(k)]
                app.logger.info(f"[SmartParser] Parser result keys with content: {_result_keys}")
                if _has_meaningful_content(result):
                    parsed = sp.normalize_dates(result)
                    parser_used = 'smart_generated'
                    generated_parser_code = final_code
                    app.logger.info(f"[SmartParser] Parser accepted (DRAFT id={parser_id})")
                else:
                    app.logger.warning(f"[SmartParser] Parser returned only header fields {list((result or {}).keys())}, falling back to heuristic")
                    parsed = parse_resume_from_extracted(extracted_data)
            except Exception as e:
                ai_error_info = _extract_ai_error_info(e)
                app.logger.error(f"[SmartParser] Generation failed: {ai_error_info['message']}", exc_info=True)
                parsed = parse_resume_from_extracted(extracted_data)

        # 2c. Heuristic fallback (no parser, no credentials, or all above failed)
        elif not best_parser and not (sp_provider and sp_api_key):
            parsed = parse_resume_from_extracted(extracted_data)

        if not parsed:
            return jsonify({"status": "error",
                            "message": "Could not parse the PDF. Try providing an AI API key for better results."}), 500

        # Clean up common AI parser artifacts (bullet prefixes, contact-as-education, etc.)
        parsed = _clean_parsed_resume(parsed)

        # Step 3: Build response
        confidence = score_parsed_resume(parsed)

        header = {
            "name": parsed.get('name', ''),
            "contact": parsed.get('contact', {})
        }

        # Build section_names from original PDF headings (not defaults)
        raw_headings = parsed.pop('_section_headings', {})
        section_names = {}
        for key, heading_text in raw_headings.items():
            section_names[key] = heading_text

        custom_sections = []
        for key in parsed:
            if key not in BUILTIN_KEYS:
                display_name = raw_headings.get(key, key.replace('_', ' ').upper())
                render_type = _infer_render_type(parsed[key])
                custom_sections.append({
                    "key": key,
                    "display_name": display_name,
                    "render_type": render_type
                })

        editable_data = strip_header(parsed, header)
        yaml_content = yaml.dump(editable_data, sort_keys=False, allow_unicode=True)

        # Emit sandbox logs through the logging system
        if sandbox_logs:
            app.logger.info(f"[Sandbox] {extraction_source} extraction logs:")
            for log_line in sandbox_logs:
                app.logger.info(f"  {log_line}")

        response_payload = {
            "yaml": yaml_content,
            "header": header,
            "style": extracted_style,
            "custom_sections": custom_sections,
            "section_names": section_names,
            "confidence": confidence,
            "extraction_source": extraction_source,
            "parser_used": parser_used,
        }

        if generated_parser_code:
            response_payload["generated_parser_code"] = generated_parser_code

        if ai_error_info:
            response_payload["status"] = "ai_parse_failed"
            response_payload["ai_error"] = ai_error_info["message"]
            response_payload["ai_status_code"] = ai_error_info["status_code"]
        else:
            response_payload["status"] = "success"

        return jsonify(response_payload)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/sandbox_status')
@login_required
def sandbox_status():
    """Check if Daytona sandbox is available for parsing."""
    return jsonify({
        "available": daytona_sandbox.is_available(),
        "api_url": daytona_sandbox.DAYTONA_API_URL if daytona_sandbox.DAYTONA_API_KEY else None,
    })


@app.route('/api/uploaded_pdf')
@login_required
def serve_uploaded_pdf():
    """Serve the uploaded onboarding PDF for in-browser viewing."""
    user_id = get_current_user_id()
    pdf_path = os.path.join(get_user_dir(user_id), 'onboarding_upload.pdf')
    if os.path.exists(pdf_path):
        return send_file(pdf_path, mimetype='application/pdf')
    return jsonify({"status": "error", "message": "No PDF found"}), 404


@app.route('/api/search_section', methods=['POST'])
@login_required
def search_section():
    """Search for a missing section in the uploaded PDF.

    Tries sandbox first, falls back to local pdfplumber extraction.
    Returns the found section as a YAML snippet ready to append.
    """
    user_id = get_current_user_id()
    data = request.json
    section_hint = data.get('section_hint', '').strip()

    if not section_hint:
        return jsonify({"status": "error", "message": "Please enter a section name to search for."}), 400

    user_dir = get_user_dir(user_id)
    pdf_path = os.path.join(user_dir, 'onboarding_upload.pdf')

    if not os.path.exists(pdf_path):
        return jsonify({"status": "error", "message": "No PDF uploaded. Please re-upload your resume."}), 400

    try:
        # Try sandbox search first
        search_result, _search_logs = daytona_sandbox.search_section_in_sandbox(pdf_path, section_hint)

        # Fallback to local search
        if not search_result.get('found'):
            search_result = _search_section_local(pdf_path, section_hint)

        if not search_result.get('found'):
            return jsonify({"status": "not_found",
                            "message": f"Could not find a section matching '{section_hint}' in your PDF."})

        # Parse the found lines into structured data
        section_lines = search_result.get('lines', [])
        text_lines = [l.get('text', '') for l in section_lines]
        line_meta = section_lines  # already has text/size/bold

        # Use smart parsing to determine best format
        render_type, parsed = _smart_parse_section(text_lines, line_meta)

        # Build section key
        section_key = _normalize_section_key(section_hint)
        if not section_key or section_key == 'other':
            section_key = section_hint.lower().replace(' ', '_')

        # Build YAML snippet
        yaml_snippet = yaml.dump({section_key: parsed}, sort_keys=False, allow_unicode=True)

        # Raw text for display
        raw_lines = '\n'.join(text_lines)

        return jsonify({
            "status": "found",
            "section_key": section_key,
            "heading": search_result.get('heading', section_hint),
            "yaml_snippet": yaml_snippet,
            "raw_lines": raw_lines,
            "render_type": render_type,
            "display_name": section_hint.upper()
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def _search_section_local(pdf_path, section_hint):
    """Local fallback for section search using pdfplumber directly."""
    try:
        extracted = extract_text_local(pdf_path)
        if not extracted or not extracted.get('pages'):
            return {"found": False}

        hint_lower = section_hint.lower().strip()

        # Flatten all lines
        all_lines = []
        for page in extracted['pages']:
            for line in page.get('lines', []):
                all_lines.append(line)

        # Search for the heading
        for i, line in enumerate(all_lines):
            line_lower = line.get('text', '').lower().strip()
            if hint_lower in line_lower or line_lower in hint_lower:
                alpha = [c for c in line.get('text', '') if c.isalpha()]
                is_caps = alpha and all(c.isupper() for c in alpha) and len(alpha) > 2
                if line.get('bold') or is_caps or line.get('size', 10) > 11:
                    context_lines = all_lines[i + 1:i + 31]
                    return {
                        "found": True,
                        "heading": line['text'],
                        "lines": context_lines
                    }

        return {"found": False}
    except Exception:
        return {"found": False}


@app.route('/api/complete_onboarding', methods=['POST'])
@login_required
def complete_onboarding():
    """Save finalized resume data and mark onboarding complete."""
    user_id = get_current_user_id()
    if is_onboarding_complete(user_id):
        return jsonify({"status": "error", "message": "Onboarding already completed."}), 400

    data = request.json
    resume_yaml = data.get('resume', '')
    header = data.get('header', {})
    style = data.get('style', {})
    custom_sections = data.get('custom_sections', [])
    section_names = data.get('section_names', {})

    try:
        user_dir = get_user_dir(user_id)
        current_settings = get_user_settings(user_id)

        merged_header = current_settings['header'].copy()
        if header.get('name'):
            merged_header['name'] = header['name']
        if header.get('contact'):
            for k, v in header['contact'].items():
                if v:
                    merged_header.setdefault('contact', {})[k] = v

        # Merge parsed section names with defaults
        merged_section_names = current_settings.get('section_names', DEFAULT_SECTION_NAMES.copy())
        if section_names:
            merged_section_names.update(section_names)

        update_user_settings(user_id, header=merged_header, style=style,
                             custom_sections=custom_sections,
                             section_names=merged_section_names)

        if resume_yaml.strip():
            full_data = merge_header(resume_yaml, merged_header)
            full_yaml = yaml.dump(full_data, sort_keys=False, allow_unicode=True)
            # Use resume_service so the initial upload is versioned in the DB
            _save_resume(user_id, full_yaml, source='upload', label='Initial upload')

        # Delete the raw PDF — PII no longer needed once YAML is saved
        onboarding_pdf = os.path.join(user_dir, 'onboarding_upload.pdf')
        if os.path.exists(onboarding_pdf):
            os.remove(onboarding_pdf)

        mark_onboarding_complete(user_id)
        return jsonify({"status": "success", "message": "Setup complete!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/ai_change_request', methods=['POST'])
@login_required
def ai_change_request():
    """Apply an AI-driven change request to the parsed YAML during onboarding review."""
    user_id = get_current_user_id()
    data = request.json
    yaml_content = data.get('yaml', '')
    change_request = data.get('change_request', '').strip()

    if not yaml_content or not change_request:
        return jsonify({"status": "error", "message": "YAML content and change request are required."}), 400

    try:
        ai_provider, ai_api_key, ai_model = _resolve_ai_credentials(data, user_id)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    try:
        system_prompt = """You are a resume content editor. You will receive a resume in YAML format and a user's change request.

Apply the requested changes to the YAML content and return the MODIFIED YAML.

Rules:
- Return ONLY the modified YAML content, no explanation or markdown code fences.
- Preserve the YAML structure and formatting.
- Only modify what the user requested. Do not add, remove, or change anything else.
- Keep all existing content intact unless the user explicitly asks to change it.
- If the request is unclear, make the most reasonable interpretation."""

        user_msg = f"CURRENT YAML:\n{yaml_content}\n\nCHANGE REQUEST:\n{change_request}"
        response_text = call_ai_provider(ai_provider, ai_api_key, system_prompt, user_msg, ai_model)

        # Clean up response — remove markdown code fences if present
        modified_yaml = response_text.strip()
        if modified_yaml.startswith('```'):
            lines = modified_yaml.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            modified_yaml = '\n'.join(lines)

        # Validate it's parseable YAML
        try:
            yaml.safe_load(modified_yaml)
        except Exception:
            return jsonify({"status": "error", "message": "AI returned invalid YAML. Try rephrasing your request."}), 400

        return jsonify({"status": "success", "yaml": modified_yaml})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/skip_onboarding', methods=['POST'])
@login_required
def skip_onboarding():
    """Skip onboarding and go straight to the editor."""
    user_id = get_current_user_id()
    if is_onboarding_complete(user_id):
        return jsonify({"status": "error", "message": "Onboarding already completed."}), 400

    mark_onboarding_complete(user_id)
    return jsonify({"status": "success", "message": "Onboarding skipped."})


# --- Main editor ---

@app.route('/')
@login_required
def index():
    user_id = get_current_user_id()
    if not is_onboarding_complete(user_id):
        return redirect(url_for('onboarding'))
    user_dir = get_user_dir(user_id)
    header = get_current_user_header()
    section_names = get_current_section_names()
    custom_sections = get_current_custom_sections()
    user = get_user_by_id(user_id)

    resume_path = os.path.join(user_dir, 'resume.yaml')
    has_resume = os.path.exists(resume_path)

    if has_resume:
        resume_data = load_yaml(resume_path)
        editable_data = strip_header(resume_data, header)
    else:
        editable_data = {}

    # Load saved style from user settings, with defaults
    settings = get_user_settings(user_id)
    saved_style = settings.get('style', {})
    style = {
        'font_family': saved_style.get('font_family', '"Times New Roman", Times, serif'),
        'font_size': saved_style.get('font_size', '10pt'),
        'line_height': saved_style.get('line_height', '1.2'),
        'margin': saved_style.get('margin', '0.4in'),
        'accent_color': saved_style.get('accent_color', '#000000')
    }

    return render_template('editor.html',
                           resume=yaml.dump(editable_data, sort_keys=False, allow_unicode=True) if editable_data else '',
                           style=style,
                           fixed_header=header,
                           section_names=section_names,
                           custom_sections=custom_sections,
                           user=user,
                           has_resume=has_resume)


# --- API routes ---

@app.route('/api/preview', methods=['POST'])
@login_required
def preview():
    data = request.json
    resume_yaml = data.get('resume', '')
    style = data.get('style', {})

    try:
        # Allow overrides from request (used during onboarding before data is saved)
        header = data.get('header') or get_current_user_header()
        section_names = data.get('section_names') or get_current_section_names()
        custom_sections = data.get('custom_sections') or get_current_custom_sections()
        resume_data = merge_header(resume_yaml, header)

        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        env.filters['md_bold'] = _md_bold
        template = env.get_template('resume.html')
        html_content = template.render(resume=resume_data, style=style,
                                       section_names=section_names,
                                       custom_sections=custom_sections)

        return html_content
    except Exception as e:
        return str(e), 400


@app.route('/api/save', methods=['POST'])
@login_required
def save():
    data = request.json
    resume_yaml = data.get('resume', '')
    keyword = data.get('keyword', 'default')
    # tags: optional list of strings to attach to this version for JD matching
    # e.g. ["python", "backend", "aws"]
    tags = data.get('tags') or None
    if isinstance(tags, list):
        tags = [str(t).strip() for t in tags if str(t).strip()]
    if not tags:
        tags = None

    try:
        user_id = get_current_user_id()
        versions_dir = get_user_versions_dir(user_id)
        header = get_current_user_header()
        user = get_user_by_id(user_id)

        full_data = merge_header(resume_yaml, header)
        full_yaml = yaml.dump(full_data, sort_keys=False, allow_unicode=True)

        # Save main file + DB version row (with optional tags)
        from services.resume import save_current_resume as _save_version
        version_id = _save_version(user_id, full_yaml, source='manual_edit', label=keyword, tags=tags)

        # Also write legacy file-based version for backward compat
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_keyword = "".join([c for c in keyword if c.isalnum() or c in ('-', '_')]).strip()
        if not safe_keyword:
            safe_keyword = "default"
        safe_name = "".join([c for c in user['name'] if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
        version_filename = f"{safe_name}_{safe_keyword}_{timestamp}.yaml"
        os.makedirs(versions_dir, exist_ok=True)
        with open(os.path.join(versions_dir, version_filename), 'w') as f:
            f.write(full_yaml)

        return jsonify({
            "status": "success",
            "message": f"Saved as {version_filename}",
            "version_id": version_id,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/history')
@login_required
def history():
    user_id = get_current_user_id()
    versions_dir = get_user_versions_dir(user_id)

    if not os.path.exists(versions_dir):
        return jsonify([])

    files = glob.glob(os.path.join(versions_dir, '*.yaml'))
    files.sort(key=os.path.getmtime, reverse=True)
    history_list = []
    for f in files:
        filename = os.path.basename(f)
        timestamp = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M:%S")
        history_list.append({"filename": filename, "timestamp": timestamp})
    return jsonify(history_list)


@app.route('/api/load/<filename>')
@login_required
def load_version(filename):
    try:
        user_id = get_current_user_id()
        versions_dir = get_user_versions_dir(user_id)
        header = get_current_user_header()

        # Sanitize filename
        filename = os.path.basename(filename)
        filepath = os.path.join(versions_dir, filename)
        if not os.path.exists(filepath):
            return jsonify({"status": "error", "message": "File not found"}), 404

        with open(filepath, 'r') as f:
            content = f.read()

        editable_data = strip_header(content, header)
        editable_yaml = yaml.dump(editable_data, sort_keys=False, allow_unicode=True)

        return jsonify({"status": "success", "content": editable_yaml})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/delete_version/<filename>', methods=['DELETE'])
@login_required
def delete_version(filename):
    try:
        user_id = get_current_user_id()
        versions_dir = get_user_versions_dir(user_id)

        filename = os.path.basename(filename)
        filepath = os.path.join(versions_dir, filename)

        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({"status": "success", "message": f"Deleted {filename}"})
        else:
            return jsonify({"status": "error", "message": "File not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# --- Settings ---

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user_id = get_current_user_id()

    if request.method == 'GET':
        s = get_user_settings(user_id)
        return jsonify({"status": "success", "settings": s})

    data = request.json
    header = data.get('header')
    section_names = data.get('section_names')
    custom_sections = data.get('custom_sections')

    update_user_settings(user_id, header=header, section_names=section_names,
                         custom_sections=custom_sections)
    return jsonify({"status": "success", "message": "Settings saved."})


@app.route('/api/settings/ai_config', methods=['GET', 'POST', 'DELETE'])
@login_required
def ai_config():
    """Manage the user's AI provider configuration (API key stored encrypted)."""
    user_id = get_current_user_id()

    if request.method == 'GET':
        config = get_user_api_config(user_id)
        if config:
            return jsonify({
                "status": "success",
                "provider": config.get('provider', 'anthropic'),
                "has_key": True,
                "model": config.get('model') or '',
            })
        return jsonify({
            "status": "success",
            "provider": "",
            "has_key": False,
            "model": "",
        })

    if request.method == 'DELETE':
        delete_user_api_config(user_id)
        return jsonify({"status": "success", "message": "AI configuration removed."})

    # POST: save new config
    data = request.json
    provider = (data.get('provider') or 'anthropic').strip()
    api_key = (data.get('api_key') or '').strip()
    model = (data.get('model') or '').strip() or None

    if not api_key:
        return jsonify({"status": "error", "message": "api_key is required"}), 400

    encrypted_key = encrypt_api_key(api_key)
    save_user_api_config(user_id, provider, encrypted_key, model)

    return jsonify({"status": "success", "message": "AI configuration saved."})


# --- Per-user data file endpoints ---

def _read_user_file(user_id, filename):
    """Read a per-user data file, return content or empty string."""
    path = os.path.join(get_user_dir(user_id), filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ''


def _write_user_file(user_id, filename, content):
    """Write a per-user data file."""
    user_dir = get_user_dir(user_id)
    os.makedirs(user_dir, exist_ok=True)
    with open(os.path.join(user_dir, filename), 'w', encoding='utf-8') as f:
        f.write(content)


@app.route('/api/settings/resume_rules', methods=['GET', 'PUT'])
@login_required
def user_resume_rules():
    """Read/write the user's resume generation rules."""
    user_id = get_current_user_id()
    if request.method == 'GET':
        return jsonify({"status": "success", "content": _read_user_file(user_id, 'resume_rules.md')})
    _write_user_file(user_id, 'resume_rules.md', (request.json or {}).get('content', ''))
    return jsonify({"status": "success", "message": "Resume rules saved."})


@app.route('/api/settings/candidate_database', methods=['GET', 'PUT'])
@login_required
def user_candidate_database():
    """Read/write the user's candidate database."""
    user_id = get_current_user_id()
    if request.method == 'GET':
        return jsonify({"status": "success", "content": _read_user_file(user_id, 'candidate_database.md')})
    _write_user_file(user_id, 'candidate_database.md', (request.json or {}).get('content', ''))
    return jsonify({"status": "success", "message": "Candidate database saved."})


@app.route('/api/settings/cover_letter_database', methods=['GET', 'PUT'])
@login_required
def user_cover_letter_database():
    """Read/write the user's cover letter database."""
    user_id = get_current_user_id()
    if request.method == 'GET':
        return jsonify({"status": "success", "content": _read_user_file(user_id, 'cover_letter_database.md')})
    _write_user_file(user_id, 'cover_letter_database.md', (request.json or {}).get('content', ''))
    return jsonify({"status": "success", "message": "Cover letter database saved."})


@app.route('/api/jd_sessions', methods=['GET'])
@login_required
def list_jd_sessions_route():
    """List past JD analysis sessions for the current user."""
    from models import list_jd_sessions
    user_id = get_current_user_id()
    sessions = list_jd_sessions(user_id)
    return jsonify({"status": "success", "sessions": sessions})


# --- Delete Profile ---

@app.route('/api/mcp_key', methods=['GET'])
@login_required
def get_mcp_key():
    """Return the current MCP API key for the logged-in user (generate one if missing)."""
    user_id = get_current_user_id()
    key = get_mcp_api_key(user_id)
    if not key:
        key = generate_mcp_api_key(user_id)
    return jsonify({"mcp_api_key": key})


@app.route('/api/mcp_key/regenerate', methods=['POST'])
@login_required
def regenerate_mcp_key():
    """Invalidate the existing MCP key and issue a new one."""
    user_id = get_current_user_id()
    key = generate_mcp_api_key(user_id)
    return jsonify({"mcp_api_key": key})


@app.route('/api/feedback', methods=['POST'])
@login_required
def submit_feedback():
    """Save user feedback to a file."""
    data = request.json
    feedback_text = data.get('feedback', '').strip()

    if not feedback_text:
        return jsonify({"status": "error", "message": "Feedback cannot be empty."}), 400

    user_id = get_current_user_id()
    user = get_user_by_id(user_id)
    user_name = user['name'] if user else 'Unknown'

    feedback_file = os.path.join(DATA_DIR, 'feedback.jsonl')
    entry = {
        "timestamp": datetime.now().isoformat(),
        "user_name": user_name,
        "user_id": user_id,
        "feedback": feedback_text
    }

    try:
        with open(feedback_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        return jsonify({"status": "success", "message": "Thank you for your feedback!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/delete_profile', methods=['POST'])
@login_required
def delete_profile():
    data = request.json
    password = data.get('password', '')
    user_id = get_current_user_id()

    if not password:
        return jsonify({"status": "error", "message": "Password is required."}), 400

    if not verify_user_password(user_id, password):
        return jsonify({"status": "error", "message": "Incorrect password."}), 403

    try:
        delete_user(user_id)
        session.clear()
        return jsonify({"status": "success", "message": "Account deleted."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# --- Parser state management ---

@app.route('/api/parser/list', methods=['GET'])
@login_required
def list_parsers():
    user_id = get_current_user_id()
    parsers = parser_service.list_user_parsers(user_id)
    return jsonify({"status": "success", "parsers": parsers})


@app.route('/api/parser/activate', methods=['POST'])
@login_required
def activate_parser():
    """Transition a DRAFT parser to ACTIVE (user confirmed content is correct)."""
    user_id = get_current_user_id()
    parser_id = request.json.get('parser_id')
    if not parser_id:
        return jsonify({"status": "error", "message": "parser_id required"}), 400
    try:
        parser_service.activate_parser(int(parser_id), user_id)
        return jsonify({"status": "success", "message": "Parser is now ACTIVE"})
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/api/parser/lock', methods=['POST'])
@login_required
def lock_parser():
    """ACTIVE/DRAFT → LOCKED: user confirmed this is their PDF layout."""
    user_id = get_current_user_id()
    parser_id = request.json.get('parser_id')
    if not parser_id:
        return jsonify({"status": "error", "message": "parser_id required"}), 400
    try:
        parser_service.confirm_and_lock(int(parser_id), user_id)
        return jsonify({"status": "success", "message": "Parser locked"})
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/api/parser/unlock', methods=['POST'])
@login_required
def unlock_parser():
    """LOCKED → ACTIVE: allow regeneration while keeping the code."""
    user_id = get_current_user_id()
    parser_id = request.json.get('parser_id')
    if not parser_id:
        return jsonify({"status": "error", "message": "parser_id required"}), 400
    try:
        parser_service.unlock_parser(int(parser_id), user_id)
        return jsonify({"status": "success", "message": "Parser unlocked"})
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/api/parser/discard', methods=['POST'])
@login_required
def discard_parser():
    """Delete a parser entirely."""
    user_id = get_current_user_id()
    parser_id = request.json.get('parser_id')
    if not parser_id:
        return jsonify({"status": "error", "message": "parser_id required"}), 400
    try:
        parser_service.discard_parser(int(parser_id), user_id)
        return jsonify({"status": "success", "message": "Parser deleted"})
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


# --- Resume versioning ---

@app.route('/api/versions', methods=['GET'])
@login_required
def list_versions():
    from services.resume import list_versions as _list_versions
    user_id = get_current_user_id()
    versions = _list_versions(user_id)
    return jsonify({"status": "success", "versions": versions})


@app.route('/api/versions/restore', methods=['POST'])
@login_required
def restore_version():
    from services.resume import restore_version as _restore
    user_id = get_current_user_id()
    version_id = request.json.get('version_id')
    if not version_id:
        return jsonify({"status": "error", "message": "version_id required"}), 400
    try:
        yaml_content = _restore(int(version_id), user_id)
        return jsonify({"status": "success", "yaml": yaml_content})
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/api/versions/<int:version_id>/tags', methods=['PATCH'])
@login_required
def update_version_tags(version_id):
    """Set or replace tags on a saved version (used for JD best-match selection).

    Body: {"tags": ["python", "backend", "aws"]}
    """
    from services.resume import tag_version as _tag_version
    user_id = get_current_user_id()
    data = request.json or {}
    tags = data.get('tags', [])
    if not isinstance(tags, list):
        return jsonify({"status": "error", "message": "tags must be a list of strings"}), 400
    tags = [str(t).strip() for t in tags if str(t).strip()]
    try:
        _tag_version(version_id, user_id, tags)
        return jsonify({"status": "success", "version_id": version_id, "tags": tags})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# --- JD analysis + application (new structured workflow) ---

@app.route('/api/jd_analyze', methods=['POST'])
@login_required
def jd_analyze():
    """Analyze the current resume against a JD. Returns match score + suggestions."""
    user_id = get_current_user_id()
    data = request.json
    jd_text = data.get('jd_text', '').strip()

    if not jd_text:
        return jsonify({"status": "error", "message": "jd_text is required"}), 400

    try:
        provider, api_key, model = _resolve_ai_credentials(data, user_id)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    try:
        session_id, result, logs = jd_service.analyze(user_id, jd_text, provider, api_key, model)
        return jsonify({
            "status": "success",
            "session_id": session_id,
            "match_score": result['match_score'],
            "suggestions": result['suggestions'],
            "base_version_id": result.get('base_version_id'),
            "base_version_label": result.get('base_version_label'),
            "logs": logs,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/jd_apply', methods=['POST'])
@login_required
def jd_apply():
    """Apply selected JD suggestions to the current resume. Saves a new version."""
    user_id = get_current_user_id()
    data = request.json
    session_id = data.get('session_id')
    suggestion_ids = data.get('suggestion_ids', [])

    if not session_id:
        return jsonify({"status": "error", "message": "session_id is required"}), 400
    if not suggestion_ids:
        return jsonify({"status": "error", "message": "suggestion_ids is required"}), 400

    try:
        provider, api_key, model = _resolve_ai_credentials(data, user_id)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    try:
        new_yaml, version_id, logs = jd_service.apply_suggestions(
            user_id, int(session_id), suggestion_ids, provider, api_key, model
        )
        return jsonify({
            "status": "success",
            "yaml": new_yaml,
            "version_id": version_id,
            "logs": logs,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/jd_generate', methods=['POST'])
@login_required
def jd_generate():
    """Multi-agent pipeline: generate tailored resume, fit to 1 page, verify ATS score.

    Workflow: pre-screen -> version match -> generate -> pdf fit -> ats verify -> loop -> tag & save.
    Returns the final YAML, ATS score, page count, and populates the user's preview.
    """
    user_id = get_current_user_id()
    data = request.json
    jd_text = data.get('jd_text', '').strip()
    target_score = data.get('target_score', 90)

    if not jd_text:
        return jsonify({"status": "error", "message": "jd_text is required"}), 400

    try:
        provider, api_key, model = _resolve_ai_credentials(data, user_id)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    try:
        result = jd_resume_agent.generate_resume_for_jd(
            user_id=user_id,
            jd_text=jd_text,
            provider=provider,
            api_key=api_key,
            model=model,
            target_score=target_score,
        )
        return jsonify({
            "status": "success",
            "yaml": result['yaml'],
            "version_id": result['version_id'],
            "ats_score": result['ats_score'],
            "ats_details": result['ats_details'],
            "assessment": result['assessment'],
            "pages": result['pages'],
            "role_type": result['role_type'],
            "blockers": result['blockers'],
            "tags": result['tags'],
            "iterations": result['iterations'],
            "logs": result['logs'],
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/jd_agent/diff', methods=['GET'])
@login_required
def jd_agent_diff():
    """Compare current resume vs last agent-generated version.

    Returns the diff so the user can be asked why they made changes.
    """
    user_id = get_current_user_id()

    agent_version = jd_resume_agent.get_last_agent_version(user_id)
    if not agent_version:
        return jsonify({"status": "error", "message": "No agent-generated version found"}), 404

    current_yaml = jd_resume_agent.get_current_resume(user_id)
    if not current_yaml:
        return jsonify({"status": "error", "message": "No current resume found"}), 404

    changes = jd_resume_agent.diff_versions(agent_version['yaml_content'], current_yaml)

    return jsonify({
        "status": "success",
        "agent_version_id": agent_version['id'],
        "changes": changes,
        "has_changes": len(changes) > 0,
    })


@app.route('/api/jd_agent/learn', methods=['POST'])
@login_required
def jd_agent_learn():
    """Store a learning from user edits to agent output.

    Body: {reason: "why the change was made", tags: ["backend", ...]}
    """
    user_id = get_current_user_id()
    data = request.json
    reason = data.get('reason', '').strip()
    tags = data.get('tags', [])

    if not reason:
        return jsonify({"status": "error", "message": "reason is required"}), 400

    agent_version = jd_resume_agent.get_last_agent_version(user_id)
    if not agent_version:
        return jsonify({"status": "error", "message": "No agent-generated version to diff against"}), 404

    current_yaml = jd_resume_agent.get_current_resume(user_id)
    if not current_yaml:
        return jsonify({"status": "error", "message": "No current resume"}), 404

    changes = jd_resume_agent.diff_versions(agent_version['yaml_content'], current_yaml)
    if not changes:
        return jsonify({"status": "success", "message": "No changes detected, nothing to learn"})

    jd_resume_agent.save_learning(user_id, tags, changes, reason)

    return jsonify({
        "status": "success",
        "message": f"Learned from {len(changes)} change(s): {reason}",
        "changes_count": len(changes),
    })


@app.route('/cover-letter')
@login_required
def cover_letter_page():
    """Cover letter editor page — split-pane YAML editor + live preview."""
    user_id = get_current_user_id()
    user = get_user_by_id(user_id)
    settings = get_user_settings(user_id)
    header = settings.get('header', {})
    contact = header.get('contact', {})

    # Load draft if it exists (written by Claude Code or the generate endpoint)
    draft_path = os.path.join(get_user_dir(user_id), 'cover_letter_draft.yaml')
    if os.path.exists(draft_path):
        with open(draft_path, 'r', encoding='utf-8') as f:
            default_yaml = f.read()
    else:
        default_yaml = yaml.dump({
            'salutation': 'Dear Hiring Manager,',
            'paragraphs': [
                'Your opening paragraph here.',
                'A story that demonstrates a relevant skill.',
                'Why this company specifically, or another relevant story.',
                'Brief closing with availability.',
            ],
        }, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return render_template('cover_letter_editor.html',
                           user=user, header=header, contact=contact,
                           default_yaml=default_yaml)


@app.route('/api/cover_letter/generate', methods=['POST'])
@login_required
def generate_cover_letter_route():
    """Generate a cover letter YAML from a JD.

    Body: {jd_text, company_name, role_title?, hiring_manager?}
    Returns: {status, yaml} — structured YAML with salutation + paragraphs.
    """
    user_id = get_current_user_id()
    data = request.json
    jd_text = data.get('jd_text', '').strip()
    company_name = data.get('company_name', '').strip()
    role_title = data.get('role_title', '').strip()
    hiring_manager = data.get('hiring_manager', '').strip()

    if not jd_text:
        return jsonify({"status": "error", "message": "Job description is required."}), 400
    if not company_name:
        return jsonify({"status": "error", "message": "Company name is required."}), 400

    try:
        provider, api_key, model = _resolve_ai_credentials(data, user_id)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    try:
        result = cover_letter_agent.generate_cover_letter(
            user_id=user_id,
            jd_text=jd_text,
            company_name=company_name,
            provider=provider,
            api_key=api_key,
            role_title=role_title,
            hiring_manager=hiring_manager,
            model=model,
        )
        # Convert plain text to structured YAML
        text = result.get("text", "")
        salutation = 'Dear Hiring Manager,'
        paragraphs = []
        lines = text.strip().splitlines()
        body_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if body_lines:
                    paragraphs.append(' '.join(body_lines))
                    body_lines = []
                continue
            if stripped.lower().startswith('dear ') and not paragraphs and not body_lines:
                salutation = stripped
            elif stripped.lower().startswith('sincerely') or stripped.lower().startswith('best') or stripped.lower().startswith('regards'):
                if body_lines:
                    paragraphs.append(' '.join(body_lines))
                    body_lines = []
                break
            else:
                body_lines.append(stripped)
        if body_lines:
            paragraphs.append(' '.join(body_lines))

        if hiring_manager:
            salutation = f'Dear {hiring_manager},'

        cl_data = {
            'salutation': salutation,
            'paragraphs': paragraphs if paragraphs else ['(No content generated)'],
        }
        cl_yaml = yaml.dump(cl_data, default_flow_style=False, allow_unicode=True, sort_keys=False)

        # Save as draft so the editor page loads it on refresh
        draft_path = os.path.join(get_user_dir(user_id), 'cover_letter_draft.yaml')
        os.makedirs(get_user_dir(user_id), exist_ok=True)
        with open(draft_path, 'w', encoding='utf-8') as f:
            f.write(cl_yaml)

        return jsonify({
            "status": "success",
            "yaml": cl_yaml,
            "company": company_name,
            "role": role_title,
        })
    except Exception as e:
        app.logger.error(f"Cover letter generation failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/cover_letter/preview', methods=['POST'])
@login_required
def preview_cover_letter():
    """Render cover letter YAML to HTML preview.

    Body: {yaml, company_name?}
    """
    user_id = get_current_user_id()
    data = request.json
    cl_yaml = data.get('yaml', '').strip()

    if not cl_yaml:
        return jsonify({"status": "error", "message": "No YAML provided."}), 400

    try:
        cl_data = yaml.safe_load(cl_yaml) or {}
    except yaml.YAMLError as e:
        return jsonify({"status": "error", "message": f"Invalid YAML: {e}"}), 400

    settings = get_user_settings(user_id)
    header = settings.get('header', {})
    contact = header.get('contact', {})

    salutation = cl_data.get('salutation', 'Dear Hiring Manager,')
    paragraphs = cl_data.get('paragraphs', [])
    if isinstance(paragraphs, str):
        paragraphs = [paragraphs]

    template_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = template_env.get_template('cover_letter.html')
    html = template.render(
        name=header.get('name', ''),
        contact=contact,
        date=datetime.now().strftime('%B %d, %Y'),
        salutation=salutation,
        paragraphs=paragraphs,
    )
    return jsonify({"status": "success", "html": html})


@app.route('/api/cover_letter/download', methods=['POST'])
@login_required
def download_cover_letter():
    """Render cover letter YAML as a PDF and return it for download.

    Body: {yaml, company_name?}
    """
    user_id = get_current_user_id()
    data = request.json
    cl_yaml = data.get('yaml', '').strip()
    company_name = data.get('company_name', '')

    if not cl_yaml:
        return jsonify({"status": "error", "message": "No YAML provided."}), 400

    try:
        cl_data = yaml.safe_load(cl_yaml) or {}
    except yaml.YAMLError as e:
        return jsonify({"status": "error", "message": f"Invalid YAML: {e}"}), 400

    settings = get_user_settings(user_id)
    header = settings.get('header', {})
    contact = header.get('contact', {})

    salutation = cl_data.get('salutation', 'Dear Hiring Manager,')
    paragraphs = cl_data.get('paragraphs', [])
    if isinstance(paragraphs, str):
        paragraphs = [paragraphs]

    template_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = template_env.get_template('cover_letter.html')
    html = template.render(
        name=header.get('name', ''),
        contact=contact,
        date=datetime.now().strftime('%B %d, %Y'),
        salutation=salutation,
        paragraphs=paragraphs,
    )

    pdf = HTML(string=html).write_pdf()
    filename = f"cover_letter_{company_name.replace(' ', '_').lower() or 'draft'}.pdf"

    from io import BytesIO
    buf = BytesIO(pdf)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)


@app.route('/api/cover_letter/draft', methods=['GET', 'PUT'])
@login_required
def cover_letter_draft():
    """Read/write the cover letter draft YAML.

    Claude Code writes here to auto-populate the cover letter editor.
    The editor page loads from here on init.
    """
    user_id = get_current_user_id()
    draft_path = os.path.join(get_user_dir(user_id), 'cover_letter_draft.yaml')

    if request.method == 'GET':
        if os.path.exists(draft_path):
            with open(draft_path, 'r', encoding='utf-8') as f:
                return jsonify({"status": "success", "yaml": f.read()})
        return jsonify({"status": "success", "yaml": ""})

    cl_yaml = (request.json or {}).get('yaml', '')
    os.makedirs(get_user_dir(user_id), exist_ok=True)
    with open(draft_path, 'w', encoding='utf-8') as f:
        f.write(cl_yaml)
    return jsonify({"status": "success", "message": "Draft saved."})


@app.route('/api/settings/cover_letter_rules', methods=['GET', 'PUT'])
@login_required
def user_cover_letter_rules():
    """Read/write the user's cover letter generation rules/instructions."""
    user_id = get_current_user_id()
    if request.method == 'GET':
        return jsonify({"status": "success", "content": _read_user_file(user_id, 'cover_letter_rules.md')})
    _write_user_file(user_id, 'cover_letter_rules.md', (request.json or {}).get('content', ''))
    return jsonify({"status": "success", "message": "Cover letter rules saved."})


@app.route('/api/jd_find', methods=['POST'])
@login_required
def jd_find():
    """Find a JD by company+role or URL, extract it, and run the resume pipeline.

    Body options:
      {company: "Stripe", role: "Backend Engineer"}
      {url: "https://boards.greenhouse.io/..."}
    """
    import requests as http_requests

    user_id = get_current_user_id()
    data = request.json
    company = data.get('company', '').strip()
    role = data.get('role', '').strip()
    url = data.get('url', '').strip()
    target_score = data.get('target_score', 90)

    try:
        provider, api_key, model = _resolve_ai_credentials(data, user_id)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    if not url and (not company or not role):
        return jsonify({"status": "error", "message": "Provide company+role or url"}), 400

    try:
        logs = []
        jd_text = None
        jd_url = url

        if url:
            # Direct URL: fetch and extract
            logs.append(f"Fetching JD from URL: {url}")
            resp = http_requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; ResumeBot/1.0)'
            })
            resp.raise_for_status()

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Remove scripts/styles
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            page_text = soup.get_text(separator='\n', strip=True)

            jd_text = jd_finder_agent.extract_jd_from_html(page_text, provider, api_key, model)
            if not jd_text:
                return jsonify({"status": "error", "message": "Could not extract a JD from that URL"}), 400
            logs.append(f"Extracted JD ({len(jd_text)} chars)")

        else:
            # Search for the JD
            query = jd_finder_agent.build_search_query(company, role)
            logs.append(f"Searching: {query}")

            # Use a simple web search via requests
            search_url = f"https://www.google.com/search?q={http_requests.utils.quote(query)}"
            resp = http_requests.get(search_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')
            search_text = soup.get_text(separator='\n', strip=True)[:5000]

            # Ask LLM to pick best URL
            selection = jd_finder_agent.select_best_url(
                search_text, company, role, provider, api_key, model
            )
            best_url = selection.get('best_url')
            logs.append(f"Best URL: {best_url} (confidence: {selection.get('confidence')})")

            if not best_url:
                return jsonify({
                    "status": "error",
                    "message": f"Could not find a job posting for {company} {role}",
                    "search_query": query,
                    "logs": logs,
                }), 404

            jd_url = best_url

            # Fetch the actual JD page
            resp2 = http_requests.get(best_url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (compatible; ResumeBot/1.0)'
            })
            resp2.raise_for_status()

            soup2 = BeautifulSoup(resp2.text, 'html.parser')
            for tag in soup2(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            page_text = soup2.get_text(separator='\n', strip=True)

            jd_text = jd_finder_agent.extract_jd_from_html(page_text, provider, api_key, model)
            if not jd_text:
                return jsonify({
                    "status": "error",
                    "message": f"Found URL but could not extract JD from {best_url}",
                    "jd_url": best_url,
                    "logs": logs,
                }), 400
            logs.append(f"Extracted JD ({len(jd_text)} chars)")

        # Run the full resume pipeline
        result = jd_resume_agent.generate_resume_for_jd(
            user_id=user_id,
            jd_text=jd_text,
            provider=provider,
            api_key=api_key,
            model=model,
            target_score=target_score,
        )

        result['jd_url'] = jd_url
        result['jd_text'] = jd_text
        result['finder_logs'] = logs
        result['status'] = 'success'
        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# --- AI features (existing) ---

@app.route('/api/match_jd', methods=['POST'])
@login_required
def match_jd():
    user_id = get_current_user_id()
    data = request.json
    jd_text = data.get('jd_text', '')

    if not jd_text:
        return jsonify({"status": "error", "message": "Missing JD text"}), 400

    try:
        provider, api_key, model = _resolve_ai_credentials(data, user_id)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    try:
        versions_dir = get_user_versions_dir(user_id)

        files = glob.glob(os.path.join(versions_dir, '*.yaml'))
        if not files:
            return jsonify({"status": "error", "message": "No saved resumes to compare"}), 404

        resumes_content = []
        file_map = {}
        for f in files:
            fname = os.path.basename(f)
            try:
                with open(f, 'r') as file:
                    content = file.read()
                    resumes_content.append(f"--- RESUME: {fname} ---\n{content}\n")
                    file_map[fname] = content
            except Exception:
                continue

        resumes_content = resumes_content[-10:]
        combined_resumes = "\n".join(resumes_content)

        ranking_system_prompt = """
        You are an expert ATS (Applicant Tracking System) ranker.
        Rank the provided resumes based on their relevance to the Job Description.
        Return ONLY a JSON list of objects. Each object must have:
        - "filename": string
        - "score": number (0-100)
        """

        ranking_user_message = f"JOB DESCRIPTION:\n{jd_text}\n\nRESUMES:\n{combined_resumes}"
        ranking_response = call_ai_provider(provider, api_key, ranking_system_prompt, ranking_user_message, model)
        results = parse_json_response(ranking_response)

        if isinstance(results, list):
            results.sort(key=lambda x: x.get('score', 0), reverse=True)
        else:
            results = []

        top_3 = results[:3]
        if top_3:
            top_3_filenames = [r['filename'] for r in top_3]
            top_3_content = []
            for fname in top_3_filenames:
                if fname in file_map:
                    top_3_content.append(f"--- RESUME: {fname} ---\n{file_map[fname]}\n")

            if top_3_content:
                detail_system_prompt = """
                You are an expert resume coach.
                For each provided resume, analyze it against the Job Description.
                Return a JSON list of objects. Each object must have:
                - "filename": string
                - "reasoning": string (brief explanation of the match score)
                - "improvements": list of strings (3-4 specific actionable bullet points)
                """
                detail_user_msg = f"JOB DESCRIPTION:\n{jd_text}\n\nRESUMES:\n{''.join(top_3_content)}"
                detail_response = call_ai_provider(provider, api_key, detail_system_prompt, detail_user_msg, model)
                details = parse_json_response(detail_response)

                detail_map = {d.get('filename'): d for d in details if isinstance(d, dict)}
                for r in results:
                    if r['filename'] in detail_map:
                        r.update(detail_map[r['filename']])
                    else:
                        r['reasoning'] = None
                        r['improvements'] = []

        return jsonify({"status": "success", "results": results})

    except Exception as e:
        print(f"Error in match_jd: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/check_grammar', methods=['POST'])
@login_required
def check_grammar():
    user_id = get_current_user_id()
    data = request.json
    resume_yaml = data.get('resume', '')
    provider = data.get('provider', 'anthropic')
    model = data.get('model', '')

    if not resume_yaml:
        return jsonify({"status": "error", "message": "Missing resume content"}), 400

    # Offline Mode
    if provider == 'local':
        try:
            def get_text_values(data):
                values = []
                if isinstance(data, dict):
                    for k, v in data.items():
                        values.extend(get_text_values(v))
                elif isinstance(data, list):
                    for item in data:
                        values.extend(get_text_values(item))
                elif isinstance(data, str):
                    values.append(data)
                return values

            try:
                parsed_yaml = yaml.safe_load(resume_yaml)
                text_segments = get_text_values(parsed_yaml)
                clean_text = "\n\n".join(text_segments)
            except Exception:
                clean_text = resume_yaml

            import language_tool_python

            try:
                tool = language_tool_python.LanguageTool('en-US')
                matches = tool.check(clean_text)

                results = []
                for match in matches:
                    context = match.context
                    if "{{" in context or "{%" in context:
                        continue
                    results.append({
                        "original": clean_text[match.offset: match.offset + match.errorLength],
                        "correction": match.replacements[0] if match.replacements else "",
                        "explanation": match.message,
                        "location": "Content Match"
                    })
                return jsonify({"status": "success", "results": results})

            except Exception as local_err:
                print(f"Local Java server failed: {local_err}. Falling back to public API.")
                import requests
                response = requests.post(
                    'https://api.languagetool.org/v2/check',
                    data={'text': clean_text, 'language': 'en-US'}
                )
                if response.status_code != 200:
                    raise Exception(f"Public API error: {response.text}")

                api_data = response.json()
                matches = api_data.get('matches', [])
                results = []
                for match in matches:
                    offset = match['offset']
                    length = match['length']
                    context_obj = match.get('context', {})
                    context_text = context_obj.get('text', '')
                    if "{{" in context_text or "{%" in context_text:
                        continue
                    replacements = match.get('replacements', [])
                    correction = replacements[0]['value'] if replacements else ""
                    results.append({
                        "original": clean_text[offset: offset + length],
                        "correction": correction,
                        "explanation": match['message'],
                        "location": "Content Match"
                    })
                return jsonify({"status": "success", "results": results})

        except ImportError:
            return jsonify({"status": "error", "message": "language-tool-python or requests not installed"}), 500
        except Exception as e:
            return jsonify({"status": "error", "message": f"Grammar check failed: {str(e)}"}), 500

    # AI Mode
    try:
        provider, api_key, model = _resolve_ai_credentials(data, user_id)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    try:
        system_prompt = """
        You are a professional resume editor. Proofread the following resume YAML content for spelling and grammar errors.
        Focus on the content values, ignoring keys and structure.
        Return a JSON list of objects. Each object must have:
        - "original": string
        - "correction": string
        - "explanation": string
        - "location": string
        If no errors are found, return an empty list.
        """
        user_msg = f"RESUME CONTENT:\n{resume_yaml}"
        response_text = call_ai_provider(provider, api_key, system_prompt, user_msg, model)
        results = parse_json_response(response_text)
        return jsonify({"status": "success", "results": results})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/analyze_resume', methods=['POST'])
@login_required
def analyze_resume():
    user_id = get_current_user_id()
    data = request.json
    resume_yaml = data.get('resume', '')
    jd_text = data.get('jd_text', '')

    if not resume_yaml or not jd_text:
        return jsonify({"status": "error", "message": "Missing Resume or JD"}), 400

    try:
        provider, api_key, model = _resolve_ai_credentials(data, user_id)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    try:
        system_prompt = """
        You are an expert ATS scanner and Resume Coach.
        Analyze the provided resume against the Job Description.
        Return a JSON object with:
        - "score": number (0-100)
        - "missing_keywords": list of strings
        - "suggestions": list of strings (3-4 specific improvements)
        """
        user_msg = f"JOB DESCRIPTION:\n{jd_text}\n\nRESUME CONTENT:\n{resume_yaml}"
        response_text = call_ai_provider(provider, api_key, system_prompt, user_msg, model)
        result = parse_json_response(response_text)

        if isinstance(result, list) and result:
            result = result[0]
        elif not isinstance(result, dict):
            result = {"score": 0, "missing_keywords": [], "suggestions": ["Failed to parse AI response"]}

        return jsonify({"status": "success", "result": result})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/analyze_selection', methods=['POST'])
@login_required
def analyze_selection():
    user_id = get_current_user_id()
    data = request.json
    jd_text = data.get('jd_text', '')
    filenames = data.get('filenames', [])

    if not filenames or not jd_text:
        return jsonify({"status": "error", "message": "Missing filenames or JD"}), 400

    try:
        provider, api_key, model = _resolve_ai_credentials(data, user_id)
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    try:
        versions_dir = get_user_versions_dir(user_id)

        resumes_content = []
        for fname in filenames:
            fname = os.path.basename(fname)
            fpath = os.path.join(versions_dir, fname)
            if os.path.exists(fpath):
                with open(fpath, 'r') as file:
                    resumes_content.append(f"--- RESUME: {fname} ---\n{file.read()}\n")

        if not resumes_content:
            return jsonify({"status": "error", "message": "Files not found"}), 404

        system_prompt = """
        You are an expert resume coach.
        For each provided resume, analyze it against the Job Description.
        Return a JSON list of objects. Each object must have:
        - "filename": string
        - "reasoning": string
        - "improvements": list of strings (3-4 bullet points)
        """
        user_msg = f"JOB DESCRIPTION:\n{jd_text}\n\nRESUMES:\n{''.join(resumes_content)}"
        response_text = call_ai_provider(provider, api_key, system_prompt, user_msg, model)
        results = parse_json_response(response_text)

        return jsonify({"status": "success", "results": results})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/download_pdf', methods=['POST'])
@login_required
def download_pdf():
    data = request.json
    resume_yaml = data.get('resume', '')
    style = data.get('style', {})
    keyword = data.get('keyword', '')
    inline = data.get('inline', False)

    try:
        user_id = get_current_user_id()
        user_dir = get_user_dir(user_id)
        header = get_current_user_header()
        section_names = get_current_section_names()
        custom_sections = get_current_custom_sections()
        user = get_user_by_id(user_id)

        resume_data = merge_header(resume_yaml, header)

        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        env.filters['md_bold'] = _md_bold
        template = env.get_template('resume.html')
        html_content = template.render(resume=resume_data, style=style,
                                       section_names=section_names,
                                       custom_sections=custom_sections)

        pdf_path = os.path.join(user_dir, 'preview.pdf')
        HTML(string=html_content, base_url=BASE_DIR).write_pdf(pdf_path)

        safe_name = "".join([c for c in user['name'] if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
        if keyword:
            safe_keyword = "".join([c for c in keyword if c.isalnum() or c in ('-', '_')]).strip()
            download_name = f"{safe_name}_{safe_keyword}.pdf"
        else:
            download_name = f"{safe_name}_Resume.pdf"

        return send_file(pdf_path, as_attachment=not inline, download_name=download_name)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# --- AI provider helpers (delegates to ai_service — single implementation) ---

def _extract_ai_error_info(e):
    from services.ai import extract_ai_error
    return extract_ai_error(e)


def call_ai_provider(provider, api_key, system_prompt, user_message, model=None):
    from services.ai import call_llm
    return call_llm(provider, api_key, system_prompt, user_message, model)


def parse_json_response(response_text):
    from services.ai import parse_json_response as _parse
    return _parse(response_text)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=os.environ.get('FLASK_DEBUG', '1') == '1', port=port, host='0.0.0.0')
