# Next Bracket: Design Document

Oct 1, 2026 · @Tom

## 1. Overview

Next Bracket is a stateless web app that tells Air Force members exactly what they scored on the PFA, what they need to pass or hit a target, and what the regulation says, with every number computed by code and every policy answer cited to DAFMAN 36-2905.

**Problem.** The fitness standards changed, and many airmen find the scoring charts and component rules confusing. Existing calculators give a number but don't answer the questions people actually have: "What do I need on the run to pass?", "Where are my cheapest points?", "Can I retest early?"

**Solution.** Three things in one page:

- A form-based calculator that scores results instantly from versioned scoring tables.
- A chat assistant (LangGraph agent) that calls the same calculator functions as tools and answers policy questions with paragraph citations.
- A printable report showing current scores, paths to a target, and projected scores.

**Context.** This is a portfolio project for AI Engineer and Forward Deployed Engineer roles, and the author's first production deployment. It should demonstrate sound engineering judgment: deterministic code where correctness matters, an LLM only where language understanding helps, and evals that prove it works.

**Name.** Next Bracket, after the app's core insight: showing users the nearest point bracket they can reach. Tagline: "PFA scoring and planning for Airmen." Branding uses no Air Force or USAF names or insignia, so the app is never mistaken for an official tool.

## 2. Goals, non-goals, and principles

The guiding question for every decision: what problem does this solve for an airman who finds the charts confusing?

**Goals**

- Score any valid set of results correctly, 100% of the time, against the official charts.
- Answer "what do I need?" with concrete, numeric options.
- Answer policy questions with a citation to a DAFMAN paragraph, or say the answer isn't in the source.
- Store no user data. Every visit is a new session.
- Run live in production at about 1,000 users/month and 10 queries per user, for under $25/month.
- Measure quality with automated evals and operational metrics.

**Non-goals (v1)**

- User accounts, login, saved history, or score tracking over time.
- Workout plans or training advice.
- Medical advice, profile guidance beyond what the regulation states, or anything that helps someone avoid testing.
- Fine-tuning, GraphRAG, rerankers, separate vector databases, Kubernetes, Terraform, Redis.

**Principles**

1. **The LLM never computes a score.** All numbers come from tested Python functions.
2. **Add a component only when an eval metric shows it is needed**, then report the before/after.
3. **Every answer is traceable:** scores to a chart version, policy to a paragraph.
4. **Form first, chat second.** The calculator must be fully usable with no LLM.

## 3. Users and use cases

Primary users are Air Force members preparing for or reviewing a PFA, plus supervisors and UFPMs helping them. Most will be on a phone.

| Use case | Example question | Handled by |
| --- | --- | --- |
| Score it | "I'm 27, male, ran in 15:40, 45 push-ups. What did I get?" | `calculate_score` |
| Goal-seek | "What do I need to pass?" / "How do I get from 72 to 90?" | `plan_to_target` |
| Look up standards | "What's the max push-ups for my age group?" / "Run or shuttle?" | `get_standards` |
| Policy question | "Can I retest early?" / "How do profiles work?" | `search_regulation` |
| Get a report | Download or print current scores, options, and projections | Report page (no LLM) |
| Out of scope | "How do I get a profile to skip my test?" | Polite refusal, no tool |

## 4. Architecture

The browser owns all session state; the backend is a stateless FastAPI service where only `/chat` calls an LLM, and the database holds regulation text only.

&#91;embedded content: System architecture · one LLM path, reference data only in the database\]

Form scoring and the report go straight to `app/core` with no LLM; chat runs through the agent, which calls the same core functions as tools.

**Request flow for a chat turn**

1. The browser sends the full message history to `POST /chat`.
2. FastAPI validates size limits and builds a fresh LangGraph run (no checkpointer).
3. The agent calls the LLM, which picks a tool or answers.
4. Tools run: `calculate_score`, `plan_to_target`, and `get_standards` read the standards JSON; `search_regulation` queries pgvector.
5. The answer streams back to the browser. Tool results are included so the UI can render scores and citations.
6. LangSmith records metadata only. The server keeps nothing after the response.

## 5. Tech stack

One mainstream pick per layer; nothing niche.

