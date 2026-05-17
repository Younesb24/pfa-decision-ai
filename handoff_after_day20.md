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
card + one-pager + MAPE fix, blog post, 25-slide deck) shipped this
session on `claude/beautiful-sutherland-12a3e6`. Pushed to `origin`; PR
not yet opened.

## 2. Current Repository State

- **Active branch:** `claude/beautiful-sutherland-12a3e6`.
- **HEAD:** `469d924 docs(day20): 25-slide soutenance deck (Marp
  source) + render guide`.
- **Tracking:** up to date with
  `origin/claude/beautiful-sutherland-12a3e6` (already pushed by user).
- **Working tree:** clean. No staged / unstaged / untracked files.
- **`main` locally:** `1acc160 Merge pull request #2 from
  Younesb24/docs/handoff`. Five commits ahead on this branch waiting on
  PR #3.
- **PR context:** [PR #1](https://github.com/Younesb24/pfa-decision-ai/pull/1)
  (Days 10–15) and [PR #2](https://github.com/Younesb24/pfa-decision-ai/pull/2)
  (Day-15 handoff doc) are merged into `main`. PR #3 (Days 16–20) is
  **not yet opened** — handoff §9 has the exact `gh pr create` command.
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
- API on `:8000` — health, auth/login + me, KPIs, insights, replay (now
  with `POST /replay/tick` + token), governance (analyst+), act (ops+),
  data-health (analyst+), ingest (ops+).
- Dashboard on `:3000` — `/`, `/data-health`, `/ingest`, `/login`.
- **118 pytest tests pass** in `api/` (was 114; +4 replay-tick contract
  tests added this session).
- **8 pytest tests pass** in `ml/tests/` (new: pin the safe-MAPE /
  sMAPE helpers).
- `python -m ruff check api ml scripts` clean.
- CI green on `main` from PR #1 + #2.

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
- **No `ANTHROPIC_API_KEY` in `api/.env`** — agent runs in offline
  template fallback. Set the key before recording the Loom.
- **Local `main` is stale only relative to `origin/main` after each
  merge** — currently in sync because the user pushed and merged PRs
  #1 and #2. After PR #3 lands, repeat `git fetch && git pull` on
  `main` before branching for further work.
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

## 4. Files Actively Edited (this session)

### Code
- `api/routers/replay.py` — added token verification + `POST
  /replay/tick`.
- `api/tests/test_app_smoke.py` — 4 new replay-tick contract tests.
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

## 5. Commands Run

### Worked
- `python -m pytest -x --tb=short -q` (from `api/`) → **118 passed**.
- `python -m pytest tests/ -x --tb=short -q` (from `ml/`) → **8
  passed**.
- `python -m ruff check api ml scripts` → all checks passed.
- `python -m ruff check api/routers/replay.py
  api/tests/test_app_smoke.py` → all checks passed.
- `git add … && git commit -m "..."` × 5 (Days 16, 17, 18, 19, 20).
  All commits on `claude/beautiful-sutherland-12a3e6`.
- `git status`, `git log`, `git diff` for inspection.
- `du -sh .[!.]* *` in repo root → identified 3.4 GB of regenerable
  junk (worktrees, `node_modules`, `.next`).
- **User-run:** `git push -u origin claude/beautiful-sutherland-12a3e6`
  before this handoff was written. `origin/claude/beautiful-
  sutherland-12a3e6` is now at HEAD.

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
- **`ANTHROPIC_API_KEY` absent on the production task.** Agent runs in
  template fallback — fine for tests, off-message for the Loom. Set
  before recording.
- **Forecast MAPE / late-delivery F1** — known weaknesses, but no
  longer hidden. Disclosed in `docs/model_card.md`; metric bug fix is
  pinned by `ml/tests/test_forecast_metrics.py`. Not blockers; "ack in
  the model card, acknowledge in the slides."
- **`PR #3` not opened.** Branch is pushed; user must run `gh pr
  create` per §9.

## 8. Next Steps

In order. Each step has a checklist of pass/fail in §10.

1. **Open PR #3** (Days 16-20). Exact command in §9. Wait for CI to go
   green (Python + dbt + Frontend jobs). Merge into `main`.
2. **Decide repo cleanup scope** — full prune of stale worktrees +
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

Run from a fresh PowerShell at the **main repo path**
(`C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai`), not
from a worktree.

```powershell
# 1. Open PR #3 — branch is already pushed.
gh pr create --base main --head claude/beautiful-sutherland-12a3e6 `
  --title "Days 16-20 — ADR-006, deploy runbook, demo script, model card, blog, deck" `
  --body @'
## Summary
- Day 16 — ADR-006 (AWS primary, Render kill-switch), terraform/eventbridge.tf fixed to use aws_cloudwatch_event_api_destination, POST /api/v1/replay/tick with X-Replay-Token auth, docs/day16_deploy_runbook.md.
- Day 17 — docs/demo_script.md (3-min Loom, OTIF crisis spine).
- Day 18 — README hero + 7-surfaces grid + Loom/live-URL placeholders, docs/one_pager.md (Pandoc A4 source), docs/model_card.md (honest disclosure on F1 + MAPE bug).
- Day 18 bonus — ml/train_forecast.py MAPE eval bug fixed (floored MAPE + sMAPE + MAE); 8 regression tests in ml/tests/test_forecast_metrics.py pin the helpers.
- Day 19 — docs/blog/why_your_llm_should_never_calculate.md (~1300 words).
- Day 20 — docs/deck/soutenance.md (25-slide Marp deck with speaker notes + per-slide timing budgets) + render guide.

## Test plan
- [x] python -m pytest -x in api/ -> 118 passed (was 114, +4 replay-tick contract tests)
- [x] python -m pytest -x in ml/  -> 8 passed (new MAPE/sMAPE helpers)
- [x] python -m ruff check api ml scripts -> clean
- [ ] terraform fmt && terraform validate in terraform/ (no Terraform CLI in dev sandbox)
- [ ] npx marp render docs/deck/soutenance.md -> soutenance.pdf
- [ ] pandoc docs/one_pager.md -> soutenance.pdf
- [ ] Replace YOUR-LOOM-ID and YOUR-PUBLIC-URL placeholders across README.md, docs/one_pager.md, docs/blog/why_your_llm_should_never_calculate.md, docs/deck/soutenance.md once the Loom and deploy are live.
'@
```

After PR #3 merges, sync local `main`:

```powershell
cd C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai
git fetch origin
git checkout main
git pull --ff-only origin main
git log --oneline -5
```

To verify the stack still boots locally before Day-16 deploy:

```powershell
# Terminal 1
cd C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai\api
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2
cd C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai\dashboard
npm run dev
```

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
- [ ] **No secrets** in any committed file (`api/.env`, the new
      `replay_tick_token` and `jwt_secret` vars, `ANTHROPIC_API_KEY`).
      Verified by `git grep -nE "(sk-|AKIA|password\s*=\s*['\"])"` on
      the current tree.

When every box above is checked, the project is defense-ready.
