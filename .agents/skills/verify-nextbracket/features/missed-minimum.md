# Missed component minimum

Missed component minimum shows 0 points and a miss note when a result is past the chart minimum for that component.

## Sub-features

- `minimum-miss` shows the miss for a push-up count one step under the minimum.
- `minimum-met` shows the minimum met when the count is raised to the chart minimum.

## How to get to it (user POV)

- On the calculator page, enter age, sex, and a `Push-up` count.
- The strength event defaults to `Push-up`. `Hand-release push-up` is the other radio.

## Driving it with the Cursor IDE browser

Preconditions:

- `verify.sh doctor` is ok and the browser is on the web URL it printed.
- The form is blank.
- `I am AFSPECWAR/EOD` is unchecked.

- **Miss.** Fill `Age` with `27`. Choose `Male`. Fill `Push-up` with `25`. After scoring settles, `Your score` reads `Enter all four components to see your total.` The Strength row shows `0 / 15` and `Minimum 28 missed by 3`. There is no total and no category.
- **Meet.** Change `Push-up` to `28`. The Strength row shows `2.5 / 15` and `Minimum 28 met`.
- **Proof.** Save an accessible-name snapshot of the miss, before changing the count to 28, to `evidence/<run-id>/missed-minimum/miss.aria.txt` and a screenshot to `evidence/<run-id>/missed-minimum/miss.png`. Both show `Minimum 28 missed by 3` and `Next Bracket`.

## Gotchas

- The total stays hidden until all four components have results. A miss on push-ups alone does not show a category. The proof is the Strength row.
- The minimum for this age and sex is 28. Another age band has a different minimum. Age must stay 27.
- `Hand-release push-up` uses a different chart. This recipe stays on `Push-up`.
- Points under the minimum are 0 even when a lower chart row exists. A Strength row that shows points above 0 for 25 push-ups fails this recipe.