| Layer | Choice | Why |
| --- | --- | --- |
| Language / packaging | Python 3.13, uv | Standard for AI work; uv is the current default package manager |
| API | FastAPI + Pydantic v2 | Typed request/response schemas; the same models become tool schemas |
| Agent | LangGraph | Most-requested agent framework; small explicit graph |
| LLM access | LangChain chat model via OpenAI-compatible endpoint (Groq in prod, OpenRouter for model bake-offs) | Model-agnostic; swap providers with config |
| Embeddings | OpenAI text-embedding-3-small | Near-zero cost at this corpus size; keeps PyTorch out of the image |
| Database | Postgres + pgvector on Supabase (free tier) | Reference data only: regulation chunks and embeddings |
| Scoring tables | Versioned JSON in the repo | Reviewable in PRs; no DB needed |
| PDF extraction | pdfplumber + manual verification | Few pages; correctness beats automation |
| Frontend | Next.js (App Router) + TypeScript + Tailwind on Vercel | Most in-demand frontend stack; free hosting |
| Container / hosting | Docker on Google Cloud Run | Scales to zero; near free at this traffic |
| CI/CD | GitHub Actions | Tests, evals, deploys on every push |
| Observability / evals | LangSmith (inputs/outputs hidden) + pytest | Native to LangGraph; metadata-only traces |

## 6. Data

Two data sources, both reference data that changes only when the Air Force publishes new standards.

### 6.1 Scoring tables (versioned JSON)

One file per standards version in `data/standards/`, named by effective date. The first is `2026-03-01.json`, from "Final USAF Physical Fitness Readiness Assessment Scoring (Effective 1 Mar 26)". Events are defined by config, not code, so adding or renaming an event requires no code change.

The 2026 charts define 8 events in 4 components. Age bands are under 25, 25-29, 30-34, 35-39, 40-44, 45-49, 50-54, 55-59, and 60 and over.

| Component | Max points | Events (unit) | Has a minimum? |
| --- | --- | --- | --- |
| Cardiorespiratory | 50 | 2-mile run (seconds, lower is better), 20m HAMR (shuttles) | Yes |
| Body composition | 20 | WHtR (hundredths, lower is better) | No |
| Muscular strength | 15 | push-up, hand-release push-up (reps) | Yes |
| Core endurance | 15 | sit-up, cross-leg reverse crunch (reps), forearm plank (seconds, higher is better) | Yes |

Example shape (values are real, from the push-up chart, male 25-29):

```json
{
  "version": "2026-03-01",
  "effective_date": "2026-03-01",
  "source": "PFRA Scoring Charts, effective 1 Mar 26",
  "passing_total": 75,
  "components": {
    "cardio":    {"max_points": 50, "has_minimum": true,  "events": ["run", "hamr"]},
    "body_comp": {"max_points": 20, "has_minimum": false, "events": ["whtr"]},
    "strength":  {"max_points": 15, "has_minimum": true,  "events": ["pushups", "hand_release_pushups"]},
    "core":      {"max_points": 15, "has_minimum": true,  "events": ["situps", "cross_leg_reverse_crunch", "plank"]}
  },
  "tables": [
    {
      "sex": "M", "age_min": 25, "age_max": 29, "event": "pushups",
      "unit": "reps", "higher_is_better": true,
      "component_minimum": 28,
      "brackets": [{"threshold": 63, "points": 15.0}, {"threshold": 62, "points": 14.5}]
    }
  ]
}
```

Rules:

- Every value comes from the charts PDF through `scripts/extract_tables.py`, then is spot-checked by hand. Never type chart values by hand into the JSON.
- Units are integers: reps, shuttles, or seconds for timed events. WHtR is stored in hundredths (0.49 becomes 49) so it stays an integer. No string times or floats in the data or the API.
- Brackets form a step function. Scoring = find the bracket the result falls in. For higher-is-better events the result must be at least the threshold. For lower-is-better events it must be at most the threshold.
- The `*` marks in the charts show the component minimum for each event, sex, and age band. It sits on the lowest scoring row (for push-ups that row is worth 2.5 points). A result below the minimum earns 0 and fails the component (para 3.7.4). The extractor must read the `*` from the PDF, not assume which row it is on.

**Scoring rules from the regulation** (DAFMAN 36-2905 dated 24 Mar 2026, paras 3.6 to 3.10):

