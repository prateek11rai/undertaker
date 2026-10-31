# Undertaker · spec

Undertaker finds the Temporal workflows that will never finish and tells you why. Point it at a Temporal server. It sweeps every running workflow, sorts the undead into causes using Temporal's own data, and writes a **certificate of undeath** for each one: the cause, the evidence (history event ids, attempts, errors), the line of your code if you give it the source, and the exact command that fixes it or lays it to rest. A local open-weight model (Gemma 4 e4b through Ollama) writes the words; plain code makes the diagnosis and checks every fact the model cites.

Built for the DEV Hacktoberfest Open-Source AI Challenge, Week 4 "Ghost in the Machine" ("build something spooky, or something that honors the past, with open-weight models or open-source AI"). Closes **Sun 2026-11-01 12:29 IST** (Sat 23:59 PDT). Prize categories: **Best Use of Temporal**, **Best Use of Gemma**.

Why it must be open and local: workflow histories hold real payloads (orders, customers, card errors), and stack traces point into private code. Sending them to a hosted model to ask "why is this stuck" is the thing most teams can't do. A 4B model on your own machine can.

## Design philosophy

1. **Code diagnoses, the model explains.** The cause of undeath comes from fixed rules over Temporal's own data (describe, history, task-queue pollers). Gemma only turns the evidence into a readable certificate. If the model's text cites anything that isn't in the evidence, it is rejected and a plain template certificate is shown instead. The page always says which one you're reading.
2. **Read-only by default.** Pointing Undertaker at a server changes nothing. *Lay to rest* (terminate) and *Resurrect* (reset) exist only with `--allow-actions`, and each asks first. Every certificate also shows the exact `temporal` CLI command, so you can act yourself.
3. **Evidence first.** Every claim points at something you can check: a history event id, an attempt count, a poller list, a file and line.
4. **Nothing leaves the machine.** Temporal on localhost or your own network, Ollama on localhost, no telemetry, no CDN, no web fonts.
5. **Spooky in the words, never in the way.** The theme lives in the vocabulary (morgue, toe tag, certificate, epitaph, laid to rest) and the look. Facts, numbers and commands stay plain and exact.
6. **One command to see it.** `undertaker demo up` starts a local Temporal dev server and a worker full of broken workflows; `undertaker serve` opens the morgue.

## Words

| Word | Means |
|---|---|
| undead | a running workflow that a rule says will not finish on its own |
| alive | a running workflow that is making progress, or has a timer due soon |
| cause | one of the categories below |
| morgue | the main page: one toe tag per running workflow |
| toe tag | the card for one workflow |
| certificate | the detail page: diagnosis, evidence, remedy |
| epitaph | one line, written by the model, the only playful sentence |
| lay to rest / resurrect | terminate / reset (only with `--allow-actions`) |

## Causes of undeath (the rules)

A sweep lists running workflows (`ExecutionStatus="Running"`), then for each: `describe` (pending workflow task, pending activities with attempt / last failure / last heartbeat / next attempt, pending children, task queue, retry policy where visible), the history (fetched once and cached by last event id), and `DescribeTaskQueue` pollers for the workflow and activity task queues. A workflow is checked against the rules in this order; the first match is its cause. Thresholds are flags; the demo uses short ones.

| # | Cause (key) | Shown as | Rule (all from Temporal data) |
|---|---|---|---|
| 1 | `orphaned` | No one is listening | Pending workflow task scheduled and never started for longer than `--quiet`, and no poller seen on its workflow task queue in the last `--poller-window` |
| 2 | `lost-activity` | Sent to a worker that never came | Pending activity in state SCHEDULED for longer than `--quiet`, no poller on that activity's task queue |
| 3 | `broken-code` | Its own code keeps killing it | Pending workflow task attempt ≥ 2, and the last `WorkflowTaskFailed` is not a non-determinism error |
| 4 | `changed-code` | Its code changed while it slept | Same, but the failure is non-determinism (`TMPRL1100`, "nondeterminism") |
| 5 | `heartbeat` | Stopped breathing | Pending activity attempt ≥ `--attempts` and last failure is a heartbeat timeout |
| 6 | `retry-loop` | Dies and rises, forever | Pending activity attempt ≥ `--attempts`, same failure type and message, retry policy without a maximum (or a maximum far away) |
| 7 | `undead-child` | Waiting on an undead child | Pending child workflow whose own sweep result is undead (link to its certificate) |
| 8 | `long-sleep` | Asleep for a very long time | A pending timer (from history: `TimerStarted` without `TimerFired`/`TimerCanceled`) longer than `--long-sleep` (default 7 days) |
| 9 | `waiting-signal` | Waiting for a visitor who never comes | Nothing pending at all (no activity, timer, child, workflow task) and the last event older than `--quiet`. If the worker answers the built-in `__temporal_workflow_metadata` query, list its signal and update names |
| — | `alive` | Alive | None of the above, with the reason shown: "heartbeat 3 s ago", "timer fires in 40 s", "activity attempt 1, started 20 s ago", "started 12 s ago" |

