# Build Undertaker · core

> The brief the build agent gets. Lives at `docs/design/build-brief.md`; the planner appends answers at the bottom. Don't edit this file.

Planner: T3 thread `mlh` (id `mcp:d6d84144-d1b5-442b-82e6-d79b07028f77`). You: T3 thread `mlh · build-undertaker`, running in the project `~/github/prateek11rai/undertaker`, branch `main`. Work only inside this repo.
Challenge: https://dev.to/challenges/hacktoberfest-week4-2026-10-26, closes **Sun 2026-11-01 12:29 IST**. Finish the core by **04:00 IST**; move fast and keep it simple. A ship pass (images, README polish, post draft; no video) follows as a second brief.

## Goal

Build all of `docs/design/spec.md` as one Python project managed with uv: the sweep (Temporal client, evidence, rules), certificates (Gemma 4 e4b through Ollama, checks, template fallback, cache), the morgue web page, the CLI, the haunted-bakery demo (dev server + worker + scenarios + manifest), eval, tests, CI and docs. `uv run undertaker demo up`, then `uv run undertaker serve`, shows every demo workflow with the right cause and a checked certificate.

## Read first

1. `docs/design/spec.md`. **Follow it. If you must deviate, write why in `docs/BUILD_LOG.md`.**
2. `docs/brand/theme-preview.html` and `docs/brand/logo.svg`: the look. Copy the palette and the logo into the app's static files; the theme preview is the reference for toe tags and the certificate.
3. `AGENTS.md`: the repo rules.

## Step 0 · Check the setup before anything else

1. **DevRelay is scoped to this repo:** your tool list includes the DevRelay gateway tools; `.agents/skills/` has nine `devrelay-*` skills; `.claude/skills` is a symlink to `../.agents/skills`; `~/.claude/skills` and `~/.agents/skills` have no `devrelay-*`. **Don't call any DevRelay tool, and never run the `devrelay` CLI.**
2. **Guards:** `git config user.email` is `165780365+prateek11rai@users.noreply.github.com`; `bash .git/info/leak-check.sh` prints `leak-check: clean`.
3. **Local tools:** `uv --version`; `/opt/homebrew/bin/python3.13 --version`; `/opt/homebrew/bin/temporal --version` (1.9.1; **always use this absolute path**: `PATH` finds an old `~/.local/bin/temporal` first); `ollama list` shows `gemma4:e4b` (the planner started Ollama).

If a check fails, report `BLOCKED-setup: <what>` to the planner and wait. Don't fix setup yourself.

## Already done by the planner

- `git init` on `main`, noreply identity, `.git/info/leak-check.sh` + `.git/info/leak-patterns` (local only; never committed).
- DevRelay registered for this repo only; skills in `.agents/skills/devrelay-*` (git-ignored through `.git/info/exclude`); `.claude/skills` → `../.agents/skills` (commit the symlink).
- `AGENTS.md`, `docs/design/spec.md`, `docs/design/plan.md`, this brief, `docs/brand/logo.svg`, `docs/brand/theme-preview.html`, `docs/img/theme-preview.png`. Commit them in your first commit.

## Dependencies