- Composite is 0 to 100. Excellent is 90 or more, Satisfactory is 75 to 89.9, Unsatisfactory is 74.9 or less, or any component minimum not met (3.6.1, Table 3.3).
- Meeting only the minimums does not reach 75 (3.7.4).
- The 2km walk is pass/fail by age and sex (Table 3.1). It is for members medically barred from the run and HAMR. It earns no points and cannot produce an Excellent score (3.7.3).
- BFA is pass/fail: 26% or less for men, 36% or less for women (Table 3.2).
- Members with an exemption from a component are placed in PFRA Hold and are not scored (3.9, 3.10.6). Members with an ALC can test the approved modalities.
- Open: the regulation text does not define a composite for a partially exempt member. See section 16.2.
- A loader validates each file with Pydantic at startup: no gaps or overlaps in age bands, brackets monotonic, every event has a table for every sex and age band.
- The newest version whose effective date is on or before today is the default. Older versions stay for reference.

### 6.2 Regulation corpus (pgvector)

- Source: DAFMAN 36-2905 (24 Mar 2026, 116 pages). v1 uses this document only. Supplements can be added later.
- The local PDF is image-only (printed to PDF, no text layer), so it cannot be parsed as is. Plan: first look for the original e-Publishing PDF, which usually has text. If not, OCR it and review the output.
- Chunk by paragraph number (e.g. 3.4.2), not by fixed token count. Each chunk stores `paragraph`, `title`, `text`, `source_doc`, `version`, `embedding`.
- The point scoring charts are a separate document, not part of the DAFMAN, and are never in the corpus. Also exclude the body fat percent tables (Attachments 9 and 10). Chart questions go to `get_standards`, never RAG.
- Retrieval: hybrid search (Postgres full-text + pgvector cosine), top 5.
- Ingestion is a one-off script (`scripts/ingest_regulation.py`), rerun only when a new version is published.

## 7. Agent and tools

The agent is a single LangGraph tool-calling loop with four tools, no checkpointer, and a cap of 4 tool calls per turn. No multi-agent setup.

### 7.1 Graph

1. `agent` node: the LLM reads the full message history (sent by the browser) and either calls a tool or answers.
2. `tools` node: runs the requested tool and returns structured JSON.
3. Loop back to `agent` until it answers or hits the tool-call cap.
4. On the cap, return a fallback message suggesting the form-based calculator.

### 7.2 System prompt rules

- Never state a score, threshold, or time that did not come from a tool result.
- Policy answers must cite the paragraph returned by `search_regulation`. If retrieval returns nothing relevant, say the regulation doesn't cover it and suggest the Fitness Assessment Cell.
- If inputs are missing (age, sex, an event result), ask one short follow-up question.
- Convert user times like "15:40" to seconds before calling tools.
- Decline: medical advice, ways to avoid or game testing, anything unrelated to Air Force fitness.
- Keep answers short and plain. Mention the standards version from the tool result.

### 7.3 Tools

All four are plain Python functions in `app/core/` with Pydantic inputs and outputs. The same functions back the REST endpoints and the report.

```python
class Profile(BaseModel):
    age: int = Field(ge=17, le=70)
    sex: Literal["M", "F"]

class Results(BaseModel):
    values: dict[str, int]  # event -> reps or seconds, e.g. {"run": 940, "pushups": 45}

def calculate_score(profile: Profile, results: Results, version: str | None = None) -> ScoreReport: ...
def plan_to_target(profile: Profile, target: float, current: Results | None = None) -> PlanResult: ...
def get_standards(profile: Profile, event: str | None = None) -> StandardsTable: ...
def search_regulation(query: str, k: int = 5) -> list[CitedChunk]: ...
```

**`calculate_score`** returns per-component points, total, overall pass/fail, any missed component minimums, and `version` + `effective_date`.

**`plan_to_target`** returns up to three options, each with exact deltas and a projected total:

- **Single-event:** reach the target by improving one event only (one option per event where feasible).
- **Quick wins:** the cheapest available points. Find events where the result sits just below the next bracket and take those first.
- **Balanced:** spread the gain across events, one bracket at a time, round-robin.

Algorithm: walk brackets one step at a time. No optimizer. If `current` is missing, plan from each component's minimum. Options must respect component minimums. If the target is impossible (above max), say so.

