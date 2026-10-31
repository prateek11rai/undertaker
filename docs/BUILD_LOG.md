# Build log

Core build for Undertaker, 1 Nov 2026 (IST), by the builder thread from `docs/design/build-brief.md`. The spec is `docs/design/spec.md`; this file records decisions, deviations, the eval numbers and the click-through.

## Setup checks (Step 0)

All passed: DevRelay scoped to this repo (no DevRelay tool or CLI used), noreply identity, leak check clean, uv 0.12.3, Python 3.13.12 from Homebrew, `/opt/homebrew/bin/temporal` 1.9.1 (Server 1.32.0), Ollama 0.35.1 with `gemma4:e4b`.

## Decisions made while building

- **Rules over plain data.** `temporal/client.py` is the only module that reads protobufs. It builds a `Snapshot` (describe + parsed history + pollers); rules, checks, remedies and templates are pure functions over it, so 60+ unit tests run without a server.
- **Children before parents.** The sweep diagnoses children on demand (memoised, cycle-safe), so `undead-child` uses the child's full result and links to its certificate.
- **The metadata query only for `waiting-signal`.** `__temporal_workflow_metadata` is asked only after a workflow matches rule 9, with a 3 s timeout, so orphaned workflows never block a sweep.
- **Activity task queue from history.** `PendingActivityInfo` has no task queue, so it comes from the matching `ActivityTaskScheduled` event (also the source of the heartbeat timeout and the first-scheduled time used for "undead for").
- **`retry-loop` "far away" maximum** means no maximum, or at least 50 attempts left. A start-to-close or other timeout is never a retry loop (heartbeat timeouts are rule 5).
- **The checks' corpus** is every evidence text and key, the workflow id, type, queue, run id, cause and rule text, formatted times, and the source excerpt. Numbers are matched as digit runs. `changed-code` also allows `workflow.patched`, Temporal's own API that its remedy names. Other cause keys are banned unless they appear in the evidence (an `undead-child` certificate may say its child is `orphaned`). `heartbeat` is not banned as a word, since "heartbeat" is ordinary English in other causes.
- **Prompt injection.** Failure messages and source go to the model inside `<data>` tags, and the system prompt says those are data. The check is what actually protects the page: model text with a URL, a `temporal workflow …`, `curl`, `rm -` or `sudo` is rejected, as is any other cause named. All model text is HTML-escaped before the page turns `` `spans` `` into `<code>`.
- **Certificate cache.** SQLite at `.data/certificates.sqlite`, keyed by workflow id, run id, last event id, pending attempt, model, and whether `--source` was used. Model errors are never cached, so a restarted Ollama gets another chance.
- **Morgue rewrites only on real change.** `retry-loop` and `heartbeat` bump the attempt every second or two without new history. The morgue writes a new certificate when the history length or the cause changes, not on every attempt; the page then says "written at event N, attempt M" so the reader knows the numbers are from then. `inspect` and `eval` always use the exact per-attempt key from the spec.
- **Background sweeps and certificate writing are decoupled.** Sweeps run every `--every`; certificates are written one at a time alongside, so a slow model never delays a sweep.
- **Actions** need `--allow-actions`, a browser confirm, and a custom `X-Undertaker: 1` header (a cross-site form can't send it). Resurrect resets to the last workflow-task finish event (completed, failed or timed out), the same point as the CLI's `--type LastWorkflowTask`, reapplying signals.
- **Demo thresholds apply by themselves** when the demo is up and the command points at its address and namespace, so plain `undertaker sweep` and `serve` show the demo right away (it says so on stderr). `--quiet`/`--attempts` still win; `--demo` forces them.
- **`demo up` always starts from an empty db.** It deletes `.data/temporal.db` first so workflow ids never clash with an old run. `demo down` sends SIGTERM to each process group, then SIGKILL after 10 s.
- **Tests without httpx.** FastAPI's `TestClient` needs `httpx`, which isn't an approved dependency, so `tests/test_morgue.py` calls the ASGI app directly.
- **Watch** stores notified workflow ids in `.data/watch-notified.json` so a restart never repeats a notification. Text reaches `osascript` as argv, never inside the AppleScript source.

## Deviations from the spec

- **`proof-dough` sleeps in rounds.** The spec says "90 s timer, then finishes". A single 90 s timer finishes before anyone opens the morgue, so it runs 20 rounds of 90 s (30 minutes) and then finishes. The eval counts an expected-alive workflow that has already finished as fine.
- **`order-1050-box` is in the manifest** as `orphaned`, since it is a running workflow of its own. So the demo has 10 undead (one per cause, plus the orphaned child) and 2 alive.
- **`order-1047` (changed-code) was seeded, not dropped.** `demo up` runs version A of `DecorateCakeWorkflow` in-process until it starts its 15 s timer, stops that worker, then starts the demo worker with version B. When the timer fires, B replays and hits `[TMPRL1100] Nondeterminism error: Activity type of scheduled event 'bake' does not match activity type of activity command 'frost'`. It worked first time, within a few minutes.
- **Source excerpts are the enclosing function** (planner review, A3), at most 8 lines either side of the frame line, instead of ~30 lines around it, so the excerpt doesn't drag in unrelated functions. Non-Python files get ±8 lines.
- **History cache is in memory**, per process, keyed by (workflow id, run id, last event id). Certificates are the expensive part and live in SQLite.
- **"Same failure every attempt"** (rule 6) can't be proven: Temporal keeps only the last failure of a retrying activity. Listed under limits in the README.
- **Epitaph check** also rejects the workflow id, type, task queue and activity or signal names, and anything with an underscore, a backtick, a file name or CamelCase.

## Eval (`uv run undertaker eval --demo --source src/undertaker/demo`)

Fresh `demo up`, 35 s wait, `serve` stopped so nothing else used the model. Two runs back to back:

| | Run 1 | Run 2 |
|---|---|---|
| Rules: found | 10/10 | 10/10 |
| Missed | 0 | 0 |
| False alarms | 0 | 0 |
| Alive and right | 2/2 | 2/2 |
| Gemma accepted on the first try | 10/10 | 10/10 |
| Retried, then accepted | 0 | 0 |
| Fell back to the template | 0 | 0 |
| Seconds per certificate (mean) | 8.4 | 7.6 |

Hardware: the owner's Apple Silicon Mac, `gemma4:e4b` on Ollama 0.35.1, `temperature` 0.2, `think` off, JSON-schema output. The first call after Ollama loads the model takes about 25 s.

Earlier in the build, while `serve` was writing certificates at the same time, one eval also had 10/10 accepted at 12.7 s each. The rejection path is covered by unit tests (`tests/test_certificate.py`) because the live model didn't trip it in these runs.

One thing the eval showed: with no `--source`, Gemma sometimes leaves the `frame1` file and line out of the prose (still correct, just less useful). The system prompt now asks for it whenever `frame1` exists. With `--source`, the retry-loop certificate says `activities.py:12`, which is the right line.

## Click-through checklist (Playwright, http://127.0.0.1:8666)

Run on 1 Nov 2026 against a fresh demo, `serve --demo --source src/undertaker/demo` (read-only), then `serve --demo --allow-actions`.

- ✓ The morgue loads: header with logo, server and namespace, "10 undead · 2 alive · swept N s ago", Sweep now.
- ✓ Every filter: All (12), each of the nine causes (orphaned 2, the rest 1) and Alive (2) shows exactly its toe tags.
- ✓ Sweep now: the button posts, the page reloads, and the "swept" timestamp is new.
- ✓ Certificate, retry-loop (`order-1042`): written by gemma4:e4b, every fact checked; names `activities.py` line 12; source excerpt with line 12 marked; terminate command.
- ✓ Certificate, waiting-signal (`order-1048`): names `payment_received` (from the worker's metadata query); signal command with the name filled in.
- ✓ Certificate, changed-code (`order-1047`): quotes the `NON_DETERMINISTIC_ERROR` (`bake` vs `frost`); reset command; remedy mentions `workflow.patched`.
- ✓ Certificate, broken-code (`order-1046`): `KeyError: 'sugar'` at `workflows.py:70`.
- ✓ Copy buttons: Copy command puts the exact `temporal workflow terminate …` line on the clipboard and the label turns to "Copied".
- ✓ Without `--allow-actions`: Lay to rest and Resurrect are disabled, with the tooltip "Read-only. Start undertaker serve with --allow-actions to enable." The endpoints return 403 (unit test).
- ✓ With `--allow-actions`: Lay to rest on `order-1045` showed the confirm; after accepting, Temporal reports it `TERMINATED` and it left the morgue.
- ✓ With `--allow-actions`: Resurrect on `order-1046` showed the confirm; after accepting, the old run is reset and a new run (`c45afce9…`) is running and back in the morgue.
- ✓ Screenshots from the Playwright page only: `docs/img/morgue.png`, `docs/img/certificate.png`.
- ✓ `inspect order-1042` prints a certificate without and with `--source`; with it, the text says `activities.py:12` and prints the excerpt.
- ✓ `demo down` leaves no process: `pgrep -fl "temporal server|undertaker.demo|undertaker serve"` prints nothing. `doctor` then says the server is not reachable and exits 1.

## Notes for the planner

- CI action SHAs are the ones the planner supplied; `actions/checkout` `11d5960…` and `actions/setup-python` `a26af69…`. uv is installed on the runner with `pip install uv==0.12.3`; Temporal and Ollama with the runner's Homebrew.
- `.git/info/leak-check.sh` now scans only pushable refs (planner change), so T3's `refs/t3/…` checkpoints don't count.
