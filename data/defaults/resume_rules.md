# Resume Generation Rules & Guidelines

## Core Principles

### 1. NEVER Make Up Information
- Only use content from `candidate_database.md`
- Don't fabricate technologies, skills, or experiences
- Be honest about experience gaps and skill levels
- Use qualifiers like "learning" or "exposure to" when appropriate

### 2. Keep It Natural and Concise
- Avoid marketing language and excessive adjectives
- Write in clear, direct language
- Keep bullets focused and impactful
- Let metrics and facts speak for themselves
- Don't use phrases like "production-grade" for hackathon projects

### 3. Maintain Accuracy
- Use actual job titles from experience
- Include real metrics only (from the candidate database)
- Don't exaggerate or inflate roles
- Be truthful about project scope (48-hour hackathons vs. production systems)

---

## Resume Generation Process

### Step 1: Analyze the Job Description

**Extract Key Information:**
1. **Top 3-5 Required Skills** - Identify must-have technical skills
2. **Core Responsibilities** - What will you actually do day-to-day
3. **Keywords** - Technologies, methodologies, tools mentioned
4. **Experience Level** - Years required, seniority expectations
5. **Dealbreakers** - Visa requirements, location, citizenship, etc.

**Flag Critical Blockers:**
- U.S. Citizenship required
- Visa sponsorship not available
- Specific location with in-office requirements
- Years of experience significantly above candidate level
- Required skills completely missing from background

### Step 2: Map Candidate Skills to JD

**Priority Matching:**
1. **Exact Matches** - Skills candidate has that JD requires
2. **Transferable Skills** - Related experience that applies
3. **Learning Gaps** - Skills candidate can acquire quickly
4. **Hard Gaps** - Missing expertise that takes years to build

**Focus Areas (adapt to each candidate):**
- Primary programming languages from candidate database
- Cloud platforms and infrastructure tools
- DevOps practices (CI/CD, monitoring)
- Domain experience relevant to the JD

### Step 3: Rewrite Bullet Points

**Bullet Point Formula:**
```
[Action Verb] + [What You Did] + [Technology/Method] + [Quantifiable Result]
```

**Examples:**
- Good: "Architected data pipelines using Python and Terraform reducing processing time by 60%"
- Good: "Engineered CI/CD system with GitHub Actions automating 20+ service deployments"
- Bad: "Worked on infrastructure" (too vague)
- Bad: "Built world-class production-grade systems" (marketing fluff)

**Strong Action Verbs:**
- **Building:** Architected, Engineered, Developed, Implemented, Built, Designed
- **Improving:** Optimized, Reduced, Enhanced, Streamlined, Accelerated
- **Leading:** Led, Spearheaded, Drove, Championed, Directed
- **Analyzing:** Analyzed, Identified, Evaluated, Assessed
- **Collaborating:** Collaborated, Partnered, Coordinated, Facilitated

**Keyword Integration:**
- Use exact terms from JD when they match actual experience
- Example: JD says "Kubernetes" -> Use "Kubernetes" not "container orchestration"
- Example: JD says "observability" -> Use "observability" not just "monitoring"

**Quantification Rules:**
- Use actual metrics from candidate database
- Never inflate numbers
- If no metric exists, describe scope instead (e.g., "40+ microservices")
- Acceptable quantifiers: time saved, cost reduced, systems managed, users served, uptime %

### Step 4: Structure the Resume

#### A. Professional Summary (3 lines max)

**Formula:**
```
[Role Title] with [X+ years] [core expertise area].
[Top 2-3 technical skills matching JD] with [specific achievement or domain].
[Educational credential or current pursuit if relevant to role].
```

**Tailoring Rules:**
- Mirror JD's role title when appropriate (e.g., "Platform Engineer" vs "DevOps Engineer")
- Lead with skills most relevant to JD
- Include domain experience if JD is industry-specific

#### B. Skills Section

**Ordering Priority:**
1. **JD-Required Skills First** - Skills explicitly mentioned in job posting
2. **Related/Transferable** - Adjacent skills that support the role
3. **Additional Technical** - Other relevant skills
4. **General/Soft Skills** - Communication, collaboration (if space permits)

**Categorization by Role Type:**

For Infrastructure/DevOps Roles:
- Cloud & Infrastructure: [Specific cloud, IaC tools]
- Containers & Orchestration: [K8s, Docker, Helm]
- CI/CD & Automation: [Specific tools]
- Monitoring & Observability: [Specific tools]
- Programming: [Languages]

For Backend/Software Engineering Roles:
- Programming & Development: [Languages first]
- Backend & APIs: [Frameworks, patterns]
- Databases & Storage: [Specific DBs]
- Cloud & Infrastructure: [Platforms]
- DevOps & Tools: [CI/CD, Git]

For ML/Data Roles:
- ML Frameworks & Libraries: [PyTorch, TensorFlow]
- Programming & Data: [Python, SQL, data tools]
- ML Systems & Infrastructure: [MLOps tools]
- Cloud & Computing: [Platforms, GPU]
- Data Engineering: [Pipelines, ETL]

