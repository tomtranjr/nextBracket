# Next Bracket verification map

This directory is the maintained source for verifying the user-facing behavior of Next Bracket. Read the index before driving the app, then use the matching feature file as the recipe.

## Baseline preconditions

- Launch with `.agents/skills/verify-nextbracket/verify.sh start` and require `verify.sh doctor` to pass.
- Open the web URL doctor prints. Do not open a different port.
- The form starts blank. There is no seed data and no login.
- The standards in force are charts `2026-03-01`.
- Never drive an instance that was not started by this verification run.

## Driving conventions

- Start every recipe from the blank form unless its preconditions say otherwise.
- Prefer ARIA roles and accessible names over CSS selectors or DOM position.
- The form scores on its own about 300 ms after a change. Wait until `Your score` is not `Scoring...`.
- Reload the page to return to the blank form. Nothing is stored, so there is no fixture to reset.
- Keep proof files. Cleanup removes the server, not the evidence directory.

## Proof and skip reporting

- Capture the user action and the resulting state, not only the final screen.
- UI proof includes an accessible-name snapshot and a screenshot of the resulting score or plan. The snapshot includes the `Next Bracket` heading. Copy the screenshot into the evidence folder if the tool stores it elsewhere.
- A score proof includes the total or the partial-total sentence, the component notes, and `Charts effective 2026-03-01`.
- A plan proof includes the option lines and each `Projected total`.
- Record the feature ID and entry point used with every artifact.
- Report an unreachable path with the attempted action and the unmet precondition.
- Do not report a skipped entry point as verified through a different path.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then uses exactly four H2 sections in this order.

1. `Sub-features` lists short IDs with one line for each behavior.
2. `How to get to it (user POV)` lists every user entry point.
3. `Driving it with the Cursor IDE browser` starts with `Preconditions:` and uses labeled bullets that pair each user action with an exact control and observable result.
4. `Gotchas` lists traps that can waste or invalidate a verification run.

## Features

- [Score a PFA](./score-pfa.md) covers the blank form, a partial score, and the known 84.5 satisfactory score.
- [Plan a target](./plan-target.md) covers the Excellent preset and the options that reach 90 from that score.
- [Waist-to-height truncation](./whtr-truncation.md) covers ratio entry and waist-and-height entry.
- [Missed component minimum](./missed-minimum.md) covers a push-up count below the chart minimum.
