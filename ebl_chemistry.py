"""Long-term player-pair familiarity for EBL.

Chemistry is earned by actual shared usage and only changes temporary game context.
It never edits permanent player ratings. Battery chemistry is visible and stronger;
infield throw/receive familiarity is intentionally subtle and mostly behind the scenes.
"""
from __future__ import annotations

BATTERY="BATTERY"
INFIELD_1B="INFIELD_1B"

BATTERY_QUALIFY_STARTS=15
BATTERY_QUALIFY_OUTS=300  # 100 innings
INFIELD_QUALIFY_GAMES=40

BATTERY_CURVE={1:.01,2:.02,3:.04,4:.08,5:.16,6:.32,7:.64,8:1.28}
INFIELD_CURVE={1:.01,2:.02,3:.04,4:.08,5:.16,6:.32,7:.64}


def chemistry_bonus(pair_type: str, consecutive_seasons: int) -> float:
    n=max(0,int(consecutive_seasons or 0))
    if pair_type==BATTERY:
        return 0.0 if n<=0 else BATTERY_CURVE.get(n,2.0)
    if pair_type==INFIELD_1B:
        return 0.0 if n<=0 else INFIELD_CURVE.get(n,1.0)
    return 0.0


def canonical_pair(pair_type: str, player_a_id: int, player_b_id: int) -> tuple[int,int]:
    a,b=int(player_a_id),int(player_b_id)
    # Battery is directional: pitcher -> catcher. Infield is directional: thrower -> first baseman.
    return a,b


def record_usage(c, season: int, pair_type: str, player_a_id: int, player_b_id: int, *, games: int=0, starts: int=0, outs: int=0) -> None:
    if not player_a_id or not player_b_id or int(player_a_id)==int(player_b_id):
        return
    a,b=canonical_pair(pair_type,player_a_id,player_b_id)
    c.execute(
        """INSERT INTO relationship_season_usage(
               season,pair_type,player_a_id,player_b_id,games,starts,outs
           ) VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(season,pair_type,player_a_id,player_b_id) DO UPDATE SET
             games=games+excluded.games,
             starts=starts+excluded.starts,
             outs=outs+excluded.outs""",
        (int(season),str(pair_type),a,b,int(games),int(starts),int(outs))
    )


def record_game_usage(c, season: int, defense_players: dict, box: dict) -> None:
    """Record the relationships that actually shared this game."""
    for fid,positions in (defense_players or {}).items():
        catcher_id=(positions or {}).get("C")
        if catcher_id:
            for line in (box.get("pitchers",{}).get(fid,[]) or []):
                pid=int(line.get("player_id",0) or 0)
                outs=int(line.get("OUTS",0) or 0)
                if pid and outs>0:
                    record_usage(c,season,BATTERY,pid,int(catcher_id),games=1,starts=1 if int(line.get("GS",0) or 0) else 0,outs=outs)
        first_id=(positions or {}).get("1B")
        if first_id:
            for pos in ("SS","2B","3B"):
                thrower=(positions or {}).get(pos)
                if thrower:
                    record_usage(c,season,INFIELD_1B,int(thrower),int(first_id),games=1)


def _qualifies(row) -> bool:
    if row["pair_type"]==BATTERY:
        return int(row["starts"] or 0)>=BATTERY_QUALIFY_STARTS or int(row["outs"] or 0)>=BATTERY_QUALIFY_OUTS
    if row["pair_type"]==INFIELD_1B:
        return int(row["games"] or 0)>=INFIELD_QUALIFY_GAMES
    return False


