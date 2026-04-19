# Resume Builder

An AI-powered resume builder that tailors your resume to any job description. Upload your resume once, paste a JD, and get a perfectly formatted 1-page PDF scored 90+ for ATS systems.

---

## Quick Start

### Option A: Docker (recommended -- zero system dependency hassle)

```bash
git clone https://github.com/tanamay-cmd/Resume.git
cd Resume
docker compose up --build
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001). Done.

### Option B: Native Python

```bash
git clone https://github.com/tanamay-cmd/Resume.git
cd Resume
chmod +x setup.sh
./setup.sh
source venv/bin/activate
python3 local_app.py
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001).

> **Note:** `setup.sh` installs WeasyPrint system libraries automatically (macOS via Homebrew, Ubuntu via apt). If you're on a different OS, see [WeasyPrint installation docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html).

---

## First-Time Setup (after the app is running)

1. **Sign up** at `/signup` with your name, email, and password
2. **Onboarding** -- upload your existing resume PDF; the app parses it into editable YAML
3. **Settings** -- click the gear icon (top-right) and paste your AI API key (Anthropic, OpenAI, or Gemini)
4. **Edit** your resume YAML with live HTML/PDF preview
5. **Paste a JD** to generate a tailored version with ATS scoring

---

## Files You Need to Update (Important!)

After signing up, the app copies template files into your user data directory (`data/{your_user_id}/`). You should update these files with your actual information to get the best results from the AI resume generator.

### 1. `data/{user_id}/candidate_database.md` -- YOUR ground truth

**This is the most important file.** It contains everything the AI knows about you. The AI will NEVER fabricate information -- it only uses what's in this file.

**Format:** Markdown with specific heading structure. The template at `data/defaults/candidate_database.md` shows the exact format.

**What to fill in:**

| Section | What to write | Example |
|---------|--------------|---------|
| **Personal Information** | Name, location, phone, email, GitHub, LinkedIn | `**Name:** Tanamay Abhay Kothari` |
| **NDA Constraints** | Clients/projects you can't name publicly | `**Client:** [Bank Name] -- never name publicly` |
| **Education** | Each degree with GPA, coursework, activities | See template |
| **Professional Experience** | Each role with bullet points using: Action + What + Tech + Result | `"Built a CI/CD pipeline using GitHub Actions, reducing deploy time by 60%"` |
| **Technical Skills** | Grouped by category (Languages, Cloud, DBs, Frameworks, etc.) | See template |
| **Projects** | 4-6 projects with context, bullets, tech stack, links | See template |
| **Quantified Achievements** | Exact metrics you can back up | `"Reduced API latency from 800ms to 120ms"` |
| **Leadership** | Clubs, volunteering, research | See template |
| **Notes for Resume Generation** | Special rules for your resumes | `"Always list Python first in skills"` |

**Example bullet point format:**
```markdown
- "Architected a real-time data pipeline using Kafka and Spark, processing 2M+ events/day with 99.9% uptime"
- "Led migration of 15 microservices to Kubernetes, reducing deployment time from 2 weeks to 2 hours"
```

### 2. `data/{user_id}/resume_rules.md` -- Generation rules

Controls how the AI generates your resume. The default rules are already good, but you can customize:

- Bullet point style (action verbs, metric placement)
- Section ordering preferences
- Abbreviation preferences
- Any title overrides (e.g., "Use 'Developer Consultant' not 'SWE' for ThoughtWorks")

**You probably don't need to change this file** unless you have specific formatting preferences.

### 3. `data/{user_id}/cover_letter_database.md` -- Stories for cover letters

The AI uses these stories (NOT your resume bullets) to write cover letters. Each story should have:

```markdown
### Story: The Migration That Couldn't Go Down
- **Context:** At [Company], Q3 2024
- **Setup:** Our banking platform needed zero-downtime migration to new infra
- **What you did:** Designed blue-green deployment with automated rollback triggers
- **Result:** Migrated 50+ services with zero customer-facing downtime
- **What it shows:** Working under pressure, infrastructure expertise
```

