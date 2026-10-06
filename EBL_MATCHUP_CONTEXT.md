# EBL Matchup Context

## Design rule

**Ratings establish capability. Context shapes opportunity. Randomness decides the moment.**

EBL contextual systems should create small, understandable probability edges rather than guaranteed outcomes. The saved player build remains the source of truth; game context temporarily changes the effective inputs used by the simulation.

## Handedness / platoon rule

The first contextual matchup rule is handedness:

| Matchup | Hitter effective ratings | Pitcher effective ratings |
| --- | --- | --- |
| Traditional hitter vs opposite-hand pitcher | VIS +1, DISC +1 | MOV -1, SEQ -1 |
| Traditional hitter vs same-hand pitcher | VIS -1, DISC -1 | MOV +1, SEQ +1 |
| Switch hitter vs either hand | Neutral | Neutral |

Switch hitters do **not** receive a permanent CON or POW penalty. Their value is consistency: they avoid the unfavorable platoon state, but they also do not receive the favorable traditional-hitter bonus every plate appearance.

These values are temporary simulation inputs only. They do not modify `attributes_json`, XP costs, player overall, training, awards, or career history.

## Transparency

Each simulated plate appearance records the matchup class (`ADVANTAGE`, `DISADVANTAGE`, or `SWITCH_NEUTRAL`) plus batter and pitcher handedness in the `PA_START` event. This allows GameCast and future analytics to explain the edge instead of hiding it.

## Future context systems

Stadium factors, coaching tendencies, fatigue, roster fit, and other future systems should follow the same principle:

1. small effect;
2. understandable cause;
3. meaningful tradeoff;
4. no guaranteed outcome;
5. no silent permanent mutation of the player build.

A future stadium system can therefore alter effective game ratings for everybody in that park while preserving the player's canonical ratings outside that game.

## Genesis CPU filler

Existing Genesis CPU filler was historically seeded almost entirely right-handed. Activating platoon effects without correcting that would create an artificial league-wide handedness bias. Active CPU filler is therefore normalized deterministically:

- each nine-hitter CPU group contains right-handed, left-handed, and switch hitters;
- each seven-pitcher CPU group contains five right-handed and two left-handed throwers;
- human-created handedness is never changed;
- the same franchise/roster slot produces the same CPU handedness after resets.

This is infrastructure balancing for CPU filler, not a hidden advantage for human players.

## Stadium / park-factor rule

The home stadium is another contextual system. Its profile applies to **both clubs** in that game; EBL does not grant a hidden ratings bonus simply because a team is at home. The strategic home-field edge comes from building a roster that is well suited to the environment where that franchise plays roughly half its schedule.

Initial balanced profiles:

| Profile | Hitter effective ratings | Pitcher effective ratings |
| --- | --- | --- |
| Neutral Park | None | None |
| Power Friendly | POW +2, CON -1, VIS -1 | None |
| Contact Friendly | CON +2, POW -1, DISC -1 | None |
| Batter's Eye | VIS +2, POW -1, CON -1 | None |
| Deep Gaps | CON +1, VIS +1, POW -2 | None |
| Pitcher Friendly | CON -1, POW -1 | MOV +1, SEQ +1 |

Every non-neutral profile has total positive and negative modifiers that cancel to zero, every individual park modifier is capped at ±2, and `stadium_level` does not amplify these gameplay effects. Stadium level can remain a franchise/facility progression concept without becoming pay-to-win competitive power.

A franchise may configure its stadium during the offseason or on Day 0 before Opening Day. Once the season begins, the stadium name and gameplay profile are locked until the next offseason. The configuration carries forward until the franchise changes it.

Each simulated game snapshots the stadium name, profile key, and temporary modifiers into the saved game box and emits a `STADIUM_CONTEXT` event. Historical GameCast therefore keeps the park that actually governed the game even if the franchise changes its stadium later.


## Repertoire and continuity

Pitch repertoire follows the same contextual philosophy. A pitcher's saved attributes remain canonical; his repertoire changes which pitch types can be selected and each pitch applies only a very small temporary identity nudge to the skills it naturally emphasizes. There are no hidden per-pitch ratings.

Long-term player relationships also remain contextual. Battery Charge can reach +2 only after nine consecutive qualifying seasons and only affects CTRL/CMD/BRK/MOV/DEC/SEQ while the exact catcher is behind the plate. Infield-to-first-base familiarity is capped at +1 and only affects the thrower's ACC and first baseman's receiving FLD on relevant ground-ball plays.

This release intentionally does **not** add position-player fatigue or weather. Depth should be added when it creates a real decision, not simply because another modifier can be simulated.
