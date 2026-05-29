# ShikshaSignal AI — Project Context for Claude Code

## 1. Project Identity

**Project Name:** ShikshaSignal AI  
**Tagline:** Agentic Mission Control for Government Education Programs  
**Project Type:** AI Agent + B2G EdTech Decision Intelligence Platform  
**Primary Builder:** Sumit Kumar  
**Target Use Case:** Flagship AI agent portfolio project for Product Management, B2G EdTech, analytics, and AI-native product development.

---

## 2. One-Line Product Pitch

ShikshaSignal AI helps government education teams convert scattered program data, policy documents, field issues, and learning-platform usage into risk alerts, root-cause insights, weekly review briefs, intervention plans, stakeholder messages, dashboards, and action trackers.

---

## 3. Product Vision

Most education dashboards answer: **what happened?**

ShikshaSignal AI should answer:

1. What happened?
2. Why might it have happened?
3. What is at risk?
4. What should be done next?
5. Who should act?
6. What evidence supports the recommendation?
7. How do we track closure?

The goal is to move education teams from passive dashboards to proactive, evidence-backed program execution.

---

## 4. Target Users

### Primary Personas

#### 1. State Program Manager
Needs to monitor education program health across districts and prepare leadership reviews.

#### 2. District Education Officer
Needs to identify high-risk blocks, schools, teacher-training gaps, learning gaps, and adoption issues.

#### 3. Block Resource Coordinator
Needs school-level actions, teacher follow-ups, and field visit priorities.

#### 4. Implementation Partner / EdTech Program Manager
Needs adoption tracking, intervention planning, client-ready reporting, and escalation management.

#### 5. Product Manager
Needs to understand usage patterns, feature adoption gaps, operational blockers, and field-level product insights.

---

## 5. Core Problem Statement

Government education programs generate large amounts of operational data through dashboards, CSVs, policy documents, assessment records, training records, and field reports. However, program teams still spend significant manual effort identifying risks, finding root causes, preparing review notes, drafting stakeholder messages, and tracking actions.

ShikshaSignal AI solves this by acting as an AI-powered decision-support and action-planning layer for education program governance.

---

## 6. MVP Scope

### MVP Name
**Weekly District Review Agent**

### MVP Goal
Allow a user to upload/select district-level education datasets and ask:

> Generate this week’s review for District A. Identify top risky blocks and schools, explain likely causes, and recommend actions.

### MVP Must Produce

1. District KPI summary
2. Block-level risk ranking
3. Top risky schools
4. Data quality warnings
5. Policy-linked observations
6. Root-cause hypotheses
7. Recommended intervention plan
8. Stakeholder messages
9. Review memo
10. Action tracker entries

---

## 7. Non-Goals for MVP

Do not build these in the first version:

1. Real student-level PII ingestion
2. WhatsApp integration
3. Live government API integration
4. Advanced RBAC
5. Full multilingual support
6. Automated outbound messaging
7. Real-time streaming pipelines
8. Complex ML prediction models

The MVP should use synthetic and public-safe data only.

---

## 8. Recommended Tech Stack

### AI / LLM
- Primary: Claude Sonnet or Claude Opus via API
- Optional fallback: OpenAI or Gemini
- Local fallback for experiments: Ollama

### Agent Framework
- LangGraph preferred
- CrewAI optional, but LangGraph is better for stateful workflows and human-in-the-loop flows

### Backend
- Python
- FastAPI
- Pydantic
- Pandas
- DuckDB
- SQLAlchemy optional

### Frontend
Choose one:

#### Fast MVP Option
- Streamlit

#### Portfolio/Product-Grade Option
- Next.js
- React
- Tailwind CSS
- Recharts
- shadcn/ui

### Database
- Start with SQLite for local MVP
- Upgrade to Supabase Postgres later

### Vector DB
- Start with Chroma local
- Upgrade to Qdrant or Supabase pgvector later

### Document Processing
- PyMuPDF
- pdfplumber
- python-docx optional
- unstructured optional

