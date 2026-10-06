"""Elite Baseball League league structure, scheduling, and postseason rules.

This module owns stable league/season primitives that are independent of the HTTP layer:
season membership, division assignment, regular-season schedule construction, and
postseason bracket helpers.

Keep request routing, simulation, transactions, awards, and news orchestration in
server.py. Architecture-only moves preserve behavior; owner-approved league-rule changes
are implemented here with explicit regression coverage.
"""
import math
import random
from collections import Counter
import itertools

from ebl_config import (
    DIVISIONS,
    REGULAR_SEASON_CALENDAR_DAYS,
    REGULAR_SEASON_GAMES,
    REGULAR_SEASON_REST_SERIES,
    REGULAR_SEASON_SERIES,
)

MIN_ACTIVE_TEAMS = 8
FULL_LEAGUE_TEAM_COUNT = 30
FULL_LEAGUE_SIZE = 15
FULL_DIVISION_SIZE = 5
# Stable internal keys. Player-facing names can change later without rewriting season history.
FULL_LEAGUE_KEYS = ("EBL-A", "EBL-B")
FULL_SCHEDULE_FORMAT = "two_league_36_30_15_v1"


def _season_number(c):
    row=c.execute("SELECT v FROM league_state WHERE k='season'").fetchone()
    return int(row["v"]) if row else 1

def _division_labels(team_count):
    if team_count<=10:
        return ["Heritage","Pioneer"]
    if team_count<=16:
        return ["Heritage","Liberty","Frontier","Pioneer"]
    if team_count<=24:
        return ["Heritage","Liberty","Union","Frontier"]
    return list(DIVISIONS)

def _full_league_key_for_division(division):
    try:
        idx=DIVISIONS.index(str(division))
    except ValueError:
        return None
    return FULL_LEAGUE_KEYS[0] if idx<3 else FULL_LEAGUE_KEYS[1]

def _backfill_full_league_keys(c,season):
    active=c.execute(
        "SELECT COUNT(*) n FROM franchise_seasons WHERE season=? AND status='ACTIVE'",
        (int(season),)
    ).fetchone()["n"]
    if int(active or 0)!=FULL_LEAGUE_TEAM_COUNT:
        return
    for division in DIVISIONS:
        league_key=_full_league_key_for_division(division)
        c.execute(
            """UPDATE franchise_seasons SET conference=?
               WHERE season=? AND status='ACTIVE' AND division=?
                 AND (conference IS NULL OR TRIM(conference)='')""",
            (league_key,int(season),division)
        )

