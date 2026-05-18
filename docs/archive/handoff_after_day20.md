# Handoff

> **For the next session — read this first, top to bottom.**
> The hard operator rules from the previous handoff still apply: **no
> Claude / Anthropic attribution in commits or PR bodies**, **never
> `git push` / `gh pr create` / merges — the user runs those**, never
> edit git config / remotes / hooks, never `--no-verify`. The repo was
> once deleted and recreated over an AI-attribution slip. Do not repeat.

## 1. Project Goal

**PFA Decision AI** — an OODA-loop decision-support tool for a
marketplace ops persona, built on the Olist Brazilian e-commerce
dataset. Stack locked in [CLAUDE.md](CLAUDE.md): PostgreSQL + DuckDB +
dbt + FastAPI + Next.js 14 + Anthropic Claude + scikit-learn / XGBoost
+ Holt-Winters + Docker. The defense (soutenance) target is a working
MVP with a public URL and a 3-minute Loom, defensible end-to-end to a
jury.

Days 1–15 (foundation, auth, ingest, Docker, Terraform skeleton) shipped
via PR #1. Days 16–20 (deploy + ADR-006, Loom script, README + model
card + one-pager + MAPE fix, blog post, 25-slide deck) shipped via
**PR #4 — merged**. Two follow-up fixes (OpenAI tool-loop translation,
TLS escape-hatch docs) landed afterwards on `claude/beautiful-sutherland-12a3e6`
and have been pushed to `origin`. The LLM-powered Decision Brief on the
dashboard now produces real briefings end-to-end against OpenAI gpt-4o.

## 2. Current Repository State

- **Active branch:** `claude/beautiful-sutherland-12a3e6`.
- **HEAD:** `bc1925b docs(env): document LLM_INSECURE_TLS / LLM_CA_BUNDLE
  escape hatches`.
- **Tracking:** local is **2 commits ahead** of
  `origin/claude/beautiful-sutherland-12a3e6` until the user runs
  `git push`.
- **Working tree:** clean. No staged / unstaged / untracked files.
- **`main` locally on the main repo path:** stale at `1acc160 Merge pull
  request #2 from Younesb24/docs/handoff` (or older — the main repo
  worktree is checked out on `docs/handoff` at `3da4f47`, see §6).
  Run `git fetch && git checkout main && git pull` on the main repo path
  before branching off main again.