**`get_standards`** returns the brackets for the user's age/sex band, optionally filtered to one event, including alternative events.

**`search_regulation`** returns chunks with `paragraph`, `title`, `text`, and a relevance score.

**Errors:** tools return a typed error (e.g. `{"error": "missing_input", "field": "age"}`) instead of raising, so the agent turns it into a follow-up question.

## 8. API

FastAPI, JSON in and out, no sessions or cookies. Only `/chat` touches the LLM.

| Method | Path | Body | Returns | LLM? |
| --- | --- | --- | --- | --- |
| POST | `/score` | `Profile`, `Results`, optional `version` | `ScoreReport` | No |
| POST | `/plan` | `Profile`, `target`, optional `Results` | `PlanResult` | No |
| POST | `/standards` | `Profile`, optional `event` | `StandardsTable` | No |
| POST | `/chat` | `messages` (full history from browser) | Streamed answer (SSE) + any tool results | Yes |
| POST | `/feedback` | `rating` (+1/-1), `tool_used` | 204 | No |
| GET | `/versions` | none | Available standards versions | No |
| GET | `/health` | none | 200 | No |

Guardrails on `/chat`:

- Max 20 messages and 4,000 characters per request; reject longer.
- Per-IP rate limit (e.g. 30 requests/min) as simple in-memory middleware. Fine for one Cloud Run instance; revisit only if traffic grows.
- Request timeout of 30 s.
- CORS restricted to the Vercel domain.

## 9. Frontend and report

A single mobile-first page: calculator on top, chat below or in a drawer, report as its own route. All state lives in React state and is gone on refresh.

### 9.1 Pages

- **`/` (home):** age, sex, and event inputs (time inputs as mm:ss, converted to seconds client-side). Score updates as you type via `/score`. A target field shows the three options from `/plan`. A "Get report" button.
- **Chat panel:** streams answers from `/chat`. Shows citations as tappable paragraph chips. Thumbs up/down per answer.
- **`/report`:** the printable report.

### 9.2 Report

The report is built only from `/score` and `/plan` responses. No LLM text, so no number on it can be hallucinated.

1. **Header:** generated date, standards version and effective date, age group, sex. No name.
2. **Current scores:** table of component, result, points, component minimum, pass/fail; total and overall status.
3. **Target and gap:** target score and points needed.
4. **Paths:** the three options with exact deltas (e.g. "+4 push-ups, -0:18 run").
5. **Projected score:** recalculated total for each option, labeled "score if achieved".
6. **Rules that apply:** templated notes triggered by the data (e.g. near a component minimum), each with its paragraph citation.
7. **Footer:** "Unofficial tool. Confirm with your Fitness Assessment Cell."

**Delivery:** print stylesheet; "Download PDF" calls `window.print()`. No PDF library, no server files.

**Sharing without storage:** inputs are encoded in the URL fragment (`/report#age=27&sex=M&run=940...`). The fragment is never sent to the server, so a bookmarked or shared report rebuilds client-side with nothing logged.

## 10. Privacy and data handling

Nothing a user types is persisted anywhere we control. Only anonymous operational metadata is kept.

| Where data could leak | Rule |
| --- | --- |
| Database | Holds regulation chunks and embeddings only. No user tables. |
| LangGraph | No checkpointer. History arrives from the browser on each request. |
| LangSmith traces | Inputs and outputs hidden. Keep latency, tokens, cost, tool name, errors. |
| FastAPI / Cloud Run logs | Never log request or response bodies. Log method, path, status, latency. |
| Feedback | Sent to LangSmith as run feedback: rating and tool name only. No database table. |
| Browser | React state only. No localStorage, cookies, or analytics scripts. |
| Report sharing | Inputs in the URL fragment, which is not sent to the server. |
| LLM provider | Inputs do pass through the provider. Choose zero-retention settings where offered and document which provider is used. |

Site copy: *"Nothing you enter is saved. We collect anonymous usage metrics (like response time) to improve the tool. Questions you ask are processed by a third-party AI model."*

## 11. Evaluation and testing

Two layers, so a wrong answer can be traced to either the tools or the agent.

### 11.1 Deterministic tests (pytest, every push)

