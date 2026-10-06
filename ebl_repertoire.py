"""Pitch-repertoire rules for Elite Baseball League.

Repertoire is identity, not a second attribute tree. Pitchers own 3-5 pitch types;
existing CTRL/CMD/VEL/BRK/MOV/DEC/SEQ ratings determine how well the arsenal works.
Learning a fourth/fifth pitch is a small personal-XP sink. No pitch has a private
0-100 rating and no legal repertoire can make a pitcher unusable.
"""
from __future__ import annotations

import json
from typing import Iterable, Mapping

PITCH_ORDER=(
    "FOUR_SEAM",
    "SINKER",
    "CUTTER",
    "SLIDER",
    "CURVEBALL",
    "CHANGEUP",
    "SPLITTER",
)

PITCH_CATALOG={
    "FOUR_SEAM":{
        "label":"Four-Seam",
        "emphasis":("VEL","CMD"),
        "description":"Primary velocity pitch. Velocity leads; command helps it live at the edges.",
        "speed_base":90.0,
        "skill_nudge":{"VEL":1.0,"CMD":0.5},
    },
    "SINKER":{
        "label":"Sinker",
        "emphasis":("MOV","VEL"),
        "description":"Late movement and useful velocity; naturally fits weak-contact pitchers.",
        "speed_base":88.5,
        "skill_nudge":{"MOV":1.0,"VEL":0.25},
    },
    "CUTTER":{
        "label":"Cutter",
        "emphasis":("MOV","VEL","BRK"),
        "description":"A firm movement pitch that blends velocity with shorter break.",
        "speed_base":87.0,
        "skill_nudge":{"MOV":0.75,"VEL":0.5,"BRK":0.5},
    },
    "SLIDER":{
        "label":"Slider",
        "emphasis":("BRK","MOV"),
        "description":"Breaking-ball weapon that leans on break with movement behind it.",
        "speed_base":84.5,
        "skill_nudge":{"BRK":1.0,"MOV":0.5},
    },
    "CURVEBALL":{
        "label":"Curveball",
        "emphasis":("BRK","CTRL"),
        "description":"Large shape that rewards break and enough control to land it.",
        "speed_base":79.5,
        "skill_nudge":{"BRK":1.0,"CTRL":0.5},
    },
    "CHANGEUP":{
        "label":"Changeup",
        "emphasis":("MOV","SEQ","DEC"),
        "description":"Speed separation and movement; sequencing and deception help it play up.",
        "speed_base":82.5,
        "skill_nudge":{"MOV":0.75,"SEQ":0.5,"DEC":0.5},
    },
    "SPLITTER":{
        "label":"Splitter",
        "emphasis":("MOV","BRK"),
        "description":"Late drop that leans on movement and break rather than raw velocity.",
        "speed_base":84.0,
        "skill_nudge":{"MOV":0.75,"BRK":0.75},
    },
}

MIN_PITCHES=3
MAX_PITCHES=5
LEARN_COSTS={4:5.0,5:8.0}


def normalize_pitch_key(value: str) -> str:
    raw=str(value or "").strip().upper().replace("-","_").replace(" ","_")
    aliases={
        "4_SEAM":"FOUR_SEAM","4SEAM":"FOUR_SEAM","FOURSEAM":"FOUR_SEAM",
        "CURVE":"CURVEBALL","CHANGE":"CHANGEUP","SPLIT":"SPLITTER",
    }
    return aliases.get(raw,raw)


def validate_repertoire(pitches: Iterable[str], *, exact_start: bool=False) -> list[str]:
    clean=[]
    for item in pitches or []:
        key=normalize_pitch_key(item)
        if key not in PITCH_CATALOG:
            raise ValueError("INVALID_PITCH")
        if key not in clean:
            clean.append(key)
    if exact_start and len(clean)!=MIN_PITCHES:
        raise ValueError("STARTING_REPERTOIRE_REQUIRES_3_PITCHES")
    if len(clean)<MIN_PITCHES or len(clean)>MAX_PITCHES:
        raise ValueError("INVALID_REPERTOIRE_SIZE")
    return clean


def learn_cost(current_count: int) -> float | None:
    return LEARN_COSTS.get(int(current_count)+1)


def pitch_fit_score(pitch_key: str, attrs: Mapping[str,float] | None) -> float:
    attrs=attrs or {}
    key=normalize_pitch_key(pitch_key)
    weights={
        "FOUR_SEAM":{"VEL":.70,"CMD":.30},
        "SINKER":{"MOV":.60,"VEL":.25,"CMD":.15},
        "CUTTER":{"MOV":.45,"VEL":.35,"BRK":.20},
        "SLIDER":{"BRK":.60,"MOV":.25,"DEC":.15},
        "CURVEBALL":{"BRK":.65,"CTRL":.20,"DEC":.15},
        "CHANGEUP":{"MOV":.45,"SEQ":.30,"DEC":.25},
        "SPLITTER":{"MOV":.45,"BRK":.40,"CMD":.15},
    }[key]
    return sum(float(attrs.get(a,0) or 0)*w for a,w in weights.items())


