"""Small contextual matchup modifiers for EBL game simulation.

These helpers never mutate permanent player ratings. They return temporary,
game-context adjustments that nudge probabilities without deciding outcomes.
"""

PLATOON_STEP = 1.0

_ZERO = {
    "hitter": {"VIS": 0.0, "DISC": 0.0},
    "pitcher": {"MOV": 0.0, "SEQ": 0.0},
}


def _hand(value, allow_switch=False):
    hand = str(value or "").strip().upper()
    allowed = {"R", "L", "S"} if allow_switch else {"R", "L"}
    return hand if hand in allowed else None


def platoon_adjustments(batter_bats, pitcher_throws):
    """Return temporary handedness modifiers for one batter/pitcher matchup.

    Traditional hitters receive a small favorable nudge against opposite-handed
    pitching and the inverse against same-handed pitching. Switch hitters are
    deliberately neutral: they avoid a bad platoon matchup but do not receive the
    favorable traditional-hitter bonus every plate appearance.
    """
    bats = _hand(batter_bats, allow_switch=True)
    throws = _hand(pitcher_throws, allow_switch=False)

    if bats == "S" and throws:
        return {
            "kind": "SWITCH_NEUTRAL",
            "batter_bats": bats,
            "pitcher_throws": throws,
            "hitter": dict(_ZERO["hitter"]),
            "pitcher": dict(_ZERO["pitcher"]),
        }

    if bats not in {"R", "L"} or throws not in {"R", "L"}:
        return {
            "kind": "NEUTRAL",
            "batter_bats": bats,
            "pitcher_throws": throws,
            "hitter": dict(_ZERO["hitter"]),
            "pitcher": dict(_ZERO["pitcher"]),
        }

    favorable = bats != throws
    hitter_delta = PLATOON_STEP if favorable else -PLATOON_STEP
    pitcher_delta = -PLATOON_STEP if favorable else PLATOON_STEP
    return {
        "kind": "ADVANTAGE" if favorable else "DISADVANTAGE",
        "batter_bats": bats,
        "pitcher_throws": throws,
        "hitter": {"VIS": hitter_delta, "DISC": hitter_delta},
        "pitcher": {"MOV": pitcher_delta, "SEQ": pitcher_delta},
    }


def effective_rating(value, adjustment=0.0):
    """Apply a temporary modifier with a zero floor and no artificial upper cap."""
    try:
        base = float(value or 0.0)
    except (TypeError, ValueError):
        base = 0.0
    try:
        delta = float(adjustment or 0.0)
    except (TypeError, ValueError):
        delta = 0.0
    return max(0.0, base + delta)


_CPU_HITTER_BATS = ("R", "L", "R", "S", "R", "L", "R", "S", "R")
_CPU_PITCHER_THROWS = ("R", "R", "L", "R", "R", "L", "R")


def _stable_team_offset(franchise_id):
    text = str(franchise_id or "")
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        return int(digits)
    return sum(ord(ch) for ch in text)


def cpu_handedness(franchise_id, slot_index, player_type):
    """Return deterministic varied handedness for CPU filler.

    Human players keep their creator choices. CPU filler uses a stable mix so
    Genesis does not accidentally make every matchup right-handed.
    """
    ptype = str(player_type or "").strip().upper()
    try:
        idx = max(0, int(slot_index))
    except (TypeError, ValueError):
        idx = 0
    shift = _stable_team_offset(franchise_id)

    if ptype == "P":
        throws = _CPU_PITCHER_THROWS[(idx + shift) % len(_CPU_PITCHER_THROWS)]
        return {"bats": "R", "throws": throws}

    bats = _CPU_HITTER_BATS[(idx + shift) % len(_CPU_HITTER_BATS)]
    return {"bats": bats, "throws": "R"}
