## **Project 3: Multi-Agent Corporate Operations Platform**

This advanced project transitions the portfolio from standard AI to **Agentic AI orchestration**, the definitive high-value skill of late 2026.

- **The Problem:** Businesses need AI that doesn't just chat, but autonomously executes multi-step workflows like auditing contracts or updating legacy databases.
- **What It Builds:** An autonomous system where multiple specialized AI agents collaborate. Agent A uses the secure Project 2 knowledge base to analyze an incoming request; Agent B verifies compliance; Agent C updates an operational Cloud SQL database.
- **How It Connects:** Reads through Project 2's (`Enterprise-RAG-Security-Guardrails`) permission-aware query API, which itself sits on Project 1's (`01-DataClean-and-Chunk`) ingestion + vector store. Running this system generates the compute and financial telemetry that becomes the input for a future cost-optimization project.
- **Tech Stack:** CrewAI, FastAPI, Docker, Cloud Run, Cloud SQL (Postgres), Pub/Sub, Vertex AI.

This document specifies the production GCP architecture for Project 3 and how it composes with Projects 1 and 2 into a single platform.

---

## How the three projects compose

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Project 1 — Data Clean & Chunk                                          │
│ Raw docs → Document AI → clean/chunk → embed → pgvector (document_chunks)│
└───────────────────────────────┬───────────────────────────────────────┘
                                 │ same Cloud SQL instance, same embedding model
┌───────────────────────────────▼───────────────────────────────────────┐
│ Project 2 — Enterprise RAG + Security Guardrails                        │
│ Permission-aware retrieval + NeMo Guardrails → POST /query (FastAPI)    │
└───────────────────────────────┬───────────────────────────────────────┘
                                 │ HTTPS, service-to-service (OIDC identity token)
┌───────────────────────────────▼───────────────────────────────────────┐
│ Project 3 — Multi-Agent Corporate Operations Platform (this repo)       │
│ CrewAI agents call Project 2 as a tool, act, and record what they did   │
└─────────────────────────────────────────────────────────────────────────┘
```

Project 3 does not re-implement retrieval or guardrails — it **consumes Project 2's `/query` endpoint as a tool call**. This keeps the security boundary (clearance/roles, prompt-injection rails) in exactly one place instead of duplicating it inside agent code.

---

## Agent design

| Agent | Role | Reads | Writes | Guardrail |
|---|---|---|---|---|
| **Agent A — Analyst** | Interprets the incoming request, calls Project 2's `/query` as a retrieval tool, produces a structured findings summary (facts + citations) | Project 2 API | Task state (Firestore) | Inherits Project 2's input/output rails on every retrieval call |
| **Agent B — Compliance Reviewer** | Checks Agent A's findings against policy rules (allowed actions, required approvals, sensitivity thresholds); can escalate to human-in-the-loop | Task state, policy config | Task state, approval flag | Deterministic rule engine first, LLM only for ambiguous cases — never the sole gate on a write action |
| **Agent C — Operator** | Executes the approved action against the operational database through a narrow, allow-listed tool interface (no free-form SQL) | Task state (must have `approved=true` from Agent B) | `corporate_ops` Cloud SQL database | Tool schema restricts Agent C to specific parameterized functions (e.g. `update_contract_status`, `create_audit_record`) — never raw query execution |

A **Crew Orchestrator** (CrewAI `Process.sequential` or `Process.hierarchical`) coordinates the handoff: A → B → (approved?) → C, with every transition persisted so a run can be resumed or audited.

**Hard rule carried over from Project 2:** Agent C never acts without Agent B's `approved=true`, and Agent B never approves without Agent A's citations resolving to actual retrieved chunks (no ungrounded approvals). This mirrors Project 2's fail-closed philosophy.

---

## GCP production architecture

```
                              ┌─────────────────────┐
  Client / internal caller ──▶  Cloud Run: api-gateway │  FastAPI — POST /tasks, GET /tasks/{id}
                              └──────────┬───────────┘
                                         │ publish
                                         ▼
                              ┌─────────────────────┐
                              │  Pub/Sub: task-queue  │  decouples request accept from agent run
                              └──────────┬───────────┘
                                         │ push subscription
                                         ▼
                              ┌─────────────────────┐
                              │ Cloud Run: orchestrator│  CrewAI crew runner, min-instances=0
                              │  (Agent A→B→C)        │  concurrency=1 per task (isolation)
                              └──┬─────────┬────────┘
                    tool call     │         │ tool call (allow-listed fns only)
       ┌────────────────────────┘         └─────────────────────┐
       ▼                                                         ▼
┌───────────────────┐                                 ┌───────────────────────┐
│ Cloud Run: Project 2 │  existing /query service       │ Cloud SQL: corporate_ops│
│ (RAG + Guardrails)   │  (OIDC-authenticated call)      │ Postgres — audit_log,   │
└──────────┬─────────┘                                 │ contracts, approvals    │
           │                                            └───────────────────────┘
           ▼