- Python 3.13 from Homebrew (`.python-version` = `3.13`); uv must never download a Python.
- `pyproject.toml` must have:

  ```toml
  [[tool.uv.index]]
  name = "pypi"
  url = "https://pypi.org/simple"
  default = true

  [tool.uv]
  exclude-newer = "2026-10-25T00:00:00Z"
  python-downloads = "never"
  python-preference = "only-system"
  ```

  (The user-level uv config points at a private mirror; this block forces public PyPI and the org's 7-day cooldown. `uv.lock` may only mention `pypi.org` and `files.pythonhosted.org`; the leak check enforces it. Never print index URLs from user-level config files.)
- Runtime, exact pins, stable releases only: `temporalio` (1.34.0 is the newest inside the cooldown), `fastapi`, `uvicorn`, `jinja2`, `pydantic`. Dev: `pytest`, `pytest-asyncio`, `ruff`. Ollama over HTTP with the standard library (`urllib.request`), no client library. CLI with `argparse`.
- Anything else: ask the planner first. No Node, npm, build step, CDN or web fonts.
- Lint: ruff with `D` rules, Google-style docstrings (`convention = "google"`, D100/D104 ignored, tests exempt). No header comment blocks; one-line comments only where needed.

## Code layout (suggested; keep files under ~400 lines)

```
src/undertaker/
  cli.py  config.py
  temporal/  client.py (connect, list running, describe, history, pollers, metadata query)  evidence.py
  diagnose/  rules.py (the nine causes + alive, in spec order)  remedies.py (sentences + commands)
  explain/   model.py (Ollama + JSON schema)  certificate.py (prompt, checks, retry, template fallback)  cache.py
  morgue/    app.py (FastAPI)  templates/ (morgue.html, certificate.html)  static/ (theme.css, morgue.js, logo.svg)
  demo/      server.py (dev server lifecycle)  worker.py  scenarios.py  seed.py  manifest.py
  sweep.py  evals.py  watch.py
tests/
```

- Rules, evidence, checks, remedies and templates are pure functions over plain data classes, so they test without a server. The Temporal client layer converts protobufs into those data classes.
- The sweep caches history per (workflow id, run id, last event id); certificates per (workflow id, run id, last event id, pending attempt), in a small SQLite or JSON file under `.data/` (git-ignored).
- The morgue renders server-side (Jinja); `morgue.js` only does Sweep now, filters, copy buttons and the two actions.
- Every server listens on 127.0.0.1 only.

## Build order

1. **Skeleton:** pyproject, uv sync, CLI stub, `doctor`, CI skeleton. Commit.
2. **Demo first:** `demo up | down | status`: start the Homebrew dev server (`--ip 127.0.0.1`, db file in `.data/`, log to `.data/`), the demo worker as a background process with a pid file, seed the scenarios from the spec table with short timeouts. `demo down` stops the worker and the server and leaves **no processes behind** (check with `pgrep`). Write the manifest. Commit.
3. **Sweep + rules:** evidence building, the nine rules plus alive, `sweep` table and `--json`. Unit tests for every rule with built evidence (good and near-miss cases), then an integration test (`@pytest.mark.temporal`) against a dev server started with `/opt/homebrew/bin/temporal` that seeds a small set and asserts causes. Commit.
4. **Remedies + template certificates:** every cause has a template and commands; `inspect` prints a certificate without the model. Commit.
5. **Model certificates:** prompt, JSON schema, checks, one retry, fallback, cache. Unit tests for the checks with bad outputs (unknown evidence key, invented number, invented file, a different cause named, digits in the epitaph, too long, prompt injection in a failure message). One `@pytest.mark.model` test that calls the real `gemma4:e4b` on one demo workflow and asserts the checks hold. `--source`: read only files inside the given folder (resolve paths, refuse `..` and symlinks out), ~30 lines around each frame. Commit.
6. **Morgue:** the page and the certificate page in the spec's look, background sweeps, Sweep now, filters, copy, actions behind `--allow-actions` with a confirm and a disabled state otherwise. Commit.
7. **Eval:** `eval --demo` prints found / missed / false alarms, model accepted / retried / fallback, and seconds per certificate. Record the real numbers in `docs/BUILD_LOG.md`.
8. **Watch (stretch, only if 1–7 are done by 03:30):** `watch` posts one macOS notification per new undead with `osascript`. Never more than one notification per workflow.
9. **CI:** `.github/workflows/test.yml`, actions pinned to commit SHAs, `permissions: contents: read`, `persist-credentials: false`: job `unit` (ubuntu, uv, ruff, pytest without markers); job `temporal` (ubuntu, `brew install temporal` with the runner's Homebrew at `/home/linuxbrew/.linuxbrew/bin/brew`, pytest `-m temporal` pointing at that binary). `paths-ignore` for `docs/**`, `**/*.md`, images. Optional `model.yml` like the planner's earlier projects (runner Homebrew Ollama + `gemma4:e4b`, only on changes under `src/undertaker/explain/**` or by hand). Never `curl | sh`.
10. **Docs:** `README.md` (what it is in two lines, why local, 60-second start with the demo, how it works with a small mermaid diagram, the causes table, commands, flags, limits, license MIT, a "Built for Hacktoberfest 2026" line with the challenge link); update `AGENTS.md` (how to run, test, the rules); `docs/BUILD_LOG.md` (decisions, eval numbers, deviations, the click-through checklist). `LICENSE` (MIT, prateek11rai).

## Acceptance (check these yourself before saying done)

1. Fresh clone: `uv sync --frozen` works; `uv run ruff check`, `uv run ruff format --check`, `uv run pytest` (with `-m temporal` and `-m model` too) pass.
2. `uv run undertaker demo up`, wait for the thresholds, then `uv run undertaker sweep`: every demo workflow has its expected cause; the two alive ones are alive; `eval --demo` shows 0 missed and 0 false alarms (or explains each in the build log).
3. `uv run undertaker serve`: with Playwright, open http://127.0.0.1:8666, check the morgue, every filter, three certificates (retry-loop, waiting-signal, changed-code or broken-code), copy buttons, Sweep now, and that the action buttons are disabled without `--allow-actions`. Then run with `--allow-actions` and lay `order-1045` to rest and resurrect `order-1046` (the confirm appears; the server state changes). Screenshot only the Playwright page into `docs/img/` (`morgue.png`, `certificate.png`). Write the checklist with ✓/✗ in `docs/BUILD_LOG.md`.
4. `inspect` with and without `--source src/undertaker/demo` prints a certificate; with source, the retry-loop certificate names the right file and line.
5. `uv run undertaker demo down` leaves no `temporal` or worker process (`pgrep -fl "temporal|undertaker"` shows nothing of ours); `doctor` reports honestly.
6. `bash .git/info/leak-check.sh` says clean; `git log --format='%ae %ce' | sort -u` shows only the noreply address; `git status` is clean.

## Rules

- No `git push`, no GitHub repo creation, no publishing, no DevRelay or DEV calls, no session submission. The planner does those with the owner.
- Commit small, with the noreply identity, each message ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Run the leak check before each commit. Never `--no-verify`.
- **Network:** PyPI and the local Ollama and Temporal only. No `ollama pull`, no other downloads, no global installs, no `curl | sh`, no Docker, no Temporal test server or CLI downloads (the time-skipping test server is off limits; use `start_local(dev_server_existing_path="/opt/homebrew/bin/temporal")`).
- Never take screenshots of the desktop (`screencapture` or similar); Playwright pages only.
- Never read, print or summarise secrets, `.env` files, keychains, `~/.claude.json` or other projects' files. Demo data is made up: no real people, companies, customers, or the owner's projects or employer.
- Leave nothing running when you stop: `demo down`, stop `serve`, check with `pgrep`.
- UI copy follows the spec: short and plain, the epitaph is the only joke.
- Don't start subagents or other threads.

## Report to the planner

When done, or when blocked or with a question you can't answer from the spec, send your report to the planner thread with `t3_thread_send` (thread `mcp:d6d84144-d1b5-442b-82e6-d79b07028f77`, mode `queue`) and stop. For questions, number them and give your recommendation for each; carry on with independent parts while you wait if you can.

The done report has: commits (hash + one line), files by area, tests with results, the eval numbers, the click-through checklist, decisions you made alone and why, and open questions with your recommendation.

## Stop line

When everything above is done and checked, end your report with exactly `DONE-undertaker-core` on its own line and stop. Don't push, publish or submit anything.

## Answers

(The planner adds answers to your questions here.)