### Evaluation / Observability
- Langfuse optional
- Phoenix optional
- Ragas optional

### Deployment
- Local first
- Then Render / Vercel / Streamlit Cloud / Supabase

---

## 9. Suggested First Build Strategy

Build the system in this sequence:

1. Create the project repo and folder structure.
2. Generate synthetic education datasets.
3. Build deterministic analytics without AI.
4. Add risk scoring.
5. Add policy document ingestion and RAG.
6. Add one District Review Agent.
7. Add dashboard.
8. Add report generation.
9. Add action tracker.
10. Add multi-agent orchestration.

Do not start with multi-agent complexity. Start with a deterministic analytics core.

---

## 10. High-Level System Architecture

```text
User
  ↓
Frontend Dashboard
  ↓
FastAPI Backend
  ↓
LangGraph Orchestrator
  ↓
Agents
  ├── Data Quality Agent
  ├── Analytics Agent
  ├── Policy RAG Agent
  ├── Risk Scoring Agent
  ├── Intervention Planner Agent
  └── Report Writer Agent
  ↓
Tools
  ├── CSV Loader
  ├── KPI Calculator
  ├── Risk Score Engine
  ├── Policy Retriever
  ├── Chart Generator
  ├── Review Memo Generator
  └── Action Tracker
  ↓
Storage
  ├── SQLite / Postgres
  ├── Chroma / Vector DB
  └── Local File Storage
```

---

## 11. Agent Design

### 11.1 Orchestrator Agent

Responsible for:
- Understanding user intent
- Selecting the right tools
- Calling relevant sub-agents
- Maintaining workflow state
- Ensuring outputs are evidence-backed

Input:
- User query
- Available data files
- User role
- Current district/block context

Output:
- Execution plan
- Agent task list
- Final response object

---

### 11.2 Data Quality Agent

Responsible for:
- Checking missing values
- Validating required columns
- Detecting stale records
- Detecting abnormal values
- Producing data quality warnings

Output example:
```json
{
  "data_quality_score": 82,
  "warnings": [
    "12 schools have missing DIKSHA usage for the latest week",
    "5 teacher training records have invalid completion percentages"
  ]
}
```

---

### 11.3 Analytics Agent

Responsible for:
- KPI calculation
- District summary
- Block ranking
- School comparison
- Trend analysis
- Funnel analysis

KPIs:
- DIKSHA sessions
- Learning minutes
- QR scans
- Teacher training completion
- Assessment score improvement
- High-risk school count
- Open field issue count

---

### 11.4 Policy RAG Agent

Responsible for:
- Retrieving relevant policy context
- Mapping policy goals to KPIs
- Supporting recommendations with policy references

Example:
- NIPUN Bharat → FLN outcomes
- PM SHRI → model school indicators
- Digital learning guidelines → adoption metrics
- Teacher training circular → completion expectations

---

### 11.5 Risk Scoring Agent

Responsible for generating school/block risk scores.

Initial risk formula:

```text
Risk Score =
  25% learning outcome risk
+ 20% digital usage risk
+ 15% teacher training gap
+ 15% infrastructure risk
+ 10% field issue severity
+ 10% attendance/data availability risk
+ 5% data quality risk
```

Risk bands:
- 0–39: Low
- 40–69: Medium
- 70–100: High

Every risk score must include explanation.

---

### 11.6 Intervention Planner Agent

Responsible for:
- Converting risks into actions
- Assigning suggested owner
- Assigning priority
- Adding evidence
- Creating review-ready next steps

Output example:
```json
{
  "school_id": "SCH_001",
  "risk": "Low DIKSHA usage and poor numeracy improvement",
  "recommended_action": "Schedule academic mentor visit and complete teacher training follow-up",
  "owner": "Block Resource Coordinator",
  "priority": "High",
  "evidence": [
    "DIKSHA sessions dropped by 32%",
    "Grade 3 numeracy is 14 points below district average"
  ]
}
```

---

### 11.7 Report Writer Agent

