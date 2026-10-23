---
name: verify-nextbracket
description: "Drive the Next Bracket website, the local PFA calculator and planner, against a disposable API and capture proof of a score or plan. Use when a change touches the calculator, planner, score form, or how the site and API start locally."
---

# Verify Next Bracket

Next Bracket is a stateless website. The user types age, sex, and PFA results. The page scores them live against the local API. Nothing is stored. The primary surface is the website at the URL `verify.sh doctor` prints. The API on its own port is the second surface: `/health`, `/score`, `/plan`, `/standards`, `/versions`. Policy chat is not built. The 2 km walk is scored by the API only. The website has no walk field.

## Launch

From the repo root:

```bash
.agents/skills/verify-nextbracket/verify.sh start
```

This starts one API and one website on free ports at `127.0.0.1`, in a new session so they keep running after the launcher exits. Stop is what ends them. The API is `uv run uvicorn app.main:app` from `backend/`. The website is `npm run dev` from `frontend/`, with `NEXT_PUBLIC_API_URL` set to that API and `NEXTBRACKET_CORS_ORIGINS` set to that website origin. Standards load from `backend/data/standards/`. There is no database, migration, or seed. A blank form is the usable state.

Ready means both of these are true:

- `GET /health` returns `{"status":"ok"}` and the known score below returns total `84.5`, category `satisfactory`, version `2026-03-01`.
- The website responds and its HTML contains `Next Bracket`. The form itself is rendered in the browser. Doctor does not prove the form until a drive does.

The known score is a 27 year old male, 2-mile run 15:40 (940 seconds), 45 push-ups, 50 sit-ups, waist-to-height ratio 0.49 (sent as `49`).

`frontend/.nvmrc` asks for Node 24. If `~/.nvm/nvm.sh` exists, start uses it. Doctor prints the Node it actually ran. A different Node does not fail doctor. Prefer 24 when it is installed.

A second instance needs a different directory:

```bash
VERIFY_NEXTBRACKET_RUN_DIR=/tmp/verify-nextbracket-b .agents/skills/verify-nextbracket/verify.sh start
```

Starting again in the same run directory, while the recorded PIDs are alive, exits with an error. Do not drive `localhost:3000` or `localhost:8000` unless doctor printed those ports for this run.

## Doctor

Run this first whenever a drive looks wrong:

```bash
.agents/skills/verify-nextbracket/verify.sh doctor
```

It checks the recorded PIDs, that `/health` is ok, that the known score is still `84.5` satisfactory on charts `2026-03-01`, that the website HTML contains `Next Bracket`, and that the API port is listened on by the PID this run started (or its child). It prints the web URL to open. If doctor fails, read `.agents/skills/verify-nextbracket/run/api.log` and `web.log`. Do not drive a failed instance.

## Drive

Open the web URL from doctor in the Cursor IDE browser. Use accessible names. Do not use coordinates.

The form never submits. It scores about 300 ms after a change. Wait until `Your score` leaves `Scoring...` before reading it.

Handles, from the page:

- Heading `Next Bracket`.
- Textbox `Age`. Placeholder `17 to 70`.
- Radios `Male` and `Female` in the `Sex` group (`name="sex"`).
- Checkbox `I am AFSPECWAR/EOD`.
- Cardio defaults to `2-mile run`. Textboxes `Minutes` and `Seconds` sit under that legend. Their placeholders are `15` and `40`.
- Textbox `Push-up`, placeholder `Reps`.
- Textbox `Sit-up`, placeholder `Reps`.
- Body composition defaults to `Waist and height`. Radios `Waist and height` and `Ratio` are in the `Enter` group (`name="whtr-mode"`).
- Textboxes `Waist (inches)` and `Height (inches)`, or, after `Ratio`, textbox `Waist-to-height ratio`.
- Region `Your score` (`aria-labelledby="result-heading"`).
- Region `Reach a target`. Textbox `Target total`. Buttons `Satisfactory (75)` and `Excellent (90)`.

Empty `Your score` text: `Enter your age, sex, and one result.`

Partial text, once one result exists and a component is still empty: `Enter all four components to see your total.`

A component row shows `points / max` and a note. A met minimum reads `Minimum <value> met`. A miss reads `Minimum <value> missed by <gap>`. Body composition with full points reads `Full points`. The chart line reads `Charts effective 2026-03-01`.

There is no saved record to read back. Reloading the page returns the empty prompt. That empty prompt is the proof that the run stored nothing.

## Evidence

Write proof under the `EVIDENCE_DIR` doctor prints, one folder per feature id, for example `evidence/<run-id>/score-pfa/`. Capture the action and the resulting state:

- The accessible-name snapshot after the action, written into that folder by the agent.
- A screenshot of the same state. Copy it into that folder if the screenshot tool stores it outside the repo.
- For a score, the total line and the component notes, not only the screenshot.
- For a plan, the option lines and `Projected total`.

The page title is `Next Bracket`. A viewport may not fit the heading and the score together. The snapshot carries the heading. The screenshot carries the score.

The API stores nothing and writes no user row. Do not treat a test-only endpoint as the proof. `/score` in doctor only checks that this instance is the right build. The feature proof is the page.

## Cleanup

```bash
.agents/skills/verify-nextbracket/verify.sh stop
```

Stop kills the recorded website PID and API PID, then their child processes, then removes the run directory (`.agents/skills/verify-nextbracket/run/` unless `VERIFY_NEXTBRACKET_RUN_DIR` is set). It does not delete `.agents/skills/verify-nextbracket/evidence/`. After stop, confirm the evidence files are still there and doctor says no instance is recorded.

## Helpers

`.agents/skills/verify-nextbracket/verify.sh` is the only helper. Commands: `start`, `doctor`, `stop`.
