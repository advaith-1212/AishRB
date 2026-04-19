# SimpleLocalBuilder - Resume Builder

## How this works: Claude IS the agent (no API key needed)

Claude Code acts as all agents directly. No external API key is required.
When a trigger is detected, Claude reads the source files, generates the
YAML itself, writes it to disk, renders the PDF, and verifies the result.

---

## Auto-detect triggers

### Trigger 1: User pastes a JD

When the user pastes what looks like a **job description** (containing phrases like
"responsibilities", "requirements", "qualifications", "about the role", "what you'll do",
"we're looking for", "you will", "experience with", "years of experience",
or a block of text describing a role at a company), run the **Resume Pipeline** below.

### Trigger 2: User gives a company + role

When the user says something like "generate resume for Stripe Backend Engineer" or
"apply to Datadog SRE role" or "find the JD for Anthropic AI Engineer":

1. Use `WebSearch` tool to find the job posting
2. From the results, pick the most likely job posting URL
   (prefer greenhouse.io, lever.co, ashbyhq.com, the company's careers page)
3. Use `WebFetch` to get the page content
4. Extract the JD text from the page (strip nav, footer, boilerplate)
5. Show the user briefly: "Found: [role] at [company]"
6. Run the **Resume Pipeline** below with the extracted JD

### Trigger 3: User gives a job URL

When the user pastes a URL to a job posting:

1. Use `WebFetch` to get the page content
2. Extract the JD text from the page
3. Run the **Resume Pipeline** below

---

## Resume Pipeline (Claude executes this directly)

### Phase 1: Pre-screen

Read the JD and check for hard blockers:
- **Hard blockers (warn user, ask before proceeding):**
  U.S. citizenship required, security clearance, visa sponsorship denied
- **NOT blockers (proceed normally):**
  Experience years off by 1-2, company type (startup vs FANG),
  "preferred" qualifications missing, location if remote/hybrid available

### Phase 2: Read source files

Read these files for context:
- `data/{user_id}/candidate_database.md` -- ground truth for all resume content
- `data/{user_id}/resume_rules.md` -- formatting, content rules, bullet style
- `data/{user_id}/resume_learnings.md` -- patterns learned from past user edits (if exists)

### Phase 3: Generate YAML

Generate a complete resume YAML following these rules:
- Follow the YAML structure exactly (name, contact, summary, education,
  technical_skills, experience, projects, extracurricular)
- Use job titles exactly as they appear in the candidate database
- Respect any NDA constraints listed in the candidate database
- Bold action phrases with `**` markers
- Wrap bullets containing special chars in double quotes
- Never use em dashes; use commas, colons, semicolons, parentheticals
- Never fabricate skills, technologies, or metrics not in the database
- Never call hackathon work "production-grade"
- Write in full natural English on first pass (NO abbreviations)
- Pick 3-4 most relevant projects, ordered by JD relevance
- 4-5 skill categories max, JD keywords first
- Follow any "Notes for Resume Generation" in the candidate database
- 3-5 bullets per project

### Phase 4: Write and render

```python
# Write the YAML to disk
import yaml
from resume_service import save_current_resume
version_id = save_current_resume(user_id, yaml_content, source='jd_agent', label='JD Agent: {role_type}', tags=tags)
```

Then render the PDF and check page count:
```python
from jd_resume_agent import render_pdf, count_pdf_pages
pdf_path = render_pdf(yaml_content, user_id)  # uses 10pt, 0.4in margins
pages = count_pdf_pages(pdf_path)
```

### Phase 5: Fit to 1 page (only if needed)

If PDF > 1 page, compress by:
1. Abbreviations: env, infra, config, auth, dev, ops, prod, k8s, DB, ML,
   CI/CD, RBAC, IaC, SSE, ETL, MTTR, MTTD, impl, perf, mgmt
2. Drop articles (a, an, the) where meaning stays clear
3. Combine related bullets with semicolons
4. Shorten "designed and implemented" to "Built"
5. Remove least relevant bullets (lowest JD match)
6. Reduce project bullets to 3 per project
7. Trim extracurricular to 1-2 bullets
8. Remove summary or extracurricular entirely (last resort)

After each compression edit, re-render PDF and re-check page count.
Repeat until pages == 1.

### Phase 6: ATS verification

Score the resume against the JD yourself:
- Keyword match: exact JD terms present in resume (40%)
- Skills alignment: required vs present (25%)
- Experience relevance: responsibilities match (20%)
- Quantified achievements (15%)

If score < 90, improve by integrating missing keywords into existing
bullets or skill lists (don't add new bullets, don't inflate).
Re-check page count after improvements.

Repeat until ATS >= 90 AND pages == 1 (max 3 iterations).

### Phase 7: Tag and report

Auto-tag with **theme-based** tags (not tech stack). Examples:
- `backend`, `devops`, `ai-engineer`, `ml`, `fullstack`, `data`, `security`
- `fintech`, `healthcare`, `startup`, `enterprise`, `cloud-native`

```python
from jd_resume_agent import extract_jd_tags
from resume_service import tag_version
tags = extract_jd_tags(jd_text, role_type)
tag_version(version_id, user_id, tags)
```

**Report to user:**
- ATS Score: X/100
- Pages: 1
- Tags: [theme tags]
- Iterations: N
- Blockers: (if any)
- Assessment: honest skill gaps
- "Resume is live in your browser preview. Refresh to see it."

---

## After user edits: learn and remember

When the user says they've edited the resume, or you detect they saved changes:

```python
from jd_resume_agent import diff_versions, get_last_agent_version, save_learning
from resume_service import get_current_resume

agent_version = get_last_agent_version(user_id=user_id)
current_yaml = get_current_resume(user_id=user_id)
changes = diff_versions(agent_version['yaml_content'], current_yaml)
```

If changes exist:
1. Tell the user what changed (summary rewritten, bullets added/removed, projects reordered, etc.)
2. **Ask WHY** they made the change
3. After they answer, save the learning:
   ```python
   save_learning(tags=tags, changes=changes, reason=user_reason)
   ```

Learnings are stored in `data/{user_id}/resume_learnings.md` and fed into future generations
so the agent improves over time.

---

## Cover Letter Pipeline (Claude executes this directly)

When the user asks to generate a cover letter for a job:

### Phase 1: Read context

Read these files:
- `data/{user_id}/candidate_database.md` -- ground truth for all facts
- `data/{user_id}/cover_letter_database.md` -- stories, motivations, career context
- `data/{user_id}/cover_letter_rules.md` -- user's formatting preferences
- `data/{user_id}/resume.yaml` -- current resume (to avoid repeating it)

### Phase 2: Generate

Generate a cover letter following the user's rules and the Cornell Tech guide:
- 4 short paragraphs, 1 page max
- Don't restate resume bullets
- Use specific stories from the cover letter database
- Keywords from the JD, used naturally

### Phase 3: Write draft YAML and open in browser

Write the result as YAML to the user's draft file:

```python
import yaml, os
from models import get_user_dir

draft = {
    'salutation': 'Dear Hiring Manager,',
    'paragraphs': ['paragraph 1', 'paragraph 2', 'paragraph 3', 'paragraph 4'],
}
draft_path = os.path.join(get_user_dir(user_id), 'cover_letter_draft.yaml')
with open(draft_path, 'w') as f:
    yaml.dump(draft, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
```

Tell the user: "Cover letter is ready. Open /cover-letter in your browser to preview and edit it."

---

## Key files

| File | Purpose |
|------|---------|
| `agents/jd_resume.py` | Multi-agent pipeline (generator, PDF fitter, ATS verifier, learner) |
| `agents/jd_finder.py` | JD search and extraction (company+role or URL) |
| `agents/cover_letter.py` | Cover letter generation agent |
| `data/defaults/candidate_database.md` | Default candidate database template (copied to new users) |
| `data/defaults/resume_rules.md` | Default resume generation rules (copied to new users) |
| `data/defaults/cover_letter_database.md` | Default cover letter database (copied to new users) |
| `data/defaults/cover_letter_rules.md` | Default cover letter rules (copied to new users) |
| `data/{user_id}/candidate_database.md` | User's ground truth for resume content |
| `data/{user_id}/resume_rules.md` | User's resume formatting and content rules |
| `data/{user_id}/cover_letter_rules.md` | User's cover letter formatting rules |
| `data/{user_id}/cover_letter_database.md` | User's stories and narratives for cover letters |
| `data/{user_id}/cover_letter_draft.yaml` | Latest generated cover letter (loaded by /cover-letter page) |
| `data/{user_id}/resume_learnings.md` | Patterns learned from user edits (auto-generated) |
| `data/{user_id}/resume.yaml` | Current resume shown in browser |
| `data/{user_id}/preview.pdf` | Rendered PDF |

## Defaults

- Font: 10pt Times New Roman
- Margins: 0.4in
- Line height: 1.15
- Target: 1 page, ATS >= 90
- Max iterations: 3
- First pass: full natural English (no abbreviations)
- Compression only when PDF > 1 page
