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
a real decision, modeled in `farkle/policy.py` via `ThresholdPolicy.resolve_roll`
and tested the same way as the main thresholds: optimize a hold-back policy
via Monte Carlo, then compare it against always taking the maximum score. See
[Results](#results-standard-ruleset) for what that found.

## Results (standard ruleset)

| Dice remaining | Bank at score >= | Bust probability (exact) | Expected score/roll (exact) |
|---|---|---|---|
| 1 | 302 | 66.67% | 25.0 |
| 2 | 246 | 44.44% | 50.0 |
| 3 | 413 | 27.78% | 86.8 |
| 4 | 1,011 | 15.74% | 143.5 |
| 5 | 3,127 | 7.72% | 225.8 |
| 6 (hot dice) | 17,188 | 2.31% | 420.3 |

A few things worth noting:

- **Thresholds rise steeply with dice remaining.** With six fresh dice the
  bust risk is so low (2.3%) that it's worth pushing to turn scores in the
  thousands before banking beats rerolling. Practically, "always continue
  on hot dice" (the common strategy-guide advice) holds almost everywhere a
  real game actually reaches.
- **Two dice is a worse spot than one.** The threshold for *d*=2 (246) is
  *lower* than for *d*=1 (302), despite *d*=2 having a lower bust
  probability. With one die, scoring *always* means hot dice (a fresh six).
  With two dice, only ~11% of scoring outcomes are hot dice; the rest
  (~44% of all outcomes) score partially and drop you into the much
  riskier *d*=1 state. The safety of "successfully rerolling" is lower at
  *d*=2 than the raw bust-probability numbers suggest, so the model is
  more reluctant to risk a large stake there.

### Which dice to save when rerolling

On a **fresh six-dice roll** (the start of a turn, or right after hot dice),
if the only scoring dice are loose 1s and 5s with no 3-of-a-kind or better,
the EV-optimal play is to lock just your single most valuable loose die and
decline the rest, rerolling them along with the non-scoring dice. Tested
directly for every possible loose-singles count on a six-dice roll with no
forced group (1 through 4):

| Loose singles rolled | Lock everything | Lock just 1, decline the rest |
|---|---|---|
| 1 | n/a (no choice) | 386 |
| 2 (e.g. two 1s) | 345 | 386 |
| 3 | 294-308 | 385-386 |
| 4 (two 1s, two 5s) | 300 | 385 |

("Value" above is the simulated EV of optimal play from that point, in
points, not the raw locked score; it already accounts for everything that
happens for the rest of the turn.) Locking just one die wins by a wide
margin in every case, because dice_remaining=5 sits in an unusually safe
part of the bust-probability curve (7.7%, barely more than six dice's 2.3%)
compared to dice_remaining=4, 3, or 2 (15.7%, 27.8%, 44.4%). Giving up 100 or
200 guaranteed points to stay at 5 dice instead of 2-4 is a good trade.

End to end, this is a **6.4% improvement in points per turn** over always
taking the maximum score:

| Strategy | Points/turn | vs. optimal |
|---|---|---|
| Optimal (six-roll hold-back, thresholds above) | 579 | baseline |
| Always take max (no hold-back) | 544 | -6.0% |
| Naive uniform hold-back (decline whenever few dice remain, at any roll size) | 529 | -8.6% |
| Flat threshold of 300, regardless of dice remaining | 489 | -15.6% |
| Bank after the very first scoring roll | 421 | -27.3% |

**This is specific to the fresh-six-dice case and does not generalize.**
Tested the same way on smaller rerolls (after some dice are already locked
away elsewhere in the turn), the result flips: sometimes locking more wins,
sometimes locking less does, state by state, because the available
dice-remaining options no longer span that same cheap 5-vs-smaller gap in
bust probability. An earlier version of this project tested a naive version
of hold-back that applied uniformly to every roll size and found it was
*always* worse than taking the max ("Naive uniform hold-back" above). That
conclusion was correct for the general case, but wrong as a blanket rule:
it missed this specific, large exception. Extending the hold-back decision
properly to every dice-remaining state is a natural next step, not
implemented here.

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
└── stats.py           exact bust probability / expected score via full enumeration
tests/
├── test_rules.py        scoring-engine unit tests
└── test_policy.py        unit tests for the which-dice-to-save decision
export_web.py               runs everything, writes web/data.js
web/
├── index.html                 the visualization page
├── style.css
├── app.js                       builds the tables/charts from data.js
└── data.js                       generated, do not hand-edit
```

## Scope & known simplifications

- **The which-dice-to-save decision only covers the fresh-six-dice,
  loose-singles-only case.** It does not cover: declining a loose single
  when a 3+-of-a-kind group is also present in the same roll, declining on
  a reroll smaller than six dice, or breaking up an already-formed group
  to decline part of it. Each of those is a plausible further extension;
  none are modeled here.
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
