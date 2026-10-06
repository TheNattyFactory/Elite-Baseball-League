# EBL Backend Architecture

`server.py` remains the production HTTP entry point. Backend refactoring is being done in behavior-preserving slices so live league rules, API payloads, and persistent data do not change accidentally.

## Current modules

- `ebl_config.py` — runtime paths, league constants, economy/progression limits, and environment-backed feature settings.
- `ebl_support.py` — public Supporter configuration.
- `ebl_security.py` — password hashing/checking and registration age validation.
- `ebl_branding.py` — franchise identity data, generated artwork helpers, and production branding asset rules.
- `ebl_roster.py` — roster eligibility, slot selection, human roster counts, and capacity rules.
- `ebl_db.py` — SQLite connection factory.
- `ebl_league.py` — season membership, division assignment, active-franchise selection, regular-season schedule construction, schedule invariants, playoff qualification, series scheduling, and bracket summaries.
- `ebl_season.py` — transactional offseason → new-season orchestration: history archival, contract advancement/expiry/renewal activation, career-cap retirement, franchise rollover, return offers, roster/fatigue reset coordination, live-stat reset, schedule creation, and new-season state.
- `ebl_matchups.py` — contextual handedness/platoon modifiers and deterministic Genesis CPU handedness balancing.
- `ebl_stadiums.py` — balanced stadium profiles, offseason/Day-0 edit rules, stadium identity, and temporary park-factor modifiers.
- `ebl_repertoire.py` — pitch catalog, starting-repertoire validation, best-fit migration, pitch-learning XP costs, and temporary pitch-type nudges.
- `ebl_chemistry.py` — earned pitcher/catcher Battery Charge, quiet infield-to-first-base familiarity, seasonal usage qualification, and relationship history.
- `server.py` — database schema/migrations, player development/economy formulas, contract pricing, roster enforcement, simulation, GameCast event generation, community, Supporter/Stripe lifecycle, commissioner actions, and HTTP routing.

## League & Season boundary

The league module owns rules that can be evaluated independently from HTTP requests and simulation:

- minimum/even active-team requirements;
- commissioner-selected season membership;
- season-specific division assignment;
- 81-game / 27-series / 95-calendar-day regular-season construction;
- full 30-team two-league structure: 36 division games / 30 same-league non-division games / 15 rotating interleague games;
- deterministic series ordering and home/away balancing;
- eight-team playoff qualification and seeding;
- playoff series home-field scheduling, winners, and bracket summaries.

Season advancement now lives in `ebl_season.py`. The module owns the order and transaction boundary but deliberately receives still-coupled behaviors (contract pricing, retirement eligibility, economy formulas, roster enforcement, fatigue reset, notifications, and news) as explicit hooks from `server.py`. This keeps the refactor behavior-preserving while making those dependencies visible and independently extractable later. The caller still owns commit/rollback.

## Game-context boundary

Handedness now follows the EBL contextual-edge rule rather than modifying saved player builds:

- opposite-hand traditional hitter: +1 effective VIS / +1 effective DISC; opposing pitcher -1 effective MOV / -1 effective SEQ;
- same-hand traditional hitter: -1 effective VIS / -1 effective DISC; opposing pitcher +1 effective MOV / +1 effective SEQ;
- switch hitter: neutral in either matchup — no favorable bonus, no unfavorable penalty, and no permanent CON/POW tax;
- effective ratings are floored at zero but keep EBL's uncapped upper development model;
- the `PA_START` GameCast event records the matchup class and handedness so the effect can be surfaced transparently later.

The rule is deliberately small. Ratings establish capability; context shapes opportunity; randomness still decides the moment.

## Contextual game systems

Handedness, stadiums, repertoire, and player-pair familiarity follow one shared product rule: **ratings establish capability; context shapes opportunity; randomness decides the moment.** These systems only change temporary effective ratings used by the simulation. They never rewrite `attributes_json`, XP costs, training, overall ratings, awards, or career history.

The home stadium applies its profile equally to both clubs. Initial park profiles are deliberately small and balanced (maximum ±2 to any affected attribute, with positive and negative deltas cancelling out). Stadium configuration is locked once league play begins, and each game snapshots its park context into saved GameCast/box data. `stadium_level` does not scale competitive park effects.

Pitch repertoire is durable player identity rather than a second development tree: pitchers choose three pitches, may learn a fourth for 5 XP and a fifth for 8 XP, and every pitch continues to use the same canonical pitching attributes. Battery/infield familiarity is earned from recorded shared usage and is finalized at season rollover; it changes only temporary game inputs.

