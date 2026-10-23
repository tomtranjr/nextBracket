# Waist-to-height truncation

Waist-to-height truncation shows the ratio the chart will score, cut to two decimals, when the Airman types extra digits or enters waist and height.

## Sub-features

- `whtr-ratio` truncates a typed ratio that has more than two decimals.
- `whtr-inches` truncates waist divided by height and shows both the longer ratio and the scored value.

## How to get to it (user POV)

- On the calculator page, in `Body composition`, choose `Ratio` or `Waist and height`.
- The section starts on `Waist and height`.

## Driving it with the Cursor IDE browser

Preconditions:

- `verify.sh doctor` is ok and the browser is on the web URL it printed.
- Age is `27` and `Male` is selected, so a ratio can score.
- Body composition is on `Waist and height` and both inch boxes are empty.

- **Inches.** Fill `Waist (inches)` with `39.5` and `Height (inches)` with `72`. The page reads `Ratio 0.5486, scored as 0.54. The ratio is truncated to two decimals (DAFMAN 36-2905, para 3.15.4.2).` After scoring settles, Body composition shows `15 / 20`.
- **Ratio.** Choose the `Ratio` radio. The inch boxes are gone and `Waist-to-height ratio` is empty. Fill it with `0.5486`. The page reads `Scored as 0.54. The ratio is truncated to two decimals (DAFMAN 36-2905, para 3.15.4.2).`
- **Proof.** Save an accessible-name snapshot to `evidence/<run-id>/whtr-truncation/ratio.aria.txt` and a screenshot to `evidence/<run-id>/whtr-truncation/ratio.png`. Both show `Scored as 0.54` and `Next Bracket`.

## Gotchas

- Switching between `Waist and height` and `Ratio` clears the other entry. Check the inches note before choosing `Ratio`.
- A ratio that already has two decimals or fewer, such as `0.54` or `0.5`, does not show the `Scored as` line.
- The inches note always shows once both boxes parse, including when the third decimal is already zero.
- The scored hundredths are what the API receives. Proof is the note on the page, not a rounded display of the raw division.
- DAFMAN 36-2905 para 3.15.4.2 truncates. A note that says the value was rounded fails this recipe.
