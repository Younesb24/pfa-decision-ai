# Handoff

> **For the next Claude session — read this first, top to bottom.**
> Hard rules live in §10. Do not skip §10.

## 0. Operator rules — non-negotiable

These apply to **every turn** of the next session.

1. **NEVER add Claude / Anthropic attribution to anything.** No
   `Co-Authored-By: Claude`, no "🤖 Generated with Claude Code" footers, no
   `Reported-by: Claude`, no mentions in PR bodies. The repo was once
   **deleted and recreated** because of this. If you catch yourself drafting
   a line that contains the word "Claude" in a commit message or PR body,
   delete the line.
2. **Do not push, do not open PRs, do not merge.** The user runs
   `git push`, `gh pr create`, and any merge / squash button. You stage and
   commit locally on a feature branch; you give the user the exact commands
   to push and open the PR. You may run `git add` and `git commit`, but
   **never `git push`, `git push --force`, `gh pr create`, `gh pr merge`,
   `git reset --hard` to a remote ref, or anything else with network or
   destructive side effects on origin.**
3. **Do not modify git config, remotes, or hooks.** No
   `git remote set-url`, no `git config user.*`, no editing `.git/hooks/*`,
   no `--no-verify`. If a hook fails, fix the underlying issue.
4. **Commit messages: plain content only.** Conventional-commit prefix is
   fine (`feat(...)`, `fix(...)`, `feat(infra): ...`). No emoji unless the
   user explicitly asks. No trailers naming any AI.

## 1. Project Goal

**PFA Decision AI** — an OODA-loop decision-support tool for a marketplace
ops persona, built on the Olist Brazilian e-commerce dataset. Stack is
locked in [CLAUDE.md](CLAUDE.md): PostgreSQL + DuckDB + dbt + FastAPI +
Next.js 16 + Anthropic Claude + scikit-learn/XGBoost + Prophet + Docker.

Current objective: **ship a working MVP with a public URL before the
soutenance**. PR #1 (Days 10–15) just landed. Five days remain on the
plan: Day 16 (first AWS deploy + ADR-006), Day 17 (Loom), Day 18 (README
+ one-pager), Day 19 (blog post), Day 20 (25-slide deck + dry-run).

## 2. Current State

**Works**
- API on `:8000` — `/health`, `/docs`, `/auth/login`, `/auth/me`, KPIs,
  insights, replay, governance (analyst+), act (ops+), data-health
  (analyst+), ingest (ops+).
- Dashboard on `:3000` — `/`, `/data-health`, `/ingest`, `/login`. Login
  flow uses bcrypt + PyJWT, token in `localStorage`, AuthGate + UserMenu
  wired into Topbar.
- 114 pytest unit tests pass (`api/tests/`).
- `npx tsc --noEmit` clean. `next build` generates all 7 pages cleanly.
- CI green on PR #1 (Python, dbt, Frontend). PR #1 merged to `main`.
- Multi-stage Dockerfiles for `api/`, `dashboard/`, `dagster_pipeline/`.
- `docker-compose.prod.yml` shape ready (not built here — no Docker).

**Partially implemented**
- Frontend hardening (Day 11): only UserMenu + `openapi-typescript`
  scripting shipped. Server Actions for `/act/*` and a full shadcn/ui
  migration were deferred (see commit `b3a6fed`).
- Ingest (Day 12): CSV only. Parquet support deferred (needs `pyarrow`).
  dbt-staging-from-Jinja scaffold deferred — the registry entry's
  `suggested_table` field is the handoff.
- Terraform (Day 15): skeleton only. **Never `terraform apply`'d.** The
  EventBridge → API target is a placeholder (`target.arn = ALB ARN`); the
  proper path is `aws_cloudwatch_event_api_destination`. See
  `terraform/README.md` for the full caveat list.

**Broken / known issues** (unchanged from earlier handoff)
- Forecast MAPE = 259262% — model fits, metric is garbage; eval window
  needs to be restricted to 2017-01..2018-08, or switch to MAE/sMAPE.
- Late-delivery F1 = 0.38 at threshold 0.62. ROC-AUC 0.82 is demo-OK.
- No `ANTHROPIC_API_KEY` in `api/.env` — agent runs in offline fallback.
- `openapi-typescript` dep removed from `dashboard/package.json` because
  `npm install` fails behind the local TLS chain. Re-add with
  `npm install -D openapi-typescript` once that's sorted.

## 3. Git State

- **Active branch in this worktree:** `claude/busy-wiles-43401b`. Head at
  `0983926 fix(login): wrap useSearchParams in a Suspense boundary`.
