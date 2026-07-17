# End-to-End Walkthrough

How to stand up all three portfolio projects together and prove a request
travels from a real caller, through `api_gateway`, through the `orchestrator`
and its Agent A, into Project 2's permission-aware retrieval, against data
Project 1 actually ingested — and that the permission boundary holds.

There are two ways to test this:

- **Full stack** (this document) — real GCP, real ingested data, real
  permission enforcement. Proves the whole platform.
- **Fast local check** — point the orchestrator at any stub `/query` server
  instead of a real Project 2. Useful for iterating on Project 3's own code
  without touching GCP, but doesn't exercise real retrieval or permissions.
  See `tests/` for the fully-mocked equivalent, and
  `infra/scripts/e2e-smoke-test.sh --help`-style usage below for how to point
  it at a stub.

This walkthrough assumes all three repos are cloned as sibling directories
(`01-DataClean-and-Chunk`, `Enterprise-RAG-Security-Guardrails`,
`Multi-Agent-Corp-Oper-Platform`), which is how their `.env.example` files
already assume they compose.

> **Already have data ingested?** If Project 1 has already processed
> documents into Cloud SQL (e.g. you ran `main.py batch` earlier and have
> chunks sitting in `document_chunks`), skip Step 1 and go straight to
> [Step 1.5 — find your filenames](#step-15--find-filenames-to-tag-skip-if-you-already-know-them),
> then Step 2.

---

## Step 1 — Ingest a document (Project 1)

```bash
cd 01-DataClean-and-Chunk
cp .env.example .env
# Fill in: GOOGLE_CLOUD_PROJECT, DOCAI_PROCESSOR_ID (create one with
# ./scripts/setup-docai.sh if you don't have one yet)

./scripts/setup-cloudsql.sh          # creates the Cloud SQL instance + database, if not already done
./scripts/setup-output-bucket.sh
./scripts/start-cloudsql-proxy.sh <project-id> <instance-name> &   # keep this running

uv sync
uv run python main.py process gs://corporate-raw-docs/<your-file>.pdf --upload --store
```

Confirm it landed:
```bash
uv run python main.py search "test" --top-k 1
```
You should get at least one result back. If not, stop here — nothing downstream will work without ingested chunks.

---

## Step 1.5 — Find filenames to tag (skip if you already know them)

Project 1's CLI has `search` but no `list`, so with 10 PDFs already loaded the
quickest way to see what's actually in the table (and under what `filename`
value, which must match exactly for tagging in Step 2) is a direct query
against the same Cloud SQL instance:

```bash
cd 01-DataClean-and-Chunk
./scripts/start-cloudsql-proxy.sh <project-id> <instance-name> &   # if not already running

psql "postgresql://pipeline:<password>@localhost:5432/docpipeline" -c \
  "SELECT filename, COUNT(*) AS chunks FROM document_chunks GROUP BY filename ORDER BY filename;"
```

This lists all 10 filenames and how many chunks each produced — copy the
exact `filename` values for Step 2. (No `psql` installed? `uv run python main.py search "<any keyword from your docs>" --top-k 10` and read the `filename` field off each result instead — noisier, but needs no extra tooling.)

---

## Step 2 — Tag permissions and serve the RAG API (Project 2)

```bash
cd ../Enterprise-RAG-Security-Guardrails
cp .env.example .env
# Point PG_CONNECTION_STRING at the same Cloud SQL proxy tunnel from Step 1
# (same instance/database Project 1 just populated)

uv sync

# Tag each document with an access-control level. Use the EXACT filename
# values from Step 1.5. With 10 PDFs, tag a real spread so the permission
# boundary in Step 5 is meaningful instead of a single pass/fail file —
# e.g.:
uv run python main.py tag-permissions public-handbook.pdf --sensitivity public
uv run python main.py tag-permissions eng-design-doc.pdf --sensitivity internal --roles engineering
uv run python main.py tag-permissions finance-report.pdf --sensitivity confidential --roles finance
# ...repeat for the rest of your 10 files, matching real filenames from Step 1.5

uv run python main.py serve --port 8000
```