Responsible for:
- Executive summary
- KPI summary
- Risk summary
- Root-cause hypotheses
- Recommended actions
- Stakeholder messages
- Meeting questions
- Review memo

Tone:
- Professional
- Evidence-backed
- Government-program friendly
- Concise but action-oriented

---

## 12. Data Requirements

Use synthetic and public-safe data.

### Required CSV Files

#### 1. schools.csv
Columns:
- school_id
- school_name
- state
- district
- block
- school_type
- grades
- enrollment
- teachers_count
- internet_available
- device_available
- infrastructure_score

#### 2. diksha_usage.csv
Columns:
- school_id
- week
- qr_scans
- sessions
- learning_minutes
- active_teachers
- active_students_proxy

#### 3. assessments.csv
Columns:
- school_id
- grade
- subject
- baseline_score
- current_score
- district_average
- proficiency_band

#### 4. teacher_training.csv
Columns:
- teacher_id
- school_id
- course_name
- status
- completion_percent
- assessment_score

#### 5. field_issues.csv
Columns:
- issue_id
- school_id
- issue_type
- severity
- status
- reported_by
- description
- created_at

#### 6. policy_documents/
Include markdown or PDF files:
- NIPUN Bharat summary
- FLN goals
- PM SHRI school indicators
- Digital learning adoption guidelines
- Teacher training circular
- District review circular

---

## 13. Synthetic Dataset Guidelines

Create synthetic data with:

- 1 state
- 5 districts
- 50 blocks
- 1,000 schools
- 5,000–10,000 teachers
- weekly usage data for 8–12 weeks
- assessment scores for Grades 1–5
- teacher training completion records
- field issue records

Avoid:
- real student names
- real phone numbers
- Aadhaar
- real child-level records
- sensitive personal information

Use aggregated or proxy student data only.

---

## 14. Initial Folder Structure

```text
shiksha-signal-ai/
├── README.md
├── CONTEXT.md
├── .env.example
├── requirements.txt
├── docker-compose.yml
│
├── data/
│   ├── synthetic/
│   ├── public/
│   └── policy_documents/
│
├── scripts/
│   ├── generate_synthetic_data.py
│   └── ingest_policy_docs.py
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── schemas/
│   ├── services/
│   ├── agents/
│   ├── tools/
│   └── routes/
│
├── app/agents/
│   ├── orchestrator.py
│   ├── data_quality_agent.py
│   ├── analytics_agent.py
│   ├── policy_rag_agent.py
│   ├── risk_scoring_agent.py
│   ├── intervention_planner_agent.py
│   └── report_writer_agent.py
│
├── app/tools/
│   ├── csv_loader.py
│   ├── data_validator.py
│   ├── kpi_calculator.py
│   ├── risk_score.py
│   ├── policy_retriever.py
│   ├── report_generator.py
│   └── action_tracker.py
│
├── frontend/
│   └── streamlit_app.py
│
├── tests/
│   ├── test_data_generation.py
│   ├── test_kpi_calculator.py
│   ├── test_risk_score.py
│   └── test_data_quality.py
│
└── docs/
    ├── PRD.md
    ├── ARCHITECTURE.md
    ├── DATA_DICTIONARY.md
    ├── AGENT_SPEC.md
    └── DEMO_SCRIPT.md
```

---

## 15. Environment Variables

Create `.env.example` with:

```env
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=

LLM_PROVIDER=anthropic
PRIMARY_MODEL=claude-sonnet
CHEAP_MODEL=
EMBEDDING_PROVIDER=local

DATABASE_URL=sqlite:///./shiksha_signal.db
VECTOR_DB_PATH=./data/vector_store

APP_ENV=development
LOG_LEVEL=INFO
```

Never commit real API keys.

---

## 16. Backend API Routes

Initial routes:

### Health
```http
GET /health
```

### Data Upload
```http
POST /data/upload
```

### Generate Synthetic Data
```http
POST /data/generate-synthetic
```

### KPI Summary
```http
GET /analytics/kpi-summary?district=District%20A
```

### Risk Ranking
```http
GET /analytics/risk-ranking?district=District%20A
```