┌───────────────────┐
│ Cloud SQL: pgvector │  Project 1's document_chunks (read-only from Project 2)
└───────────────────┘

Cross-cutting:
┌─────────────────────────────────────────────────────────────────────────┐
│ Firestore          — task/run state machine (status, agent transcripts)  │
│ Vertex AI           — LLM calls for all three agents (Gemini, model-      │
│                        pinned per agent role; swappable per Project 2's   │
│                        provider-factory pattern)                          │
│ Secret Manager       — DB creds, service-to-service auth config           │
│ Cloud Logging        — structured logs, one entry per agent decision      │
│ Cloud Trace          — end-to-end latency across the 3-agent handoff      │
│ Cloud Monitoring     — SLOs, alert on approval-rate anomalies / DLQ depth │
│ VPC Service Controls — perimeter around Cloud SQL + Vertex AI             │
│ IAM                  — dedicated service account per Cloud Run service,   │
│                        least-privilege, no shared credentials             │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Pub/Sub between the gateway and the orchestrator
Agent runs are multi-step and can take tens of seconds (multiple LLM calls + a Project 2 round trip). Accepting the HTTP request, handing it to Pub/Sub, and returning a `task_id` immediately avoids holding client connections open and gives free retry/backoff/DLQ semantics — the same pattern Project 1 already uses for its Airflow DAG's error handling.

### Why Firestore for task state
Agent runs are a state machine (`queued → analyzing → reviewing → approved/rejected → executing → done/failed`) with nested transcripts per agent. Firestore's document model fits this better than relational rows, and it's cheap at portfolio scale. Cloud SQL (`corporate_ops`) is reserved for the actual business data the agents mutate — keeping "what the agents did" separate from "what the agents changed" makes audit review straightforward.

### Why a separate `corporate_ops` database, same Cloud SQL instance
Reuses the infrastructure Projects 1–2 already stood up (no new instance to provision/pay for), but keeps agent write-access scoped to its own database/schema — Agent C's service account has no grant on `document_chunks`.

---

## Repository structure (target)

```
├── services/
│   ├── api_gateway/            # FastAPI: POST /tasks, GET /tasks/{id}, GET /health
│   ├── orchestrator/           # CrewAI crew: agents, tasks, tool definitions
│   │   ├── agents/
│   │   │   ├── analyst.py      # Agent A — wraps Project 2 client as a CrewAI tool
│   │   │   ├── compliance.py   # Agent B — rule engine + LLM fallback
│   │   │   └── operator.py     # Agent C — allow-listed DB tool functions
│   │   ├── tools/
│   │   │   ├── rag_client.py   # typed client for Project 2's /query
│   │   │   └── ops_db.py       # parameterized functions only, no raw SQL exposed to LLM
│   │   ├── state/task_store.py # Firestore read/write for run state
│   │   └── crew.py             # Process definition, agent wiring, handoff rules
│   └── shared/                 # config, logging, auth helpers shared by both services
├── infra/
│   ├── terraform/              # Cloud Run services, Pub/Sub, Firestore, IAM, Cloud SQL db
│   └── scripts/                # setup-*.sh in the style of Project 1/2's scripts/
├── policies/                   # Agent B's declarative rule set (YAML) — versioned, reviewable
├── tests/                      # pytest, fully mocked GCP/DB/LLM clients (matches Project 2)
├── docker/
│   ├── api_gateway.Dockerfile
│   └── orchestrator.Dockerfile
└── .env.example
```

---

## Security model (extends Project 2's guardrails to actions, not just answers)

1. **Identity propagation** — the original caller's `UserContext` (user_id, clearance, roles) travels with the task through Pub/Sub and is passed to Project 2's `/query` on every retrieval, so Agent A can never see chunks the requesting user isn't cleared for.
2. **No free-form SQL for Agent C** — the LLM only ever sees a small set of typed tool functions (e.g. `update_contract_status(contract_id, status, reason)`). This is the same "narrow the blast radius" principle as Project 2's SQL ACL predicate, applied to writes instead of reads.
3. **Human-in-the-loop escalation** — Agent B can set `status=needs_human_approval` for actions above a configurable risk/value threshold instead of auto-approving; the API exposes `POST /tasks/{id}/approve` for that path.
4. **Full audit trail** — every agent decision (inputs, tool calls, outputs, model + prompt version) is written to `audit_log` in `corporate_ops` and to Cloud Logging, satisfying the same "structured audit logging of denied/blocked queries" item Project 2 flagged as a to-do — extended here to cover approvals and writes.
5. **Service-to-service auth** — Cloud Run → Cloud Run calls (orchestrator → Project 2) use OIDC identity tokens validated by Cloud Run's built-in IAM invoker check, not a shared API key.
6. **VPC Service Controls perimeter** around Cloud SQL and Vertex AI so exfiltration via a compromised agent tool call is bounded even if guardrails are bypassed.

