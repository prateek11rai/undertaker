# Undertaker · plan (HF26 Week 4, "Ghost in the Machine")

Due **Sun 2026-11-01 12:29 IST** (Sat 23:59 PDT). Written at 00:20 IST by the planner (T3 thread `mlh`). The planner reviews every builder result; the owner only pushes and gives the post a last look.

## What we're entering

**Undertaker** finds the Temporal workflows that will never finish and writes a checked certificate of undeath for each one, using a local Gemma 4 e4b. The repo includes a haunted-bakery demo: a local Temporal dev server and a worker whose workflows are broken on purpose (9 causes), plus healthy and completed ones. Details: `docs/design/spec.md`.

- **Theme fit:** zombie workflows, literally the ghost in the machine. The vocabulary carries the theme (morgue, toe tag, certificate, epitaph, laid to rest), and the facts stay exact.
- **Prize categories:** Best Use of Temporal ($100; about 4 % of the entries we sampled claim it), Best Use of Gemma ($200 featured; crowded, but it's our model anyway). Also eligible for the overall prize on the writing.
- **Field:** of 959 Week 4 entries, none is a Temporal stuck-workflow tool (the closest is a cron-to-n8n "Ghost Workflow Medium"). Scan: `smoker/investigations/2026-10-31-hf26-week4-ghost-in-the-machine-field-scan.md`.

## Who does what

The planner (T3 thread `mlh`) runs this end to end and is the reviewer for every builder result. The owner is not a review step. The owner does one thing: the final `git push` (creating the GitHub repo and making it public at the same time), and then a last look at the post before publishing.

| Phase | Who | Target (IST, Sun 1 Nov) | Output |
|---|---|---|---|
| 0. Setup | planner | done 00:20 | repo, guards, DevRelay for this repo only, docs, logo, theme preview |
| 1. Core build | builder thread `mlh · build-undertaker` (T3, project `undertaker`, Opus 5.5) | 00:30–04:00 | the app, demo, tests, CI, README, build log, `DONE-undertaker-core` |
| 2. Review | planner | as soon as the builder reports | diff, tests run again, demo run, morgue checked in Playwright, leak check; fixes go back to the same builder as a short brief |
| 3. Ship pass | the same builder, brief `docs/design/ship.md` (planner writes it during phase 1) | 04:00–05:30 | banner, DEV cover, social preview, diagrams, screenshots, release notes, post draft. **Images only, no video** |
| 4. Review | planner | 05:30–06:00 | images looked at, post checked against the code and build log |
| 5. Submit | planner | 06:00–06:30 | session curated and submitted (private), DEV draft created (unpublished) |
| 6. Owner | owner | any time before 12:00 | push the repo (public); read the draft; say "publish" (or publish it in DEV); publish the session in DEV's UI |

## Phase 5 and 6 in detail

1. **DevRelay session (planner):** take the builder thread's Claude Code transcript (`~/.claude/projects/-Users-prateek-rai-github-prateek11rai-undertaker/<session>.jsonl`), curate it with the handoff's Appendix A script (redaction plus leak patterns), scan the result, and submit with `devrelay sessions submit --tool claude_code` (with `DEVRELAY_DISABLE_AUTO_UPDATE=1 DEVRELAY_SKILLS_AUTO_SYNC=0` inline; then check `~/.devrelay/update.log` didn't grow). The session starts private, and the owner publishes it in DEV's UI. Only the builder's session is ever submitted, never the planner's.
2. **DEV draft (planner):** through the DevRelay gateway (`create_article`, `published: false`, cover image from the repo, the session embedded), then `get_my_articles {"state":"unpublished"}` to confirm (it says "unavailable" but succeeds). Images use `raw.githubusercontent.com/prateek11rai/undertaker/main/...`, so they appear once the owner has pushed and the repo is public.
3. **Owner:** push the repo and make it public. Then read the draft and either publish it in DEV or tell the planner "publish" (the planner then sets `published: true`). Publish the session in DEV's UI.
4. **After the owner's push (planner, with a yes):** release `v0.1.0` with the banner; repo description, topics and homepage; the README gets the post link in a commit for the owner to push. Owner uploads the social preview in Settings.

## The post (draft in the ship pass)

- **Title candidates** (one concrete number, as past winners do):
  - "9 of my Temporal workflows were never going to finish. A 4B model on my laptop wrote their death certificates"
  - "I built an undertaker for Temporal workflows that won't die, and it runs on Gemma on my laptop"
  - "Zombie workflows: a local Gemma reads my Temporal history and tells me why each one is stuck"
- **Template sections:** What I Built · Demo (screenshots of the morgue and certificates; no video) · Code · How I Built It (rules first, the model second, the checks; diagrams) · Why Does Open Innovation Matter? (workflow histories hold payloads and stack traces point into private code; a hosted model can't see them; a local one can) · My Agent Session (`{% agent_session <id> %}`) · The Spirit of It (what the demo found, told plainly; no invented personal story) · Prize Categories (Temporal, Gemma).
- **Tags:** `devchallenge, hf26challenge, temporal, opensource`.
- **Voice:** plain and first person, about 1,000–1,400 words, honest limits. No AI-speak, emoji or exclamation marks. Never name the employer (a leak pattern). Say "at work" generically if at all.

## Setup facts (done)

- Repo `~/github/prateek11rai/undertaker`, `main`, git identity `165780365+prateek11rai@users.noreply.github.com`.
- `.git/info/leak-check.sh` + `leak-patterns` copied from munshi; `.git/info/exclude` has `.agents/skills/devrelay-*/`, `.claude/settings.local.json`, `.env`, `.worktrees/`.
- 9 `devrelay-*` skills in `.agents/skills/`; `.claude/skills -> ../.agents/skills`.
- DevRelay MCP `devrelay-gateway` registered with **local scope for this repo only**, env `DEVRELAY_SKILLS_DIR=<repo>/.agents/skills`, `DEVRELAY_DISABLE_AUTO_UPDATE=1`. Checked: no `devrelay-*` in the global skill folders, no DevRelay LaunchAgent, `~/.devrelay/update.log` unchanged.
- T3 project `undertaker` so the builder thread runs with this repo as its working directory (this is what makes DevRelay available to it, and puts its transcript under the repo's own Claude project folder).

## Before the builder starts (planner)

- Start Ollama with `brew services start ollama` (Homebrew 0.35.1; do not upgrade). Check that `gemma4:e4b` answers.
- Nothing else is running: Postgres 17 was stopped tonight, and Temporal is started only by `undertaker demo up`.

## Risks and fallbacks

- **`changed-code` seeding is fiddly.** The builder has 45 minutes for it; if it isn't working by then, the rule is kept with a unit test and the demo drops to 8 causes.
- **Gemma rejects too often.** The template certificate is always there, and the eval prints the accepted share honestly.
- **The builder runs late.** The ship pass shrinks to the README banner, the DEV cover and the post draft.
- **CI installs Temporal on the runner with Homebrew.** That is the CI runner, not this Mac, the same way Munshi's CI installed Ollama. The owner's "no Temporal downloads" rule is about this machine. Going ahead with it; the owner can say no.
- **Time:** if the core isn't done by 05:00, the planner cuts scope (watch, changed-code, model CI) and ships what works.

## After the deadline

Check the winners post (the week of Nov 2), then update the vault master note `references/hacktoberfest-2026-dev-challenges.md`.
