"""
Cover Letter Agent -- generates tailored cover letters that go beyond the resume.

Architecture:
    1. CONTEXT GATHER  -- read candidate DB, current resume YAML, JD
    2. STORY EXTRACTOR -- identify beyond-resume narratives (motivations, pivots,
                          leadership moments, "why this company", cultural fit)
    3. GENERATOR       -- LLM (or Claude Code acting as LLM) produces the letter
    4. REVIEW          -- check format (3-5 paragraphs, 1 page, professional tone)

Follows Cornell Tech Career Management Cover Letter Guide:
    - 3-5 concise paragraphs, 1 page max
    - Don't restate the resume; frame experience and tell your story
    - Specific examples showing skills the employer wants
    - Professional tone, tailored to each company
    - Keywords from the job posting

Usage (with LLM API):
    from cover_letter_agent import generate_cover_letter
    result = generate_cover_letter(
        user_id=user_id, jd_text="...", company_name="Acme",
        provider="anthropic", api_key="your-key"
    )

Usage (Claude Code as LLM -- returns the prompt for Claude Code to complete):
    from cover_letter_agent import build_cover_letter_prompt
    prompt = build_cover_letter_prompt(user_id=user_id, jd_text="...", company_name="Acme")
"""

import os
import re
import yaml
from datetime import datetime

import json as _json

_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_DIR)  # project root (parent of agents/)


def _get_database_path(user_id: int) -> str:
    """Return path to user's candidate database, falling back to global default."""
    from models import get_user_dir
    user_path = os.path.join(get_user_dir(user_id), 'candidate_database.md')
    if os.path.exists(user_path):
        return user_path
    return os.path.join(_PROJECT_DIR, 'data', 'defaults', 'candidate_database.md')


def _get_cl_database_path(user_id: int) -> str:
    """Return path to user's cover letter database, falling back to global default."""
    from models import get_user_dir
    user_path = os.path.join(get_user_dir(user_id), 'cover_letter_database.md')
    if os.path.exists(user_path):
        return user_path
    return os.path.join(_PROJECT_DIR, 'data', 'defaults', 'cover_letter_database.md')


def _get_story_bank_path(user_id: int) -> str:
    """Return path to user's cover letter stories JSON."""
    from models import get_user_dir
    return os.path.join(get_user_dir(user_id), 'cover_letter_stories.json')


def _load_story_bank(user_id: int) -> list[dict]:
    """Load the user's story bank from their data directory. Returns empty list if none."""
    path = _get_story_bank_path(user_id)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = _json.load(f)
        if isinstance(data, list):
            return data
    return []


def _read_file(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------------------
# Beyond-resume story bank
# ---------------------------------------------------------------------------

def select_stories(jd_text: str, company_name: str, user_id: int, max_stories: int = 4) -> list[dict]:
    """Select the most relevant beyond-resume stories for a given JD.

    Uses keyword matching against story themes and JD text to pick
    the narratives most likely to resonate with this specific role.
    """
    story_bank = _load_story_bank(user_id)
    if not story_bank:
        return []

    jd_lower = jd_text.lower()
    company_lower = company_name.lower()

    # Score each story by theme relevance to JD
    scored = []
    for story in story_bank:
        score = 0
        for theme in story["theme"]:
            theme_keywords = {
                "fintech": ["fintech", "financial", "banking", "insurance", "payments", "rent"],
                "product-thinking": ["product", "business needs", "stakeholder", "customer"],
                "cross-functional": ["cross-functional", "collaborate", "product manager", "design"],
                "leadership": ["lead", "senior", "mentor", "team", "champion"],
                "ownership": ["ownership", "autonomy", "end-to-end", "full-stack"],
                "engineering-culture": ["code review", "clean", "maintainable", "best practices"],
                "compliance": ["compliance", "regulated", "security", "governance"],
                "infrastructure": ["infrastructure", "cloud", "aws", "kubernetes", "serverless"],
                "reliability": ["reliability", "sre", "incident", "monitoring", "uptime"],
                "ai": ["ai", "machine learning", "ml", "llm", "generative"],
                "safety": ["safety", "trust", "responsible"],
                "impact": ["impact", "mission", "social"],
                "growth": ["growth", "learning", "career"],
                "startup": ["startup", "early-stage", "fast-paced", "series"],
                "team-building": ["team", "culture", "mentor", "champion"],
                "code-quality": ["clean", "maintainable", "code review", "testing"],
                "tdd": ["tdd", "test", "testing", "quality"],
                "solo-builder": ["build", "architect", "ship"],
                "crisis-management": ["incident", "on-call", "reliability"],
                "empathy": ["user", "customer", "experience"],
                "domain-passion": ["fintech", "financial", "insurance", "rent"],
                "initiative": ["initiative", "autonomy", "ownership"],
                "technical-depth": ["system design", "algorithms", "data structures"],
                "ambition": ["senior", "lead", "growth"],
                "user-research": ["user", "feedback", "validate"],
                "healthcare": ["health", "medical", "clinical"],
                "multilingual": ["multilingual", "global", "international"],
            }
            keywords = theme_keywords.get(theme, [theme])
            for kw in keywords:
                if kw in jd_lower:
                    score += 2
                    break

        scored.append((score, story))

    # Sort by score descending, take top N
    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored[:max_stories] if s[0] > 0]


