# Undertaker · agent guide

Undertaker finds Temporal workflows that will never finish and writes a checked "certificate of undeath" for each, using a local Gemma 4 e4b through Ollama. Spec: `docs/design/spec.md`. Build notes: `docs/BUILD_LOG.md`.

## Run and test

- Python 3.13 (Homebrew) with uv: `uv sync`, `uv run undertaker …`. uv never downloads a Python.
- Checks: `uv run ruff check && uv run ruff format --check && uv run pytest`. Markers: `-m temporal` (needs `/opt/homebrew/bin/temporal`), `-m model` (needs Ollama with `gemma4:e4b`).
- Demo: `uv run undertaker demo up`, then `uv run undertaker serve` (http://127.0.0.1:8666). Always `uv run undertaker demo down` when finished; leave no processes behind.

## Rules

- Temporal CLI and dev server: always `/opt/homebrew/bin/temporal` (an older `temporal` sits earlier on `PATH`). Never download a Temporal test server or CLI.
- Dependencies come only from public PyPI with the 7-day cooldown in `pyproject.toml`. `uv.lock` is committed. Never print package-index URLs from user-level config; they can embed tokens.
- Undertaker is read-only by default. Terminate and reset only behind `--allow-actions` with a confirm.
- Code makes the diagnosis; the model only explains, and every fact it cites is checked. Never let model text reach the page unchecked.
- Everything listens on 127.0.0.1. No telemetry, CDN or web fonts.
- Demo data is made up (a bakery). Never real people, companies, customers or tickets.
- Never take desktop screenshots; use Playwright on the app's own page.
- Run `bash .git/info/leak-check.sh` before every commit. Commits use the GitHub noreply identity. Never `--no-verify`. Don't push; the owner pushes.
- DevRelay skills in `.agents/skills/devrelay-*` are local and git-ignored. Don't call DevRelay tools or the `devrelay` CLI unless the planner asks.