- **Golden chart set:** for each event and age/sex band, the boundary values of every bracket (on the threshold, one below, one above) checked against values hand-copied from the PDF. Target: 100% pass.
- **Table validation:** the Pydantic loader checks from section 6.1.
- **`plan_to_target` properties:** every returned option, when re-scored with `calculate_score`, reaches the target and meets all component minimums.
- **API tests:** each endpoint with valid, missing, and out-of-range inputs.

### 11.2 Agent evals (LangSmith dataset, on PRs that touch the agent or prompts)

A hand-written set of 50 to 100 questions in `evals/dataset.jsonl`, written from the regulation and the use cases in section 3. Each row has the question, expected tool, expected arguments, and the expected answer or paragraph.

| Metric | How measured | Target (v1) |
| --- | --- | --- |
| Tool selection accuracy | Called tool equals expected tool | 95% or higher |
| Argument extraction accuracy | Tool arguments equal expected (exact match on numbers) | 95% or higher |
| Retrieval recall@5 | Expected paragraph appears in top 5 chunks | 90% or higher |
| Citation faithfulness | LLM judge: is the answer supported by the cited chunk? | 90% or higher |
| Out-of-scope refusal rate | Share of out-of-scope questions correctly declined | 100% |
| Numeric hallucination | Any number in the answer not present in a tool result | 0 |

Targets are starting points; adjust after the first baseline run. A drop of more than 5 points on any metric fails CI.

### 11.3 Model bake-off (OpenRouter, one-off)

Run the agent eval set against 4 to 5 models via OpenRouter. Record accuracy metrics, p95 latency, and cost per query. Pick the production model from that table and commit the results to `evals/results/`.

## 12. Observability and metrics

Production metrics answer two questions: is it working, and is it useful? All come from LangSmith metadata and Cloud Run metrics, never user content.

| Question | Metric | Source |
| --- | --- | --- |
| Is it fast? | p50 / p95 latency for `/chat` and `/score` | LangSmith, Cloud Run |
| Is it cheap? | Tokens and cost per chat turn; monthly spend | LangSmith, provider dashboard |
| Is it reliable? | Error rate; tool-call cap hits | LangSmith, Cloud Run |
| Is it useful? | Thumbs-up rate per tool | LangSmith feedback |
| Where is the corpus weak? | Count of `search_regulation` calls whose top score is below a threshold | LangSmith metadata |
| What do people use? | Share of turns by tool | LangSmith metadata |

Trace sampling: 100% in development; in production, 100% of errored turns and a 25% sample of the rest, to stay near LangSmith's free trace allowance. Feedback is recorded only on sampled turns; adjust the rate once real volume is known. Set a monthly spend cap with the LLM provider.

## 13. Deployment, CI/CD, and cost

Backend on Cloud Run, frontend on Vercel, database on Supabase; expected total about $5 to $25/month.

### 13.1 Environments

- **Local:** `docker compose` with Postgres + pgvector and the API; Next.js dev server. LLM via OpenRouter or Groq key in `.env`.
- **Production:** Cloud Run (min instances 0, max 2), Vercel, Supabase. Secrets in Google Secret Manager and Vercel env vars, never in the repo.

### 13.2 GitHub Actions

1. **On every push:** ruff lint, mypy, pytest (deterministic tests), frontend lint and type check.
2. **On PRs touching `app/agent/` or prompts:** run agent evals against LangSmith; fail on regression.
3. **On merge to `main`:** build Docker image, push to Artifact Registry, deploy to Cloud Run. Vercel deploys the frontend automatically.

### 13.3 Cost estimate (10,000 chat turns/month)

| Item | Estimate |
| --- | --- |
| LLM (small/medium open model on Groq, \~3K in / 300 out tokens per turn, up to 2 calls per turn) | $4 to $20 |
| Embeddings (queries only) | under $1 |
| Cloud Run | $0 to $3 |
| Vercel, Supabase, LangSmith | $0 (free tiers) |

Form-based scoring never calls the LLM, so real spend should come in below this. Verify current provider pricing before launch.

## 14. Repo structure

One monorepo, backend and frontend side by side.

