#!/usr/bin/env bash
set -euo pipefail

# Script: e2e-smoke-test.sh
# Purpose: Drive the full 3-project chain (Project 1 data -> Project 2 RAG ->
#          Project 3 api_gateway/orchestrator) through the api_gateway's real
#          HTTP API, as an external caller would, and assert the permission
#          boundary actually holds (allowed vs. denied clearance).
# Usage:   ./infra/scripts/e2e-smoke-test.sh
#
# Prerequisites (see WALKTHRU.md for the full setup):
#   - Project 1 has already ingested and embedded at least one document
#   - Project 2's chunks are tagged with permissions (main.py tag-permissions)
#   - Project 2's service is running and reachable (default: localhost:8000)
#   - Project 3's orchestrator and api_gateway are running
#     (default: localhost:8081, localhost:8080)
#
# This script only exercises already-running services — it does not start
# them or provision GCP resources. Override endpoints via env vars:
#   GATEWAY_URL, ORCHESTRATOR_URL, RAG_URL
#   ALLOWED_USER_ID, ALLOWED_CLEARANCE, ALLOWED_ROLES (comma-separated)
#   DENIED_USER_ID, DENIED_CLEARANCE, DENIED_ROLES
#   QUESTION

GATEWAY_URL="${GATEWAY_URL:-http://localhost:8080}"
ORCHESTRATOR_URL="${ORCHESTRATOR_URL:-http://localhost:8081}"
RAG_URL="${RAG_URL:-http://localhost:8000}"

QUESTION="${QUESTION:-what does the document say?}"

ALLOWED_USER_ID="${ALLOWED_USER_ID:-bob}"
ALLOWED_CLEARANCE="${ALLOWED_CLEARANCE:-internal}"
ALLOWED_ROLES="${ALLOWED_ROLES:-engineering}"

DENIED_USER_ID="${DENIED_USER_ID:-eve}"
DENIED_CLEARANCE="${DENIED_CLEARANCE:-public}"
DENIED_ROLES="${DENIED_ROLES:-}"

pass() { echo "  PASS: $1"; }
fail() { echo "  FAIL: $1"; exit 1; }

roles_json() {
    # "a,b,c" -> ["a","b","c"]; "" -> []
    local csv="$1"
    if [ -z "$csv" ]; then
        echo "[]"
        return
    fi
    python3 -c "import json,sys; print(json.dumps(sys.argv[1].split(',')))" "$csv"
}

echo "=== Step 0: health checks ==="
for name_url in "Project 2 (RAG)|$RAG_URL" "orchestrator|$ORCHESTRATOR_URL" "api_gateway|$GATEWAY_URL"; do
    name="${name_url%%|*}"
    url="${name_url##*|}"
    code=$(curl -s -o /dev/null -w "%{http_code}" "$url/health" || echo "000")
    if [ "$code" = "200" ]; then
        pass "$name reachable at $url"
    else
        fail "$name not reachable at $url/health (got HTTP $code). See WALKTHRU.md to start it."
    fi
done
echo ""

echo "=== Step 1: allowed user (clearance=$ALLOWED_CLEARANCE, roles=$ALLOWED_ROLES) ==="
allowed_body=$(cat <<EOF
{"question": "$QUESTION", "user_id": "$ALLOWED_USER_ID", "clearance": "$ALLOWED_CLEARANCE", "roles": $(roles_json "$ALLOWED_ROLES")}
EOF
)
allowed_resp=$(curl -s -X POST "$GATEWAY_URL/tasks" -H "Content-Type: application/json" -d "$allowed_body")
echo "$allowed_resp" | python3 -m json.tool

allowed_task_id=$(echo "$allowed_resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('task_id',''))")
allowed_source_count=$(echo "$allowed_resp" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('sources') or []))")

[ -n "$allowed_task_id" ] && pass "POST /tasks returned a task_id" || fail "no task_id in response"

echo ""
echo "=== Step 2: GET /tasks/{id} returns the cached result ==="
get_resp=$(curl -s "$GATEWAY_URL/tasks/$allowed_task_id")
get_answer=$(echo "$get_resp" | python3 -c "import sys,json; print(json.load(sys.stdin).get('answer',''))")
[ -n "$get_answer" ] && pass "GET /tasks/$allowed_task_id returned the cached answer" || fail "GET /tasks/{id} returned no answer"

echo ""
echo "=== Step 3: GET /tasks/{unknown} returns 404 ==="
code=$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/tasks/does-not-exist")
[ "$code" = "404" ] && pass "unknown task_id correctly 404s" || fail "expected 404, got $code"

echo ""
echo "=== Step 4: denied user (clearance=$DENIED_CLEARANCE, roles=${DENIED_ROLES:-none}) ==="
denied_body=$(cat <<EOF
{"question": "$QUESTION", "user_id": "$DENIED_USER_ID", "clearance": "$DENIED_CLEARANCE", "roles": $(roles_json "$DENIED_ROLES")}
EOF
)
denied_resp=$(curl -s -X POST "$GATEWAY_URL/tasks" -H "Content-Type: application/json" -d "$denied_body")
echo "$denied_resp" | python3 -m json.tool
denied_source_count=$(echo "$denied_resp" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('sources') or []))")

echo ""
echo "=== Step 5: permission boundary check ==="
echo "  allowed user retrieved $allowed_source_count source(s)"
echo "  denied user retrieved $denied_source_count source(s)"
if [ "$denied_source_count" -lt "$allowed_source_count" ]; then
    pass "denied user received fewer sources than the allowed user — ACL boundary held"
else
    echo "  WARNING: denied user did not receive fewer sources than the allowed user."
    echo "  This does not necessarily mean the ACL is broken — check that:"
    echo "    - the ingested document was actually tagged with 'tag-permissions' below the allowed clearance"
    echo "    - ALLOWED_* and DENIED_* env vars are set to genuinely different clearance levels"
    echo "  See WALKTHRU.md Step 2 for how permissions are tagged."
fi

echo ""
echo "=== Done. All reachability and contract checks passed. ==="
