# Plan a target

Plan a target lets an Airman set a total and read ways to reach it from the same results as the calculator.

## Sub-features

- `plan-hint` says what is missing before a plan can run.
- `plan-preset` fills the target from the Excellent button.
- `plan-known` lists ways to reach 90 from the known 84.5 score.

## How to get to it (user POV)

- On the calculator page, use the `Reach a target` section under `Your score`.
- Choose `Excellent (90)` or type a target in `Target total`.
- `Satisfactory (75)` is the other preset.

## Driving it with the Cursor IDE browser

Preconditions:

- `verify.sh doctor` is ok and the browser is on the web URL it printed.
- The known score in [Score a PFA](./score-pfa.md) is showing: age 27, Male, run 15:40, 45 push-ups, 50 sit-ups, ratio 0.49, total 84.5 Satisfactory.
- `Target total` is empty.

- **Hint before a target.** With the known score showing and `Target total` empty, `Reach a target` reads `Enter a target.`
- **Excellent preset.** Choose the `Excellent (90)` button. `Target total` shows `90`. After planning settles, the page does not read `Enter a target.` or `Working out your options.`
- **Options.** Under `Change one event`, the page shows `2-mile run: 15:40 to 13:54 (44 to 49.5 points)` and `Push-up: 45 to 60 (8.5 to 14 points)`, each with `Projected total 90`. Under `Quick wins`, it shows `2-mile run: 15:40 to 14:13 (44 to 49 points)` and `Push-up: 45 to 46 (8.5 to 9 points)`, with `Projected total 90`. Under `Balanced`, it shows `2-mile run: 15:40 to 14:51 (44 to 47 points)`, `Push-up: 45 to 49 (8.5 to 10 points)`, and `Sit-up: 50 to 52 (12 to 13 points)`, with `Projected total 90`.
- **Proof.** Save an accessible-name snapshot to `evidence/<run-id>/plan-target/plan.aria.txt` and a screenshot to `evidence/<run-id>/plan-target/plan.png`. Both show `Reach a target`, `13:54`, `14:13`, and `Projected total 90`.

## Gotchas

- The planner uses the same age, sex, and results as the calculator. An empty calculator reads `Enter your age and sex.` A calculator with age and sex but no result reads `Enter at least one result.`
- A component left blank is planned from its minimum. The page then says `No result for ...` and `It starts from the minimum.` This recipe enters all four components, so that note must be absent.
- `Working out your options.` is the pending state. Read the options only after it is gone.
- Quick wins is not labeled easiest. The heading is `Quick wins`.
- A target the member already meets does not list options. 90 is above 84.5, so this recipe lists options.