Leave this running. Sanity check it directly, before Project 3 is involved — ask about a document you tagged `internal`, once as a cleared user and once as an uncleared one:
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "what does the document say?", "user_id": "bob", "clearance": "internal", "roles": ["engineering"]}'

curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "what does the document say?", "user_id": "eve", "clearance": "public", "roles": []}'
```
The first should return a real `answer` with non-empty `sources`; the second's `sources` should come back empty (or only include chunks you separately tagged `public`). If both calls return the same thing, the tagging in this step didn't take — re-check the filename match against Step 1.5's output before continuing.

---

## Step 3 — Start Project 3's services

```bash
cd ../Multi-Agent-Corp-Oper-Platform
cp .env.example .env
# RAG_SERVICE_URL=http://localhost:8000 (Project 2's serve port from Step 2)
# LOCAL_DEV=true

uv sync

uv run python -m services.orchestrator.main &   # :8081
uv run python -m services.api_gateway.main &     # :8080
```

---

## Step 4 & 5 — Run the smoke test

Rather than typing the curl commands by hand, `infra/scripts/e2e-smoke-test.sh`
drives the same requests through the running stack and checks the results:

```bash
./infra/scripts/e2e-smoke-test.sh
```

It will:
1. Health-check all three services (fails fast with a clear message if one isn't reachable)
2. `POST /tasks` as an **allowed** user (`clearance=internal`, `roles=engineering` by default) and print the response
3. `GET /tasks/{id}` and confirm the cached result comes back
4. `GET /tasks/{unknown-id}` and confirm it 404s
5. `POST /tasks` again as a **denied** user (`clearance=public`, no roles by default) and print the response
6. Compare source counts between the allowed and denied calls and assert the denied user got fewer (proving the ACL boundary set up in Step 2 actually holds end-to-end, not just inside Project 2 alone)

Override any of the identities, question, or endpoints via env vars if your
tagging in Step 2 used different roles/clearance:

```bash
ALLOWED_CLEARANCE=confidential ALLOWED_ROLES=finance \
DENIED_CLEARANCE=public \
QUESTION="what is the policy?" \
./infra/scripts/e2e-smoke-test.sh
```

To point the script at services running elsewhere (e.g. deployed Cloud Run URLs instead of localhost):

```bash
GATEWAY_URL=https://api-gateway-xyz.run.app \
ORCHESTRATOR_URL=https://orchestrator-xyz.run.app \
RAG_URL=https://rag-security-guardrails-xyz.run.app \
./infra/scripts/e2e-smoke-test.sh
```

---

## What "passing" actually proves

- `api_gateway` → `orchestrator` HTTP call works (with OIDC auth if `LOCAL_DEV=false`)
- `orchestrator`'s `AnalystAgent` correctly calls Project 2's `/query` contract
- Project 2's permission filtering is enforced all the way through Project 3's task API, not just when called directly
- The task resource contract (`POST /tasks` → `task_id` → `GET /tasks/{id}`) works end-to-end
- Unknown task IDs correctly 404

## What it does NOT prove

- NeMo Guardrails input/output rails (Project 2's own test suite covers this — the smoke test only checks the ACL boundary, not prompt-injection blocking)
- Any behavior beyond Phase 1 (no Agent B/C, no Pub/Sub, no Firestore — see `README.md`'s roadmap)
- Load/concurrency behavior — this is a single-request smoke test, not a load test

## Cleaning up

```bash
# Stop Project 3's services
pkill -f "services.orchestrator.main"
pkill -f "services.api_gateway.main"

# Stop Project 2's server: Ctrl-C its terminal, or:
pkill -f "src.rag_guardrails.api.app"

# Stop the Cloud SQL proxy from Step 1
pkill -f cloud-sql-proxy
```