```
next-bracket/
  backend/
    app/
      core/            # scoring, planning, standards lookup (pure functions, no I/O)
      rag/             # retrieval: hybrid search over pgvector
      agent/           # LangGraph graph, tools wrappers, system prompt
      api/             # FastAPI routers: score, plan, standards, chat, feedback
      models.py        # Pydantic schemas shared by API, tools, report
      config.py        # settings from env vars
      main.py
    data/standards/    # versioned scoring JSON
    data/sources/      # official PDFs (charts committed; DAFMAN kept local, git-ignored)
    scripts/           # ingest_regulation.py, extract_tables.py
    tests/             # pytest: golden chart set, planner properties, API
    evals/             # dataset.jsonl, run_evals.py, results/
    Dockerfile
    pyproject.toml     # uv
  frontend/
    app/               # Next.js routes: /, /report
    components/        # Calculator, ChatPanel, ReportView
    lib/               # API client, time parsing, URL-fragment encoding
  docker-compose.yml   # local Postgres + API
  .github/workflows/   # ci.yml, evals.yml, deploy.yml
  CLAUDE.md            # this design doc, condensed, for Claude Code
  README.md
```

## 15. Build plan

Eight milestones, each ending in something that works and can be demoed. Do not start a milestone until the previous one's tests pass.

- [x] **M0. Setup:** `backend/` layout, uv, ruff, mypy, pytest, and CI on every push (moved up from M5).
- [ ] **M1. Scoring core:** standards JSON (verified by hand against the PDF), Pydantic loader, `calculate_score`, golden chart tests at 100%.
- [ ] **M2. Planning:** `plan_to_target` and `get_standards`, with property tests.
- [ ] **M3. API:** FastAPI endpoints `/score`, `/plan`, `/standards`, `/health`, with tests and Dockerfile.
- [ ] **M4. Frontend calculator:** Next.js form and live scoring against the local API.
- [ ] **M5. First deploy:** Cloud Run + Vercel + deploy workflow. The calculator is live with no AI.
- [ ] **M6. RAG:** ingest DAFMAN into pgvector, `search_regulation`, retrieval recall@5 measured.
- [ ] **M7. Agent:** LangGraph loop with all four tools, `/chat` streaming, chat panel, LangSmith tracing with hidden inputs, agent eval set and model bake-off.
- [ ] **M8. Report and polish:** `/report` page, print stylesheet, URL-fragment sharing, feedback buttons, privacy copy, README with architecture and eval results.

## 16. Instructions for Claude Code and open questions

### 16.1 Working rules for Claude Code

- Build one milestone at a time from section 15. Stop at the end of each milestone and summarize what was built and how to run the tests.
- Never invent scoring values. If a standards JSON value is unknown, leave a clearly marked placeholder and a failing test, and flag it.
- Keep `app/core/` free of I/O and LLM calls. Tools in `app/agent/` are thin wrappers around `core`.
- Do not add dependencies outside section 5 without asking. No new infrastructure (Redis, auth, extra databases).
- Never log request bodies or user inputs. Never add storage of user data.
- Write tests alongside code. Type hints everywhere; ruff and mypy clean.
- I am learning: explain non-obvious decisions in short code comments and in the milestone summary.

### 16.2 Open questions (resolve before M1)

- [x] Which events and components are in the current standard? Resolved: 8 events in 4 components (section 6.1). Passing total is 75. Component minimums are per event, sex, and age band, marked `*` in the charts.
- [x] What effective date and version label should the first standards file use? Resolved: `2026-03-01`, from the charts header "Effective 1 Mar 26".
- [x] Are scoring charts available as text in the PDF? Resolved: yes, the charts PDF has a text layer, so pdfplumber works. The DAFMAN PDF does not (section 6.2).
- [x] Which official documents go in the RAG corpus? Resolved for v1: DAFMAN 36-2905 only.
- [x] GitHub repo: `tomtranjr/nextBracket` (private for now). Domain is still open and not needed until M5.
- [ ] How is the composite scored when a component is exempt or replaced? Paras 3.9 and 3.10 put exempt members in PFRA Hold and do not give a formula. Until this is answered, `calculate_score` scores only a full set of components and reports exempt components as "not scored". Decide before PR 7.
- [ ] Which Groq (or OpenRouter) model is the starting default before the bake-off? Decide at the agent PRs.
- [ ] Does the DAFMAN have a text-layer original on e-Publishing, or does it need OCR? Decide at the RAG PRs.