Defaults: `--quiet 10m`, `--attempts 5`, `--poller-window 2m`, `--long-sleep 7d`. Demo: `--quiet 20s --attempts 3`.

Each result carries an **evidence** list: small keyed facts like `{"key": "e11", "kind": "event", "text": "ActivityTaskScheduled charge_card", "time": …}`, `{"key": "attempt", "text": "47"}`, `{"key": "failure", "text": "ValueError: amount must be positive"}`, `{"key": "frame1", "text": "activities.py:42 in charge_card"}`, `{"key": "pollers", "text": "0 pollers on bakery-ovens (activity)"}`.

## Remedies (code, per cause)

A short sentence and the exact commands (with `--address` and `--namespace` filled in), for example:
- orphaned / lost-activity: "Start a worker that polls `<queue>`." `temporal task-queue describe --task-queue <queue>`
- broken-code / changed-code: "Fix the workflow code and deploy, or reset past the bad task." `temporal workflow reset --workflow-id <id> --type LastWorkflowTask --reason "..."` (changed-code also mentions `workflow.patched`)
- heartbeat / retry-loop: "Fix the activity, or mark the error non-retryable." `temporal workflow terminate --workflow-id <id> --reason "..."`
- waiting-signal: `temporal workflow signal --workflow-id <id> --name <signal> --input '...'` when the signal name is known
- long-sleep: the fire time, and `temporal workflow reset` / signal
- undead-child: a link to the child's certificate

The model never writes commands. It may pick which of the code-made remedies to show first.

## The certificate (model + checks)

Input to Gemma: the cause and its rule text, workflow type and id, born time, last event, the evidence list, the top stack frames, and (with `--source`) up to ~30 lines of source around each frame **that resolves to a file inside the source folder**. Nothing else; no raw payloads beyond the failure message (truncated).

Output (Ollama `format` JSON schema, temperature low):

```json
{"headline": "≤ 12 words", "diagnosis": "≤ 70 words", "evidence": ["e11", "attempt", "failure"], "next_step": "≤ 30 words", "epitaph": "≤ 14 words"}
```

Checks (all in code): `evidence` keys exist; every number in `headline`/`diagnosis`/`next_step` appears in the evidence; every `code span`, file name, `file:line`, activity or signal name in the text appears in the evidence or source excerpt; the cause's own words are not contradicted (no other cause key named); lengths hold; the epitaph has no digits and no identifiers. One retry with the reasons on failure; then the template certificate for that cause. Certificates are cached by (workflow id, run id, last event id, pending attempt), so the model runs once per state and the morgue opens instantly.

## What the person sees

### The morgue (`undertaker serve`, http://127.0.0.1:8666)

- Header: logo, "undertaker", the server and namespace, "9 undead · 2 alive · swept 12 s ago", a **Sweep now** button.
- Filters: one chip per cause with counts, plus Alive.
- A grid of toe tags: cause chip (colour per cause), workflow id (mono), type and task queue, "undead for 2 h 14 min", one cause-specific fact ("attempt 47", "0 pollers", "timer fires 31 Oct 2027").
- Sweeps run in the background every `--every 30s`; certificates are written after each sweep for new or changed states.

### The certificate page (`/w/<workflow id>`)

Laid out like a certificate (serif headings, dashed rules): Born · Last sign of life (event id, type, time) · Cause · Diagnosis (model or template, labelled) · Evidence table (key, what, time) · Source excerpt (if `--source`) · Remedy with copyable commands · Epitaph · buttons Copy command, Lay to rest, Resurrect (disabled without `--allow-actions`, with a tooltip saying why). Child links for `undead-child`.

### The terminal

