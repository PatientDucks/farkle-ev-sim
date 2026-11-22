# Farkle EV Simulator

A Monte Carlo simulator for the dice game Farkle, built to answer one
question: **for a given turn score and number of dice left to roll, is it
worth rerolling, or should you bank?**

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

For each dice-remaining state *d* in {1..6}, there's a turn score *s* at which
rerolling and banking have equal expected value: below it, reroll; above
it, bank. The project finds that threshold two ways:

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

## Results (standard ruleset)

| Dice remaining | Bank at score >= | Bust probability (exact) | Expected score/roll (exact) |
|---|---|---|---|
| 1 | 287 | 66.67% | 25.0 |
| 2 | 237 | 44.44% | 50.0 |
| 3 | 407 | 27.78% | 86.8 |
| 4 | 1,017 | 15.74% | 143.5 |
| 5 | 3,051 | 7.72% | 225.8 |
| 6 (hot dice) | 18,151 | 2.31% | 420.3 |

A few things worth noting:

- **Thresholds rise steeply with dice remaining.** With six fresh dice the
  bust risk is so low (2.3%) that it's worth pushing to turn scores in the
  thousands before banking beats rerolling. Practically, "always continue
  on hot dice" (the common strategy-guide advice) holds almost everywhere a
  real game actually reaches.
- **Two dice is a worse spot than one.** The threshold for *d*=2 (237) is
  *lower* than for *d*=1 (287), despite *d*=2 having a lower bust
  probability. With one die, scoring *always* means hot dice (a fresh six).
  With two dice, only ~11% of scoring outcomes are hot dice; the rest
  (~44% of all outcomes) score partially and drop you into the much
  riskier *d*=1 state. The safety of "successfully rerolling" is lower at
  *d*=2 than the raw bust-probability numbers suggest, so the model is
  more reluctant to risk a large stake there.
- **The optimized policy clearly beats naive heuristics.** Simulated mean
  points per turn, 300,000 trials each:

  | Strategy | Points/turn | vs. optimal |
  |---|---|---|
  | Optimal (per-dice-remaining thresholds above) | 545 | baseline |
  | Flat threshold of 300, regardless of dice remaining | 488 | -10.5% |
  | Bank after the very first scoring roll | 421 | -22.8% |
  | Hold back loose singles to keep more dice live (see below) | 506 | -7.2% |

- **Declining a loose single to "keep more dice live" is also worse, not
  better.** Farkle lets you set aside fewer than all available scoring dice
  on a given roll (e.g. leaving a lone 5 unbanked instead of scoring it, so
  you reroll it along with the non-scoring dice, hoping for a bigger combo).
  It's a real option, so this project tested it: a policy that declines
  cheap loose singles whenever locking everything would leave very few dice
  behind was optimized the same way as the main thresholds, then compared
  against always taking the max. The result was consistent across every
  target tried: declining monotonically *lowers* expected points per turn
  (506 at a moderate hold-back target, dropping further the more aggressively
  it declines). The guaranteed points from a loose single are worth more
  than the extra safety from one more die in the cup. Always taking the
  maximum score from every roll is the right call under this ruleset.

## Running it

Requires Python 3.10+, standard library only (no `pip install` needed).

```
python -m unittest tests.test_rules -v   # scoring-engine correctness tests
python export_web.py                     # full precision, ~40s, regenerates web/data.js
python export_web.py --fast              # low trial counts, for quick iteration (~3s)
```

Then open `web/index.html` in a browser (no server required; the data is
inlined as a `<script>` rather than fetched, so `file://` works fine).

## Project layout

```
farkle/
├── rules.py       scoring engine, the ruleset lives here
├── policy.py      ThresholdPolicy: reroll-vs-bank thresholds, plus the loose-singles hold-back choice
├── simulate.py     Monte Carlo turn simulation under a given policy
├── optimize.py      binary-search threshold finder (the "optimizer")
└── stats.py           exact bust probability / expected score via full enumeration
tests/
└── test_rules.py        scoring-engine unit tests
export_web.py               runs everything, writes web/data.js
web/
├── index.html                 the visualization page
├── style.css
├── app.js                       builds the tables/charts from data.js
└── data.js                       generated, do not hand-edit
```

## Scope & known simplifications

- **3+-of-a-kind groups and whole-roll special combos (straight, three
  pairs, two triplets) are always locked in full if rolled, not individually
  declinable.** The loose-singles hold-back decision above *is* modeled;
  breaking up an already-formed group to decline part of it is a much
  smaller and rarer consideration that isn't.
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
