"""Roster eligibility and capacity rules.
"""
POSITION_GROUPS=("INF","OF","PITCHER")
INF_POSITIONS={"C","1B","2B","3B","SS"}
OF_POSITIONS={"LF","CF","RF","DH","UTIL"}
PITCHER_POSITIONS={"SP","RP","LR","MR","SU","CL"}








def position_group_for_pos(pos):
    pos=str(pos or "").upper()
    if pos in PITCHER_POSITIONS:return "PITCHER"
    if pos in OF_POSITIONS:return "OF"
    return "INF"








def eligible_roster_slot_groups(player):
    """Exact roster slots a player may occupy based on broad market group.








    Catcher is never a roster gate: any position player may occupy C when a
    club needs one. Choosing C as the preferred position is a specialization
    that unlocks CALL development, not eligibility. Pitcher SP/RP labels are
    preferences only; coach rotation/bullpen assignment controls game usage.
    """
    group=str(player.get("position_group") or position_group_for_pos(player.get("primary_pos"))).upper()
    pref=str(player.get("primary_pos") or "").upper()
    if group=="PITCHER":
        slots=["SP","RP"]
    elif group=="OF":
        slots=["LF","CF","RF","DH","C"]
    else:
        slots=["1B","2B","3B","SS","DH","C"]
    if pref in slots:
        slots=[pref]+[x for x in slots if x!=pref]
    return slots
















def available_roster_roles(c,fid,player):
    """Open/CPU roles this player can legally take, preferred role first."""
    allowed=eligible_roster_slot_groups(player)
    if str(player.get("type") or "H").upper()=="P":
        allowed=[x for x in allowed if x in ("SP","RP")]
    else:
        allowed=[x for x in allowed if x in ("C","1B","2B","3B","SS","LF","CF","RF","DH")]
    if not allowed:return []
    marks=",".join("?" for _ in allowed)
    rows=c.execute(f"""SELECT position_group,occupant_type,slot_no
                       FROM roster_slots
                       WHERE franchise_id=? AND position_group IN ({marks})
                         AND occupant_type IN ('OPEN','CPU')""",
                   (fid,*allowed)).fetchall()
    rank={role:i for i,role in enumerate(allowed)}
    rows=sorted(rows,key=lambda row:(rank.get(str(row["position_group"] or "").upper(),999),0 if row["occupant_type"]=="OPEN" else 1,int(row["slot_no"] or 0)))
    seen=set();out=[]
    for row in rows:
        role=str(row["position_group"] or "").upper()
        if role and role not in seen:
            seen.add(role);out.append(role)
    return out
















def roster_offer_slot(c,fid,player,proposed_role=None):
    """Return the best open/CPU slot, honoring a proposed role when it is available."""
    roles=available_roster_roles(c,fid,player)
    target=str(proposed_role or "").upper()
    if target and target in roles:
        roles=[target]+[x for x in roles if x!=target]
    if not roles:return None
    marks=",".join("?" for _ in roles)
    return c.execute(f"""SELECT slot_no,player_id,occupant_type,position_group
                          FROM roster_slots
                          WHERE franchise_id=? AND position_group IN ({marks})
                            AND occupant_type IN ('OPEN','CPU')
                          ORDER BY CASE WHEN position_group=? THEN 0 ELSE 1 END,
                                   CASE occupant_type WHEN 'OPEN' THEN 0 ELSE 1 END,slot_no
                          LIMIT 1""",(fid,*roles,roles[0])).fetchone()
















def human_roster_count(c,fid):
    row=c.execute("SELECT COUNT(*) n FROM roster_slots WHERE franchise_id=? AND occupant_type='HUMAN'",(fid,)).fetchone()
    return int(row["n"] or 0) if row else 0
















def roster_capacity_state(c,fid):
    """authoritative 16-man EBL roster capacity."""
    rows=c.execute("""
        SELECT rs.slot_no,rs.position_group,rs.player_id,rs.occupant_type,
               p.type,p.user_id,p.active,p.status
        FROM roster_slots rs
        LEFT JOIN players p ON p.id=rs.player_id
        WHERE rs.franchise_id=?
        ORDER BY rs.slot_no
    """,(fid,)).fetchall()
    hitter_groups={"C","1B","2B","3B","SS","LF","CF","RF","DH"}
    hitters=[r for r in rows if r["position_group"] in hitter_groups]
    pitchers=[r for r in rows if r["position_group"] in ("SP","RP")]
    return {
        "total_slots":len(rows),"hitter_slots":len(hitters),"pitcher_slots":len(pitchers),
        "open_or_cpu_hitters":sum(1 for r in hitters if r["occupant_type"] in ("OPEN","CPU")),
        "open_or_cpu_pitchers":sum(1 for r in pitchers if r["occupant_type"] in ("OPEN","CPU"))
    }