def finalize_relationship_season(c, season: int) -> dict:
    """Convert qualifying shared usage into next-season familiarity tiers."""
    qualified=0
    rows=c.execute(
        "SELECT * FROM relationship_season_usage WHERE season=? ORDER BY pair_type,player_a_id,player_b_id",
        (int(season),)
    ).fetchall()
    for row in rows:
        if not _qualifies(row):
            c.execute(
                "UPDATE relationship_season_usage SET qualified=0,consecutive_after=0,bonus_after=0 WHERE season=? AND pair_type=? AND player_a_id=? AND player_b_id=?",
                (int(season),row["pair_type"],row["player_a_id"],row["player_b_id"])
            )
            continue
        rel=c.execute(
            "SELECT * FROM player_relationships WHERE pair_type=? AND player_a_id=? AND player_b_id=?",
            (row["pair_type"],row["player_a_id"],row["player_b_id"])
        ).fetchone()
        if rel and int(rel["last_qualified_season"] or 0)==int(season)-1:
            consecutive=int(rel["consecutive_seasons"] or 0)+1
        else:
            consecutive=1
        total=int(rel["total_qualified_seasons"] or 0)+1 if rel else 1
        bonus=chemistry_bonus(row["pair_type"],consecutive)
        c.execute(
            """INSERT INTO player_relationships(
                   pair_type,player_a_id,player_b_id,consecutive_seasons,total_qualified_seasons,last_qualified_season,bonus
               ) VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(pair_type,player_a_id,player_b_id) DO UPDATE SET
                 consecutive_seasons=excluded.consecutive_seasons,
                 total_qualified_seasons=excluded.total_qualified_seasons,
                 last_qualified_season=excluded.last_qualified_season,
                 bonus=excluded.bonus,
                 updated_at=CURRENT_TIMESTAMP""",
            (row["pair_type"],row["player_a_id"],row["player_b_id"],consecutive,total,int(season),bonus)
        )
        c.execute(
            "UPDATE relationship_season_usage SET qualified=1,consecutive_after=?,bonus_after=? WHERE season=? AND pair_type=? AND player_a_id=? AND player_b_id=?",
            (consecutive,bonus,int(season),row["pair_type"],row["player_a_id"],row["player_b_id"])
        )
        qualified+=1
    # Continuity must actually be continuous. Pairs that did not qualify this
    # season keep their lifetime history but lose the active streak/bonus before
    # the next season opens.
    c.execute(
        "UPDATE player_relationships SET consecutive_seasons=0,bonus=0,updated_at=CURRENT_TIMESTAMP "
        "WHERE last_qualified_season IS NULL OR last_qualified_season<?",
        (int(season),)
    )
    return {"season":int(season),"qualified_relationships":qualified}


def relationship_state(c, pair_type: str, player_a_id: int, player_b_id: int) -> dict:
    row=c.execute(
        "SELECT * FROM player_relationships WHERE pair_type=? AND player_a_id=? AND player_b_id=?",
        (pair_type,int(player_a_id),int(player_b_id))
    ).fetchone()
    if not row:
        return {"pair_type":pair_type,"consecutive_seasons":0,"total_qualified_seasons":0,"last_qualified_season":None,"bonus":0.0}
    return dict(row)


def battery_bonus(c, pitcher_id: int, catcher_id: int | None) -> float:
    if not catcher_id:return 0.0
    return float(relationship_state(c,BATTERY,pitcher_id,catcher_id).get("bonus",0) or 0)


def infield_receive_bonus(c, thrower_id: int, first_base_id: int | None) -> float:
    if not first_base_id:return 0.0
    return float(relationship_state(c,INFIELD_1B,thrower_id,first_base_id).get("bonus",0) or 0)


def player_relationships(c, player_id: int, limit: int=12) -> dict:
    pid=int(player_id)
    batteries=[]
    for row in c.execute(
        """SELECT r.*,pa.name AS pitcher_name,pb.name AS catcher_name
             FROM player_relationships r
             JOIN players pa ON pa.id=r.player_a_id
             JOIN players pb ON pb.id=r.player_b_id
            WHERE r.pair_type=? AND (r.player_a_id=? OR r.player_b_id=?)
            ORDER BY r.bonus DESC,r.total_qualified_seasons DESC LIMIT ?""",
        (BATTERY,pid,pid,int(limit))
    ).fetchall():
        batteries.append(dict(row))
    # Infield familiarity remains intentionally low-salience. Return counts/history
    # for future profile storytelling without exposing a min-max meter in the UI.
    infield_count=c.execute(
        "SELECT COUNT(*) n FROM player_relationships WHERE pair_type=? AND (player_a_id=? OR player_b_id=?)",
        (INFIELD_1B,pid,pid)
    ).fetchone()["n"]
    return {"batteries":batteries,"infield_relationship_count":int(infield_count or 0)}