```
undertaker sweep [--json]            # table: id, type, cause, undead for, key fact
undertaker inspect <workflow-id>     # the certificate as text
undertaker serve                     # the morgue on 127.0.0.1:8666
undertaker watch                     # sweep every minute; macOS notification for each new undead (osascript); stretch
undertaker demo up | down | status   # local dev server + demo worker + scenarios
undertaker eval [--demo]             # found / missed / false alarms, model accepted / fallback, seconds per certificate
undertaker doctor                    # Temporal reachable, Ollama reachable, model present, versions
```

Common flags: `--address 127.0.0.1:7233 --namespace default --source PATH --allow-actions --model gemma4:e4b --ollama http://127.0.0.1:11434` plus the thresholds. Env vars `UNDERTAKER_*` mirror them. Temporal Cloud / mTLS is out of scope (listed under limits).

## The demo: a haunted bakery

`undertaker demo up` starts `/opt/homebrew/bin/temporal server start-dev` on 127.0.0.1 (ports 7233 and UI 8233, db file under `.data/`), a demo worker, and seeds one workflow per cause plus healthy ones. Made-up bakery: orders, ovens, inventory. No real people or companies.

| Workflow id | Expected | How it's made |
|---|---|---|
| `order-1042` | retry-loop | `charge_card` raises `ValueError` for amount 0; unlimited retries |
| `order-1043` | heartbeat | `bake_batch` heartbeats once then hangs; heartbeat timeout 5 s; unlimited retries |
| `order-1044` | lost-activity | activity routed to task queue `bakery-ovens`, which no worker polls |
| `order-1045` | orphaned | workflow started on `bakery-legacy`, which no worker polls |
| `order-1046` | broken-code | workflow code reads a missing dict key (plain exception → workflow task failure loop) |
| `order-1047` | changed-code | seeded with worker version A, which runs `bake` then sleeps 15 s; worker restarted with version B, which runs `frost` first → non-determinism on replay |
| `order-1048` | waiting-signal | waits for `payment_received`, which never comes |
| `order-1049` | long-sleep | `workflow.sleep(timedelta(days=365))` ("meant 365 seconds") |
| `order-1050` | undead-child | parent waits on child `order-1050-box`, which is orphaned |
| `inventory-nightly` | alive | long activity that heartbeats every 2 s with progress |
| `proof-dough` | alive | 90 s timer, then finishes |
| `order-1001..1003` | (completed) | finish normally, so the morgue isn't only bodies |

`order-1047` is the hardest to seed. If it takes more than 45 minutes, drop it, note why in `docs/BUILD_LOG.md`, and keep the rule with a unit test.

`demo/manifest` holds the expected cause per id; `undertaker eval --demo` compares and prints the score. The title number comes from here.

## Look and feel

- Dark, "funeral parlour paperwork". Palette (CSS variables in one `theme.css`): crypt `#0f1211`, slab `#161b19`, mortar `#2a312e`, bone `#e9e4d8`, ash `#8f968f`, ectoplasm `#8be3a0` (the one bright colour). Cause colours: orphaned `#a3a7a3`, lost-activity `#b8b08a`, retry-loop `#d9825f`, heartbeat `#a993e6`, broken-code `#e06666`, changed-code `#e08fb8`, waiting-signal `#e3c46f`, long-sleep `#7fa7d9`, undead-child `#5fbfb3`, alive `#8be3a0`.
- System fonts only: serif headings (`"Iowan Old Style", Palatino, Georgia, serif`), sans body (system UI), mono for ids and commands (`ui-monospace, "SF Mono", Menlo`).
- Toe tags: rounded right edge, a punched hole on the left. Certificates: serif labels, dashed rules.
- Logo: a headstone with an engraved three-step workflow, two steps done and the last one hollow and glowing, with a wisp rising from it (`docs/brand/logo.svg`). Reference page: `docs/brand/theme-preview.html` → `docs/img/theme-preview.png`.
- Copy is short and plain. No emoji, no exclamation marks, no AI-speak. The epitaph is the only joke.

## Limits (say them in the README)

- Tested against the Temporal dev server and Python workers only. Other SDKs' stack traces are shown as text without source lookup.
- No Temporal Cloud / mTLS / API-key login yet.
- Rules are heuristics with thresholds; a slow but healthy workflow can look undead until the thresholds are tuned.
- `waiting-signal` can't know whether the signal is still coming; it says so.
- Poller info in Temporal lags a few minutes after a worker dies.