### Ask Agent
```http
POST /agent/ask
```

Request:
```json
{
  "query": "Generate weekly review for District A",
  "district": "District A",
  "role": "District Education Officer"
}
```

### Action Tracker
```http
GET /actions
POST /actions
PATCH /actions/{action_id}
```

---

## 17. Frontend MVP Screens

If using Streamlit first:

### Screen 1: Mission Control
- District selector
- KPI cards
- Block risk ranking
- Top high-risk schools
- Open issues

### Screen 2: Ask Agent
- Chat input
- Suggested prompts
- Agent response
- Source/evidence panel

### Screen 3: Review Memo
- Generated weekly review
- Copy/download button
- Meeting questions
- Stakeholder messages

### Screen 4: Action Tracker
- Actions table
- Owner
- Priority
- Status
- Evidence
- Approval state

---

## 18. Example User Prompts

Use these as golden prompts:

1. Generate weekly review for District A.
2. Which blocks are highest risk this week?
3. Why is Block 3 underperforming?
4. Which schools need immediate intervention?
5. Create an action plan for low DIKSHA usage.
6. Draft a message for block coordinators.
7. Prepare a review memo for district leadership.
8. What data quality issues should I check before review?
9. Which policy goals are at risk?
10. Summarize top 5 actions for next week.

---

## 19. Output Requirements

Every agent response should include:

1. Summary
2. Key findings
3. Evidence
4. Risk level
5. Recommended actions
6. Assumptions
7. Data quality warnings, if any
8. Next steps

Avoid unsupported claims. If data is missing, say so clearly.

---

## 20. Safety and Governance Rules

1. Do not process real child-level PII.
2. Use synthetic or aggregated data only.
3. Label root causes as hypotheses unless proven.
4. Every recommendation should include evidence.
5. Every automated action should require human approval.
6. Show data freshness and missing-data warnings.
7. Avoid overconfident conclusions.
8. Keep audit logs for agent decisions.

---

## 21. First Milestone

Build Milestone 1 without AI.

### Milestone 1 Objective
Generate synthetic education data and create deterministic district KPI + risk scoring output.

### Milestone 1 Deliverables
1. Project repo scaffold
2. Python virtual environment
3. `generate_synthetic_data.py`
4. Five CSV files generated in `data/synthetic/`
5. KPI calculator
6. Risk score calculator
7. Basic CLI or FastAPI route to print district summary

### Milestone 1 Success Criteria
Running one command should generate data and print:

- number of districts
- number of blocks
- number of schools
- average DIKSHA sessions
- teacher training completion rate
- average assessment improvement
- top 5 high-risk schools
- top 5 high-risk blocks

---

## 22. First Claude Code Instruction

Start by creating the repo scaffold and deterministic analytics foundation. Do not add LLM, LangGraph, RAG, frontend, or deployment yet.

Build the following first:

1. Folder structure from this CONTEXT.md
2. `requirements.txt`
3. `.env.example`
4. `scripts/generate_synthetic_data.py`
5. `app/tools/csv_loader.py`
6. `app/tools/kpi_calculator.py`
7. `app/tools/risk_score.py`
8. `tests/test_data_generation.py`
9. `tests/test_kpi_calculator.py`
10. `README.md` with setup and run instructions

The first runnable command should be:

```bash
python scripts/generate_synthetic_data.py
```

The second runnable command should be:

```bash
python -m app.tools.kpi_calculator
```

The third runnable command should be:

```bash
python -m app.tools.risk_score
```

---

## 23. Coding Standards

Use:
- Python 3.11+
- Type hints
- Pydantic where useful
- Clear function names
- Modular files
- Unit tests
- No hardcoded secrets
- No real PII
- Simple deterministic functions before AI calls

Prefer:
- readable code over clever code
- small functions
- clear test coverage
- logging for important steps
- docstrings for public functions

---

## 24. Immediate Next Step

The next step is to create the initial repository scaffold and generate the synthetic data engine.

Do not proceed to AI agents until the data layer and risk scoring are working correctly.
