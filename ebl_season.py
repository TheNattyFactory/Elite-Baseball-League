"""EBL season-transition orchestration.

This module owns the transactional rollover from a completed offseason into the
next regular season. It deliberately does not own player-development math,
contract pricing, franchise-economy formulas, roster construction, fatigue
rules, notifications, or news. Those behaviors are injected by server.py so
this extraction can preserve current gameplay while giving the rollover one
explicit, testable boundary.

The caller owns commit/rollback. ``advance_to_next_season`` never commits.
"""
import json

from ebl_config import CONTRACT_ESCALATION, REGULAR_SEASON_GAMES, SALARY_MIN, TEAM_BUDGET
from ebl_league import (
    active_franchise_ids,
    generate_season_schedule,
    set_season_membership,
    team_name,
)


class SeasonAdvanceError(Exception):
    """Expected season-transition failure that maps cleanly to an HTTP response."""

    def __init__(self, payload, status=400):
        self.payload=dict(payload or {})
        self.status=int(status)
        super().__init__(self.payload.get("error") or "SEASON_ADVANCE_ERROR")


def _season_state(c):
    rows={r["k"]:r["v"] for r in c.execute(
        "SELECT k,v FROM league_state WHERE k IN ('season','phase','champion')"
    ).fetchall()}
    return {
        "season":int(rows.get("season") or 1),
        "phase":str(rows.get("phase") or "REGULAR"),
        "champion":str(rows.get("champion") or ""),
    }


def _archive_completed_season(c,current_season,champion,current_active):
    """Persist player/team history for the season that just ended."""
    players=c.execute(
        "SELECT id,user_id,franchise_id,name,type,season_json,age,active FROM players WHERE active=1"
    ).fetchall()
    for pl in players:
        c.execute(
            """INSERT OR IGNORE INTO season_history(season,player_id,franchise_id,player_type,stats_json)
               VALUES(?,?,?,?,?)""",
            (current_season,pl["id"],pl["franchise_id"],pl["type"],pl["season_json"] or "{}")
        )

    if champion:
        c.execute(
            "INSERT OR REPLACE INTO season_champions(season,franchise_id) VALUES(?,?)",
            (current_season,champion)
        )

    if current_active:
        q_active=",".join("?" for _ in current_active)
        for fr in c.execute(
            f"SELECT id,wins,losses,runs_for,runs_against FROM franchises WHERE id IN ({q_active})",
            current_active
        ).fetchall():
            finish="CHAMPION" if champion and fr["id"]==champion else None
            c.execute(
                """INSERT OR REPLACE INTO franchise_season_history(
                       season,franchise_id,wins,losses,runs_for,runs_against,playoff_finish,champion
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                (current_season,fr["id"],fr["wins"],fr["losses"],fr["runs_for"],fr["runs_against"],finish,1 if finish else 0)
            )


def _expire_market_offers(c,summary):
    expiring=c.execute(
        "SELECT COUNT(*) n FROM offers WHERE status IN ('OPEN','HELD')"
    ).fetchone()["n"]
    if expiring:
        c.execute(
            "UPDATE offers SET status='EXPIRED_OFFSEASON' WHERE status IN ('OPEN','HELD')"
        )
    summary["offers_expired"]=int(expiring or 0)


def _roll_contracts(
    c,
    next_season,
    summary,
    return_offer_candidates,
    *,
    veteran_retirement_due,
    notify_user,
):
    """Expire, renew, or advance every active contract exactly once."""
    contracts=c.execute("SELECT * FROM contracts ORDER BY id").fetchall()
    for con in contracts:
        remaining=int(con["years_remaining"] or 0)-1
        pid=con["player_id"]

        # Players at the career cap are handled by the retirement pass below.
        if veteran_retirement_due(c,pid):
            continue

        if remaining<=0:
            pl=c.execute("SELECT user_id,name FROM players WHERE id=?",(pid,)).fetchone()
            seen=c.execute(
                """SELECT 1 FROM contract_history
                   WHERE player_id=? AND franchise_id=? AND ABS(salary-?)<0.0001 AND signed_at=?
                   LIMIT 1""",
                (pid,con["franchise_id"],con["salary"],con["signed_at"])
            ).fetchone()
            if not seen:
                c.execute(
                    """INSERT INTO contract_history(player_id,franchise_id,bonus,salary,years,signed_at,ended_at)
                       VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                    (
                        pid,con["franchise_id"],con["bonus"],con["salary"],
                        max(1,int(con["years_total"] or con["years_remaining"] or 1)),con["signed_at"]
                    )
                )

            renewal=c.execute(
                """SELECT * FROM offers
                   WHERE player_id=? AND franchise_id=? AND offer_type='RENEWAL'
                     AND status='ACCEPTED' AND effective_season=?
                   ORDER BY id DESC LIMIT 1""",
                (pid,con["franchise_id"],next_season)
            ).fetchone()

            if renewal:
                c.execute(
                    """UPDATE contracts
                       SET bonus=0,salary=?,years_remaining=?,years_total=?,starting_salary=?,signed_at=CURRENT_TIMESTAMP
                       WHERE player_id=?""",
                    (renewal["salary"],renewal["years"],renewal["years"],renewal["salary"],pid)
                )
                c.execute(
                    "UPDATE offers SET status='ACTIVATED_RENEWAL' WHERE id=?",
                    (renewal["id"],)
                )
                summary["renewals_activated"]+=1
                if pl and pl["user_id"]:
                    notify_user(
                        c,pl["user_id"],"CONTRACT","Renewal begins",
                        f"{pl['name']} remains with {team_name(c,con['franchise_id'])} at {float(renewal['salary']):.2f} XP/game for {int(renewal['years'])} season(s).",
                        str(pid)
                    )
                c.execute(
                    "INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                    (
                        "RENEWAL_ACTIVATED",pl["user_id"] if pl else None,
                        json.dumps({
                            "player_id":pid,"franchise_id":con["franchise_id"],
                            "salary":renewal["salary"],"years":renewal["years"],"season":next_season
                        })
                    )
                )
            else:
                c.execute("DELETE FROM contracts WHERE player_id=?",(pid,))
                c.execute(
                    "UPDATE roster_slots SET player_id=NULL,occupant_type='OPEN' WHERE player_id=?",
                    (pid,)
                )
                c.execute(
                    "UPDATE players SET franchise_id=NULL,status='FREE_AGENT' WHERE id=? AND active=1",
                    (pid,)
                )
                summary["contracts_expired"]+=1
                if pl:
                    summary["free_agents"].append(pl["name"])
                    if pl["user_id"]:
                        return_offer_candidates.append({
                            "player_id":pid,
                            "user_id":pl["user_id"],
                            "player_name":pl["name"],
                            "franchise_id":con["franchise_id"],
                            "previous_salary":float(con["salary"] or SALARY_MIN),
                        })
                        notify_user(
                            c,pl["user_id"],"CONTRACT","Contract expired",
                            f"{pl['name']} is now an EBL free agent. Your former club will send a return offer for the new season.",
                            str(pid)
                        )
        else:
            next_salary=round(float(con["salary"] or SALARY_MIN)+CONTRACT_ESCALATION,2)
            c.execute(
                "UPDATE contracts SET years_remaining=?,salary=? WHERE player_id=?",
                (remaining,next_salary,pid)
            )
            summary["contracts_advanced"]+=1


