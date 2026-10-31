# Undertaker · ship pass (images, README, release notes, post draft)

> Second brief for the builder thread `mlh · build-undertaker`, sent by the planner after the core review. The planner appends answers at the bottom. Don't edit this file.

Same repo, same branch (`main`), same rules as `docs/design/build-brief.md`. Target: done by **05:30 IST**. **Images only, no video** anywhere (README, post, release).

## Read first

`docs/design/spec.md`, `README.md`, `docs/BUILD_LOG.md` (the eval numbers), `src/undertaker/morgue/static/theme.css`, `src/undertaker/morgue/static/logo.svg`, `docs/brand/theme-preview.html`.

## You own these files

`docs/brand/**`, `docs/img/**`, `README.md`, `docs/release-notes-v0.1.0.md`, `docs/devto-post.md`. Only touch code if a screenshot shows a real UI bug; then fix it in its own commit, with tests still passing, and say so in the report.

## Rendering

Make each image as an HTML page in `docs/brand/` in the app's own colours and fonts (system fonts only; pages load nothing from the network). Render with a small `docs/brand/render.cjs` (Playwright + the installed Google Chrome, `channel: "chrome"`, abort every non-`file:` request, exact viewport, device scale 1 for the committed file; check one 2x render for crispness in `/tmp`). Playwright is available without installing anything: `NODE_PATH=<node_modules> node docs/brand/render.cjs` (the planner gives you the real folder in a message; never write it into a file). Don't run npm or npx installs. Document the command in `docs/brand/README.md` with `<node_modules>` instead of the real path. **Look at every PNG yourself before committing.**

## Make, in order

1. **Screenshots of the real app** (Playwright on http://127.0.0.1:8666 with `demo up` running, viewport 1440 wide, device scale 2, page only, never the desktop) into `docs/img/`: `morgue.png` (all toe tags), `certificate-retry-loop.png` (with `--source`, showing the file and line), `certificate-changed-code.png` (or broken-code), `certificate-waiting-signal.png`, `certificate-undead-child.png`. Plus `sweep.png`: the `undertaker sweep` table rendered as a terminal-styled HTML page from real output (copy the real text; don't invent rows).
2. **README banner** `docs/img/banner.png`, 1280 × 400: logo left, "undertaker" in the serif, tagline "Finds the Temporal workflows that will never finish, and tells you why", small line "Local Gemma 4 · read-only by default · nothing leaves your machine". A faint row of headstones or toe tags in the background is fine; keep it calm.
3. **DEV cover** `docs/img/devto-cover.png`, 1000 × 420. Link previews crop it to 1200 × 627 proportions (about 10 % off each side), so keep the logo, name and tagline inside the middle 80 % of the width.
4. **GitHub social preview** `docs/img/social-preview.png`, 1280 × 640: like the banner, plus a slightly tilted crop of `morgue.png` on the right.
5. **Diagrams** (DEV can't render Mermaid), 1600 px wide, readable at 800 px, same look, into `docs/img/diagrams/`:
   - `how-it-works.png`: Temporal server (list, describe, history, task-queue pollers) → evidence → rules → cause → certificate (Gemma 4 e4b via Ollama → checks → accepted, or template) → morgue and CLI. Mark the machine boundary: nothing crosses it.
   - `causes.png`: the nine causes as a cheat sheet: colour chip, name, one-line rule, one-line remedy.
   - `certificate-checks.png`: what the model gets, its JSON, each check, the retry, the fallback.
6. **README polish:** banner first (relative path `docs/img/banner.png`), then the two-line pitch, the morgue screenshot, a 60-second demo start, the causes image or table, how it works (the diagram), certificates and checks, commands and flags, the real eval numbers from `docs/BUILD_LOG.md`, limits, "Built for Hacktoberfest 2026" with the challenge link and a `{{POST_URL}}` placeholder, an empty "After the deadline" section, credits (Temporal, Gemma 4 via Ollama), license. Relative image paths only.
7. **Release notes** `docs/release-notes-v0.1.0.md`: what it does, demo in 60 seconds, the causes, read-only by default, the measured numbers, limits, credits.
8. **Post draft** `docs/devto-post.md` (below).
9. Commit in small commits after the leak check (`bash .git/info/leak-check.sh`), noreply identity, `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## The post draft

Front matter: three candidate titles in an HTML comment above `title:`; each names one concrete outcome or number from the eval, e.g. "9 of my Temporal workflows were never going to finish. A 4B model on my laptop wrote their death certificates". Then `published: false`, `tags: devchallenge, hf26challenge, temporal, opensource`, `cover_image:` left empty (the planner sets it).

First line, exactly: `*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 4: Ghost in the Machine](https://dev.to/challenges/hacktoberfest-week4-2026-10-26)*`

Sections, in this order:
- **What I Built:** the problem (workflows that stay "Running" forever and nobody knows why), how I read the theme (zombie workflows, literally a ghost in the machine), what Undertaker does.
- **Demo:** the screenshots, with one-line captions. No video.
- **Code:** `{% github prateek11rai/undertaker %}`.
- **How I Built It:** rules first, the model second; the nine causes (the cheat-sheet image); the certificate checks (the image); Temporal APIs used (list, describe, history, `DescribeTaskQueue`, the metadata query); Gemma 4 e4b on Ollama with a JSON schema; the haunted-bakery demo and how each zombie is made; the eval numbers.
- **Why Does Open Innovation Matter?:** histories hold real payloads and stack traces point into private code; teams can't paste those into a hosted model; a 4B open model on the laptop can read them; Temporal itself is open source, so the whole loop is inspectable; read-only by default.
- **My Agent Session:** `{% agent_session {{SESSION_ID}} %}` and one sentence on the planner/builder split (a planner thread wrote the spec and reviewed; this builder session wrote the code).
- **The Spirit of It:** short and true: what it felt like when the morgue first listed every zombie with its cause; the epitaphs Gemma wrote for them (quote two real ones from the demo run). No invented personal story.
- **Prize Categories:** Best Use of Temporal, Best Use of Gemma.

Voice: first person, plain, specific, short paragraphs, about 1,000–1,400 words. No AI-speak ("delve", "seamless", "game-changer", "leverage"), no emoji, no exclamation marks, no em-dash chains. Every claim and number must match the code and `docs/BUILD_LOG.md`. Images use `https://raw.githubusercontent.com/prateek11rai/undertaker/main/docs/img/<file>`. Never mention an employer.

## Report when done

Commits, every PNG with its size, the three title candidates, placeholders left, and anything you'd change with more time. Send it to the planner (`t3_thread_send`, thread `mcp:d6d84144-d1b5-442b-82e6-d79b07028f77`, mode `queue`), end with exactly `DONE-undertaker-ship` on its own line, and stop. Leave nothing running.

## Answers

(The planner adds answers here.)
