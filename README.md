# Farkle EV Simulator

A Monte Carlo simulator for the dice game Farkle, built to answer two
questions: **for a given turn score and number of dice left to roll, is it
worth rerolling, or should you bank? And which dice should you actually save
when you do reroll?**

Open `web/index.html` directly in a browser to see the results (no server
needed; the data is inlined, not fetched).

## The ruleset

This implements the most common "standard" Farkle scoring table. House rules
vary a lot, so if yours differs, `farkle/rules.py` is a single small file:
change the constants and re-run `export_web.py`.

| Roll | Points |
|---|---|
| Single 1 | 100 |
| Single 5 | 50 |
| Three of a kind (face *v*) | 1000 if *v*=1, else *v* x 100 |
| Four of a kind | 2x the three-of-a-kind value |
| Five of a kind | 4x the three-of-a-kind value |
| Six of a kind | 8x the three-of-a-kind value |
| Straight (1-2-3-4-5-6) | 1500 |
| Three pairs | 1500 |
| Two triplets (two different faces) | 2500 |

A roll that scores nothing is a **Farkle**: the entire turn score is lost and
the turn ends immediately. A roll where every remaining die scores is **hot
dice**: the player may reroll a fresh six dice, keeping the turn score built
up so far.

`ENTRY_THRESHOLD` (500, to get "on the board") and `WINNING_SCORE` (10,000)
are documented in `rules.py` but **not used** by the core optimizer; see
[Scope](#scope--known-simplifications) below.

## What it computes

**1. Reroll vs. bank.** For each dice-remaining state *d* in {1..6}, there's
a turn score *s* at which rerolling and banking have equal expected value:
below it, reroll; above it, bank. The project finds that threshold two ways:

- **Monte Carlo** (`farkle/optimize.py`): binary-search each threshold
  against its own indifference condition, `EV(reroll at s, d) == s`, using
  thousands of simulated turn-continuations per probe. The six thresholds are
  interdependent (hitting hot dice from *d*=4 routes you to *d*=6, for
  example), so this runs several rounds, recomputing all six against the
  previous round's values until they stabilize.
- **Exact enumeration** (`farkle/stats.py`): bust probability and expected
  score per roll for a given dice count are computed by enumerating all
  6^d outcomes directly (at most 46,656 for six dice) rather than simulated.
  These are exact, not estimates, and serve as a sanity check on the
  simulated numbers (e.g. the well-known "~2.3% chance of busting with six
  dice" falls out exactly: 2.315%).

**2. Which dice to save.** 3+-of-a-kind groups and whole-roll special combos
are always locked in full if rolled. But Farkle also lets you set aside
*fewer* than all your loose 1s/5s on a given roll, rerolling the declined
ones along with the non-scoring dice instead of banking their points. That's
a real decision, modeled in `farkle/policy.py` via `ThresholdPolicy.resolve_roll`.
`farkle/holdback.py` enumerates every reachable (dice remaining, loose 1s,
loose 5s) state with no forced group present, 38 of them, and sweeps every
possible lock count at each one via Monte Carlo to find the best. The
resulting table and the six bank thresholds are then refined together: each
depends on the other, so `export_web.py` alternates optimizing the
thresholds against the current table and rebuilding the table against the
current thresholds until both stop moving. See
[Results](#results-standard-ruleset) for what that found.

## Results (standard ruleset)

| Dice remaining | Bank at score >= | Bust probability (exact) | Expected score/roll (exact) |
|---|---|---|---|
| 1 | 300 | 66.67% | 25.0 |
| 2 | 241 | 44.44% | 50.0 |
| 3 | 414 | 27.78% | 86.8 |
| 4 | 977 | 15.74% | 143.5 |
| 5 | 2,615 | 7.72% | 225.8 |
| 6 (hot dice) | 16,824 | 2.31% | 420.3 |

A few things worth noting:

- **Thresholds rise steeply with dice remaining.** With six fresh dice the
  bust risk is so low (2.3%) that it's worth pushing to turn scores in the
  thousands before banking beats rerolling. Practically, "always continue
  on hot dice" (the common strategy-guide advice) holds almost everywhere a
  real game actually reaches.
- **Two dice is a worse spot than one.** The threshold for *d*=2 (241) is
  *lower* than for *d*=1 (300), despite *d*=2 having a lower bust
  probability. With one die, scoring *always* means hot dice (a fresh six).
  With two dice, only ~11% of scoring outcomes are hot dice; the rest
  (~44% of all outcomes) score partially and drop you into the much
  riskier *d*=1 state. The safety of "successfully rerolling" is lower at
  *d*=2 than the raw bust-probability numbers suggest, so the model is
  more reluctant to risk a large stake there.

### Which dice to save when rerolling

3+-of-a-kind groups are always locked in full. But on any roll where the only
scoring dice are loose 1s and 5s, with no group and no special combo, the
player can lock fewer than all of them, rerolling the declined dice along
with whatever didn't score. `farkle/holdback.py` enumerates every reachable
(dice remaining, loose 1s, loose 5s) state where this choice exists, 38 of
them across all six dice-remaining counts, and sweeps every lock count at
each one via Monte Carlo to find the best.

Hold-back changes the right play in 12 of those 38 states. Every other state
(26 of 38) should just lock everything rolled, no exceptions:

| Dice remaining | Loose 1s | Loose 5s | Lock | Decline |
|---|---|---|---|---|
| 4 | 1 | 1 | 1 | 1 |
| 5 | 0 | 2 | 1 | 1 |
| 5 | 1 | 1 | 1 | 1 |
| 5 | 1 | 2 | 1 | 2 |
| 5 | 2 | 0 | 1 | 1 |
| 5 | 2 | 1 | 1 | 2 |
| 6 | 0 | 2 | 1 | 1 |
| 6 | 1 | 1 | 1 | 1 |
| 6 | 1 | 2 | 1 | 2 |
| 6 | 2 | 0 | 1 | 1 |
| 6 | 2 | 1 | 1 | 2 |
| 6 | 2 | 2 | 1 | 3 |

The pattern: at dice_remaining 5 and 6, locking down to just your single most
valuable loose die and declining the rest is almost always right, because
landing at dice_remaining=4 or 5 after the reroll sits in an unusually safe
part of the bust-probability curve (15.7% and 7.7%) compared to staying at
dice_remaining 1-3 (66.7%, 44.4%, 27.8%). Giving up 100-200 guaranteed points
to land in that safer spot is a good trade almost everywhere this choice
comes up.

The one case that breaks the pattern is the most revealing result in the
whole table: at dice_remaining=5 with 2 loose 1s and 2 loose 5s (300
guaranteed points on the table), locking all 4 wins, while the identical
loose composition at dice_remaining=6 still prefers holding back to 1. The
difference is what each state falls back to if it goes wrong. At
dice_remaining=1, busting or hitting hot dice are the only two outcomes;
that "clean" all-or-nothing shape makes landing there less bad than its raw
66.7% bust probability suggests. At dice_remaining=5, there just isn't
enough guaranteed score on the table (300 points) to make trading it away
for that safety worth it. At dice_remaining=6, locking down to 1 instead
lands you at dice_remaining=5, a far safer spot than dice_remaining=1, so
the same trade is worth it there.

End to end, this is an **8.1% improvement in points per turn** over always
taking the maximum score:

| Strategy | Points/turn | vs. optimal |
|---|---|---|
| Optimal (full table, thresholds above) | 586.2 | baseline |
| Six-roll hold-back only (lock 1, fresh six dice only) | 581.5 | -0.8% |
| Always take max (no hold-back) | 542.1 | -7.5% |
| Naive uniform hold-back (decline whenever few dice remain, at any roll size) | 536.2 | -8.5% |
| Flat threshold of 300, regardless of dice remaining | 488.9 | -16.6% |
| Bank after the very first scoring roll | 421.4 | -28.1% |

Two earlier, narrower versions of this analysis are kept in the table above
for comparison. A naive hold-back rule applied uniformly to every roll size
was tested first and found to be *always* worse than taking the max; that
conclusion was correct for a uniform rule but wrong as a blanket statement
about hold-back in general, since it missed the fresh-six-dice case
entirely. A second pass modeled hold-back correctly, but only for fresh
six-dice rolls, missing the dice_remaining=4 and 5 states covered above. The
full table in this section supersedes both.

## Running it

Requires Python 3.10+, standard library only (no `pip install` needed).

```
python -m unittest discover tests -v     # scoring-engine + policy correctness tests
python export_web.py                     # full precision, ~2-3 min, regenerates web/data.js
python export_web.py --fast              # low trial counts, for quick iteration (~10s)
```

Then open `web/index.html` in a browser (no server required; the data is
inlined as a `<script>` rather than fetched, so `file://` works fine).

## Project layout

```
farkle/
├── rules.py       scoring engine, the ruleset lives here (including RollDecomposition)
├── policy.py      ThresholdPolicy: reroll-vs-bank thresholds, plus which dice to save on reroll
├── simulate.py     Monte Carlo turn simulation under a given policy
├── optimize.py      binary-search threshold finder (the "optimizer")
├── holdback.py         builds the full which-dice-to-save table, state by state
└── stats.py               exact bust probability / expected score via full enumeration
tests/
├── test_rules.py        scoring-engine unit tests
├── test_policy.py        unit tests for the which-dice-to-save decision
└── test_holdback.py       unit tests for the reachable-state enumeration
export_web.py               runs everything, writes web/data.js
web/
├── index.html                 the visualization page
├── style.css
├── app.js                       builds the tables/charts from data.js
└── data.js                       generated, do not hand-edit
```

## Scope & known simplifications

- **The which-dice-to-save decision only covers loose-singles-only rolls.**
  Every reachable (dice remaining, loose 1s, loose 5s) state with no forced
  group present is covered by the full table above. It does not cover
  declining a loose single when a 3+-of-a-kind group is also rolled on the
  same turn, or breaking up an already-formed group to decline part of it.
  Each of those is a plausible further extension, not modeled here.
- **Entry threshold (500) and the 10,000-point win condition are not
  modeled.** The optimizer treats every banked point as equally valuable,
  which is the right objective for "maximize expected points per turn in
  isolation." A full multiplayer race to 10,000 would make the correct
  threshold *context-dependent* (more aggressive when behind late in the
  game, more conservative when protecting a lead); that's a reasonable
  extension, not implemented here.
- **House rules vary.** The four/five/six-of-a-kind doubling rule, whether
  two-triplets is a special bonus at all, and the entry threshold are all
  commonly-house-ruled differently. Change the constants in `rules.py` and
  re-run `export_web.py` to see how the optimal thresholds shift.
