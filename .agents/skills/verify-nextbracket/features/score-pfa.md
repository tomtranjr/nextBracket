# Score a PFA

Score a PFA lets an Airman enter age, sex, and component results and read the chart points, the total, and the category on the same page.

## Sub-features

- `score-blank` shows the empty prompt before any result is scored.
- `score-partial` scores the components that have results and withholds the total until all four are present.
- `score-known` shows 84.5 Satisfactory for the documented 27 year old male.
- `score-unstored` shows the empty prompt again after a reload.

## How to get to it (user POV)

- Open the site root. The only page is the calculator.

## Driving it with the Cursor IDE browser

Preconditions:

- `verify.sh doctor` is ok and the browser is on the web URL it printed.
- The form is blank.
- Charts in force are `2026-03-01`.

- **Blank.** Open the page. The heading is `Next Bracket`. `Your score` reads `Enter your age, sex, and one result.`
- **Age and sex.** Fill the `Age` textbox with `27`. Choose the `Male` radio. `Your score` still reads `Enter your age, sex, and one result.`
- **Partial run.** Under `2-mile run`, fill `Minutes` with `15` and `Seconds` with `40`. After scoring settles, `Your score` reads `Enter all four components to see your total.` The Cardio row shows `44 / 50` and `Minimum 19:55 met`. Strength, Core, and Body composition read `Not entered`. The page reads `Charts effective 2026-03-01`.
- **Known score.** Fill `Push-up` with `45` and `Sit-up` with `50`. Choose the `Ratio` radio. Fill `Waist-to-height ratio` with `0.49`. After scoring settles, `Your score` reads `84.5` and `Satisfactory`. Cardio is `44 / 50` and `Minimum 19:55 met`. Strength is `8.5 / 15` and `Minimum 28 met`. Core is `12 / 15` and `Minimum 31 met`. Body composition is `20 / 20` and `Full points`. The page reads `Charts effective 2026-03-01`.
- **Proof.** Save an accessible-name snapshot to `evidence/<run-id>/score-pfa/score.aria.txt` and a screenshot to `evidence/<run-id>/score-pfa/score.png`. The snapshot includes the heading `Next Bracket`. The screenshot shows `84.5` and `Satisfactory`. The browser screenshot tool may write under a temp screenshots directory. Copy that file into the evidence path.
- **Unstored.** Reload the page. `Your score` reads `Enter your age, sex, and one result.` Save `evidence/<run-id>/score-pfa/reloaded.aria.txt`.

## Gotchas

- A blank minutes or seconds box counts as 0. Seconds above 59 are an error, not a time.
- Body composition starts on `Waist and height`. The known 0.49 case uses the `Ratio` radio. Leaving the mode on measurements and typing `0.49` into the waist box does not score 0.49.
- `Your score` can show `Scoring...` for a moment, and longer on the first call while the API wakes. Read the score only after that text is gone.
- Age and sex start blank on purpose. A result with either one missing does not score.
- The `I am AFSPECWAR/EOD` checkbox switches the chart. Leave it unchecked for this recipe.
- `next dev` can show a Next.js issue badge. Read `Your score` anyway. The badge is not the score.
- Reloading discards the score because the page keeps inputs in memory only. The empty prompt is the expected second view.