# ---------------------------------------------------------------------------
# Cover letter system prompt
# ---------------------------------------------------------------------------

COVER_LETTER_SYSTEM = """\
You are an expert cover letter writer following the Cornell Tech Career Management
Cover Letter Guide. You write letters that go BEYOND the resume, telling the
candidate's story in a way that bullet points cannot.

TONE AND VOICE:
- Write like a real person, not a template. Short sentences mixed with longer ones.
- Subtle excitement through specificity, not adjectives. Show you researched the
  company by referencing something concrete, not just their mission statement.
- Personal but professional. First person is fine. Contractions are fine.
- Trim ruthlessly. Every sentence should earn its place. If a paragraph works
  in 3 sentences, don't use 5.
- No corporate cliches: "passionate about leveraging", "excited to bring my
  unique perspective", "I believe I would be a great fit"
- No throat-clearing openings: "I'm writing to express my interest in..."
  Just start with something real.

STRUCTURE:
1. 4 short paragraphs, 1 page max. Shorter is better.
2. Paragraph 1: Quick hook. Role + company + why it caught your eye. 2-3 sentences.
3. Paragraph 2: One story that shows (not tells) a skill the JD cares about.
   Use human detail from the Cover Letter Database. Keep it tight.
4. Paragraph 3: One more story, different skill. Or: why THIS company specifically
   (not generic fintech/startup praise; something concrete about their product,
   culture, or stage). Weave in a career context note if natural.
5. Paragraph 4: Close. Availability, one sentence. End warm but brief.

RULES:
- Do NOT restate resume bullets. The resume is attached; they'll read it.
- Use the Cover Letter Database for stories, motivations, and career context.
  These are the candidate's own words and feelings; preserve their voice.
- Use keywords from the JD naturally, never forced.
- Never fabricate experiences or metrics.
- Never use em dashes; use commas, colons, semicolons.
- Never mention visa status or work authorization.
- Address: "Dear Hiring Manager," (unless a contact name is provided)

OUTPUT: The cover letter text only. No headers, no metadata, no commentary.
Start directly with "Dear Hiring Manager," and end with the signature block.
"""


# ---------------------------------------------------------------------------
# Prompt builder (for Claude Code acting as LLM)
# ---------------------------------------------------------------------------