def ensure_season_membership(c,season):
    existing=c.execute(
        "SELECT COUNT(*) n FROM franchise_seasons WHERE season=?",
        (season,)
    ).fetchone()["n"]
    if existing:
        _backfill_full_league_keys(c,season)
        return

    # Preserve an already-built season by activating every franchise that
    # actually appears on that season's schedule. Fresh seasons honor the
    # commissioner-selected league size.
    participants=[
        r["franchise_id"] for r in c.execute(
            """SELECT franchise_id FROM (
                   SELECT away_id franchise_id FROM games WHERE season=?
                   UNION
                   SELECT home_id franchise_id FROM games WHERE season=?
               ) ORDER BY franchise_id""",
            (season,season)
        ).fetchall()
    ]
    if not participants:
        pref=c.execute("SELECT v FROM league_config WHERE k='active_team_count'").fetchone()
        try:
            desired=int(pref["v"]) if pref else MIN_ACTIVE_TEAMS
        except (TypeError,ValueError):
            desired=MIN_ACTIVE_TEAMS
        total=c.execute("SELECT COUNT(*) n FROM franchises").fetchone()["n"]
        desired=max(MIN_ACTIVE_TEAMS,min(desired,total))
        if desired%2: desired-=1
        participants=[
            r["id"] for r in c.execute(
                "SELECT id FROM franchises ORDER BY id LIMIT ?",
                (desired,)
            ).fetchall()
        ]

    all_ids=[r["id"] for r in c.execute("SELECT id FROM franchises ORDER BY id").fetchall()]
    active_set=set(participants)
    labels=_division_labels(len(participants))
    per_div=max(1,math.ceil(len(participants)/len(labels)))
    active_index=0
    for fid in all_ids:
        if fid in active_set:
            div=labels[min(len(labels)-1,active_index//per_div)]
            conference=_full_league_key_for_division(div) if len(participants)==FULL_LEAGUE_TEAM_COUNT else None
            c.execute(
                """INSERT OR IGNORE INTO franchise_seasons(
                       season,franchise_id,status,division,conference,expansion_team
                   ) VALUES(?,?, 'ACTIVE', ?, ?, 0)""",
                (season,fid,div,conference)
            )
            c.execute(
                """UPDATE franchises
                   SET established_season=COALESCE(established_season,?)
                   WHERE id=?""",
                (season,fid)
            )
            active_index+=1
        else:
            c.execute(
                """INSERT OR IGNORE INTO franchise_seasons(
                       season,franchise_id,status,division,conference,expansion_team
                   ) VALUES(?,?, 'DORMANT', NULL, NULL, 0)""",
                (season,fid)
            )
    _backfill_full_league_keys(c,season)

def active_franchise_ids(c,season=None):
    season=_season_number(c) if season is None else int(season)
    ensure_season_membership(c,season)
    return [
        r["franchise_id"] for r in c.execute(
            """SELECT franchise_id
               FROM franchise_seasons
               WHERE season=? AND status='ACTIVE'
               ORDER BY franchise_id""",
            (season,)
        ).fetchall()
    ]

def set_season_membership(c,season,active_ids):
    active_ids=list(dict.fromkeys(str(x) for x in active_ids))
    if len(active_ids)<MIN_ACTIVE_TEAMS:
        raise ValueError("MINIMUM_8_TEAMS")
    if len(active_ids)%2:
        raise ValueError("EVEN_TEAM_COUNT_REQUIRED")

    valid={r["id"] for r in c.execute("SELECT id FROM franchises").fetchall()}
    if any(fid not in valid for fid in active_ids):
        raise ValueError("UNKNOWN_FRANCHISE")

    previous_active=set(active_franchise_ids(c,season-1)) if season>1 else set()
    labels=_division_labels(len(active_ids))
    per_div=max(1,math.ceil(len(active_ids)/len(labels)))
    active_order={fid:i for i,fid in enumerate(active_ids)}

    c.execute("DELETE FROM franchise_seasons WHERE season=?",(season,))
    for fid in sorted(valid):
        if fid in active_order:
            idx=active_order[fid]
            div=labels[min(len(labels)-1,idx//per_div)]
            conference=_full_league_key_for_division(div) if len(active_ids)==FULL_LEAGUE_TEAM_COUNT else None
            expansion=1 if season>1 and fid not in previous_active else 0
            c.execute(
                """INSERT INTO franchise_seasons(
                       season,franchise_id,status,division,conference,expansion_team
                   ) VALUES(?,?, 'ACTIVE', ?, ?, ?)""",
                (season,fid,div,conference,expansion)
            )
            c.execute(
                """UPDATE franchises
                   SET established_season=COALESCE(established_season,?)
                   WHERE id=?""",
                (season,fid)
            )
        else:
            c.execute(
                """INSERT INTO franchise_seasons(
                       season,franchise_id,status,division,conference,expansion_team
                   ) VALUES(?,?, 'DORMANT', NULL, NULL, 0)""",
                (season,fid)
            )
    _backfill_full_league_keys(c,season)

def season_division(c,season,fid):
    ensure_season_membership(c,season)
    row=c.execute(
        "SELECT division FROM franchise_seasons WHERE season=? AND franchise_id=?",
        (season,fid)
    ).fetchone()
    return row["division"] if row and row["division"] else division_for(fid)

def season_conference(c,season,fid):
    ensure_season_membership(c,season)
    row=c.execute(
        "SELECT conference,division FROM franchise_seasons WHERE season=? AND franchise_id=?",
        (season,fid)
    ).fetchone()
    if not row:
        return None
    return row["conference"] or _full_league_key_for_division(row["division"])

def _circle_series_rounds(team_count,series_count=REGULAR_SEASON_SERIES):
    """Return perfect-match series rounds for any supported even league size."""
    arr=list(range(team_count));base=[]
    for _ in range(team_count-1):
        base.append([(arr[i],arr[-1-i]) for i in range(team_count//2)])
        arr=[arr[0]]+[arr[-1]]+arr[1:-1]
    out=[]
    for idx in range(series_count):
        pairs=list(base[idx%len(base)])
        if (idx//len(base))%2:
            pairs=[(b,a) for a,b in pairs]
        out.append(pairs)
    return out

def _perfect_matching_from_multiset(edge_counts,team_count,rng,node_limit=120000):
    """Small deterministic backtracker used to decompose the 30-team series map."""
    unmatched=set(range(team_count));nodes=[0]
    def rec():
        nodes[0]+=1
        if nodes[0]>node_limit:return None
        if not unmatched:return []
        best_v=None;best_candidates=None
        for v in tuple(unmatched):
            cand=[u for u in unmatched if u!=v and edge_counts.get(tuple(sorted((u,v))),0)>0]
            if not cand:return None
            if best_candidates is None or len(cand)<len(best_candidates):
                best_v=v;best_candidates=cand
                if len(cand)==1:break
        v=best_v;options=[]
        for u in best_candidates:
            edge=tuple(sorted((u,v)))
            neighbor_count=sum(1 for w in unmatched if w not in (u,v) and edge_counts.get(tuple(sorted((u,w))),0)>0)
            options.append((edge_counts[edge],-neighbor_count,rng.random(),u))
        options.sort(reverse=True)
        unmatched.remove(v)
        for _copies,_constraint,_jitter,u in options:
            unmatched.remove(u)
            rest=rec()
            if rest is not None:
                unmatched.add(u);unmatched.add(v)
                return [(v,u)]+rest
            unmatched.add(u)
        unmatched.add(v)
        return None
    return rec()

def _full_league_metadata(c,season,fids):
    rows=c.execute(
        """SELECT franchise_id,division,conference FROM franchise_seasons
           WHERE season=? AND status='ACTIVE' ORDER BY franchise_id""",
        (int(season),)
    ).fetchall()
    by_id={r["franchise_id"]:dict(r) for r in rows}
    meta=[]
    for fid in fids:
        row=by_id.get(fid) or {}
        division=row.get("division") or division_for(fid)
        conference=row.get("conference") or _full_league_key_for_division(division)
        meta.append({"fid":fid,"division":division,"conference":conference})
    return meta

def _structured_series_target_30(c,season,fids):
    """Build the canonical 27-series full-league opponent map.

    Per club:
      * 12 division series: four rivals, three series each (36 games)
      * 10 same-league non-division series: every other club in its 15-team league once (30 games)
      * 5 interleague series: a rotating third of the opposite league (15 games)

    The three-season interleague cycle covers all 15 clubs in the opposite league.
    """
    if len(fids)!=FULL_LEAGUE_TEAM_COUNT:
        raise ValueError("FULL_LEAGUE_REQUIRES_30_TEAMS")
    meta=_full_league_metadata(c,season,fids)
    by_div={}
    by_conf={}
    for idx,row in enumerate(meta):
        by_div.setdefault(row["division"],[]).append(idx)
        by_conf.setdefault(row["conference"],[]).append(idx)
    if sorted(len(v) for v in by_div.values()) != [FULL_DIVISION_SIZE]*6:
        raise RuntimeError("FULL_LEAGUE_DIVISION_SHAPE_MISMATCH")
    if sorted(len(v) for v in by_conf.values()) != [FULL_LEAGUE_SIZE]*2:
        raise RuntimeError("FULL_LEAGUE_CONFERENCE_SHAPE_MISMATCH")

    target=Counter()
    pair_kind={}

    # Every division rival appears in three series.
    for division in DIVISIONS:
        teams=sorted(by_div.get(division,[]))
        for a,b in itertools.combinations(teams,2):
            edge=tuple(sorted((a,b)))
            target[edge]+=3
            pair_kind[edge]="DIVISION"

    # Every other team in the same 15-team league appears once.
    for conference in FULL_LEAGUE_KEYS:
        teams=sorted(by_conf.get(conference,[]))
        for a,b in itertools.combinations(teams,2):
            if meta[a]["division"]==meta[b]["division"]:
                continue
            edge=tuple(sorted((a,b)))
            target[edge]+=1
            pair_kind[edge]="SAME_LEAGUE"

    # Five interleague opponents per club. The five cyclic offsets rotate by
    # season, so Seasons 1-3 cover all 15 opposite-league clubs exactly once.
    left=sorted(by_conf[FULL_LEAGUE_KEYS[0]])
    right=sorted(by_conf[FULL_LEAGUE_KEYS[1]])
    phase=(int(season)-1)%3
    offsets=range(phase*5,phase*5+5)
    for local_i,a in enumerate(left):
        for offset in offsets:
            b=right[(local_i+offset)%FULL_LEAGUE_SIZE]
            edge=tuple(sorted((a,b)))
            target[edge]+=1
            pair_kind[edge]="INTERLEAGUE"

    degree=[0]*FULL_LEAGUE_TEAM_COUNT
    for (a,b),copies in target.items():
        degree[a]+=copies;degree[b]+=copies
    if set(degree)!={REGULAR_SEASON_SERIES}:
        raise RuntimeError(f"FULL_LEAGUE_SERIES_DEGREE_MISMATCH:{degree}")
    return target,pair_kind,meta

def _structured_series_rounds_30(c,season,fids):
    target,pair_kind,meta=_structured_series_target_30(c,season,fids)
    for attempt in range(60):
        rng=random.Random(7500831+int(season)*997+attempt*104729)
        remaining=target.copy();rounds=[];failed=False
        for _ in range(REGULAR_SEASON_SERIES):
            match=_perfect_matching_from_multiset(remaining,FULL_LEAGUE_TEAM_COUNT,rng)
            if not match:
                failed=True;break
            match=[tuple(sorted(x)) for x in match]
            rounds.append(match)
            for edge in match:remaining[edge]-=1
        if not failed and not any(remaining.values()):
            return rounds,pair_kind,meta
    raise RuntimeError("SERIES_SCHEDULE_DECOMPOSITION_FAILED")

def _structured_home_series_30(rounds,pair_kind,meta,season):
    """Orient the 30-team schedule with exact, repeatable home/away rules.

    Division rivals split 3 series 2/1 and reverse the advantage next season.
    Same-league non-division matchups flip parks every season and give every club
    exactly five home series from those ten opponents. Interleague matchups give
    one league three home series and the other two, then flip when that five-team
    interleague group returns three seasons later. The result is always 13/14
    home series per club.
    """
    occurrences={}
    for ridx,pairs in enumerate(rounds):
        for pidx,(a,b) in enumerate(pairs):
            occurrences.setdefault(tuple(sorted((a,b))),[]).append((ridx,pidx,a,b))

    orientation={}
    season_flip=(int(season)-1)%2
    interleague_cycle=(int(season)-1)//3

    # Division: regular five-team tournament gives each club two 2-home rivals
    # and two 1-home rivals -> exactly six home division series.
    for edge,items in occurrences.items():
        kind=pair_kind[edge]
        a,b=edge
        if kind!="DIVISION":
            continue
        div=meta[a]["division"]
        teams=sorted(i for i,row in enumerate(meta) if row["division"]==div)
        local={team:i for i,team in enumerate(teams)}
        ai,bi=local[a],local[b]
        a_adv=((bi-ai)%5 in (1,2))
        if season_flip:
            a_adv=not a_adv
        a_home_count=2 if a_adv else 1
        ordered=sorted(items)
        for k,(ridx,pidx,_x,_y) in enumerate(ordered):
            a_home=k<a_home_count
            orientation[(ridx,pidx)]=(b,a) if a_home else (a,b)

    # Same-league non-division: the three divisions form a cycle. The advantaged
    # division gets a 3/2 home split against the other; complement the whole rule
    # in alternating seasons. Each club totals exactly five home series here.
    div_index={d:i for i,d in enumerate(DIVISIONS)}
    for edge,items in occurrences.items():
        kind=pair_kind[edge]
        if kind!="SAME_LEAGUE":
            continue
        a,b=edge
        da,db=div_index[meta[a]["division"]],div_index[meta[b]["division"]]
        conf_start=0 if meta[a]["conference"]==FULL_LEAGUE_KEYS[0] else 3
        la,lb=da-conf_start,db-conf_start
        # In the 3-division cycle: 0 > 1, 1 > 2, 2 > 0.
        a_div_adv=((lb-la)%3==1)
        teams_a=sorted(i for i,row in enumerate(meta) if row["division"]==meta[a]["division"])
        teams_b=sorted(i for i,row in enumerate(meta) if row["division"]==meta[b]["division"])
        ia,ib=teams_a.index(a),teams_b.index(b)
        if a_div_adv:
            a_home=((ib-ia)%5 in (0,1,2))
        else:
            # b is the advantaged division; a hosts on the complementary 2/5 set.
            b_home=((ia-ib)%5 in (0,1,2))
            a_home=not b_home
        if season_flip:
            a_home=not a_home
        ridx,pidx,_x,_y=items[0]
        orientation[(ridx,pidx)]=(b,a) if a_home else (a,b)

    # Interleague: each season's five cyclic matchings alternate which league
    # hosts. When the same group returns three seasons later, every matchup flips.
    left=sorted(i for i,row in enumerate(meta) if row["conference"]==FULL_LEAGUE_KEYS[0])
    left_local={team:i for i,team in enumerate(left)}
    phase=(int(season)-1)%3
    for edge,items in occurrences.items():
        kind=pair_kind[edge]
        if kind!="INTERLEAGUE":
            continue
        a,b=edge
        if meta[a]["conference"]==FULL_LEAGUE_KEYS[0]:
            left_team,right_team=a,b
        else:
            left_team,right_team=b,a
        right=sorted(i for i,row in enumerate(meta) if row["conference"]==FULL_LEAGUE_KEYS[1])
        right_local={team:i for i,team in enumerate(right)}
        offset=(right_local[right_team]-left_local[left_team])%FULL_LEAGUE_SIZE
        local_k=offset-phase*5
        if local_k not in range(5):
            raise RuntimeError("INTERLEAGUE_ROTATION_ORIENTATION_MISMATCH")
        left_home=(local_k%2==0)
        if interleague_cycle%2:
            left_home=not left_home
        ridx,pidx,_x,_y=items[0]
        orientation[(ridx,pidx)]=(right_team,left_team) if left_home else (left_team,right_team)

    oriented=[]
    home_series=[0]*FULL_LEAGUE_TEAM_COUNT
    for ridx,pairs in enumerate(rounds):
        row=[]
        for pidx,_pair in enumerate(pairs):
            away,home=orientation[(ridx,pidx)]
            row.append((away,home));home_series[home]+=1
        oriented.append(row)
    if set(home_series)!={13,14}:
        raise RuntimeError(f"FULL_LEAGUE_HOME_SERIES_MISMATCH:{home_series}")
    return oriented

def _order_series_rounds_no_repeat(rounds,team_count):
    """Reorder series blocks so no club faces the same opponent in back-to-back series."""
    if len(rounds)<2:return rounds
    maps=[]
    for pairs in rounds:
        opp={}
        for a,b in pairs:opp[int(a)]=int(b);opp[int(b)]=int(a)
        maps.append(opp)
    n=len(rounds)
    compatible=[[False]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i==j:continue
            compatible[i][j]=all(maps[i].get(t)!=maps[j].get(t) for t in range(team_count))
    degree=[sum(1 for x in compatible[i] if x) for i in range(n)]
    for start in sorted(range(n),key=lambda i:degree[i]):
        path=[start];used={start}
        def rec(v):
            if len(path)==n:return True
            candidates=[u for u in range(n) if u not in used and compatible[v][u]]
            candidates.sort(key=lambda u:sum(1 for w in range(n) if w not in used and w!=u and compatible[u][w]))
            for u in candidates:
                used.add(u);path.append(u)
                if rec(u):return True
                path.pop();used.remove(u)
            return False
        if rec(start):return [rounds[i] for i in path]
    raise RuntimeError("SERIES_ROUND_ORDER_FAILED")

def _balanced_home_series(rounds,team_count):
    """Orient series for both pair-level and season-level home/away balance.








    Repeated opponents split their series evenly between parks whenever possible.
    The one leftover occurrence from every odd-multiplicity pairing forms an odd-degree
    residual graph; a dummy Euler edge per club then guarantees 13/14 total home series.
    """
    edges=[];round_edge_ids=[];groups={}
    for round_pairs in rounds:
        ids=[]
        for a,b in round_pairs:
            a=int(a);b=int(b);eid=len(edges);ids.append(eid);edges.append((a,b))
            groups.setdefault(tuple(sorted((a,b))),[]).append(eid)
        round_edge_ids.append(ids)








    orientation={};residual=[]
    for pair,ids in groups.items():
        a,b=pair
        ordered=list(ids)
        while len(ordered)>=2:
            e1=ordered.pop(0);e2=ordered.pop(0)
            orientation[e1]=(a,b)   # b hosts one
            orientation[e2]=(b,a)   # a hosts one
        if ordered:residual.append(ordered[0])








    # Every club has odd residual degree because its full slate is 27 series and
    # all already-balanced pair groups removed an even number of edges.
    dummy=team_count
    temp_edges=[(edges[eid][0],edges[eid][1],eid) for eid in residual]
    temp_edges.extend((dummy,team,None) for team in range(team_count))
    adjacency=[[] for _ in range(team_count+1)]
    for tid,(a,b,orig) in enumerate(temp_edges):
        adjacency[a].append((tid,b));adjacency[b].append((tid,a))
    used=[False]*len(temp_edges);stack=[dummy]
    while stack:
        v=stack[-1]
        while adjacency[v] and used[adjacency[v][-1][0]]:adjacency[v].pop()
        if not adjacency[v]:stack.pop();continue
        tid,u=adjacency[v].pop()
        if used[tid]:continue
        used[tid]=True
        orig=temp_edges[tid][2]
        if orig is not None:orientation[orig]=(v,u)
        stack.append(u)
    if not all(used) or len(orientation)!=len(edges):
        raise RuntimeError("SERIES_HOME_ORIENTATION_FAILED")








    oriented=[]
    for ids in round_edge_ids:
        oriented.append([orientation[eid] for eid in ids])
    return oriented

def _team_regular_games_before(c,season,fid,league_day):
    return int(c.execute(
        """SELECT COUNT(*) n FROM games
           WHERE season=? AND status='FINAL' AND league_day<? AND league_day<=?
             AND (away_id=? OR home_id=?)""",
        (int(season),int(league_day),REGULAR_SEASON_CALENDAR_DAYS,str(fid),str(fid))
    ).fetchone()["n"] or 0)

def _team_postseason_games_before(c,season,fid,league_day):
    return int(c.execute(
        """SELECT COUNT(*) n FROM games
           WHERE season=? AND status='FINAL' AND league_day>? AND league_day<?
             AND (away_id=? OR home_id=?)""",
        (int(season),REGULAR_SEASON_CALENDAR_DAYS,int(league_day),str(fid),str(fid))
    ).fetchone()["n"] or 0)

def generate_season_schedule(c,season):
    fids=active_franchise_ids(c,season);n=len(fids)
    if n<MIN_ACTIVE_TEAMS:raise ValueError("MINIMUM_8_TEAMS")
    if n%2:raise ValueError("EVEN_TEAM_COUNT_REQUIRED")








    # Full EBL has a baseball-shaped 36/30/15 split: 36 division games,
    # 30 games against the other ten clubs in the same 15-team league, and
    # 15 rotating interleague games. Smaller leagues retain the circle-method
    # opponent rotation but use the same 27-series / 95-calendar-day rhythm.
    if n==FULL_LEAGUE_TEAM_COUNT:
        rounds,pair_kind,meta=_structured_series_rounds_30(c,season,fids)
        rounds=_order_series_rounds_no_repeat(rounds,n)
        rounds=_structured_home_series_30(rounds,pair_kind,meta,season)
    else:
        rounds=_circle_series_rounds(n)
        rounds=_order_series_rounds_no_repeat(rounds,n)
        rounds=_balanced_home_series(rounds,n)








    gid=1;calendar_day=1
    team_games={fid:0 for fid in fids}
    for series_no,round_pairs in enumerate(rounds,1):
        rest_round=series_no in REGULAR_SEASON_REST_SERIES
        duration=4 if rest_round else 3
        for pair_index,(away_i,home_i) in enumerate(round_pairs):
            away=fids[away_i];home=fids[home_i]
            # On a rest round half the series rest first and half rest last. The
            # middle two dates still carry a full league slate, while the outside
            # dates create real team-specific recovery days instead of league-wide pauses.
            if rest_round and (pair_index+series_no+int(season))%2:
                game_days=(calendar_day+1,calendar_day+2,calendar_day+3)
            else:
                game_days=(calendar_day,calendar_day+1,calendar_day+2)
            for game_day in game_days:
                game_id=f"S{season:02d}-G{gid:04d}"
                c.execute(
                    """INSERT INTO games(id,season,league_day,away_id,home_id,status)
                       VALUES(?,?,?,?,?,'SCHEDULED')""",
                    (game_id,int(season),int(game_day),away,home)
                )
                gid+=1;team_games[away]+=1;team_games[home]+=1
        calendar_day+=duration








    if calendar_day-1!=REGULAR_SEASON_CALENDAR_DAYS:
        raise RuntimeError(f"REGULAR_CALENDAR_LENGTH_MISMATCH:{calendar_day-1}")
    bad={fid:g for fid,g in team_games.items() if g!=REGULAR_SEASON_GAMES}
    if bad:raise RuntimeError(f"REGULAR_TEAM_GAME_COUNT_MISMATCH:{bad}")
    if n==FULL_LEAGUE_TEAM_COUNT:
        c.execute(
            "INSERT INTO league_config(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            (f"schedule_format_s{int(season)}",FULL_SCHEDULE_FORMAT)
        )

def ensure_current_full_league_schedule_format(c,season):
    """Safely upgrade an unplayed 30-team season to the current schedule format.

    Existing history always wins. A schedule is rebuilt only when the season is
    still on league day 0 and has no FINAL games. Otherwise the current schedule
    is preserved and the new format begins the next time a schedule is generated.
    """
    season=int(season)
    active=active_franchise_ids(c,season)
    if len(active)!=FULL_LEAGUE_TEAM_COUNT:
        return {"changed":False,"reason":"NOT_FULL_LEAGUE"}
    key=f"schedule_format_s{season}"
    row=c.execute("SELECT v FROM league_config WHERE k=?",(key,)).fetchone()
    if row and str(row["v"] or "")==FULL_SCHEDULE_FORMAT:
        return {"changed":False,"reason":"CURRENT"}
    state={r["k"]:r["v"] for r in c.execute(
        "SELECT k,v FROM league_state WHERE k IN ('season','league_day','phase')"
    ).fetchall()}
    day=int(state.get("league_day") or 0)
    final_count=int(c.execute(
        "SELECT COUNT(*) n FROM games WHERE season=? AND status='FINAL'",(season,)
    ).fetchone()["n"] or 0)
    if day!=0 or final_count:
        return {"changed":False,"reason":"SEASON_ALREADY_STARTED","league_day":day,"final_games":final_count}
    c.execute("DELETE FROM games WHERE season=?",(season,))
    generate_season_schedule(c,season)
    return {"changed":True,"reason":"UPGRADED","games_created":int(c.execute(
        "SELECT COUNT(*) n FROM games WHERE season=?",(season,)
    ).fetchone()["n"] or 0)}

def division_for(fid):
    try:
        n=int(fid.split("F")[-1])
    except:return "Unknown"
    return DIVISIONS[min(5,(n-1)//5)]

def team_name(c,fid):
    r=c.execute("SELECT name FROM franchises WHERE id=?",(fid,)).fetchone()
    return r["name"] if r else fid

def playoff_teams(c):
    season=_season_number(c)
    active=active_franchise_ids(c,season)
    if len(active)<8:
        return []
    q=",".join("?" for _ in active)
    teams=[dict(x) for x in c.execute(
        f"""SELECT id,name,wins,losses,runs_for,runs_against
            FROM franchises
            WHERE id IN ({q})""",
        active
    )]
    for t in teams:
        t["division"]=season_division(c,season,t["id"])
        t["diff"]=t["runs_for"]-t["runs_against"]








    # Existing postseason format is an eight-team bracket. For an eight-team
    # league everyone reaches the postseason; at larger sizes the best eight
    # records qualify. Seeding still determines every matchup/home-field edge.
    teams.sort(
        key=lambda t:(t["wins"],t["diff"],t["runs_for"]),
        reverse=True
    )
    return teams[:8]

def playoff_series_games(c,season,code):
    return [dict(x) for x in c.execute(
        "SELECT * FROM games WHERE season=? AND id LIKE ? ORDER BY league_day,id",
        (season,f"S{season:02d}-{code}-G%")
    )]

def playoff_series_winner(c,season,code,wins_needed):
    games=playoff_series_games(c,season,code)
    wins={}
















    for g in games:
        if g["status"]!="FINAL":
            continue
















        winner=g["away_id"] if g["away_runs"]>g["home_runs"] else g["home_id"]
        wins[winner]=wins.get(winner,0)+1
















        if wins[winner]>=wins_needed:
            return winner
















    return None

def schedule_series_game(c,season,code,game_no,day,team_a,team_b):
    # team_a owns home-field advantage
    if game_no in (1,2,5,7):
        away,home=team_b,team_a
    else:
        away,home=team_a,team_b
















    gid=f"S{season:02d}-{code}-G{game_no}"
















    c.execute(
        "INSERT OR IGNORE INTO games(id,season,league_day,away_id,home_id,status) VALUES(?,?,?,?,?,'SCHEDULED')",
        (gid,season,day,away,home)
    )

def playoff_series_summary(c,season,code,wins_needed):
    games=playoff_series_games(c,season,code)
    wins={}
    teams=[]
    for g in games:
        for fid in (g["away_id"],g["home_id"]):
            if fid not in teams:
                teams.append(fid)
        if g["status"]=="FINAL":
            w=g["away_id"] if g["away_runs"]>g["home_runs"] else g["home_id"]
            wins[w]=wins.get(w,0)+1
    names={}
    if teams:
        q=",".join("?" for _ in teams)
        names={r["id"]:r["name"] for r in c.execute(f"SELECT id,name FROM franchises WHERE id IN ({q})",teams)}
    winner=None
    for fid,n in wins.items():
        if n>=wins_needed:
            winner=fid
            break
    return {
        "code":code,
        "wins_needed":wins_needed,
        "teams":[{"id":fid,"name":names.get(fid,fid),"wins":wins.get(fid,0)} for fid in teams],
        "winner_id":winner,
        "winner_name":names.get(winner) if winner else None,
        "games":[{k:g.get(k) for k in ("id","league_day","away_id","home_id","away_runs","home_runs","status")} for g in games]
    }

def playoff_bracket(c,season):
    state={r["k"]:r["v"] for r in c.execute(
        "SELECT k,v FROM league_state WHERE k IN ('phase','playoff_round','champion')"
    )}
    rounds=[
        {"name":"Quarterfinals","series":[playoff_series_summary(c,season,x,2) for x in ("QF1","QF2","QF3","QF4")]},
        {"name":"Semifinals","series":[playoff_series_summary(c,season,x,3) for x in ("SF1","SF2")]},
        {"name":"EBL Championship","series":[playoff_series_summary(c,season,"CH",4)]}
    ]
    return {"season":season,"phase":state.get("phase","REGULAR"),"round":state.get("playoff_round",""),"champion":state.get("champion",""),"rounds":rounds}

