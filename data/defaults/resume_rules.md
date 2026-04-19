# Resume Generation Rules & Guidelines

## Core Principles

### 1. NEVER Make Up Information
- Only use content from `CANDIDATE_DATABASE.md`
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
- Include real metrics only (60% deployment reduction, 40% provisioning, 20% cost optimization, 45% MTTR reduction)
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

**Focus Areas:**
- Primary programming languages (Python, Java, TypeScript)
- Cloud platforms (Azure primary, AWS secondary)
- Infrastructure tools (Terraform, Kubernetes, Helm, Ansible)
- DevOps practices (CI/CD, GitLab CI, monitoring)
- Domain experience (banking/fintech, healthcare, data engineering)

### Step 3: Rewrite Bullet Points

**Bullet Point Formula:**
```
[Action Verb] + [What You Did] + [Technology/Method] + [Quantifiable Result]
```

**Examples:**
- Good: "Architected data pipelines using Python and Terraform reducing processing time by 60%"
- Good: "Engineered CI/CD system with GitLab CI automating 40+ microservice deployments"
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
- Mention MEng only if relevant to role (technical depth, research, ML focus)

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
- 10-12 bullets max for primary role, prioritized by JD relevance
- 2-3 bullets for graduate role

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
1. Never include ThoughtWorks work in projects - that goes in Experience
2. Pick 3-4 most relevant projects to the JD
3. Order by relevance to role, not chronologically
4. Academic projects are valid (MiniTorch, ColorEdit-Flux)
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

**Project Reordering Examples:**
- For ML Role: MiniTorch -> ColorEdit-Flux -> CTCC -> Dan.ai
- For Backend Role: Dan.ai -> Pitchbox -> CTCC -> MiniTorch
- For DevOps Role: Pitchbox -> Dan.ai -> CTCC
- For Data Role: CTCC -> MiniTorch -> Dan.ai
- For AI Safety/LLM Role: FairSight -> Dan.ai -> SeeMeThru

#### E. Education & Extracurricular

**Coursework Selection:**
- Pick courses that align with JD requirements
- ML role -> Machine Learning Engineering, Deep Learning
- Systems role -> Distributed Systems, System Design
- Data role -> Data Processing, Machine Learning Engineering

**Extracurricular:**
- Keep to 2-3 bullets max
- Include leadership if relevant (AARUUSH committee lead)
- Include current role (Future Founders Treasurer)
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
name: Aishwarya Birla
contact:
  location: New York, NY
  phone: +1 646-244-9594
  email: ab3347@cornell.edu
  github: https://github.com/birlaaishwarya11
  linkedin: https://www.linkedin.com/in/aishwarya-birla/
  portfolio_label: Portfolio
  portfolio_url: https://aishwaryabirla.lovable.app/

summary: [3-line tailored summary]

education:
- institution: Cornell Tech, Cornell University
  location: New York, NY
  degree: MEng in Computer Science
  gpa: '3.9'
  date: May 2026
  coursework: [1-3 most relevant courses to JD]
- institution: SRM Institute of Science & Technology
  location: Chennai, India
  degree: BTech in Computer Science Engineering
  gpa: '4.0'
  date: May 2022

technical_skills:
- category: [JD-relevant category name]
  skills: [Comma-separated skills, JD keywords first]

experience:
- company: ThoughtWorks
  role: [Actual title matching JD focus]
  location: Pune, India
  date: July 2022 - May 2025
  bullets:
  - [10-12 bullets prioritized by JD relevance]
- company: ThoughtWorks
  role: [Graduate title]
  location: Pune, India
  date: March 2022 - June 2022
  bullets:
  - [2-3 bullets]

projects:
- name: [Project Name]
  event: [Event/Type]
  award: [If applicable]
  date: [Date]
  bullets:
  - [3-5 bullets]

extracurricular:
  bullets:
  - [2-3 leadership/community bullets]
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
