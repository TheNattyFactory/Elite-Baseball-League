# Elite Baseball League — League Structure

## Full-league regular season

The full EBL has 30 clubs split into two 15-team leagues. Each league contains three five-team divisions. The existing six division identities remain intact:

- Internal League A: Heritage, Liberty, Union
- Internal League B: Frontier, Continental, Pioneer

`EBL-A` and `EBL-B` are stable internal database keys only. Public league names are intentionally not locked yet; they can be named later without rewriting season history.

Each club plays an 81-game regular season across 27 three-game series:

- **Division:** 4 rivals × 3 series = 12 series / 36 games
- **Same league, other divisions:** 10 clubs × 1 series = 10 series / 30 games
- **Interleague:** 5 clubs × 1 series = 5 series / 15 games
- **Total:** 27 series / 81 games

A club therefore faces 19 different opponents in a season: all 14 clubs in its own league plus five from the opposite league.

## Interleague rotation

Interleague play rotates through one third of the opposite league each season.

- Season 1: first five-opponent rotation
- Season 2: second five-opponent rotation
- Season 3: third five-opponent rotation
- Season 4: Season 1 opponents return

Across any three-season cycle, every club faces all 15 clubs in the opposite league exactly once. When an interleague pairing returns three seasons later, the home ballpark flips.

## Home/away rules

Division opponents meet in three series. Each pairing has a 2-home / 1-away series split for one club, and that advantage reverses the following season. Within each five-team division, the schedule is balanced so every club receives six home division series and six road division series.

Same-league non-division opponents meet once per season. The orientation rule gives every club exactly five home and five road series in this category, and matchups flip parks the following season.

Interleague play gives one side of the league split three home interleague series and the other side two; that flips when the same interleague group returns. Across the complete schedule every club finishes with either 13 or 14 home series (39 or 42 home games).

## Calendar

The schedule remains 27 series across the existing 95-day simulated calendar. Rest-series behavior is unchanged.

## Genesis migration safety

If the full Season 1 schedule already exists when this format is deployed, EBL upgrades it automatically only when the league is still on Day 0 and has zero completed games. Once any game has been played, the existing schedule is preserved as league history; the new format begins with the next clean Genesis reset or newly generated season.

## Postseason

This schedule change does **not** change the current eight-team postseason format yet. A later design pass can decide how league champions, division winners, and wild cards should feed the EBL Championship.

## Design rationale

The purpose is to make the six divisions and the two halves of EBL matter without making the league feel isolated. Division rivals are familiar, every club sees the rest of its own league every season, and interleague games stay fresh because the opponents rotate. The system creates recurring matchups and rivalry history without requiring every club to play all 29 opponents every year.