- **`main`:** locally stale at `1e131f1` (initial commit). On GitHub,
  PR #1 was merged so `origin/main` is ahead — run `git fetch && git
  checkout main && git pull` from the **main repo path**, not from a
  worktree, before starting Day 16.
- **Working tree:** clean. No staged / unstaged / untracked files.
- **PR context:** [PR #1](https://github.com/Younesb24/pfa-decision-ai/pull/1)
  "Days 10-15 — auth, ingest, docker, terraform skeleton" merged. Six
  feature commits (`e8efac9` Day 10 → `d2514f3` Day 15) plus two CI fixes
  (`73962e1`, `0983926`).
- **Other worktrees exist:** `nostalgic-kirch-eb3521`,
  `vigilant-bartik-fbf40f`. Leave them alone unless asked. Claude Code
  cannot yet relocate worktrees out of `.claude/worktrees/` — feature
  request anthropics/claude-code#28242 is open.

## 4. Files Actively Edited (this session)

Backend (new):
- `api/services/auth.py` — bcrypt + PyJWT helpers, `CurrentUser`,
  `require_role(min_role)` dependency factory.
- `api/routers/auth.py` — `POST /auth/login` (JSON + OAuth2 form),
  `GET /auth/me`.
- `api/routers/ingest.py` — `POST /ingest/upload`, `GET /ingest/sources`.
- `api/services/profiler.py` — stdlib-only CSV profiler.
- `api/tests/test_auth.py` (15 tests), `api/tests/test_profiler.py` (13).

Backend (modified):
- `api/main.py` — registered `auth` + `ingest` routers; gated
  `governance`, `data-health`, `act`, `ingest` via `require_role(...)`.
- `api/requirements.txt` — added `bcrypt`, `PyJWT`, `python-multipart`.
- `api/tests/test_app_smoke.py` — added auth/ingest contract tests.
- `api/Dockerfile` — multi-stage, non-root, HEALTHCHECK.
- `api/.dockerignore` — new.

Scripts / migrations (new):
- `scripts/users_migration.sql`, `scripts/source_registry_migration.sql`,
  `scripts/seed_users.py`.

Frontend (new):
- `dashboard/src/app/login/page.tsx`, `dashboard/src/app/ingest/page.tsx`.
- `dashboard/src/components/auth-gate.tsx`,
  `dashboard/src/components/dashboard/user-menu.tsx`.
- `dashboard/src/lib/auth.ts`.
- `dashboard/Dockerfile`, `dashboard/.dockerignore`.

Frontend (modified):
- `dashboard/src/lib/api.ts` — `fetchJson` attaches Bearer + 401 redirect.
- `dashboard/src/app/data-health/page.tsx` — added Connected sources
  panel + token-aware fetch.
- `dashboard/src/components/dashboard/sidebar.tsx` — `NavItem.href` for
  real anchor-based nav (`/data-health`, `/ingest`).
- `dashboard/src/components/dashboard/top-bar.tsx` — wired UserMenu.
- `dashboard/package.json` — final state: no `openapi-typescript` dep
  (removed for CI), no `gen:api-types` script.

Infra (new):
- `dagster_pipeline/Dockerfile`, `docker-compose.prod.yml`,
  root `.dockerignore`.
- `terraform/` — `main.tf`, `variables.tf`, `vpc.tf`, `rds.tf`,
  `secrets.tf`, `iam.tf`, `alb.tf`, `ecs.tf`, `eventbridge.tf`,
  `outputs.tf`, `terraform.dev.tfvars`, `.gitignore`, `README.md`.

Other:
- `Makefile` — `users-init`, `seed-users`, `auth-init`, `ingest-init`,
  `prod-up`, `prod-down`, `prod-logs` targets.
- `.env.example` — `NEXT_PUBLIC_API_URL` corrected; documented
  `JWT_SECRET`, `JWT_TTL_MIN`.

## 5. Commands Run

### Worked
- `python -m pytest -x --tb=short -q` (under `api/`) → 114 passed.
- `npx tsc --noEmit` (under `dashboard/`) → clean.
- `npx next build` (under `dashboard/`) → all 7 pages prerender.
- `python -m ruff check --fix api ml scripts` → fixed I001, F401, UP012
  across new files.
- `git add … && git commit -m "..."` for six feature commits + two CI
  fixes. **User ran** `git push -u origin claude/busy-wiles-43401b` and
  `gh pr create` from PowerShell.
- `git -C <main-repo> worktree list` → enumerated worktrees fine.

### Failed
- **`git worktree move .claude/worktrees/busy-wiles-43401b worktrees/busy-wiles-43401b`**
  - Error: `Permission denied`.
  - Reason: this Claude Code session is rooted in the worktree and
    Windows held the directory open.
  - Workaround: closing the session and running the move from PowerShell.
    The user didn't end up doing this — left as-is.
- **`npm install --save-dev openapi-typescript`** (Day 11)
  - Error: `UNABLE_TO_VERIFY_LEAF_SIGNATURE`.
  - Reason: corporate TLS chain on the npm registry.
  - Workaround: added the dep to `package.json` anyway. Backfired on CI
    because `package-lock.json` was out of sync → `npm ci` rejected it.
    Final fix: removed the dep from `package.json` entirely (commit
    `73962e1`). Re-add when the registry trusts cleanly.
- **`docker --version`** → not installed in this environment.
  - Effect: Day 14 Dockerfiles + `docker-compose.prod.yml` checked in
    but **never built or run**. Expect debugging on first `make prod-up`.
- **`terraform --version`** → not installed.
  - Effect: `terraform fmt` / `validate` never run on the Day 15 files.
- **`gh pr create` with bash heredoc** (PowerShell rejected the heredoc
  syntax). Final workaround: PowerShell array joined with `` `n``.