- **PR context:**
  - [PR #1](https://github.com/Younesb24/pfa-decision-ai/pull/1) (Days
    10–15) — merged.
  - [PR #2](https://github.com/Younesb24/pfa-decision-ai/pull/2)
    (Day-15 handoff doc) — merged.
  - [PR #4](https://github.com/Younesb24/pfa-decision-ai/pull/4)
    (Days 16–20 + Day-20 handoff doc) — **merged**.
  - **No open PR currently.** The two follow-up fix commits below have
    been pushed; opening another PR is optional, the work is local-bug
    territory and can ride the next batch.
- **Other worktrees on disk** (do not touch unless asked):
  - `.claude/worktrees/busy-wiles-43401b` — PR #1 worktree, branch
    already merged into `main`. 637 MB on disk, mostly
    `dashboard/node_modules` + `.next`.
  - `.claude/worktrees/nostalgic-kirch-eb3521` — `claude/nostalgic-
    kirch-eb3521`, behind `origin/main` by 11. 821 MB on disk.
  - `.claude/worktrees/vigilant-bartik-fbf40f` — `feat/day7-8-9-agent-
    and-data-health`, remote-branch already gone. 1.1 GB on disk.

## 3. Current Code State

### Works (verified this session)
- API on `:8000` — 26 routes: health, auth/login + me, KPIs, insights,
  replay (state + tick), governance (analyst+), act (ops+), data-health
  (analyst+), ingest (ops+), ask + ask/agent.
- Dashboard on `:3000` — `/`, `/data-health`, `/ingest`, `/login`.
- **Decision Brief panel works end-to-end** against OpenAI gpt-4o.
  Tool calls (`get_kpi_timeseries`, `get_anomalies`) succeed, narrative
  is generated, evidence cites `gold.agg_daily_ops_kpi`, brief returns
  via `POST /api/v1/ask/agent`.
- **118 pytest tests pass** in `api/`. **8 pytest tests pass** in
  `ml/tests/`. `python -m ruff check api ml scripts` clean.
- CI green on `main` from PR #1 / #2 / #4.

### Shipped this session (Days 16-20)
- `docs/adr/006-aws-over-render.md` — primary deploy is AWS; Render is
  the 12-hour kill-switch.
- `docs/day16_deploy_runbook.md` — image build → terraform apply → RDS
  seed → Vercel proxy → replay-tick enable. Includes common first-
  deploy failure table and Render fallback shape.
- `terraform/eventbridge.tf` — replaced placeholder `target.arn =
  aws_lb.main.arn` with `aws_cloudwatch_event_api_destination` +
  connection + invoke IAM role. Schedule defaults to off; flip on after
  the API target group is healthy.
- `terraform/variables.tf` + `terraform.dev.tfvars` — new
  `replay_tick_token` (sensitive), `enable_replay_schedule` default
  flipped to `false`.
- `api/routers/replay.py` — `POST /api/v1/replay/tick`. Requires
  `X-Replay-Token` header; missing env returns 503 (fail-closed);
  wrong header returns 401. Wraps `scripts.replay_simulator.tick()`.
- `api/tests/test_app_smoke.py` — 4 new tests covering the contract.
- `docs/demo_script.md` — 3-minute Loom script. Beats, lines to say,
  lines to avoid, recovery plan if a take goes wrong.
- `README.md` — Demo section (Loom + live-URL + hero-image
  placeholders), 7-surfaces grid, honest-disclosure block, ADR-006/
  007/008 entries, updated ML status row to point at the model card.
- `docs/one_pager.md` — Pandoc-ready A4 source for the executive
  one-pager.
- `docs/model_card.md` — late-delivery classifier (ROC-AUC 0.82, F1
  0.38 disclosed, threshold = 0.30 recommended in UI); forecast (sMAPE
  ~13%, MAPE ~14% floored, MAE ~22), with the 259 262 % postmortem;
  LLM governance contract (audit_log row before render).
- `ml/train_forecast.py` — replaced plain MAPE with `_safe_mape`
  (denominator floored at 1 order) + `_smape` + MAE. Headline metric
  changed to sMAPE. JSON artifact now carries all three.
- `ml/tests/test_forecast_metrics.py` — 8 tests on the helpers
  (zero-actuals don't explode, sMAPE symmetric + bounded, perfect
  prediction is zero).
- `docs/blog/why_your_llm_should_never_calculate.md` — ~1300-word
  post; thesis is the same rule that runs through the codebase
  (LLM = narrator, never calculator).
- `docs/deck/soutenance.md` — 25-slide Marp deck, OTIF crisis spine,
  per-slide timing budget in HTML comments.
- `docs/deck/README.md` — Marp render command + dry-run guide.
- `docs/img/.gitkeep` — directory placeholder for the hero screenshot.

### Incomplete / placeholders to replace
- **`YOUR-LOOM-ID`** in `README.md`, `docs/one_pager.md`,
  `docs/blog/...`, `docs/deck/soutenance.md`. Replace once the Loom is
  recorded.
- **`YOUR-PUBLIC-URL`** in the same four files. Replace once a public
  URL exists (AWS ALB DNS / Vercel / Render).
- **`docs/img/hero.png`** — currently just `.gitkeep`. Add a real
  dashboard screenshot once the live URL is up.
- **Live deploy** — never apply'd. `terraform/` skeleton is ready but
  no AWS account in this environment.
- **Loom recording** — script ready, recording is the user's job.
- **`docs/deck/soutenance.pdf`** — render with Marp before the
  defense; not in git (generated artifact).
- **`docs/one_pager.pdf`** — render with Pandoc before the defense.

### Broken / known issues
- **`governance.users` table doesn't exist on the local Postgres** —
  `POST /api/v1/auth/login` 500s with `psycopg2.errors.UndefinedTable`.
  Run `make auth-init` (which executes `scripts/users_migration.sql`
  + `scripts/seed_users.py`) once. Not blocking the LLM demo because
  `/ask/agent` isn't auth-gated.
- **OpenAI behind corporate TLS chain** — Windows schannel cannot do
  certificate revocation check (`CRYPT_E_NO_REVOCATION_CHECK`), and the
  openai SDK's certifi bundle won't validate either. Documented escape
  hatch: `LLM_INSECURE_TLS=1` in `api/.env` (already set on this
  machine; documented in `.env.example`). **Never** set this in prod.
  Better long-term fix: export the corporate root cert and set
  `LLM_CA_BUNDLE=/path/to/corporate-root.pem` instead.
- **`ANTHROPIC_API_KEY` not yet set on this machine** — agent runs on
  OpenAI gpt-4o. Set the Anthropic key in `api/.env` before recording
  the Loom (Anthropic Sonnet is the canonical provider per ADR-001
  and CLAUDE.md).
- **Stale local `main`** — the main repo path at
  `C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai` is
  checked out on `docs/handoff` at `3da4f47` (pre-Day-10). Working
  tree there shows ~30 files as "untracked" because they're on
  newer commits the local checkout never pulled. Run
  `git fetch && git checkout main && git pull` from that path.
- **`openapi-typescript`** — removed from `dashboard/package.json`
  during Day 11 because corporate TLS chain blocked `npm install`.
  Re-add when the registry trusts cleanly. Tracked in §6.
- **No Docker locally** in the dev sandbox — Day-14 Dockerfiles and
  `docker-compose.prod.yml` were checked in but never built or run.
  Expect debugging on the first `make prod-up`.
- **No Terraform CLI locally** — `terraform fmt` / `validate` not run
  on the Day-15 files or on the Day-16 EventBridge fix. Run before the
  first apply.
- **Replay `tick()` import path** — `api/routers/replay.py` adds the
  repo root to `sys.path` so `from scripts.replay_simulator import
  tick` resolves. Works in dev and in the Docker image because the
  Dockerfile copies the full tree. Verify on first prod deploy.
- **3 stale worktrees + dashboard build artifacts on disk** —
  ~3.4 GB of regenerable junk. Cleanup deliberately paused on the
  user's instruction (2026-05-17); the plan is still in §7.

## 4. Files Actively Edited (this session)

### Code
- `api/routers/replay.py` — added token verification + `POST
  /replay/tick`.
- `api/tests/test_app_smoke.py` — 4 new replay-tick contract tests.
- `api/llm_client.py` — new `_msgs_to_openai()` translator (symmetric
  to the Anthropic one). Internal neutral assistant tool_calls were
  being sent straight to OpenAI's SDK without the required
  `type="function"` + nested `"function"` wrapper, so the second
  agent-loop iteration always 400'd. Translator JSON-stringifies
  arguments and reshapes per-tool-call.
- `api/agents/decision_analyst.py` — `_build_brief` now coerces
  unknown `action_type` values (model said `"meeting"`) to `review`
  and unknown `urgency` to `medium`, so a single vocabulary slip
  from the LLM doesn't 500 the whole brief.
- `ml/train_forecast.py` — safe-MAPE + sMAPE + MAE helpers, updated
  metrics dict shape, headline switched to sMAPE.
- `ml/tests/__init__.py` (new) + `ml/tests/test_forecast_metrics.py`
  (new) — 8 helper-level regression tests.

### Infra
- `terraform/eventbridge.tf` — proper API-destination + connection +
  IAM invoke role.
- `terraform/variables.tf` — `replay_tick_token` var,
  `enable_replay_schedule` default `false`.
- `terraform/terraform.dev.tfvars` — same defaults, comment updated.

### Docs
- `README.md` — Demo + 7-surfaces + honest-disclosure + ADR links.
- `docs/adr/006-aws-over-render.md` (new).
- `docs/day16_deploy_runbook.md` (new).
- `docs/demo_script.md` (new).
- `docs/one_pager.md` (new).
- `docs/model_card.md` (new).
- `docs/blog/why_your_llm_should_never_calculate.md` (new).
- `docs/deck/soutenance.md` (new) + `docs/deck/README.md` (new).
- `docs/img/.gitkeep` (new).
- `handoff_after_day20.md` (new — this doc).
- `.env.example` — documents `LLM_INSECURE_TLS` and `LLM_CA_BUNDLE`
  escape hatches with a "never set in prod" warning.

## 5. Commands Run

### Worked
- `python -m pytest -x --tb=short -q` (from `api/`) → **118 passed**.
- `python -m pytest tests/ -x --tb=short -q` (from `ml/`) → **8
  passed**.
- `python -m ruff check api ml scripts` → all checks passed.
- `git add … && git commit -m "..."` × 7 (Days 16, 17, 18, 19, 20 +
  post-Day-20 handoff + LLM fix-up + env-doc). All commits on
  `claude/beautiful-sutherland-12a3e6`.
- `wmic process where "name='python.exe'" get ProcessId,CommandLine` —
  found a zombie uvicorn worker (PID 34392, parent_pid=13048) holding
  `:8000`. `taskkill /F /PID 34392` released the socket.
- Diagnosis loop on the "Decision Brief — LLM provider not configured"
  bug — three causal layers, fixed in order:
  1. Wrong uvicorn was serving (pre-Day-10 main.py). Killed the
     zombie worker; restarted from this worktree.
  2. OpenAI SDK "Connection error" → corporate TLS chain. Added
     `LLM_INSECURE_TLS=1` to `api/.env`; documented in
     `.env.example`.
  3. OpenAI second-iteration 400 (`Missing required parameter:
     'messages[N].tool_calls[0].type'`) → patched `llm_client.py`
     with `_msgs_to_openai()`.
- Direct `OpenAI(http_client=httpx.Client(verify=False)).chat.completions.create`
  call from Python confirmed `verify=False` works → proved TLS was
  the blocker, not network/key/quota.
- **User-run:** `git push -u origin claude/beautiful-sutherland-12a3e6`
  and `gh pr create` for PR #4.

### Not run (deliberately)
- **`git push`** / **`gh pr create`** / **`git pull`** / **`git
  merge`** — operator-only per §0.
- **Folder cleanup** (`git worktree remove`, `rm -rf .next /
  node_modules`, planning-doc move). User asked to pause this and
  rewrite the handoff first.
- **`terraform init` / `plan` / `apply`** — no Terraform CLI locally;
  no AWS creds.
- **`docker build`** — no Docker locally.
- **`npx marp …`** — no Marp installed; deck source ships, PDF is
  rendered before the defense.
- **`pandoc …`** — same for the one-pager PDF.

### Notes from prior sessions (still relevant)
- `git worktree move .claude/worktrees/<name> worktrees/<name>` fails
  on Windows with "Permission denied" because the active Claude Code
  session holds the directory open. Workaround: close the session and
  move from PowerShell, or wait for anthropics/claude-code#28242.
- `npm install --save-dev openapi-typescript` fails with
  `UNABLE_TO_VERIFY_LEAF_SIGNATURE` on the corporate TLS chain.

## 6. Failed Attempts / Do Not Repeat

- **Do not** assume `Stop-Process -Id <reloader-pid> -Force` kills the
  child uvicorn worker on Windows — it does not. The child becomes
  parentless and keeps holding `:8000`. The reliable kill is via
  `wmic process where ... get ProcessId,CommandLine`, find the
  `multiprocessing.spawn ... parent_pid=<dead>` child, then
  `taskkill /F /PID <child>`. Or run uvicorn without `--reload` while
  diagnosing port issues.
- **Do not** send the internal neutral `tool_calls` shape directly to
  OpenAI's SDK. OpenAI requires
  `{"id","type":"function","function":{"name","arguments":"<json-string>"}}`.
  The neutral `{"id","name","arguments":{...}}` shape produces
  `Missing required parameter: 'messages[N].tool_calls[0].type'`.
  Use `_msgs_to_openai()` in `api/llm_client.py`.
- **Do not** trust the OpenAI SDK's bare `"Connection error"` string —
  it hides the underlying TLS / network exception. Reproduce the call
  with `httpx.Client(verify=False)` to confirm a TLS-interception
  cause before blaming the key or quota.
- **Do not** strip the `LLM_INSECURE_TLS` knob from `api/llm_client.py`
  "because it's insecure." The codebase documents it as local-dev-only
  in `.env.example`; production runs in ECS where certifi works out of
  the box and the knob is irrelevant.
- **Do not** edit `RecommendedAction.action_type` to be a free-form
  string. The enum constraint protects downstream `/act/*` routers
  from acting on a model hallucination. Instead, coerce unknown values
  to `review` in `_build_brief` — already done.
- **Do not** add `Co-Authored-By: Claude`, "🤖 Generated with Claude
  Code", or any AI attribution to commits or PR bodies. The repo was
  deleted and recreated once over this. Hard rule.
- **Do not** `git push`, `git push --force`, `gh pr create`,
  `gh pr merge`, `git remote set-url`, `git reset --hard origin/*`, or
  pass `--no-verify`. The user runs every network and destructive
  operation.
- **Do not** delete worktrees or planning docs without explicit
  confirmation. User asked to pause that step (2026-05-17).
- **Do not** branch off local `main` without `git fetch && git pull`
  first — stale local `main` will drop merged PRs.
- **Do not** import `EmailStr` from pydantic without
  `pydantic[email]` installed (not in `requirements.txt`). Use plain
  `str` with `Field(min_length=...)` — see `api/routers/auth.py`.
- **Do not** add devDependencies to `dashboard/package.json` without
  updating `package-lock.json`. CI runs `npm ci` which is strict; a
  phantom dep kills the Frontend job.
- **Do not** put `0` / `1` in the boolean-token set in
  `api/services/profiler.py` — they shadow ints; the regression test
  exists for a reason.
- **Do not** call `useSearchParams()` outside a `<Suspense>` boundary
  on a Next page that prerenders. CI build catches it.
- **Do not** assume the worktree's `package-lock.json` reflects local
  `node_modules` — the background `npm install` in this env hits the
  same TLS issue as the foreground.
- **Do not** try to relocate Claude Code worktrees out of
  `.claude/worktrees/` from inside an active session — Windows holds
  the directory open.
- **Do not** mass-rewrite git history (rebase / squash / amend
  published commits) to "clean up" the AI-flavor of older messages.
  History is honest. Cleanup, if it happens, is forward-only.

## 7. Current Blockers

- **Repo cleanup is pending user decision.** 3.4 GB of regenerable
  junk (stale worktrees, `dashboard/.next`, `dashboard/node_modules`,
  `.ruff_cache`, `.pytest_cache`) is on disk. Also 6 planning .md files
  at repo root (`EXECUTION_HANDOFF.md`, `PFA_V3_*.md`,
  `PFA_LEVERAGE_PLAYBOOK.md`, `pfa_master_plan.md`,
  `PFA_FOLDER_EXPLAINED.md`) that a jury sees before any code. User
  paused this step on 2026-05-17.
- **No public URL.** Day-16 deploy never executed. Either AWS via
  Terraform (`docs/day16_deploy_runbook.md`) or Render kill-switch (per
  ADR-006).
- **No Loom recording.** Script is ready (`docs/demo_script.md`),
  recording is the user's job.
- **No real hero screenshot.** `docs/img/hero.png` is a placeholder.
- **`ANTHROPIC_API_KEY` absent on this machine.** Agent runs on
  OpenAI gpt-4o currently. Off-message for the Loom (the deck and
  blog post say "Claude Sonnet"). Set the Anthropic key in
  `api/.env`, restart uvicorn, re-test before recording.
- **`governance.users` migration not run on this machine.** Login
  endpoint 500s. Run `make auth-init`. Not blocking the LLM demo
  because `/ask/agent` isn't gated.
- **Forecast MAPE / late-delivery F1** — known weaknesses, but no
  longer hidden. Disclosed in `docs/model_card.md`; metric bug fix is
  pinned by `ml/tests/test_forecast_metrics.py`. Not blockers; "ack in
  the model card, acknowledge in the slides."
- **Two follow-up commits not yet pushed.** `2ff4a76` (LLM fix-up)
  and `bc1925b` (env docs) sit on `claude/beautiful-sutherland-12a3e6`
  ahead of `origin`. Push with `git push`. PR is optional.

## 8. Next Steps

In order. Each step has a checklist of pass/fail in §10.

1. **Push the two fix-up commits.** `git push` from the worktree.
   PR is optional — the work is local-bug territory. If batching
   another PR, the existing PR-body template in the prior §9 works.
2. **Seed `governance.users`.** `make auth-init` from the main repo
   path once it's synced — see step 4. Login then works at
   `ops@pfa.local / ops123`.
3. **Set `ANTHROPIC_API_KEY` in `api/.env`** and restart uvicorn so
   the demo runs on the canonical Claude path (matches the deck
   narrative). Verify with one `/ask/agent` call; provider should
   come back as `"anthropic"`.
4. **Sync local `main`** on the main repo path:
   `git fetch && git checkout main && git pull --ff-only origin main`.
   The current local HEAD is far behind merged work.
5. **Decide repo cleanup scope** — full prune of stale worktrees +
   `.next` + `node_modules` + tool caches (3.4 GB freed) vs. caches
   only (1.3 GB). Move the 6 root-level planning .md files into
   `docs/planning/` (or delete from working tree, keep in git
   history). Both pending user confirmation.
3. **Day-16 deploy.** Follow `docs/day16_deploy_runbook.md`:
   bootstrap S3 + DynamoDB backend → build & push 3 Docker images →
   `terraform init` → `workspace new dev` → `plan` → `apply` → seed
   RDS → smoke-test public URL → enable replay schedule. **Kill-
   switch:** if Day 16 is >12 h over budget, ship to Render instead
   (see ADR-006).
4. **Record the Loom.** Script in `docs/demo_script.md`. 2-take max.
   Update `YOUR-LOOM-ID` placeholders in 4 files (README, one_pager,
   blog post, deck).
5. **Take the hero screenshot.** Save as `docs/img/hero.png`. The
   README and the deck reference it.
6. **Render the PDFs.** `pandoc docs/one_pager.md -o docs/one_pager.pdf
   --pdf-engine=xelatex` and `npx @marp-team/marp-cli
   docs/deck/soutenance.md -o docs/deck/soutenance.pdf`.
7. **Dry-run the deck**, timed. Hard cap 25 minutes including a 60-90s
   Q&A bumper. If it overruns, cut slide 17 (text-to-SQL safety) — it
   subsumes into a Q&A answer.
8. **Cross-post the blog.** LinkedIn + Medium. Use the canonical URL
   already in the front-matter.

## 9. Exact Next Commands

Run from PowerShell. Step 0 is the immediate push of the fix-up
commits; the rest are from the **main repo path**
(`C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai`).

```powershell
# 0. Push the two fix-up commits sitting on claude/beautiful-sutherland-12a3e6.
#    From the worktree:
git push
```

Optional PR for the fix-up commits (skip if batching with later work):

```powershell
gh pr create --base main --head claude/beautiful-sutherland-12a3e6 `
  --title "fix(llm): OpenAI tool-loop + TLS escape-hatch docs" `
  --body @'
## Summary
- Fix complete_with_tools (OpenAI branch) — translate the internal neutral tool_calls format to OpenAI's required {type:"function", function:{...}} shape. Previously the second loop iteration always 400'd with "Missing required parameter: messages[N].tool_calls[0].type".
- Make _build_brief schema-tolerant — coerce unknown action_type/urgency values (model said "meeting") to safe defaults so a single LLM vocabulary slip doesn't 500 the brief.
- Document LLM_INSECURE_TLS and LLM_CA_BUNDLE in .env.example with a prod-warning. The escape hatches were already wired in api/llm_client.py but undocumented.

## Test plan
- [x] python -m pytest -x in api/ -> 118 passed
- [x] python -m ruff check api ml scripts -> clean
- [x] POST /api/v1/ask/agent end-to-end returns full DecisionBrief with real Gold-table evidence + LLM narrative.
'@
```

Sync local `main` on the main repo path (it's stuck at `3da4f47` /
`docs/handoff`):

```powershell
cd C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai
git fetch origin
git checkout main
git pull --ff-only origin main
git log --oneline -5
```

Seed the auth schema so login works:

```powershell
make auth-init
```

Start (or restart) uvicorn from this worktree — **not** from the main
repo path (its `api/main.py` is still pre-Day-10 until you pull
above). Don't use `--reload` while debugging port issues; the worker
child becomes orphaned if the reloader dies:

```powershell
cd C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai\.claude\worktrees\beautiful-sutherland-12a3e6\api
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

If `:8000` is held by a zombie from a previous run:

```powershell
wmic process where "name='python.exe'" get ProcessId,CommandLine | findstr "main:app multiprocessing.spawn"
taskkill /F /PID <PID-from-above>
```

Dashboard:

```powershell
cd C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai\.claude\worktrees\beautiful-sutherland-12a3e6\dashboard
npm run dev
```

Verify the LLM path returns real data (not the "LLM provider not
configured" fallback):

```powershell
curl.exe -s -X POST http://127.0.0.1:8000/api/v1/ask/agent -H "Content-Type: application/json" -d '{\"question\":\"What is the current OTIF rate trend?\"}'
```

Expected: a JSON body with `"provider": "anthropic"` (or `"openai"`),
non-empty `evidence`, and a `chart_hint.data` array with ~30 OTIF
rows. If `what_happened` starts with "LLM provider not configured"
or "Agent error: Connection error", see §3 / §6.

For Day-16 first apply (read `terraform/README.md` and
`docs/day16_deploy_runbook.md` first):

```powershell
cd C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai\terraform
terraform init
terraform workspace new dev
terraform plan -var-file=terraform.dev.tfvars
```

For the deck and one-pager (renders skip on every commit; do before
defense):

```powershell
cd C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai
npx @marp-team/marp-cli docs/deck/soutenance.md -o docs/deck/soutenance.pdf
pandoc docs/one_pager.md -o docs/one_pager.pdf --pdf-engine=xelatex
```

## 10. Definition of Done

The defense is ready when all of the following are true:

- [ ] **Public URL** is live (AWS ALB DNS, Vercel, or Render — does
      not matter which).
- [ ] **`POST /api/v1/auth/login`** succeeds from the public URL with
      one of the seeded demo users (`ops@pfa.local / ops123`).
- [ ] **One full OODA-loop walkthrough** (anomaly → narrative →
      recommendation → human review) is reproducible from the public
      URL.
- [ ] **3-minute Loom** recorded, public, embedded in `README.md` with
      a real `loom.com/share/...` link.
- [ ] **Hero screenshot** at `docs/img/hero.png`.
- [ ] **One-page PDF** rendered from `docs/one_pager.md`.
- [ ] **25-slide deck PDF** rendered from `docs/deck/soutenance.md`,
      dry-run timed under 25 minutes including Q&A bumper.
- [ ] **ADR-006** is up to date with whichever host won.
- [ ] **CI on `main`** is green.
- [ ] **Honest disclosure** lives in `docs/model_card.md` and the
      model-card section of `README.md` — not hidden, not buried.
- [ ] **`/api/v1/ask/agent` returns a real DecisionBrief** on the
      public URL — `provider` is `anthropic` (or `openai`), `evidence`
      cites `gold.*`, and `chart_hint.data` is non-empty. No "LLM
      provider not configured" / "Agent error: Connection error".
- [ ] **No secrets** in any committed file (`api/.env`, the new
      `replay_tick_token` and `jwt_secret` vars, `ANTHROPIC_API_KEY`).
      Verified by `git grep -nE "(sk-|AKIA|password\s*=\s*['\"])"` on
      the current tree.

When every box above is checked, the project is defense-ready.
