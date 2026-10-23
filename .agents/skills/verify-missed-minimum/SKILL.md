---
name: verify-missed-minimum
description: "Prove that a missed PFA component minimum scores 0 points and makes a complete test Unsatisfactory, on every chart row in scope. Use when changing scoring.py, standards lookup, the standards JSON, or categorize."
---

# Verify a missed component minimum

A result that misses a component minimum scores 0 on that component. On a complete test the category is Unsatisfactory, including when the total would otherwise be Satisfactory or Excellent. A result exactly on the minimum meets it and keeps that chart row's points.

Harm if this breaks: an Airman who failed a component can be shown points for it, or a Satisfactory or Excellent total.

## When a change needs this check

Run the check when a change touches any of these. The sync commit is the last commit at which this check was confirmed to describe that code.

- `backend/app/core/scoring.py`: `score_event`, `calculate_score`, `categorize`, `_meets`
- `backend/app/core/standards.py`: `find_table`
- `backend/app/models.py`: `EventTable`, `Profile`, `Results`, `ScoreReport`, `StandardsFile`
- `backend/data/standards/*.json`

Sync commit: `c50ad984521aea8c665da5a283814ca17693a217`

If the covered files differ from that commit, the check may be stale. After you confirm the script still describes the code at the new commit, update the sync commit in this file to that commit. Do not move it forward only because the check passed on an old reading of the code.

## Run

From the repo root, with the backend virtualenv:

```bash
cd backend && uv run python ../.agents/skills/verify-missed-minimum/check_missed_minimum.py
```

Exit 0 prints one line per standards file, with the number of `score_event` results and complete scores checked. Exit 1 prints `failed:` and one counterexample: the chart version, age, sex, event, result, and what came back instead of 0 points or Unsatisfactory. The run is a few seconds. Python 3.13 and `uv` are the tools. No extra package.

On `2026-03-01.json` a passing run checks 34759 `score_event` results and 259 complete scores. A later standards file can change those counts. A run that checks nothing is a failure.

## What is in scope

Every `*.json` file in `backend/data/standards/`. For each table that has a component minimum (cardio, strength, and core; not body composition):

- Every integer result from 0 through one past the farther of the top-row threshold and the minimum, passed to `score_event`.
- A complete `calculate_score` at each end of the age band that a profile can hold (ages 17 through 70). The failing event is one step past its minimum. Every other component is at the top row of the same sex and age.
- The same complete score for an AFSPECWAR/EOD profile, age 40, sex F, for each event listed in `afspecwar_eod`. Those events use the male under-25 table. Body composition still uses her own sex and age.
- `categorize(90, passing total, missed)` and `categorize(passing total, passing total, missed)` are Unsatisfactory.

A step past the minimum is one rep or one second on the failing side. Higher-is-better events step down. The 2-mile run and the other lower-is-better events step up.

## What is out of scope

- Body composition. It has no component minimum.
- The 2 km walk. A walk fail is Unsatisfactory by a separate rule, and a walk pass cannot be Excellent. This check does not build a walk result.
- Which bracket a result earns when it is strictly better or worse than the minimum row, except that a miss is 0 and the exact minimum keeps that row's points.
- Planning, the website, and truncation of the waist-to-height ratio.
- Ages outside 17 through 70, and negative results. `Profile` and `Results` reject those.

A pass covers those inputs on the shipped charts. It does not cover a chart that is not in `backend/data/standards/`.

## A failure versus a modeling error

`failed:` followed by points, a category, or a gap is a finding in the product code. Report it. Do not change the property or the script to make that case pass, and do not change product code unless the user asks.

`checker built an illegal result` means the script paired two events in one component or left a component empty. That is a modeling error in the script. Fix the script so the result is one event per component. Do not weaken the property.

`resolved to a different table` means `find_table` did not return the band the script selected, for an age inside that band. Treat that as a product finding in lookup.

`checked nothing` means the standards file has no minimums the script could see. Treat that as a modeling error until you confirm the file really has no component minimums.

## Tool

The check enumerates the real functions. The legal results are bounded integers and the charts are finite, so enumeration covers every case in the bounds above. A model checker would be a second copy of the charts. The repo does not already depend on an SMT verifier, and this script adds none.
