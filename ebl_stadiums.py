"""EBL stadium identity and small park-factor modifiers.

Park factors are contextual game inputs, never permanent player development.
The home park applies to both clubs equally; any home-field advantage comes from
roster construction and familiarity with the environment, not a hidden home-team buff.
"""

from copy import deepcopy


PARK_PROFILES = {
    "NEUTRAL": {
        "name": "Neutral Park",
        "description": "No gameplay modifier. The park plays straight.",
        "hitter": {},
        "pitcher": {},
    },
    "POWER_FRIENDLY": {
        "name": "Power Friendly",
        "description": "The ball carries, but pure contact and pitch recognition are a little harder.",
        "hitter": {"POW": 2.0, "CON": -1.0, "VIS": -1.0},
        "pitcher": {},
    },
    "CONTACT_FRIENDLY": {
        "name": "Contact Friendly",
        "description": "A park that rewards putting the ball in play more than selling out for damage.",
        "hitter": {"CON": 2.0, "POW": -1.0, "DISC": -1.0},
        "pitcher": {},
    },
    "BATTERS_EYE": {
        "name": "Batter's Eye",
        "description": "Hitters see the ball well, trading some raw damage and contact authority for recognition.",
        "hitter": {"VIS": 2.0, "POW": -1.0, "CON": -1.0},
        "pitcher": {},
    },
    "DEEP_GAPS": {
        "name": "Deep Gaps",
        "description": "Big dimensions reward line-drive contact and recognition while suppressing home-run power.",
        "hitter": {"CON": 1.0, "VIS": 1.0, "POW": -2.0},
        "pitcher": {},
    },
    "PITCHER_FRIENDLY": {
        "name": "Pitcher Friendly",
        "description": "Pitch shape and sequencing play up while hitters lose a little contact and power.",
        "hitter": {"CON": -1.0, "POW": -1.0},
        "pitcher": {"MOV": 1.0, "SEQ": 1.0},
    },
}

ALLOWED_HITTER_ATTRS = {"CON", "POW", "VIS", "DISC", "TIM"}
ALLOWED_PITCHER_ATTRS = {"MOV", "SEQ", "BRK", "CTRL", "CMD", "VEL", "DEC"}
MAX_ABS_PARK_STEP = 2.0


def normalize_profile_key(value):
    key = str(value or "NEUTRAL").strip().upper()
    if key not in PARK_PROFILES:
        raise ValueError("INVALID_PARK_PROFILE")
    return key


def profile(key="NEUTRAL"):
    return deepcopy(PARK_PROFILES[normalize_profile_key(key)])


def profile_catalog():
    return [
        {
            "key": key,
            "name": data["name"],
            "description": data["description"],
            "hitter": dict(data["hitter"]),
            "pitcher": dict(data["pitcher"]),
        }
        for key, data in PARK_PROFILES.items()
    ]


def validate_profiles():
    """Raise if a profile stops being a small balanced contextual tradeoff."""
    for key, data in PARK_PROFILES.items():
        hitter = data.get("hitter") or {}
        pitcher = data.get("pitcher") or {}
        if set(hitter) - ALLOWED_HITTER_ATTRS:
            raise ValueError(f"INVALID_HITTER_PARK_ATTR:{key}")
        if set(pitcher) - ALLOWED_PITCHER_ATTRS:
            raise ValueError(f"INVALID_PITCHER_PARK_ATTR:{key}")
        values = [float(v) for v in list(hitter.values()) + list(pitcher.values())]
        if any(abs(v) > MAX_ABS_PARK_STEP for v in values):
            raise ValueError(f"PARK_EFFECT_TOO_LARGE:{key}")
        # Neutral is exactly zero. Every other profile must be a tradeoff with
        # total positive and negative effect cancelling out.
        if key == "NEUTRAL":
            if any(values):
                raise ValueError("NEUTRAL_PARK_HAS_EFFECT")
        elif not values or abs(sum(values)) > 1e-9 or not any(v > 0 for v in values) or not any(v < 0 for v in values):
            raise ValueError(f"UNBALANCED_PARK_PROFILE:{key}")
    return True


def stadium_edit_open(phase, league_day):
    """Parks can be configured in the offseason or before Opening Day only."""
    try:
        day = int(league_day or 0)
    except (TypeError, ValueError):
        day = 0
    return str(phase or "REGULAR").strip().upper() == "OFFSEASON" or day == 0


def effective_season_for_edit(current_season, phase):
    season = max(1, int(current_season or 1))
    return season + 1 if str(phase or "REGULAR").strip().upper() == "OFFSEASON" else season


def stadium_state(c, franchise_id, fallback_team_name=None):
    row = c.execute(
        "SELECT franchise_id,stadium_name,park_profile,effective_season,updated_at FROM franchise_stadiums WHERE franchise_id=?",
        (str(franchise_id),),
    ).fetchone()
    if row:
        data = dict(row)
        try:
            key = normalize_profile_key(data.get("park_profile"))
        except ValueError:
            key = "NEUTRAL"
        saved_name = str(data.get("stadium_name") or "").strip()
        effective_season = int(data.get("effective_season") or 1)
        updated_at = data.get("updated_at")
    else:
        key = "NEUTRAL"
        saved_name = ""
        effective_season = 1
        updated_at = None
    fallback = f"{str(fallback_team_name or 'EBL').strip()} Ballpark"
    p = profile(key)
    return {
        "franchise_id": str(franchise_id),
        "stadium_name": saved_name or fallback,
        "custom_name": saved_name,
        "park_profile": key,
        "profile_name": p["name"],
        "description": p["description"],
        "hitter": p["hitter"],
        "pitcher": p["pitcher"],
        "effective_season": effective_season,
        "updated_at": updated_at,
    }


def set_stadium_configuration(c, franchise_id, park_profile, stadium_name="", effective_season=1):
    key = normalize_profile_key(park_profile)
    name = str(stadium_name or "").strip()
    if len(name) > 60 or any(ord(ch) < 32 for ch in name):
        raise ValueError("INVALID_STADIUM_NAME")
    c.execute(
        """INSERT INTO franchise_stadiums(franchise_id,stadium_name,park_profile,effective_season,updated_at)
           VALUES(?,?,?,?,CURRENT_TIMESTAMP)
           ON CONFLICT(franchise_id) DO UPDATE SET
             stadium_name=excluded.stadium_name,
             park_profile=excluded.park_profile,
             effective_season=excluded.effective_season,
             updated_at=CURRENT_TIMESTAMP""",
        (str(franchise_id), name, key, max(1, int(effective_season or 1))),
    )
    return key


def park_adjustment(stadium, player_type, attribute):
    """Return one temporary attribute delta from a stadium-state/profile object."""
    if not stadium:
        return 0.0
    ptype = str(player_type or "").strip().upper()
    bucket = "pitcher" if ptype == "P" else "hitter"
    try:
        return float((stadium.get(bucket) or {}).get(str(attribute).upper(), 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


validate_profiles()