---

## Phased build roadmap

**Phase 1 — Single-agent skeleton on Cloud Run**
Stand up `api_gateway` and `orchestrator` as two Cloud Run services with a stub Agent A that only calls Project 2's `/query` and returns the answer. Validates the service-to-service auth and Pub/Sub plumbing before adding multi-agent complexity.

**Phase 2 — Add Agent B (compliance) with a static policy set**
Introduce Firestore task state, the sequential handoff, and a small YAML rule set in `policies/`. No writes yet — Agent B's decision is the end state.

**Phase 3 — Add Agent C (operator) against `corporate_ops`**
Provision the Cloud SQL database/schema, build the allow-listed tool functions, wire the approval gate. This is the first phase with real side effects — add the audit log here, not after.

**Phase 4 — Human-in-the-loop + observability**
`POST /tasks/{id}/approve`, Cloud Monitoring dashboards/alerts, Cloud Trace spans across the 3-agent handoff, structured audit logging finished end-to-end.

**Phase 5 — Hardening for production exposure**
Real SSO/JWT identity (closing Project 2's biggest open to-do, inherited here), rate limiting on `api_gateway`, VPC Service Controls perimeter, load test the orchestrator's concurrency=1-per-task assumption under queue backlog.

**Phase 6 — Cost/compute telemetry export**
Cloud Run + Vertex AI usage and Cloud SQL query stats exported (BigQuery sink) — this is the "massive compute and financial data" the original brief earmarks as the foundation for a future optimization project.

---

## Tech Stack

- **Agent framework:** CrewAI (sequential/hierarchical process)
- **API:** FastAPI + Uvicorn, containerized, deployed on Cloud Run
- **Async task handoff:** Pub/Sub (push subscription into the orchestrator)
- **Task/run state:** Firestore
- **Operational data store:** Cloud SQL for PostgreSQL, `corporate_ops` database (separate from Project 1's `document_chunks`, same instance)
- **LLM:** Vertex AI (Gemini), provider-factory pattern matching Project 2's pluggable `llm/provider.py`
- **Retrieval + guardrails:** Project 2's `/query` API, called as a tool, not reimplemented
- **Secrets:** Secret Manager
- **Observability:** Cloud Logging, Cloud Trace, Cloud Monitoring
- **Security perimeter:** IAM (per-service accounts), VPC Service Controls
- **IaC:** Terraform
- **Tests:** pytest + pytest-mock, fully mocked GCP/DB/LLM clients (no live calls), matching Projects 1–2's testing convention

## Local development

```bash
# 1. Install dependencies
uv sync

# 2. Copy and fill in environment variables
cp .env.example .env

# 3. Run tests (fully mocked, no live GCP/DB/LLM calls)
uv run pytest -v

# 4. Run both services locally (needs Project 2 running on :8000, or point
#    RAG_SERVICE_URL at any /query-compatible server)
uv run python -m services.orchestrator.main   # :8081
uv run python -m services.api_gateway.main    # :8080

# ...or via Docker Compose (still expects Project 2 reachable at
# host.docker.internal:8000 — see docker-compose.yml)
docker compose up --build

# 5. Exercise the task API
curl -X POST http://localhost:8080/tasks \
  -H "Content-Type: application/json" \
  -d '{"question": "what is the vacation policy?", "user_id": "bob", "clearance": "internal", "roles": ["engineering"]}'
```

## Status

- [x] Architecture and GCP production design specified (this document)
- [x] Phase 1 — `api_gateway` + `orchestrator` skeleton on Cloud Run
      `services/api_gateway` (FastAPI: `POST /tasks`, `GET /tasks/{id}`, `GET /health`) calls
      `services/orchestrator` (FastAPI: `POST /run-task`, `GET /health`) over HTTP, OIDC-authenticated
      via `services/shared/auth_session.py` when not `LOCAL_DEV`. `AnalystAgent` (Agent A stub) calls
      Project 2's `/query` through `RagClient`. 12 tests passing (fully mocked); both Dockerfiles build
      and serve `$PORT` correctly; verified end-to-end locally through a live 3-hop HTTP chain.
- [ ] Phase 2 — Agent B + Firestore task state
- [ ] Phase 3 — Agent C + `corporate_ops` Cloud SQL + audit log
- [ ] Phase 4 — human-in-the-loop approval + observability
- [ ] Phase 5 — production hardening (SSO/JWT, rate limiting, VPC-SC)
- [ ] Phase 6 — cost/compute telemetry export to BigQuery
