# EBL Pitch Repertoire & Player Relationships

## Product rule

**Depth must stay understandable.** EBL may reward specialization and continuity, but a legal player build should never become secretly unusable because the player failed to understand an undocumented interaction.

Pitch repertoire and relationship chemistry therefore sit on top of the existing ratings system instead of creating new rating trees.

## Pitch repertoire

Every pitcher begins with exactly **3 pitches** selected during Player Creation.

Current pitch catalog:

| Pitch | Naturally leans on |
| --- | --- |
| Four-Seam | VEL, CMD |
| Sinker | MOV, VEL |
| Cutter | MOV, VEL, BRK |
| Slider | BRK, MOV |
| Curveball | BRK, CTRL |
| Changeup | MOV, SEQ, DEC |
| Splitter | MOV, BRK |

These are **emphases, not requirements**. A movement-heavy pitcher can still throw a four-seam; it simply will not be the part of his arsenal most enhanced by his build. All pitches still use the same canonical pitcher ratings: CTRL, CMD, VEL, BRK, MOV, DEC, and SEQ.

There are no separate pitch ratings and no pitch-specific XP trees.

### Learning more pitches

- Starting repertoire: 3 pitches, free with player creation.
- 4th pitch: **5 personal XP**.
- 5th pitch: **8 personal XP**.
- Maximum repertoire: **5 pitches**.
- Learning a pitch is permanent player identity; it does not directly raise Overall.
- More pitches create options for sequencing. They do not grant an automatic effectiveness bonus simply for owning more pitches.

The simulator chooses only from the pitcher's saved repertoire. Small pitch-type nudges (maximum +1 to an emphasized effective skill) express the physical identity of a pitch without rewriting permanent attributes.

Existing pitchers created before this system are backfilled deterministically with the three pitches that best match their current build rather than being handed one arbitrary universal arsenal.

## Battery Charge

Pitcher/catcher continuity creates a long-term relationship called **Battery Charge**.

A season qualifies when the exact pitcher/catcher pair records either:

- at least **15 starts together**, or
- at least **100 innings (300 outs) together**.

A qualifying season is finalized at season rollover and affects the following season. Consecutive qualified seasons build the charge:

| Consecutive qualified seasons | Battery Charge |
| ---: | ---: |
| 1 | +0.01 |
| 2 | +0.02 |
| 3 | +0.04 |
| 4 | +0.08 |
| 5 | +0.16 |
| 6 | +0.32 |
| 7 | +0.64 |
| 8 | +1.28 |
| 9+ | **+2.00 cap** |

Battery Charge applies only while that exact catcher is catching that exact pitcher. It temporarily nudges the pitcher's **CTRL, CMD, BRK, MOV, DEC, and SEQ**.

It does **not** increase VEL, STA, PCLT, permanent attributes, XP costs, Overall, awards, or career-history values.

The catcher therefore helps the pitcher execute what he already has rather than magically making him throw harder.

If the pair fails to record a qualifying season, the consecutive streak ends. Their total shared history remains stored for career/history presentation, and a future reunion can begin a new streak.

## Infield throw/receive familiarity

EBL also stores a quieter relationship between an infielder and the first baseman who receives his throws.

Current tracked pairs are:

- SS → 1B
- 2B → 1B
- 3B → 1B

A pair qualifies after **40 games together in one season**. The same doubling pattern is used but with a smaller ceiling:

`+0.01 → +0.02 → +0.04 → +0.08 → +0.16 → +0.32 → +0.64 → +1.00 cap`

This familiarity is applied only on across-the-diamond ground-ball plays:

- the thrower receives the temporary amount on effective **ACC**;
- the first baseman receives the temporary amount on effective **FLD** for the receive/scoop check.

This relationship is deliberately low-salience. Players do not manage a chemistry meter or spend XP on it. It exists because players who actually stay together should become slightly more polished together.

SS/2B double-play chemistry is not implemented yet because EBL does not currently have a dedicated double-play resolution path. It should be added only when the underlying baseball event exists, rather than inventing a bonus with nowhere legitimate to apply it.

## Explicit non-goals

- **No hitter/fielder fatigue system.** EBL currently has no bench/injury ecosystem that would make position-player fatigue an interesting decision, so adding it would create punishment without strategy.
- **No weather gameplay system yet.** Weather may become a small environmental layer later, but it is intentionally not part of this release.
- No generic team-chemistry rating.
- No chemistry purchases.
- No hidden permanent player boosts.

## Persistence and transparency

`pitcher_repertoires` stores each pitcher's durable arsenal.

`relationship_season_usage` stores the actual shared work performed by each pair during a season.

`player_relationships` stores qualified continuity, total qualified seasons, the latest qualified season, and the currently earned contextual bonus.

`PA_START` records the active catcher and Battery Charge for that plate appearance. Pitch events record both the canonical pitch key and the human-readable pitch name. This makes the simulation explainable without exposing every low-level probability calculation.

Genesis clean-slate league resets clear relationship history along with league history, but they preserve a player's chosen repertoire because the repertoire is part of player identity rather than season history.
