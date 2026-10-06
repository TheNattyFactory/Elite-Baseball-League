# EBL Stadium System

## Principle

A stadium changes the kind of baseball played there. It does **not** give the home club a hidden ratings bonus.

The same park modifiers apply to both teams. A home-field advantage emerges because the home franchise can construct its roster around the environment it plays in for roughly half its schedule.

## Initial park profiles

| Profile | Hitter effect | Pitcher effect |
| --- | --- | --- |
| Neutral Park | — | — |
| Power Friendly | POW +2, CON -1, VIS -1 | — |
| Contact Friendly | CON +2, POW -1, DISC -1 | — |
| Batter's Eye | VIS +2, POW -1, CON -1 | — |
| Deep Gaps | CON +1, VIS +1, POW -2 | — |
| Pitcher Friendly | CON -1, POW -1 | MOV +1, SEQ +1 |

These are **effective game ratings only**. A 62 POW player remains a 62 POW player on his profile. In a Power Friendly stadium, the simulation evaluates that attribute as 64 for that game.

## Guardrails

- maximum individual modifier: ±2;
- each non-neutral profile must contain both an advantage and a disadvantage;
- total positive and negative park deltas must cancel to zero;
- modifiers apply equally to visitors and the home club;
- no permanent mutation of player attributes;
- `stadium_level` does not strengthen park factors;
- stadium configuration is available only in the offseason or on Day 0 before Opening Day;
- once games begin, the park is locked for the season.

## Persistence and history

`franchise_stadiums` stores the current stadium name and profile. The configuration carries forward until changed.

Every simulated game snapshots its stadium context into `box_json` and emits a `STADIUM_CONTEXT` GameCast event. Old games therefore retain the exact stadium environment that governed them even if a franchise later changes its park.

## API surfaces

`GET /api/coach/team` returns the club's stadium, edit availability, and the permitted park-profile catalog.

`POST /api/coach/stadium` accepts `stadium_name` and `park_profile` while the edit window is open.

`GET /api/team/<franchise_id>` exposes the public stadium identity and current park profile so team pages can display it.

## Coach HUD and GameCast

The Coach HUD exposes the stadium editor inside Franchise Upgrades. Coaches can see the current profile, its exact hitter/pitcher modifiers, and whether the edit window is open before saving. Once league play begins the controls become read-only until the offseason.

GameCast receives the persisted `STADIUM_CONTEXT` event, so replay/play-by-play can identify the ballpark and profile that governed the game.
