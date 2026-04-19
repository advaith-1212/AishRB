# Backward-compatibility shim — import from agents.jd_resume instead
from agents.jd_resume import *  # noqa: F401,F403
from agents.jd_resume import (  # noqa: F401
    generate_resume_for_jd, analyze_jd, extract_jd_tags,
    score_resume_ats, render_pdf, count_pdf_pages,
    diff_versions, save_learning, get_learnings, get_last_agent_version,
    find_reusable_version,
)
