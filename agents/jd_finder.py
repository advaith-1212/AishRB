"""
JD Finder Agent -- searches for a job posting by company + role, extracts
the JD text, and feeds it into the resume generation pipeline.

Usage:
    from jd_finder_agent import find_and_generate

    # By company + role
    result = find_and_generate(
        company="Stripe", role="Backend Engineer",
        user_id=user_id, provider="anthropic", api_key="your-key"
    )

    # By URL (skip search, just extract)
    result = find_and_generate(
        url="https://boards.greenhouse.io/stripe/jobs/12345",
        user_id=user_id, provider="anthropic", api_key="your-key"
    )
"""

import json
import os
import re

from services.ai import call_llm, parse_json_response
from agents.jd_resume import generate_resume_for_jd, analyze_jd


# ---------------------------------------------------------------------------
# Job board URL patterns (for building targeted search queries)
# ---------------------------------------------------------------------------

_JOB_BOARDS = [
    'greenhouse.io', 'lever.co', 'ashbyhq.com', 'jobs.lever.co',
    'boards.greenhouse.io', 'apply.workable.com', 'careers.smartrecruiters.com',
    'myworkdayjobs.com', 'icims.com', 'jobvite.com', 'ultipro.com',
    'linkedin.com/jobs', 'indeed.com', 'wellfound.com',
]


# ---------------------------------------------------------------------------
# Search for JD
# ---------------------------------------------------------------------------

def search_for_jd(company: str, role: str) -> list[dict]:
    """Search the web for a job posting matching company + role.

    Returns a list of candidate URLs with titles, sorted by relevance.
    Uses WebSearch-style queries targeting common job boards.
    """
    # This function is called from the Flask route or CLI, which will
    # use the actual WebSearch tool. Here we just build the search queries.
    queries = [
        f"{company} {role} job posting 2026",
        f"{company} {role} careers site:greenhouse.io OR site:lever.co OR site:ashbyhq.com",
        f"{company} {role} open position",
    ]
    return queries


def build_search_query(company: str, role: str) -> str:
    """Build the best single search query for finding a JD."""
    return f"{company} {role} job posting 2026"


# ---------------------------------------------------------------------------
# Extract JD text from a URL
# ---------------------------------------------------------------------------

_EXTRACT_SYSTEM = """\
You are a job description extractor. Given the raw content of a job posting page,
extract ONLY the job description text. Include:
- Job title
- Company name
- Location and work arrangement (remote/hybrid/onsite)
- About the role / overview
- Responsibilities / What you'll do
- Requirements / Qualifications (required and preferred)
- Tech stack / Tools mentioned
- Compensation (if listed)
- Visa/sponsorship info (if mentioned)

Do NOT include:
- Navigation menus, footers, cookie notices
- Other job listings on the page
- Company boilerplate unrelated to this role
- Application form fields

Return the extracted JD as clean text, preserving the section structure.
If the page does not contain a job description, respond with: NO_JD_FOUND
"""


def extract_jd_from_html(page_content: str, provider: str, api_key: str, model: str | None = None) -> str | None:
    """Extract structured JD text from raw page content using an LLM.

    Args:
        page_content: Raw text/markdown from the job posting page.
        provider: LLM provider.
        api_key: API key.
        model: Optional model override.

    Returns:
        Extracted JD text, or None if no JD was found on the page.
    """
    # Truncate very long pages (keep first 15k chars, which covers most JDs)
    content = page_content[:15000]

    raw = call_llm(provider, api_key, _EXTRACT_SYSTEM, content, model)

    if 'NO_JD_FOUND' in raw:
        return None

    return raw.strip()


# ---------------------------------------------------------------------------
# Select best URL from search results
# ---------------------------------------------------------------------------

_SELECT_SYSTEM = """\
You are a job posting URL selector. Given search results for a specific company and role,
identify which URL is most likely the actual job posting (not a blog post, news article,
or generic careers page).

Prefer URLs from known job boards: greenhouse.io, lever.co, ashbyhq.com, workable.com,
myworkdayjobs.com, linkedin.com/jobs, wellfound.com, or the company's own careers page.

Return ONLY a JSON object:
{
    "best_url": "https://...",
    "confidence": "high" | "medium" | "low",
    "reason": "why this URL"
}

If none of the results look like actual job postings, return:
{"best_url": null, "confidence": "none", "reason": "no job posting found in results"}
"""


def select_best_url(search_results: str, company: str, role: str,
                    provider: str, api_key: str, model: str | None = None) -> dict:
    """Given search result text, pick the best URL for the actual job posting."""
    user_msg = (
        f"Company: {company}\nRole: {role}\n\n"
        f"Search Results:\n{search_results}"
    )
    raw = call_llm(provider, api_key, _SELECT_SYSTEM, user_msg, model)
    result = parse_json_response(raw)
    if not isinstance(result, dict):
        return {'best_url': None, 'confidence': 'none', 'reason': 'Failed to parse response'}
    return result


# ---------------------------------------------------------------------------
# Full pipeline: search -> extract -> generate
# ---------------------------------------------------------------------------

def find_and_generate(
    user_id: int,
    provider: str,
    api_key: str,
    model: str | None = None,
    company: str | None = None,
    role: str | None = None,
    url: str | None = None,
    jd_text: str | None = None,
    target_score: int = 90,
) -> dict:
    """Find a JD and run the full resume generation pipeline.

    Provide EITHER:
    - company + role (will search and extract)
    - url (will extract JD from that page)
    - jd_text (will skip search/extract entirely)

    Returns the same result dict as generate_resume_for_jd, plus:
    - jd_source: 'search', 'url', or 'direct'
    - jd_url: the URL the JD was extracted from (if applicable)
    - jd_text: the extracted JD text
    - search_query: the query used (if searched)
    """
    logs = []
    jd_source = 'direct'
    jd_url = url
    search_query = None

    if jd_text:
        # Direct JD text provided, skip search
        jd_source = 'direct'
        logs.append("Using provided JD text directly")

    elif url:
        # URL provided, extract JD from it
        jd_source = 'url'
        logs.append(f"Extracting JD from: {url}")
        # The caller (Flask route or CLI) handles the actual web fetch
        # and passes the page content. This function expects jd_text
        # to be set by the caller after fetching.
        raise ValueError(
            "URL extraction requires page content. Use extract_jd_from_html() "
            "with the fetched page content, then pass the result as jd_text."
        )

    elif company and role:
        # Need to search -- the caller handles actual web search
        jd_source = 'search'
        search_query = build_search_query(company, role)
        logs.append(f"Search query: {search_query}")
        raise ValueError(
            "Search-based flow requires the caller to perform web search and fetch. "
            "Use build_search_query() to get the query, search, then extract and pass jd_text."
        )

    else:
        raise ValueError("Provide company+role, url, or jd_text")

    # Pre-screen
    analysis = analyze_jd(jd_text)
    logs.append(f"Role type: {analysis['role_type']}")
    if analysis['has_blockers']:
        logs.append(f"BLOCKERS: {analysis['blockers']}")

    # Run the full generation pipeline
    result = generate_resume_for_jd(
        user_id=user_id,
        jd_text=jd_text,
        provider=provider,
        api_key=api_key,
        model=model,
        target_score=target_score,
    )

    # Augment result
    result['jd_source'] = jd_source
    result['jd_url'] = jd_url
    result['jd_text'] = jd_text
    result['search_query'] = search_query
    result['finder_logs'] = logs + result.get('logs', [])

    return result
