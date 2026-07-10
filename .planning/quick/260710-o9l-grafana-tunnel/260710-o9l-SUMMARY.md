---
phase: quick-260710-o9l
plan: 01
subsystem: infra/routing
status: complete
tags: [nginx, caddy, grafana, tunnel, routing-bug]
dependency-graph:
  requires: [BONUS-B-GRAFANA (260710-nc0), BONUS-A-BATCH]
  provides: [BONUS-A-BATCH-tunnel, BONUS-B-GRAFANA-tunnel]
  affects: [deploy/local/nginx-tunnel.conf, deploy/caddy/Caddyfile, docker-compose.yml]
tech-stack:
  added: []
  patterns:
    - "nginx per-request upstream re-resolve (resolver 127.0.0.11 + set $var) reused for the new /grafana/ location"
    - "Grafana GF_SERVER_SERVE_FROM_SUB_PATH + relative-asset base-href makes sub-path hosting Host-agnostic"
key-files:
  created: []
  modified:
    - docker-compose.yml
    - deploy/local/nginx-tunnel.conf
    - deploy/caddy/Caddyfile
    - README.md
decisions:
  - "api GET /metrics stays off both public entrypoints (tunnel + prod Caddy): unauthenticated aggregate data, no functional need to publish; Prometheus scrapes it internally, curated Grafana dashboard is the public metrics surface"
  - "No depends_on: grafana on the proxy service — grafana is profile-gated (metrics), a non-profiled service depending on it would break plain docker compose up -d"
  - "location /analyze prefix match (not location = /analyze) — future /analyze-* endpoints are covered automatically"
metrics:
  duration: "~35 min"
  completed: 2026-07-10
---

# Quick Task 260710-o9l: Grafana behind the tunnel proxy + fix /analyze-batch routing Summary

Exposed the Grafana dashboard at `/grafana/` through the single-port tunnel proxy and fixed a
confirmed routing bug where `POST /analyze-batch` fell through to OpenWebUI's catch-all (405)
instead of reaching the api, mirroring both fixes in the prod Caddy config and documenting
everything honestly in README with numbers measured live against the running stack.

## What Was Built

**Task 1 — Grafana at `/grafana/` through the tunnel.**
`docker-compose.yml`: added `GF_SERVER_SERVE_FROM_SUB_PATH=true` and
`GF_SERVER_ROOT_URL=http://localhost:3001/grafana/` to the `grafana` service, with a comment
explaining the root_url host is cosmetic (Grafana emits `<base href="/grafana/">` + relative
asset paths, so rendering is Host-agnostic; the tunnel never routes bare `/` to Grafana).
`deploy/local/nginx-tunnel.conf`: added `set $grafana_upstream http://grafana:3000;` (same
re-resolve pattern as the existing api/openwebui upstreams) and a `location /grafana/` block
with the same websocket/header set as `location /` (Grafana Live uses websockets). No
`depends_on: grafana` was added to `proxy` — grafana is profile-gated (`metrics`), and gluing a
non-profiled service to a profiled one would break plain `docker compose up -d`.

**Task 2 — `/analyze*` routing fix (nginx + Caddy).**
Root cause (measured): `location = /analyze` in nginx-tunnel.conf is an EXACT match, so
`/analyze-batch` missed it and fell through to the OpenWebUI catch-all, returning 405. Changed
to a PREFIX `location /analyze` covering `/analyze`, `/analyze-batch`, and any future
`/analyze-*` in one line — safe because OpenWebUI has no route beginning with `/analyze`.
Mirrored the same bug/fix in `deploy/caddy/Caddyfile`: the `@api` matcher's
`/analyze /analyze/*` tokens became a single `/analyze*` glob. Explicitly decided NOT to add a
`/metrics` location — the decision and rationale are documented as a comment in both nginx and
README (api `GET /metrics` stays internal-only; Prometheus scrapes it on the compose network;
the curated Grafana dashboard is the public metrics surface).

**Task 3 — regression + profile-off proof, then README.**
Proved no regression (chat, REST, websockets, `/docs`, `/openapi.json` all intact), proved the
"metrics profile off" path (`docker compose stop prometheus grafana` + plain
`docker compose up -d --force-recreate proxy`: nginx starts clean with zero errors,
`/grafana/` returns 502 instead of crashing nginx at boot), then restored the metrics stack and
updated README.md — Grafana access line changed from bare `:3001` to `:3001/grafana/` (noting
the self-healing 301 redirect), a new line documents the dashboard reachable through the tunnel
at `:8080/grafana/` (and therefore on the live trycloudflare demo), and the Cloudflare Tunnel
section now notes the `/analyze*` family fix and the `/metrics`-stays-private decision. No
existing measured number (WER, latency, RAM) was touched.

## Deviations from Plan

None — plan executed exactly as written. All file paths, decisions, and comment rationale match
the plan's tasks. No Rule 1/2/3 auto-fixes were needed; no Rule 4 architectural questions arose.

## Verification — Observed Live Against the Running Stack

### Task 1 — Grafana sub-path (all from plan's automated verify block, run twice: immediately
after the edit, and again in the final sanity sweep)

