"""Elite Baseball League runtime configuration and league constants.

This module contains stable configuration only. Mutable process state stays in server.py.
"""
import os

ROOT=os.path.dirname(os.path.abspath(__file__))
DB=os.environ.get("EBL_DB_PATH", os.path.join(ROOT,"ebl.db"))
STATIC=os.path.join(ROOT,"static")

HITTER_ATTRS=["CON","POW","VIS","DISC","TIM","SPD","BRIQ","LEAD","FLD","ARM","ACC","REAC","CALL"]
PITCHER_ATTRS=["STA","PCLT","CTRL","CMD","VEL","BRK","MOV","DEC","SEQ","FLD","ARM","ACC","REAC"]
SALARY_MIN=0.30
BONUS_CAP=25.0
REGULAR_SEASON_GAMES=81
REGULAR_SEASON_SERIES=27
REGULAR_SEASON_OFF_DAYS=14
REGULAR_SEASON_CALENDAR_DAYS=REGULAR_SEASON_GAMES+REGULAR_SEASON_OFF_DAYS  # 95 simulated calendar days
# Series 2,4,...,26 plus the final series use a staggered fourth day. Each club
# still plays exactly three games in the series and receives one team-specific off day.
REGULAR_SEASON_REST_SERIES=set(range(2,27,2))|{27}
REGULAR_SEASON_CHECKPOINT_DAYS=(24,49,70,95)  # 21, 42, 60 and 81 games completed per club
ALL_STAR_BREAK_DAY=49
ALL_STAR_SELECTION_XP=1.0
PLAYOFF_ROSTER_XP=1.0
FINAL_FOUR_XP=1.0
CHAMPIONSHIP_BERTH_XP=1.0
CHAMPIONSHIP_WIN_XP=1.0
DIVISIONS=["Heritage","Liberty","Union","Frontier","Continental","Pioneer"]
DIVISION_RENAMES={
    "Atlantic":"Heritage","North":"Liberty","Central":"Union",
    "South":"Frontier","West":"Continental","Pacific":"Pioneer"
}
ACTIVE_ROSTER_SIZE=16
TEAM_BUDGET=480.0
# CPU-generated rookie offers use one league-standard entry contract.
# The baseline club budget protects all 16 roster jobs at rookie minimum first;
# the remaining baseline pool is divided evenly so every rookie can receive the
# same signing bonus regardless of whether they sign first or last.
CPU_ROOKIE_CONTRACT_YEARS=3
CPU_ROOKIE_SIGNING_BONUS=round(
    max(0.0, TEAM_BUDGET-(ACTIVE_ROSTER_SIZE*SALARY_MIN*REGULAR_SEASON_GAMES))
    / ACTIVE_ROSTER_SIZE,
    1
)
CONTRACT_ESCALATION=0.01
# contract renewal human identity is carried through the coach contract payload.
REVENUE_UPGRADE_COSTS=[50.0,65.0,80.0,100.0,125.0]
REVENUE_UPGRADE_BONUSES=[0.0,5.0,10.0,20.0,40.0,80.0]
REVENUE_BRANCH_MAX=5
FINISH_REWARD_MIN=1.0
FINISH_REWARD_MAX=30.0
REBUILD_XP_MAX=0.05
POOL_GROWTH_TOP=5.0
POOL_GROWTH_MIDDLE=4.0
POOL_GROWTH_BOTTOM=3.0
STORAGE_KEEP_FULL_GAME_DAYS=7
SP_XP_MULTIPLIER=4.0
RP_XP_MULTIPLIER=1.75
CHAT_RETENTION_HOURS=12
FREE_PLAYER_LIMIT=1
SUPPORTER_PLAYER_LIMIT=3
ABSOLUTE_PLAYER_LIMIT=3
# Slot enforcement stays disabled during the current Genesis validation run.
# Turn EBL_SUPPORTER_SLOTS_ENFORCED=1 on before public recruiting to make
# Free=1 / Supporter=3 the live creation rule without another code deploy.
SUPPORTER_SLOTS_ENFORCED=str(os.environ.get("EBL_SUPPORTER_SLOTS_ENFORCED","0")).strip().lower() in ("1","true","on","yes")
try:
    GENESIS_FREE_SUPPORTER_SLOTS=max(0,int(os.environ.get("EBL_GENESIS_FREE_SUPPORTER_SLOTS","100") or 100))
except (TypeError,ValueError):
    GENESIS_FREE_SUPPORTER_SLOTS=100
GENESIS_FREE_SUPPORTER_SEASON=1
RENEWAL_OPEN_DAY=70
MAX_REQUEST_BYTES=20*1024*1024
MAX_TEAM_LOGO_DATA_URL_CHARS=7_100_000
MAX_PROFILE_PHOTO_DATA_URL_CHARS=900_000
BETA_MODE=str(os.environ.get("EBL_BETA_MODE","1")).strip().lower() not in ("0","false","off","no")
try:
    GENESIS_PLAYER_TARGET=max(1,int(os.environ.get("EBL_GENESIS_PLAYER_TARGET","150") or 150))
except (TypeError,ValueError):
    GENESIS_PLAYER_TARGET=150
COACH_APPLICATIONS_OPEN=str(os.environ.get("EBL_COACH_APPLICATIONS_OPEN","1")).strip().lower() in ("1","true","on","yes")
AGE_REQUIREMENT=13