No hitter/fielder fatigue or weather gameplay modifier is part of this architecture pass. Those mechanics are intentionally absent until they create a real player decision instead of background complexity.

## Regression foundation

`tests/test_ebl_league.py` protects the league/schedule boundary with standard-library `unittest` coverage. It verifies:

1. division layouts at supported league sizes;
2. commissioner active-team-count membership behavior;
3. rejection of too-small and odd-sized leagues;
4. exact deterministic Season 1 schedule signatures for 8-team and 30-team leagues;
5. 81 games per club and 95-day calendar limits;
6. two 15-team league assignments with three five-team divisions per league;
7. the full-league 36/30/15 division / same-league / interleague split;
8. 19 distinct opponents per full-league season;
9. a three-season interleague rotation that covers all 15 opposite-league clubs;
10. ballpark reversal when an interleague matchup returns in Season 4;
11. 2/1 division-series home splits that reverse the following season;
12. 13/14 home-series balance per club;
13. playoff seeding by wins, run differential, and runs scored;
14. playoff home-field pattern and series-winner detection;
15. safe Day-0 migration of an already-generated full-league schedule;
16. immutable preservation of a started season when any game history exists.

The 8-team schedule remains byte-for-byte compatible with the pre-refactor implementation. The 30-team schedule intentionally changed after the owner approved the two-league 36/30/15 format; its new deterministic signature is regression-locked.

`tests/test_ebl_season.py` protects the rollover boundary. It verifies:

1. non-offseason advancement is rejected without mutation;
2. a pre-existing next-season schedule returns an idempotent conflict without mutation;
3. completed player and franchise history is archived before live state is reset;
4. expiring contracts become free agency and generate eligible return offers;
5. accepted renewals activate and multi-year contracts advance with the existing salary escalation;
6. 12-season retirement removes live contracts/roster occupancy while preserving final history;
7. sponsorship expiry, franchise financial rollover, season membership, roster rebuild coordination, and pitcher-fatigue reset all occur in the existing sequence;
8. active player live statistics reset before the new schedule opens;
9. Season 2 schedule creation still satisfies the league schedule module;
10. the caller owns the transaction and a rollback restores the entire pre-transition state.

The combined backend domain suite currently runs **41 tests**.

`tests/test_ebl_matchups.py` protects the handedness boundary. It verifies opposite-hand and same-hand nudges, switch-hitter neutrality, zero-floor / uncapped effective-rating behavior, and deterministic mixed handedness for Genesis CPU filler.

`tests/test_ebl_stadiums.py` protects the park-factor boundary. It verifies balanced ±2-or-smaller profiles, the owner-approved Power Friendly profile, neutral defaults, persistent stadium identity, the offseason/Day-0 edit lock, effective-season targeting, and invalid-profile/name rejection.

`tests/test_ebl_repertoire.py` protects the arsenal boundary. It verifies exact three-pitch creation, 5/8 XP expansion costs, the five-pitch cap, build-aware migration, small temporary pitch nudges, and repertoire persistence without per-pitch ratings.

`tests/test_ebl_chemistry.py` protects the continuity boundary. It verifies the exact Battery Charge curve and +2 cap, the quieter +1 infield cap, real-usage qualification thresholds, consecutive-season behavior, gap resets with preserved total history, and directional SS/2B/3B-to-1B familiarity.

## Refactor rules

1. Preserve API routes and response payloads during architecture-only changes.
2. Preserve persistent database keys and compatibility identifiers.
3. Do not alter simulation probabilities, XP values, economy values, roster rules, contract rules, or season rules during a module extraction.
4. Add regression coverage before moving a fragile domain boundary.
5. Run Python compilation, import checks, behavioral parity checks, and domain tests before replacing production source.
6. Keep `python server.py` as the production entry point throughout the migration.
7. Treat league history and retired-career data as durable product data, not disposable cache.

## Next extraction order

1. player development, contracts, and franchise economy (the remaining season-rollover hooks);
2. simulation engine and GameCast event generation;
3. community, notifications, and moderation;
4. Supporter/Stripe lifecycle;
5. commissioner/admin operations;
6. GET/POST route dispatch into explicit domain routers.

The long-term target is a small HTTP entry point backed by explicit EBL domain modules and a regression suite that protects the league rules players have built history around.