def _retire_due_players(
    c,
    summary,
    *,
    veteran_retirement_due,
    veteran_extension_cost,
    notify_user,
):
    cap_rows=c.execute(
        """SELECT p.id,p.user_id,p.name,p.franchise_id,p.age,p.career_extension_through,
                  COUNT(sh.season) seasons_played
           FROM players p JOIN season_history sh ON sh.player_id=p.id
           WHERE p.active=1
           GROUP BY p.id
           HAVING COUNT(sh.season)>=12"""
    ).fetchall()

    for pl in cap_rows:
        pid=pl["id"]
        seasons_played=int(pl["seasons_played"] or 0)
        if not veteran_retirement_due(c,pid):
            continue

        retiring_contract=c.execute(
            "SELECT * FROM contracts WHERE player_id=?",(pid,)
        ).fetchone()
        if retiring_contract:
            seen=c.execute(
                """SELECT 1 FROM contract_history
                   WHERE player_id=? AND franchise_id=? AND ABS(salary-?)<0.0001 AND signed_at=?
                   LIMIT 1""",
                (
                    pid,retiring_contract["franchise_id"],
                    retiring_contract["salary"],retiring_contract["signed_at"]
                )
            ).fetchone()
            if not seen:
                c.execute(
                    """INSERT INTO contract_history(player_id,franchise_id,bonus,salary,years,signed_at,ended_at)
                       VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                    (
                        pid,retiring_contract["franchise_id"],retiring_contract["bonus"],
                        retiring_contract["salary"],
                        max(1,int(retiring_contract["years_total"] or retiring_contract["years_remaining"] or 1)),
                        retiring_contract["signed_at"]
                    )
                )

        c.execute("DELETE FROM contracts WHERE player_id=?",(pid,))
        c.execute(
            "UPDATE offers SET status='CANCELLED_RETIRED' WHERE player_id=? AND status IN ('OPEN','HELD','ACCEPTED')",
            (pid,)
        )
        c.execute(
            "UPDATE roster_slots SET player_id=NULL,occupant_type='OPEN' WHERE player_id=?",
            (pid,)
        )
        c.execute(
            "UPDATE players SET active=0,status='RETIRED',franchise_id=NULL WHERE id=?",
            (pid,)
        )
        summary["retired"]+=1
        if pl["user_id"]:
            summary["retired_names"].append(pl["name"])
        reason="12_SEASON_CPU_CAP" if pl["user_id"] is None else "VETERAN_EXTENSION_NOT_PURCHASED"
        c.execute(
            "INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
            (
                "PLAYER_RETIRED",pl["user_id"],
                json.dumps({
                    "player_id":pid,"player_name":pl["name"],"franchise_id":pl["franchise_id"],
                    "reason":reason,"seasons_played":seasons_played
                })
            )
        )
        if pl["user_id"]:
            next_cost=veteran_extension_cost(seasons_played)
            notify_user(
                c,pl["user_id"],"CAREER","Veteran career complete",
                f"{pl['name']} completed {seasons_played} EBL seasons. The {next_cost:g} XP extension for career Season {seasons_played+1} was not purchased before rollover.",
                str(pid)
            )


def _roll_franchise_economy(c,current_season,current_active,summary,*,apply_finish_economy,annual_team_budget):
    economy_awards=apply_finish_economy(c,current_season,current_active)
    summary["franchise_economy"]=economy_awards
    for frrow in c.execute("SELECT * FROM franchises").fetchall():
        fr=dict(frrow)
        budget=float(fr.get("xp_budget",TEAM_BUDGET) or TEAM_BUDGET)
        spent=float(fr.get("xp_spent",0) or 0)
        unused=max(0.0,budget-spent)
        reserve=float(fr.get("xp_reserve",0) or 0)+unused
        fr["xp_reserve"]=reserve
        next_budget=round(annual_team_budget(fr)+reserve,3)
        c.execute(
            """UPDATE franchises
               SET wins=0,losses=0,runs_for=0,runs_against=0,
                   xp_reserve=0,xp_spent=0,xp_budget=?
               WHERE id=?""",
            (next_budget,fr["id"])
        )


def _create_return_offers(
    c,
    return_offer_candidates,
    current_active,
    summary,
    *,
    minimum_offer_salary,
    signing_pool_state,
    notify_user,
):
    for cand in return_offer_candidates:
        if cand["franchise_id"] not in current_active:
            continue
        active=c.execute(
            "SELECT active,status FROM players WHERE id=?",(cand["player_id"],)
        ).fetchone()
        if not active or not active["active"] or active["status"]!="FREE_AGENT":
            continue
        if c.execute(
            """SELECT 1 FROM offers
               WHERE player_id=? AND franchise_id=? AND status IN ('OPEN','HELD')""",
            (cand["player_id"],cand["franchise_id"])
        ).fetchone():
            continue

        fr=c.execute(
            "SELECT name,xp_budget,xp_spent FROM franchises WHERE id=?",
            (cand["franchise_id"],)
        ).fetchone()
        salary=minimum_offer_salary(c,cand["player_id"],cand["franchise_id"])
        pool=signing_pool_state(c,cand["franchise_id"])
        salary_premium=max(0.0,salary-SALARY_MIN)*REGULAR_SEASON_GAMES
        available_bonus=max(0.0,pool["available"]-salary_premium)
        bonus=round(min(5.0,available_bonus),1)
        offer_cost=round(bonus+salary_premium,3)
        if offer_cost>pool["available"]+1e-9:
            continue

        cur=c.execute(
            """INSERT INTO offers(franchise_id,player_id,bonus,salary,years,status)
               VALUES(?,?,?,?,2,'OPEN')""",
            (cand["franchise_id"],cand["player_id"],bonus,salary)
        )
        summary["return_offers"]+=1
        if cand["user_id"]:
            notify_user(
                c,cand["user_id"],"CONTRACT",
                f"Return offer from {fr['name'] if fr else cand['franchise_id']}",
                f"{bonus:g} XP bonus • {salary:g} XP/game • 2 years",
                str(cur.lastrowid)
            )


def _reset_active_player_season_stats(c):
    hitters=json.dumps({
        "G":0,"PA":0,"AB":0,"H":0,"1B":0,"2B":0,"3B":0,"HR":0,
        "BB":0,"SO":0,"R":0,"RBI":0,"SB":0,"CS":0,
    })
    pitchers=json.dumps({
        "G":0,"GS":0,"OUTS":0,"H":0,"ER":0,"BB":0,"SO":0,"W":0,"L":0,"SV":0,
    })
    for pl in c.execute("SELECT id,type FROM players WHERE active=1").fetchall():
        c.execute(
            "UPDATE players SET season_json=? WHERE id=?",
            (hitters if pl["type"]=="H" else pitchers,pl["id"])
        )


def _set_new_season_state(c,next_season):
    for key,value in (
        ("season",str(next_season)),
        ("league_day","0"),
        ("phase","REGULAR"),
        ("playoff_round",""),
        ("champion",""),
        ("pitcher_workload_season",str(next_season)),
    ):
        c.execute(
            "INSERT INTO league_state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            (key,value)
        )
    c.execute(
        "INSERT INTO league_config(k,v) VALUES('season_number',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
        (str(next_season),)
    )


def advance_to_next_season(
    c,
    actor_user_id,
    *,
    veteran_retirement_due,
    veteran_extension_cost,
    apply_finish_economy,
    annual_team_budget,
    minimum_offer_salary,
    signing_pool_state,
    enforce_active_rosters,
    reset_pitcher_fatigue,
    notify_user,
    post_news,
    finalize_relationships=None,
):
    """Roll a completed EBL season forward without committing the transaction.

    The HTTP layer passes the current implementations of still-coupled domain
    behaviors. Keeping those as hooks makes the extraction behavior-preserving
    now and lets later modules replace one dependency at a time.
    """
    state=_season_state(c)
    current_season=state["season"]
    phase=state["phase"]
    champion=state["champion"]
    if phase!="OFFSEASON":
        raise SeasonAdvanceError({"error":"SEASON_NOT_COMPLETE","phase":phase},400)

    next_season=current_season+1
    if c.execute("SELECT 1 FROM games WHERE season=? LIMIT 1",(next_season,)).fetchone():
        raise SeasonAdvanceError({"error":"NEXT_SEASON_ALREADY_EXISTS","season":next_season},409)

    summary={
        "contracts_expired":0,
        "contracts_advanced":0,
        "renewals_activated":0,
        "retired":0,
        "retired_names":[],
        "free_agents":[],
        "offers_expired":0,
        "return_offers":0,
        "rosters_rebuilt":False,
    }
    return_offer_candidates=[]

    current_active=active_franchise_ids(c,current_season)
    _archive_completed_season(c,current_season,champion,current_active)
    if finalize_relationships:
        summary["relationships"]=finalize_relationships(c,current_season)
    _expire_market_offers(c,summary)

    _roll_contracts(
        c,next_season,summary,return_offer_candidates,
        veteran_retirement_due=veteran_retirement_due,
        notify_user=notify_user,
    )

    # Preserve the current rollover ordering: all active players age before the
    # career-cap retirement pass runs, and sponsorships expire for the new season.
    c.execute("UPDATE players SET age=age+1 WHERE active=1")
    c.execute(
        "UPDATE team_sponsorships SET status='EXPIRED' WHERE status='ACTIVE' AND end_season<?",
        (next_season,)
    )

    _retire_due_players(
        c,summary,
        veteran_retirement_due=veteran_retirement_due,
        veteran_extension_cost=veteran_extension_cost,
        notify_user=notify_user,
    )

    _roll_franchise_economy(
        c,current_season,current_active,summary,
        apply_finish_economy=apply_finish_economy,
        annual_team_budget=annual_team_budget,
    )

    if not c.execute(
        "SELECT 1 FROM franchise_seasons WHERE season=? LIMIT 1",(next_season,)
    ).fetchone():
        set_season_membership(c,next_season,current_active)

    _create_return_offers(
        c,return_offer_candidates,current_active,summary,
        minimum_offer_salary=minimum_offer_salary,
        signing_pool_state=signing_pool_state,
        notify_user=notify_user,
    )

    enforce_active_rosters(c,next_season)
    summary["rosters_rebuilt"]=True

    # Pitchers start Opening Day fully recovered, then every active player's
    # live season totals are reset before the new schedule is built.
    reset_pitcher_fatigue(
        c,"NEW_SEASON",season=next_season,league_day=0,announce=False
    )
    _reset_active_player_season_stats(c)
    generate_season_schedule(c,next_season)
    _set_new_season_state(c,next_season)

    post_news(
        c,"LEAGUE",f"Season {next_season} is open",
        f"A new EBL season begins. Rosters, contracts, standings, and statistics have rolled forward for Season {next_season}.",
        0,None,None,None,4,season=next_season
    )
    c.execute(
        "INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
        (
            "SEASON_ADVANCED",actor_user_id,
            json.dumps({"from":current_season,"to":next_season,**summary})
        )
    )

    games_created=c.execute(
        "SELECT COUNT(*) n FROM games WHERE season=?",(next_season,)
    ).fetchone()["n"]
    return {
        "ok":True,
        "previous_season":current_season,
        "season":next_season,
        "day":0,
        "phase":"REGULAR",
        "games_created":games_created,
        "offseason":summary,
    }