#### C. Experience Section

**Job Entry Format:**
- 8-12 bullets for primary/longest role, prioritized by JD relevance
- 2-4 bullets for shorter or earlier roles

**Bullet Point Rules:**
- First 3-4 bullets: Most relevant to JD (use their keywords)
- Middle bullets: Supporting technical achievements
- Last bullets: Collaboration, mentorship, process improvements
- Max length: 1-2 lines per bullet
- Tense: Past tense for all previous roles

**What to Emphasize by Role Type:**

| Role Type | Emphasize |
|-----------|-----------|
| DevOps/Platform | Infrastructure automation, deployment pipelines, cost optimization, reliability |
| Backend Engineering | API design, scalability, performance, database optimization |
| ML Engineering | Model training, deployment pipelines, data processing, performance optimization |
| Data Engineering | ETL pipelines, data quality, processing scale, integration |
| Security/Cloud Governance | Security controls, compliance, IAM, encryption, monitoring |

#### D. Projects Section

**Project Selection Rules:**
1. Never include full-time work experience in projects -- that goes in Experience
2. Pick 3-4 most relevant projects to the JD
3. Order by relevance to role, not chronologically
4. Academic projects are valid
5. Hackathon projects are valid but don't oversell

**Project Entry Format:**
- 3-5 bullets focusing on JD-relevant aspects

**Project Bullet Point Rules:**
- Focus on technologies matching JD
- Describe architecture/approach, not just "built X"
- Include specific technical choices and why
- Mention scale/scope honestly (dataset size, users, performance)
- Don't call hackathon work "production-grade"
- Do highlight relevant technical depth

**Project Reordering:** Order projects by relevance to the JD. For example, if applying to an ML role, put ML projects first. If applying to a backend role, put backend/API projects first.

#### E. Education & Extracurricular

**Coursework Selection:**
- Pick courses that align with JD requirements
- ML role -> ML, Deep Learning courses
- Systems role -> Distributed Systems, System Design courses
- Data role -> Data Processing, Database courses

**Extracurricular:**
- Keep to 2-3 bullets max
- Include leadership roles if relevant
- Only include if demonstrates relevant skills

#### F. ATS Scoring
- After generating the YAML, score it against the JD
- Target 90+ ATS score
- If below 90, iterate and improve keyword coverage

---

## Content Guidelines

### What to Include
- Actual quantified achievements from candidate database
- Specific technologies used (not generic descriptions)
- Scope of work (number of services, users, systems)
- Collaboration and cross-functional work
- Process improvements and optimizations

### What to Avoid
- Made-up technologies or skills
- Inflated metrics or achievements
- Generic buzzwords without substance
- "Production-grade" for hackathon projects
- Responsibilities not actually performed
- Em dashes (--) anywhere in the resume; use semicolons, commas, colons instead
- Excessive adjectives like "robust", "cutting-edge", "world-class"
- Vague phrases like "worked on" or "helped with"

---

## Output Format

### YAML Structure
```yaml
name: [Full Name]
contact:
  location: [City, State]
  phone: [Phone Number]
  email: [Email]
  github: [GitHub URL]
  linkedin: [LinkedIn URL]
  portfolio_label: Portfolio        # optional
  portfolio_url: [Portfolio URL]    # optional

summary: [3-line tailored summary]

education:
- institution: [University Name]
  location: [City, State]
  degree: [Degree Name]
  gpa: '[GPA]'
  date: [Graduation Date]
  coursework: [1-3 most relevant courses to JD]
- institution: [Previous University]
  location: [City, Country]
  degree: [Degree Name]
  gpa: '[GPA]'
  date: [Graduation Date]

technical_skills:
- category: [JD-relevant category name]
  skills: [Comma-separated skills, JD keywords first]

experience:
- company: [Company Name]
  role: [Actual Title]
  location: [City, State/Country]
  date: [Start] - [End]
  bullets:
  - "[Action verb] + [what] + [tech] + [result]"
- company: [Previous Company]
  role: [Title]
  location: [City, State/Country]
  date: [Start] - [End]
  bullets:
  - "[Bullet 1]"

projects:
- name: [Project Name]
  event: [Event/Type]
  award: [If applicable]
  date: [Date]
  bullets:
  - "[3-5 bullets]"

extracurricular:
  bullets:
  - "[2-3 leadership/community bullets]"
```

### Assessment Comments (after YAML)
```
### Honest Assessment:
What You Actually Have: [matches]
Experience Gaps: [missing skills]
```

---

## Quality Checklist

- All information is from candidate database
- No fabricated skills or experiences
- Metrics are actual, not inflated
- Job titles match actual roles
- Bullet points use JD keywords where accurate
- Action verbs start each bullet
- Quantification included where possible
- Skills ordered by JD priority
- Most relevant projects highlighted
- Natural, concise language throughout
- No "production-grade" for hackathons
- No em dashes anywhere
- Critical blockers flagged if present