| Check | Expected | Observed |
|---|---|---|
| `GET :8080/grafana/api/health` | 200 | **200** |
| `GET :8080/grafana/` HTML contains `<base href="/grafana/">` | yes | **yes** — `<base href="/grafana/"` found |
| Bare `"/public/` refs in that HTML | 0 | **0** |
| A referenced asset (`public/build/grafana.dark.722d809dba5a31f57d49.css`) under `/grafana/public/` | 200 | **200** |
| Foreign `Host: random-name.trycloudflare.com` on `/grafana/api/health` | 200, no redirect | **200, r=** (empty, no redirect) |
| `GET :8080/grafana/api/search?query=MTBank` | lists "MTBank Call Analytics" | **yes** — `{"id":1,"uid":"mtbank-call-analytics","title":"MTBank Call Analytics",...}` |
| `proxy` service has `depends_on: grafana` | absent | **confirmed absent** — `depends_on:` on `proxy` lists only `openwebui`, `api` |
| Bare `http://localhost:3001/` (direct port) | self-heals via 301 | **301 -> `http://localhost:3001/grafana/`** (verified before writing this claim into README) |

### Task 2 — `/analyze*` routing fix

| Check | Expected | Observed |
|---|---|---|
| Baseline (before fix) `POST :8080/analyze-batch {"urls":[]}` | 405 (bug) | **405** — reproduced |
| Baseline `POST :8080/analyze {}` | 400 | **400** |
| After fix: `POST :8080/analyze-batch {"urls":[]}` | 400 (api reached) | **400** |
| After fix: `POST :8080/analyze {}` | 400 (unchanged) | **400** |
| `GET :8080/metrics` body contains `mtbank_calls_total` | must NOT | **not present** (0 matches) |
| `caddy validate --adapter caddyfile` on the edited Caddyfile (via `docker run --rm caddy:2`) | valid | **"Valid configuration"** |

### Task 3 — regression + profile-off + README

| Check | Expected | Observed |
|---|---|---|
| `GET :8080/health` | 200 | **200** |
| `GET :8080/` (OpenWebUI) | 200 | **200** |
| `GET :8080/docs` | 200 | **200** |
| `GET :8080/openapi.json` | 200 | **200** |
| `POST :8080/analyze {"url":"http://files/call_dialog.mp3"}` (real analysis through proxy) | 200 | **200** |
| `docker compose exec -T api pytest -q` | 67 passed | **67 dots, exit code 0** (pytest's own textual "N passed" summary line did not print in this non-tty exec, so pass count was independently confirmed by counting `.` characters in the output: 67, matching the file's own record; exit code 0 confirms no failures/errors) |
| Profile-off: `docker compose stop prometheus grafana` then `docker compose up -d --force-recreate proxy` | nginx starts clean, no errors, no restarts | **`status=running restarts=0`; nginx log shows clean startup ("Configuration complete", 10 worker processes started), zero `[error]`/`[emerg]` lines** |
| `:8080/health`, `:8080/` with metrics profile off | 200, 200 | **200, 200** |
| `:8080/grafana/` with grafana absent | 502 (not a crash) | **502** |
| Metrics stack restored (`docker compose --profile metrics up -d`) + `:8080/grafana/api/health` | 200 | **200** — restored successfully |
| `README.md` contains `localhost:3001/grafana/` | yes | **yes** |
| `README.md` contains `localhost:8080/grafana/` | yes | **yes** |

**Everything specified in the plan's verification block and success criteria was directly
observed — nothing could not be verified.** Groq rate-limiting (429, mentioned as an expected
caveat in the task brief) did not surface during this run: the real `/analyze` call through the
proxy returned a clean 200 within the timeout.

## Final Stack State

All 7 services `Up` at task end (`api`, `files`, `grafana`, `openwebui`, `pipelines`,
`prometheus`, `proxy`), metrics profile restored to the state it was in before this task began.
Working tree is clean except this `.planning/` directory (left for the orchestrator to commit
separately, per instructions).

## Commits

1. `ab36176` — `feat(grafana): expose dashboard at /grafana/ through the tunnel proxy`
   (docker-compose.yml, deploy/local/nginx-tunnel.conf)
2. `3175c25` — `fix(proxy): route the whole /analyze* family, not just the exact path`
   (deploy/local/nginx-tunnel.conf, deploy/caddy/Caddyfile)
3. `201520f` — `docs: document Grafana sub-path and the /analyze* tunnel fix`
   (README.md)

All three commits authored by `ib0gdan` only — no `Co-Authored-By: Claude` trailer, per the
project's hard constraint.

## Self-Check

- `docker-compose.yml` contains `GF_SERVER_SERVE_FROM_SUB_PATH` and `GF_SERVER_ROOT_URL`: **FOUND**
- `deploy/local/nginx-tunnel.conf` contains `location /grafana/` and `location /analyze` (prefix,
  no `=`): **FOUND**
- `deploy/caddy/Caddyfile` contains `/analyze*` glob: **FOUND**
- `README.md` contains both `localhost:3001/grafana/` and `localhost:8080/grafana/`: **FOUND**
- Commit `ab36176` exists in `git log`: **FOUND**
- Commit `3175c25` exists in `git log`: **FOUND**
- Commit `201520f` exists in `git log`: **FOUND**

## Self-Check: PASSED
