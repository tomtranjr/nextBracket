# Golden chart cases

Each row is one result for one member and the points the printed chart gives.

- `chart_cases.csv`: 17 columns of the 2026-03-01 charts, read by eye from the rendered PDF pages. For every printed row the cases are on the threshold, one worse, and one better.
- `age_edges.csv`: results on both sides of an age band edge, and the youngest and oldest ages.
- `walk_cases.csv`: the 2 km walk, pass/fail. Each sex and band at the maximum time (pass) and 1 second over (fail), both sides of every band edge (29/30, 39/40, 49/50, 59/60), and AFSPECWAR/EOD members (they keep their own sex and age row). Times were typed from charts page 11, which matches DAFMAN 36-2905 Table 3.1.
- `afspecwar_eod_cases.csv`: AFSPECWAR/EOD members score the male under-25 push-up and run tables. WHtR keeps their own sex and age.

Columns: `minimum_met` is empty when the event has no component minimum (WHtR).

The expected values did not come from `data/standards/*.json`. They were transcribed from the PDF, then diffed against the JSON (no differences). Push-up, male, 30-34 follows the printed table: 26 earns 3.0 and 25 misses the minimum.