def build_cover_letter_prompt(
    user_id: int,
    jd_text: str,
    company_name: str,
    role_title: str = "",
    hiring_manager: str = "",
) -> dict:
    """Build the full context needed to generate a cover letter.

    Returns a dict with 'system' and 'user' prompt strings.
    This can be used by Claude Code directly or passed to call_llm().
    """
    database = _read_file(_get_database_path(user_id))

    # Read cover letter database (stories, motivations, career context)
    cl_database = ""
    cl_path = _get_cl_database_path(user_id)
    if os.path.exists(cl_path):
        cl_database = _read_file(cl_path)

    # Read current resume YAML for context on what's already highlighted
    from models import get_user_dir
    resume_path = os.path.join(get_user_dir(user_id), 'resume.yaml')
    resume_yaml = ""
    if os.path.exists(resume_path):
        resume_yaml = _read_file(resume_path)

    # Select relevant beyond-resume stories
    stories = select_stories(jd_text, company_name, user_id)
    story_text = "\n\n".join(
        f"STORY: {s['id']}\nThemes: {', '.join(s['theme'])}\n{s['narrative']}"
        for s in stories
    )

    system = COVER_LETTER_SYSTEM

    # Append user's custom cover letter rules if they exist
    from models import get_user_dir as _gud
    rules_path = os.path.join(_gud(user_id), 'cover_letter_rules.md')
    if os.path.exists(rules_path):
        user_rules = _read_file(rules_path).strip()
        if user_rules:
            system += f"\n\nADDITIONAL USER RULES:\n{user_rules}"

    if hiring_manager:
        system += f"\n\nAddress the letter to: Dear {hiring_manager},"

    user_parts = [
        f"CANDIDATE DATABASE (source of truth for all facts):\n{database}",
        f"COVER LETTER DATABASE (stories, motivations, career context in candidate's own voice):\n{cl_database}",
        f"CURRENT RESUME (what's already covered; do NOT repeat these bullets):\n{resume_yaml}",
        f"JOB DESCRIPTION:\n{jd_text}",
        f"COMPANY: {company_name}",
    ]
    if role_title:
        user_parts.append(f"ROLE TITLE: {role_title}")
    if story_text:
        user_parts.append(
            f"BEYOND-RESUME STORIES (use 2-3 of these as narrative material; "
            f"adapt and weave them naturally, don't copy verbatim):\n{story_text}"
        )

    return {
        "system": system,
        "user": "\n\n".join(user_parts),
        "stories_selected": [s["id"] for s in stories],
    }


# ---------------------------------------------------------------------------
# Full generation (with LLM API)
# ---------------------------------------------------------------------------

def generate_cover_letter(
    user_id: int,
    jd_text: str,
    company_name: str,
    provider: str,
    api_key: str,
    role_title: str = "",
    hiring_manager: str = "",
    model: str | None = None,
) -> dict:
    """Generate a tailored cover letter using an LLM API.

    Returns dict with keys: text, stories_used, company, role
    """
    from services.ai import call_llm

    prompt = build_cover_letter_prompt(
        user_id, jd_text, company_name, role_title, hiring_manager
    )

    raw = call_llm(provider, api_key, prompt["system"], prompt["user"], model)

    # Clean up any markdown fences
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()

    # Save to file
    from models import get_user_dir
    output_dir = get_user_dir(user_id)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'cover_letter.txt')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)

    return {
        "text": text,
        "stories_used": prompt["stories_selected"],
        "company": company_name,
        "role": role_title,
        "output_path": output_path,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Generate tailored cover letter')
    parser.add_argument('--jd', type=str, required=True,
                        help='Job description text (or path to .txt file)')
    parser.add_argument('--company', type=str, required=True,
                        help='Company name')
    parser.add_argument('--role', type=str, default='',
                        help='Role title')
    parser.add_argument('--hiring-manager', type=str, default='',
                        help='Hiring manager name (optional)')
    parser.add_argument('--provider', type=str, default='anthropic',
                        choices=['anthropic', 'openai', 'gemini'])
    parser.add_argument('--api-key', type=str,
                        help='LLM API key (or set via env var)')
    parser.add_argument('--model', type=str, default=None)
    parser.add_argument('--user-id', type=int, required=True)
    parser.add_argument('--prompt-only', action='store_true',
                        help='Print the prompt instead of calling LLM')

    args = parser.parse_args()

    jd_text = args.jd
    if os.path.isfile(jd_text):
        jd_text = _read_file(jd_text)

    if args.prompt_only:
        prompt = build_cover_letter_prompt(
            args.user_id, jd_text, args.company, args.role, args.hiring_manager
        )
        print("=== SYSTEM PROMPT ===")
        print(prompt["system"])
        print("\n=== USER PROMPT ===")
        print(prompt["user"])
        print(f"\n=== STORIES SELECTED: {prompt['stories_selected']} ===")
    else:
        api_key = args.api_key or os.environ.get({
            'anthropic': 'ANTHROPIC_API_KEY',
            'openai': 'OPENAI_API_KEY',
            'gemini': 'GOOGLE_API_KEY',
        }.get(args.provider, ''), '')
        if not api_key:
            print('Error: --api-key required or set env var')
            raise SystemExit(1)

        result = generate_cover_letter(
            user_id=args.user_id,
            jd_text=jd_text,
            company_name=args.company,
            role_title=args.role,
            hiring_manager=args.hiring_manager,
            provider=args.provider,
            api_key=api_key,
            model=args.model,
        )
        print(result["text"])
        print(f"\n--- Saved to: {result['output_path']} ---")
        print(f"--- Stories used: {result['stories_used']} ---")