Also fill in:
- **Motivations & Values** -- why you do what you do (the AI uses this to connect your work to a company's mission)
- **Career Context** -- graduation date, availability, visa status, location preferences

### 4. `data/{user_id}/cover_letter_rules.md` -- Cover letter format

Controls cover letter style. Default is fine for most people:
- 4 short paragraphs, 1 page max
- Professional but personal tone
- No corporate cliches

---

## How the AI Resume Generation Works

```
Paste JD  -->  Pre-screen (check for hard blockers like citizenship requirements)
          -->  Map your skills to JD requirements
          -->  Generate tailored YAML resume (picks best bullets, reorders skills)
          -->  Render PDF, check page count
          -->  If > 1 page: compress (abbreviations, trim least relevant bullets)
          -->  ATS verify (score 0-100 against JD keywords)
          -->  Loop until ATS >= 90 AND pages == 1 (max 3 iterations)
          -->  Tag and save version
```

**Output:** A 1-page PDF resume scoring 90+ on ATS, with theme tags like `backend`, `fullstack`, `devops`, `fintech`, etc.

---

## Using with Claude Code (Optional but Powerful)

If you have [Claude Code](https://claude.ai/claude-code) installed, you can use it as an AI agent that directly generates resumes by reading your data files, writing YAML, and rendering PDFs -- all without needing an API key.

Just paste a job description in Claude Code and it will:
1. Read your candidate database and rules
2. Generate a tailored resume YAML
3. Render the PDF and verify it's 1 page
4. Score it against the JD for ATS compliance
5. Save it with tags

The `CLAUDE.md` file in this repo contains all the agent instructions.

---

## Project Structure

```
Resume/
├── local_app.py              # Flask app -- all HTTP routes (port 5001)
├── models.py                 # Database layer (SQLite/PostgreSQL)
├── mcp_server.py             # MCP server for agentic workflows (optional)
│
├── services/                 # Business logic
│   ├── ai.py                 # LLM abstraction (Anthropic, OpenAI, Gemini)
│   ├── crypto.py             # Fernet encryption for stored API keys
│   ├── resume.py             # Resume YAML persistence + versioning
│   ├── parser.py             # Parser lifecycle management
│   └── jd.py                 # JD analysis + suggestion engine
│
├── agents/                   # AI agent pipelines
│   ├── jd_resume.py          # Multi-agent resume generation from JD
│   ├── jd_finder.py          # Job posting search + extraction
│   └── cover_letter.py       # Cover letter generation
│
├── parsers/                  # PDF parsing strategies
│   ├── pdf.py                # Heuristic parser (no AI needed)
│   ├── smart.py              # LLM-generated parser + sandbox
│   └── confidence.py         # Parse quality scoring
│
├── data/
│   ├── defaults/             # Template files (copied to new users on signup)
│   │   ├── candidate_database.md
│   │   ├── resume_rules.md
│   │   ├── cover_letter_database.md
│   │   └── cover_letter_rules.md
│   └── {user_id}/            # YOUR data (auto-created, gitignored)
│       ├── resume.yaml
│       ├── preview.pdf
│       ├── candidate_database.md   <-- FILL THIS IN
│       ├── resume_rules.md
│       ├── cover_letter_database.md
│       └── versions/
│
├── templates/                # Jinja2 HTML templates
│   ├── resume.html           # Resume render template (PDF output)
│   ├── editor.html           # Main YAML editor with live preview
│   ├── onboarding.html       # PDF upload + parse review
│   └── ...
│
├── docker-compose.yml        # One-command Docker startup
├── Dockerfile
├── setup.sh                  # One-command native setup (macOS/Ubuntu)
├── requirements.txt
└── CLAUDE.md                 # Claude Code agent instructions
```

---

## Environment Variables

All optional -- the app runs with sensible defaults out of the box.

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `dev-secret-change-in-production` | Flask session encryption key |
| `FERNET_KEY` | Auto-generated `.fernet_key` file | Encryption key for stored API keys |
| `DATABASE_URL` | SQLite `resume_builder.db` | Set to `postgresql://...` for PostgreSQL |
| `DATA_DIR` | `./data` | Directory for per-user data files |
| `PORT` | `5001` | Flask dev server port |

---

## API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/signup` | Create account |
| GET/POST | `/login` | Log in |
| GET | `/logout` | Log out |

### Resume
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main editor page |
| POST | `/api/preview` | Render YAML to HTML preview |
| POST | `/api/save` | Save current resume |
| POST | `/api/download_pdf` | Export as PDF |

### JD Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/jd_analyze` | Score resume against JD + suggestions |
| POST | `/api/jd_generate` | Full AI pipeline (generate + fit + ATS verify) |
| POST | `/api/jd_find` | Find JD by company+role, then generate |

### AI Features
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ai_change_request` | Natural-language resume edits |
| POST | `/api/check_grammar` | Grammar/style check |
| POST | `/api/analyze_resume` | ATS analysis of current resume |

---

## Running Tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

Tests run fully offline -- no API keys or external services needed.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: weasyprint` | Run `./setup.sh` or install system libs manually (see WeasyPrint docs) |
| `cairo` / `pango` errors | macOS: `brew install cairo pango gdk-pixbuf libffi` |
| PDF preview blank | Check that WeasyPrint system libs are installed |
| AI features not working | Go to Settings (gear icon) and paste your API key |
| Port 5001 in use | Set `PORT=5002 python3 local_app.py` |