## 6. Decisions Made

- **JWT in `localStorage`, not httpOnly cookies.** Trade-off: smaller
  CSRF surface, slightly larger XSS blast radius. For a single-page
  operator console behind auth it's the right call. Re-evaluate if/when
  the dashboard accepts user-generated content.
- **bcrypt + PyJWT, not passlib + python-jose.** bcrypt 5.x ships wheels
  for Windows; passlib's bcrypt detection broke on bcrypt 4.x.
- **Router-level role guards** (`dependencies=[Depends(require_role(...))]`)
  rather than per-endpoint decorators. New endpoints added under
  `/governance/*`, `/act/*`, `/data-health/*`, `/ingest/*` inherit the
  guard by default — easier to remember.
- **Role hierarchy**: `admin > ops > analyst > viewer`. `/act/*` and
  `/ingest/*` require `ops+`; the others require `analyst+`.
- **Stdlib-only CSV profiler.** Pulling pandas in for profiling would
  bloat the API image by ~80 MB.
- **Ingest blobs go to `data/ingest/<source_id>/raw.csv`.** The registry
  row is inserted first so the id namespaces the path — if disk write
  fails we mark the row `status='failed'`, never leave a dangling path.
- **Multi-stage Dockerfiles, non-root user, HEALTHCHECK each.** ECS/k8s
  hardened defaults reject uid 0.
- **Single Terraform root, workspaces for `dev/staging/prod`.** Per-env
  knobs in a `local.size_profile` map. Module-per-tier was overkill
  for a one-week deployment.
- **Path-based ALB routing** (`/api/*` → api, `/orchestrator/*` →
  dagster, else → dashboard) instead of multiple ALBs. Cheaper.

## 7. Current Blockers / Risks

- **AWS deploy untested.** Day 16 is the risk hotspot. Expect to iterate
  on: security-group rules, ECS health-check timing, EventBridge target
  wiring (currently a placeholder ARN), and ACM/HTTPS once a domain is
  picked.
- **No Docker locally.** Can't validate the prod-parity compose stack
  before pushing to AWS.
- **`ANTHROPIC_API_KEY` absent.** The Decision Analyst agent and
  narrative endpoints run in template-fallback mode. Set the key in
  `api/.env` before recording the soutenance Loom (Day 17).
- **`origin/main` is ahead of local `main`.** Don't branch from local
  `main` until you `git pull` — you'd be branching off the initial
  commit and missing every merged PR.
- **Forecast MAPE bug** (259262%) and **late-delivery F1 = 0.38** remain
  open. Plan calls them out as "acknowledge in the model card; not a
  blocker for the defense".

## 8. Next Steps

1. **Sync `main`** locally (see §9). Verify the merged PR #1 is in.
2. **Day 16 — first AWS deploy.**
   a. Push the three Docker images to ECR (api / dashboard / dagster).
      Decide tag scheme — `latest` for first apply, then commit SHAs.
   b. Create the S3 + DynamoDB backend bucket + lock table (one-time
      bootstrap, commands inlined in `terraform/main.tf`).
   c. `cd terraform && terraform init`,
      `terraform workspace new dev`,
      `terraform plan -var-file=terraform.dev.tfvars`.
   d. Read every diff line in the plan. Apply. Expect 12–15 min.
   e. Hit the ALB DNS. Fix what's broken. **Common first-deploy
      failures**: ECS task can't pull image (IAM), task fails healthcheck
      (path mismatch — recheck `aws_lb_target_group.api.health_check.path`),
      RDS unreachable (SG rule order).
   f. Decide on Vercel front: point the Vercel project at the ALB DNS
      and override `NEXT_PUBLIC_API_URL`. Rebuild the dashboard image
      with the public URL baked in (Next inlines it).
   g. Write **ADR-006** under `docs/adr/`: "Why AWS over Render" + the
     trade-offs (cost, prestige, IAM debt). Two paragraphs is enough.