def best_fit_repertoire(attrs: Mapping[str,float] | None, count: int=MIN_PITCHES) -> list[str]:
    count=max(MIN_PITCHES,min(MAX_PITCHES,int(count)))
    ranked=sorted(PITCH_ORDER,key=lambda k:(-pitch_fit_score(k,attrs),PITCH_ORDER.index(k)))
    return ranked[:count]


def pitch_context(pitch_key: str) -> dict:
    key=normalize_pitch_key(pitch_key)
    row=PITCH_CATALOG[key]
    return {
        "key":key,
        "label":row["label"],
        "speed_base":float(row["speed_base"]),
        "skill_nudge":dict(row["skill_nudge"]),
    }


def apply_pitch_nudges(skills: Mapping[str,float], pitch_key: str) -> dict[str,float]:
    """Return a temporary pitch-specific skill copy; never mutate player ratings."""
    out={k:float(v or 0) for k,v in (skills or {}).items()}
    for attr,delta in PITCH_CATALOG[normalize_pitch_key(pitch_key)]["skill_nudge"].items():
        out[attr]=max(0.0,out.get(attr,0.0)+float(delta))
    return out


def public_catalog() -> list[dict]:
    return [{
        "key":key,
        "label":PITCH_CATALOG[key]["label"],
        "emphasis":list(PITCH_CATALOG[key]["emphasis"]),
        "description":PITCH_CATALOG[key]["description"],
    } for key in PITCH_ORDER]


def ensure_pitcher_repertoires(c) -> int:
    """Backfill deterministic 3-pitch repertoires for pitchers that predate the feature."""
    changed=0
    rows=c.execute("SELECT id,attributes_json FROM players WHERE type='P' ORDER BY id").fetchall()
    for row in rows:
        if c.execute("SELECT 1 FROM pitcher_repertoires WHERE player_id=?",(row["id"],)).fetchone():
            continue
        try: attrs=json.loads(row["attributes_json"] or "{}")
        except Exception: attrs={}
        pitches=best_fit_repertoire(attrs,MIN_PITCHES)
        c.execute("INSERT INTO pitcher_repertoires(player_id,pitches_json) VALUES(?,?)",(row["id"],json.dumps(pitches)))
        changed+=1
    return changed


def repertoire_state(c, player_id: int, attrs: Mapping[str,float] | None=None) -> dict:
    row=c.execute("SELECT pitches_json,updated_at FROM pitcher_repertoires WHERE player_id=?",(int(player_id),)).fetchone()
    if row:
        try: pitches=validate_repertoire(json.loads(row["pitches_json"] or "[]"))
        except Exception: pitches=best_fit_repertoire(attrs,MIN_PITCHES)
    else:
        pitches=best_fit_repertoire(attrs,MIN_PITCHES)
        c.execute("INSERT OR IGNORE INTO pitcher_repertoires(player_id,pitches_json) VALUES(?,?)",(int(player_id),json.dumps(pitches)))
    next_cost=learn_cost(len(pitches))
    return {
        "pitches":pitches,
        "pitch_count":len(pitches),
        "max_pitches":MAX_PITCHES,
        "next_pitch_cost":next_cost,
        "can_learn":next_cost is not None,
        "catalog":public_catalog(),
    }


def set_starting_repertoire(c, player_id: int, pitches: Iterable[str]) -> list[str]:
    clean=validate_repertoire(pitches,exact_start=True)
    c.execute(
        "INSERT INTO pitcher_repertoires(player_id,pitches_json) VALUES(?,?) "
        "ON CONFLICT(player_id) DO UPDATE SET pitches_json=excluded.pitches_json,updated_at=CURRENT_TIMESTAMP",
        (int(player_id),json.dumps(clean))
    )
    return clean


def learn_pitch(c, player_id: int, pitch_key: str, xp_wallet: float) -> dict:
    state=repertoire_state(c,player_id)
    key=normalize_pitch_key(pitch_key)
    if key not in PITCH_CATALOG:
        raise ValueError("INVALID_PITCH")
    if key in state["pitches"]:
        raise ValueError("PITCH_ALREADY_LEARNED")
    cost=learn_cost(len(state["pitches"]))
    if cost is None:
        raise ValueError("REPERTOIRE_FULL")
    if float(xp_wallet or 0)<cost:
        raise ValueError("INSUFFICIENT_XP")
    pitches=state["pitches"]+[key]
    c.execute("UPDATE pitcher_repertoires SET pitches_json=?,updated_at=CURRENT_TIMESTAMP WHERE player_id=?",(json.dumps(pitches),int(player_id)))
    return {"pitches":pitches,"cost":cost,"xp_after":round(float(xp_wallet)-cost,3)}
