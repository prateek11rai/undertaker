![undertaker: finds the Temporal workflows that will never finish, and tells you why](docs/img/banner.png)

Undertaker finds the Temporal workflows that will never finish, sorts each one into a cause using Temporal's own data, and writes a checked **certificate of undeath** for it.
Gemma 4 runs on your laptop through Ollama and writes the words; plain code makes the diagnosis and checks every fact the model cites.

![The morgue: one toe tag per running workflow, coloured by cause](docs/img/morgue.png)

## Why local

Workflow histories hold real payloads (orders, customers, card errors), and stack traces point into private code. Sending them to a hosted model to ask "why is this stuck" is the thing most teams can't do. A 4B open model on your own machine can. Undertaker talks to your Temporal server and to Ollama on localhost, and nothing else: no telemetry, no CDN, no web fonts.

## The demo in 60 seconds

You need macOS with Homebrew, `uv`, the Temporal CLI (`brew install temporal`) and, for model certificates, Ollama with `gemma4:e4b`.

```sh
uv sync
uv run undertaker demo up      # local dev server + a worker full of broken bakery workflows
uv run undertaker sweep        # wait ~30 s first
uv run undertaker serve --source src/undertaker/demo   # the morgue on http://127.0.0.1:8666
uv run undertaker demo down    # stops everything it started
```

The demo is a made-up bakery with one zombie per cause, two healthy workflows and three finished orders. While it is up, Undertaker uses short demo thresholds (`--quiet 20s --attempts 3`) by itself. `--source` lets certificates quote the function around each stack frame.

![undertaker sweep: ten undead workflows, each with its cause, and two alive](docs/img/sweep.png)

## Causes of undeath

![Nine causes of undeath, each with its rule and remedy](docs/img/diagrams/causes.png)

| Cause | Shown as | Rule |
|---|---|---|
| `orphaned` | No one is listening | Workflow task scheduled, never started, for longer than `--quiet`, and no poller on its task queue within `--poller-window` |
| `lost-activity` | Sent to a worker that never came | Activity scheduled for longer than `--quiet`, no poller on that activity's task queue |
| `broken-code` | Its own code keeps killing it | Workflow task attempt ≥ 2 and the last `WorkflowTaskFailed` is a plain error |
| `changed-code` | Its code changed while it slept | The same, but the failure is non-determinism (`TMPRL1100`) |
| `heartbeat` | Stopped breathing | Activity attempt ≥ `--attempts`, last failure a heartbeat timeout |
| `retry-loop` | Dies and rises, forever | Activity attempt ≥ `--attempts`, a real failure, no retry maximum in sight |
| `undead-child` | Waiting on an undead child | A pending child workflow that is itself undead |
| `long-sleep` | Asleep for a very long time | An open timer longer than `--long-sleep` |
| `waiting-signal` | Waiting for a visitor who never comes | Nothing pending at all and the last event older than `--quiet`; lists the signal names the worker reports |
| `alive` | Alive | None of the above, with the reason ("heartbeat 3 s ago", "timer fires in 40 s") |

The first matching rule wins, in this order. Every remedy comes with the exact `temporal` command, with your `--address` and `--namespace` filled in.

## How it works

![How Undertaker works: Temporal, evidence, rules, cause, Gemma, checks, morgue; all on your machine](docs/img/diagrams/how-it-works.png)

1. **Code diagnoses.** A sweep lists running workflows, then reads `describe`, the history (cached by last event id) and the `DescribeTaskQueue` pollers. Fixed rules, in a fixed order, pick the cause and collect evidence: event ids, attempts, failures, stack frames, poller counts. For `waiting-signal` it asks the worker's built-in `__temporal_workflow_metadata` query for signal names.
2. **The model explains.** Gemma 4 e4b gets the cause, the rule, the evidence and (with `--source`) the function around each frame, read only from files inside your source folder. It answers in an Ollama JSON schema: headline, diagnosis, cited evidence keys, next step and an epitaph.
3. **Code checks the model.** One retry with the reasons, then a plain template. The page always says which one you are reading.
4. **Commands come from code.** The model never writes commands.

## Certificates and checks

![A certificate of undeath for a retry loop, naming activities.py line 12](docs/img/certificate-retry-loop.png)

![How a certificate is checked: what the model gets, its JSON answer, seven checks, the retry and the fallback](docs/img/diagrams/certificate-checks.png)

The checks, all in code:

- every cited evidence key exists;
- every number in the text appears in the evidence;
- every `code span`, file name, `file:line`, activity or signal name appears in the evidence or the source excerpt;
- no other cause is named;
- no commands or URLs;
- the lengths hold (headline 12 words, diagnosis 70, next step 30, epitaph 14);
- the epitaph has no digits and no identifiers.