3. **Day 16 kill-switch.** If anything in step 2 burns >24h, drop
   Terraform on a branch and ship to Render.com instead. Public URL is
   non-negotiable for the jury.
4. **Day 17 — Loom (3 min).** Script lives in `docs/demo_script.md`
   (create it). Walk the OTIF crisis scenario through the OODA loop.
   Record before bed; re-record once if it's not crisp.
5. **Day 18 — README hero shot + Loom embed + 7-surfaces grid.** Build
   the one-page PDF with Pandoc.
6. **Day 19 — blog post**, ~800 words: *"Why your LLM should never
   calculate."* Cross-post LinkedIn + Medium.
7. **Day 20 — 25-slide deck.** OTIF crisis as the spine. <25 min. One
   full dry-run, time it.

## 9. Exact Next Commands

Run these from a fresh PowerShell, **outside the `.claude/worktrees`
worktree** (use the main repo path):

```powershell
# Sync main with the merged PR #1
cd C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai
git fetch origin
git checkout main
git pull --ff-only origin main
git log --oneline -10   # confirm Day-15 commits are now on main
```

To resume work (Day 16 onward), create a fresh feature branch:

```powershell
git checkout -b feat/day16-aws-deploy
```

To verify the stack still boots locally before touching infra:

```powershell
# Terminal 1 — API
cd C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai\api
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 — dashboard
cd C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai\dashboard
npm run dev
```

Then:
- `http://localhost:8000/health` → 200
- `http://localhost:3000/login` → sign in as `ops@pfa.local / ops123`
  (you must have run `make auth-init` once)
- `http://localhost:3000/ingest` → drop a CSV, confirm preview

For Day 16 first apply (do **not** run before reading
`terraform/README.md`):

```powershell
cd C:\Users\yb360\.gemini\antigravity\scratch\pfa-decision-ai\terraform
terraform init
terraform workspace new dev
terraform plan -var-file=terraform.dev.tfvars
```

## 10. Do Not Repeat / Avoid

- **Do not** add `Co-Authored-By: Claude` or any AI attribution to commits
  or PR bodies. (See §0 rule 1.)
- **Do not** run `git push`, `git push --force`, `gh pr create`,
  `gh pr merge`, `git remote set-url`, `git reset --hard origin/*`, or
  `--no-verify`. The user runs those. (See §0 rule 2.)
- **Do not** import `EmailStr` from pydantic without first installing
  `pydantic[email]` — it's not in `requirements.txt`. Use plain `str`
  with `Field(min_length=...)` like `api/routers/auth.py:LoginRequest`.
- **Do not** add devDependencies to `dashboard/package.json` without
  also updating `package-lock.json`. CI uses `npm ci`, which is strict.
  If `npm install` fails locally (TLS), don't commit a phantom dep.
- **Do not** put `0` and `1` in the boolean-token set when extending
  `services/profiler.py`. They shadow ints; tests caught this once.
- **Do not** call `useSearchParams()` outside a `<Suspense>` boundary
  in any Next page that needs to prerender. CI build catches it.
- **Do not** assume the worktree's `package-lock.json` reflects the
  state of `node_modules` here. The background `npm install` in this
  env hits the same TLS issue as the foreground.
- **Do not** branch off local `main` without `git pull` first — local
  is stale.
- **Do not** try to relocate Claude Code worktrees out of
  `.claude/worktrees/` from inside an active session. Permission
  denied on Windows because the dir is in use.

## 11. Definition of Done

The current task — shipping the MVP for the soutenance — is done when
**all** of the following are true:

- Public URL is live and the dashboard loads on first hit (AWS or Render,
  doesn't matter which).
- `POST /api/v1/auth/login` succeeds from the public URL using one of the
  four seeded demo users.
- At least one full OODA-loop walkthrough (anomaly → narrative →
  recommendation → action) is reproducible from the public URL.
- A 3-minute Loom is recorded, embedded in the README, and shows the
  OTIF crisis scenario end-to-end.
- README has a hero screenshot + the 7-surfaces grid.
- One-page PDF generated via Pandoc, checked in under `docs/`.
- 25-slide deck checked in under `docs/`, dry-run timed under 25 min.
- ADR-006 ("Why AWS over Render", or vice versa) checked in.
- CI on `main` is green.
- Known issues (forecast MAPE, late-delivery F1, agent offline fallback
  when no `ANTHROPIC_API_KEY`) are acknowledged in the model card,
  not hidden.

When all of the above are checked off, the project is defense-ready.