Failure messages reach the model inside `<data>` tags as data, and all model text is HTML-escaped before it reaches the page.

More certificates: [changed code](docs/img/certificate-changed-code.png) · [waiting for a signal](docs/img/certificate-waiting-signal.png) · [undead child](docs/img/certificate-undead-child.png).

## Commands

```
undertaker sweep [--json]            table: id, type, cause, undead for, key fact
undertaker inspect <workflow-id>     the certificate as text
undertaker serve [--allow-actions]   the morgue on 127.0.0.1:8666
undertaker watch [--once]            sweep every minute; one macOS notification per new undead
undertaker demo up | down | status   local dev server + demo worker + scenarios
undertaker eval --demo               found / missed / false alarms, model accepted / fallback, seconds
undertaker doctor                    Temporal reachable, Ollama reachable, model present, versions
```

## Flags

| Flag | Default | |
|---|---|---|
| `--address` | `127.0.0.1:7233` | Temporal frontend |
| `--namespace` | `default` | |
| `--quiet` | `10m` | how long something may sit before it counts |
| `--attempts` | `5` | activity attempts before a retry counts as a loop |
| `--poller-window` | `2m` | how recent a poller must be |
| `--long-sleep` | `7d` | timers longer than this are a long sleep |
| `--source PATH` | none | folder with your workflow code, for excerpts |
| `--model` | `gemma4:e4b` | Ollama model |
| `--ollama` | `http://127.0.0.1:11434` | Ollama URL |
| `--no-model` | off | template certificates only |
| `--allow-actions` | off | `serve` only: enables Lay to rest (terminate) and Resurrect (reset), each with a confirm |
| `--every` | `30s` serve, `60s` watch | sweep interval |
| `--demo` | off | `--quiet 20s --attempts 3` (automatic while the demo is up) |

Every flag has an `UNDERTAKER_*` environment variable (`UNDERTAKER_QUIET=5m`).

Undertaker is read-only unless you pass `--allow-actions`. The action endpoints also require a custom header, so another page in your browser can't trigger them.

## Measured on the demo

From `uv run undertaker eval --demo --source src/undertaker/demo`, two runs on a fresh demo (details in [docs/BUILD_LOG.md](docs/BUILD_LOG.md)):

| | Run 1 | Run 2 |
|---|---|---|
| Undead found by the rules | 10/10 | 10/10 |
| Missed | 0 | 0 |
| False alarms | 0 | 0 |
| Alive and right | 2/2 | 2/2 |
| Gemma certificates accepted on the first try | 10/10 | 10/10 |
| Fell back to the template | 0 | 0 |
| Seconds per certificate | 8.4 | 7.6 |

On an Apple Silicon Mac with `gemma4:e4b` on Ollama 0.35.1. These are ten made-up workflows, built on purpose to match the rules, so treat them as a smoke test rather than a benchmark. The rejection path is covered by unit tests.

## Limits

- Tested against the Temporal dev server and Python workers only. Other SDKs' stack traces are shown as text without source lookup.
- No Temporal Cloud, mTLS or API-key login yet.
- Rules are heuristics with thresholds; a slow but healthy workflow can look undead until the thresholds are tuned.
- Temporal keeps only the last failure of a retrying activity, so `retry-loop` can't prove every attempt failed the same way.
- `waiting-signal` can't know whether the signal is still coming; it says so.
- Poller info in Temporal lags a few minutes after a worker dies.
- `--source` reads only regular files inside the folder you give; it refuses `..` and symlinks out.

## Development

```sh
uv run ruff check && uv run ruff format --check && uv run pytest
uv run pytest -m temporal   # needs /opt/homebrew/bin/temporal
uv run pytest -m model      # needs Ollama with gemma4:e4b
```

Build notes and decisions: [docs/BUILD_LOG.md](docs/BUILD_LOG.md). Design: [docs/design/spec.md](docs/design/spec.md). How the images are made: [docs/brand/README.md](docs/brand/README.md).

## Built for Hacktoberfest 2026

Built for the DEV [Hacktoberfest Open-Source AI Challenge, Week 4: Ghost in the Machine](https://dev.to/challenges/hacktoberfest-week4-2026-10-26). The post: [10 of my Temporal workflows were never going to finish](https://dev.to/prateek11rai/10-of-my-temporal-workflows-were-never-going-to-finish-a-4b-model-on-my-laptop-wrote-their-death-45f6)

## After the deadline

## Credits

- [Temporal](https://temporal.io), the open-source durable execution platform, and its Python SDK and CLI.
- [Gemma 4](https://ai.google.dev/gemma) (`gemma4:e4b`), run locally through [Ollama](https://ollama.com).
- FastAPI, Uvicorn, Jinja2 and Pydantic.

## License

MIT. See [LICENSE](LICENSE).
