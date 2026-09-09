from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
import sqlite3, json, secrets, hashlib, os, mimetypes, hmac, random, math, smtplib, ssl, datetime, time, threading
from email.message import EmailMessage
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


ROOT=os.path.dirname(os.path.abspath(__file__))
DB=os.environ.get("EBL_DB_PATH", os.path.join(ROOT,"ebl.db"))
STATIC=os.path.join(ROOT,"static")
SESSIONS={}
R=random.Random(7500831)
RATE_STATE={}
RATE_LOCK=threading.Lock()


HITTER_ATTRS=["CON","POW","VIS","DISC","TIM","SPD","BRIQ","LEAD","FLD","ARM","ACC","REAC"]
PITCHER_ATTRS=["STA","H9","K9","BB9","HR9","PCLT","CTRL","VEL","BRK","FLD","ARM","ACC","REAC"]
SALARY_TIERS=[.25,.30,.35,.40,.45]
BONUS_CAP=25.0
TEAM_BUDGET=550.0
STORAGE_KEEP_FULL_GAME_DAYS=7
SP_XP_MULTIPLIER=3.0
CHAT_RETENTION_HOURS=12


FIRST_NAMES=["Marcus","Eli","Jordan","Dominic","Andre","Caleb","Noah","Isaiah","Lucas","Mateo","Julian","Miles","Cameron","Darius","Adrian","Nolan","Gavin","Roman","Jalen","Malik","Evan","Cole","Wesley","Bryce","Theo","Grant","Micah","Jonah","Emmett","Xavier","Leo","Mason","Owen","Silas","Aaron","Damian","Trevor","Derek","Logan","Rafael","Victor","Diego","Luis","Marco","Tomas","Javier","Nico","Santiago","Gabriel","Felix","Henry","Jack","Sam","Ben","Tyler","Connor","Dylan","Austin","Zachary","Nathan","Peter","Alex","Eric","Ryan","Sean","Ian","Blake","Chase","Troy","Reid","Dean","Clay","Jesse","Colin","Spencer","Garrett","Max","Milo","Asher","Ezra","Kai","Jace","Rory","Finn","Dante","Desmond","Terrence","Quincy","Leon","Curtis","Maurice","Devin","Kendrick","Avery","Tristan","Cody","Mitchell","Preston","Walker","Brody"]
LAST_NAMES=["Bennett","Navarro","Hayes","Russo","Wallace","Moreno","Carter","Brooks","Foster","Reed","Sullivan","Price","Turner","Collins","Ramirez","Ortiz","Vega","Castillo","Mendoza","Flores","Santos","Rivera","Delgado","Rojas","Herrera","Cruz","Kim","Park","Lee","Nguyen","Tran","Patel","Shah","Murphy","Kelly","OBrien","Doyle","Walsh","Miller","Davis","Wilson","Moore","Taylor","Anderson","Thomas","Jackson","White","Harris","Martin","Thompson","Garcia","Martinez","Robinson","Clark","Lewis","Young","Allen","King","Wright","Hill","Scott","Green","Adams","Baker","Nelson","Hall","Campbell","Mitchell","Roberts","Phillips","Evans","Edwards","Stewart","Morris","Rogers","Cook","Morgan","Bell","Bailey","Cooper","Richardson","Cox","Howard","Ward","Torres","Peterson","Gray","James","Watson","Wood","Barnes","Ross","Henderson","Coleman","Jenkins","Perry","Powell","Long"]


def cpu_build(attr_names, role, rng):
    # Every Genesis player starts from zero and spends exactly the same 50-point pool.
    vals={a:0 for a in attr_names}
    if role in ("SP","RP","LR","MR","SU","CL"):
        preferred=["CTRL","VEL","BRK","K9","H9"] + (["STA"] if role=="SP" else ["PCLT"])
    else:
        preferred={
          "C":["FLD","ARM","ACC","CON","VIS"],"SS":["FLD","REAC","ACC","CON","SPD","BRIQ"],
          "2B":["CON","FLD","REAC","VIS","SPD","BRIQ"],"3B":["POW","ARM","CON","REAC","FLD"],
          "1B":["POW","CON","DISC","TIM","FLD"],"CF":["SPD","BRIQ","LEAD","REAC","FLD"],
          "LF":["POW","CON","TIM","DISC","FLD"],"RF":["POW","ARM","CON","TIM","FLD"],
          "DH":["POW","CON","TIM","DISC","VIS"],"UTIL":["CON","FLD","SPD","BRIQ","REAC"]
        }.get(role,["CON","VIS","TIM","FLD","SPD","BRIQ"])
    weights={a:1.0 for a in attr_names}
    for rank,a in enumerate(preferred):
        if a in weights: weights[a]=3.2-max(0,rank)*.25
    keys=list(attr_names)
    for _ in range(50):
        pick=rng.choices(keys,weights=[weights[a] for a in keys],k=1)[0]
        vals[pick]+=1
    return vals


def conn():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=30000")
    return c


def pwhash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    dk=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),200_000)
    return salt+"$"+dk.hex()


def pwcheck(password, stored):
    try:
        salt, expected = stored.split("$", 1)
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            200_000
        )
        return hmac.compare_digest(dk.hex(), expected)
    except (ValueError, AttributeError, TypeError):
        return False


def pwok(password,stored):
    try:
        salt,hexd=stored.split("$",1)
        return hmac.compare_digest(pwhash(password,salt).split("$",1)[1],hexd)
    except: return False


def init_db():
    c=conn()
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'PLAYER' CHECK(role IN ('PLAYER','COACH','COMMISSIONER')),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS franchises(
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      owner_user_id INTEGER,
      xp_budget REAL NOT NULL DEFAULT 550,
      xp_spent REAL NOT NULL DEFAULT 0,
      xp_reserve REAL NOT NULL DEFAULT 0,
      training_level INTEGER NOT NULL DEFAULT 0,
      stadium_level INTEGER NOT NULL DEFAULT 0,
      scouting_level INTEGER NOT NULL DEFAULT 0,
      performance_level INTEGER NOT NULL DEFAULT 0,
      hq_level INTEGER NOT NULL DEFAULT 0,
      identity_locked INTEGER NOT NULL DEFAULT 1,
      wins INTEGER NOT NULL DEFAULT 0,
      losses INTEGER NOT NULL DEFAULT 0,
      runs_for INTEGER NOT NULL DEFAULT 0,
      runs_against INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS players(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      franchise_id TEXT,
      name TEXT NOT NULL,
      type TEXT NOT NULL CHECK(type IN ('H','P')),
      primary_pos TEXT NOT NULL,
      bats TEXT NOT NULL,
      throws TEXT NOT NULL,
      xp_wallet REAL NOT NULL DEFAULT 0,
      attributes_json TEXT NOT NULL,
      season_json TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'FREE_AGENT',
      active INTEGER NOT NULL DEFAULT 1,
      face_id INTEGER NOT NULL DEFAULT 1,
      hair_id INTEGER NOT NULL DEFAULT 1,
      age INTEGER NOT NULL DEFAULT 18
    );
    CREATE TABLE IF NOT EXISTS offers(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      franchise_id TEXT NOT NULL,
      player_id INTEGER NOT NULL,
      bonus REAL NOT NULL,
      salary REAL NOT NULL,
      years INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'OPEN',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS contracts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      player_id INTEGER UNIQUE NOT NULL,
      franchise_id TEXT NOT NULL,
      bonus REAL NOT NULL,
      salary REAL NOT NULL,
      years_remaining INTEGER NOT NULL,
      signed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS xp_ledger(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      player_id INTEGER NOT NULL,
      event_type TEXT NOT NULL,
      xp REAL NOT NULL,
      detail_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS lineups(
      franchise_id TEXT PRIMARY KEY,
      batting_order_json TEXT NOT NULL DEFAULT '[]',
      rotation_json TEXT NOT NULL DEFAULT '[]'
    );
    CREATE TABLE IF NOT EXISTS team_strategy(
      franchise_id TEXT PRIMARY KEY,
      bullpen_json TEXT NOT NULL DEFAULT '{}',
      defense_json TEXT NOT NULL DEFAULT '{}',
      bench_json TEXT NOT NULL DEFAULT '[]',
      substitutions_json TEXT NOT NULL DEFAULT '{}',
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );




    CREATE TABLE IF NOT EXISTS news(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      league_day INTEGER NOT NULL DEFAULT 0,
      category TEXT NOT NULL,
      headline TEXT NOT NULL,
      body TEXT NOT NULL,
      franchise_id TEXT,
      player_id INTEGER,
      game_id INTEGER,
      importance INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS games(
      id TEXT PRIMARY KEY,
      season INTEGER NOT NULL,
      league_day INTEGER NOT NULL,
      away_id TEXT NOT NULL,
      home_id TEXT NOT NULL,
      away_runs INTEGER,
      home_runs INTEGER,
      status TEXT NOT NULL DEFAULT 'SCHEDULED',
      box_json TEXT NOT NULL DEFAULT '{}',
      events_json TEXT NOT NULL DEFAULT '[]'
    );
    CREATE TABLE IF NOT EXISTS league_state(
      k TEXT PRIMARY KEY,
      v TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS transactions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_type TEXT NOT NULL,
      actor_user_id INTEGER,
      payload_json TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS chat_messages(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      channel TEXT NOT NULL CHECK(channel IN ('EBL','TEAM')),
      team_id TEXT,
      message TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS rivalries(
      team_a TEXT NOT NULL, team_b TEXT NOT NULL, games INTEGER NOT NULL DEFAULT 0,
      a_wins INTEGER NOT NULL DEFAULT 0, b_wins INTEGER NOT NULL DEFAULT 0,
      one_run_games INTEGER NOT NULL DEFAULT 0, intensity REAL NOT NULL DEFAULT 0,
      PRIMARY KEY(team_a,team_b)
    );
    CREATE TABLE IF NOT EXISTS league_records(
      record_key TEXT PRIMARY KEY, record_label TEXT NOT NULL, record_value REAL NOT NULL,
      holder_type TEXT NOT NULL, holder_id TEXT NOT NULL, game_id INTEGER,
      league_day INTEGER NOT NULL DEFAULT 0, detail TEXT
    );


    CREATE TABLE IF NOT EXISTS direct_messages(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sender_user_id INTEGER NOT NULL,
      recipient_user_id INTEGER NOT NULL,
      message TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      read_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_dm_pair ON direct_messages(sender_user_id,recipient_user_id,id);


    CREATE TABLE IF NOT EXISTS account_recovery(
      user_id INTEGER PRIMARY KEY,
      recovery_hash TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS franchise_branding(
      franchise_id TEXT PRIMARY KEY,
      display_name TEXT,
      logo_style INTEGER NOT NULL DEFAULT 1,
      primary_color TEXT NOT NULL DEFAULT '#071A31',
      secondary_color TEXT NOT NULL DEFAULT '#D7262E',
      accent_color TEXT NOT NULL DEFAULT '#D9E0E8',
      uniform_home TEXT NOT NULL DEFAULT 'WHITE',
      uniform_away TEXT NOT NULL DEFAULT 'NAVY',
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );


    CREATE TABLE IF NOT EXISTS league_config(
      k TEXT PRIMARY KEY,
      v TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS commissioner_audit(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      league_day INTEGER NOT NULL DEFAULT 0,
      action TEXT NOT NULL,
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS roster_slots(
      franchise_id TEXT NOT NULL,
      slot_no INTEGER NOT NULL,
      position_group TEXT NOT NULL,
      player_id INTEGER,
      occupant_type TEXT NOT NULL DEFAULT 'CPU',
      PRIMARY KEY(franchise_id,slot_no)
    );


    CREATE TABLE IF NOT EXISTS user_security(
      user_id INTEGER PRIMARY KEY,
      email TEXT UNIQUE,
      email_verified INTEGER NOT NULL DEFAULT 0,
      email_token_hash TEXT,
      email_token_expires TEXT,
      reset_token_hash TEXT,
      reset_token_expires TEXT,
      muted_until TEXT,
      suspended_until TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS persistent_sessions(
      token_hash TEXT PRIMARY KEY,
      user_id INTEGER NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      expires_at TEXT NOT NULL,
      last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      user_agent TEXT,
      ip TEXT
    );
    CREATE TABLE IF NOT EXISTS rate_limits(
      bucket_key TEXT PRIMARY KEY,
      window_start INTEGER NOT NULL,
      count INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS moderation_actions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      moderator_user_id INTEGER NOT NULL,
      target_user_id INTEGER NOT NULL,
      action TEXT NOT NULL,
      reason TEXT,
      expires_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS user_blocks(
      blocker_user_id INTEGER NOT NULL,
      blocked_user_id INTEGER NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(blocker_user_id,blocked_user_id)
    );
    CREATE TABLE IF NOT EXISTS user_reports(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      reporter_user_id INTEGER NOT NULL,
      reported_user_id INTEGER,
      message_id INTEGER,
      channel TEXT,
      reason TEXT NOT NULL,
      detail TEXT,
      status TEXT NOT NULL DEFAULT 'OPEN',
      resolution TEXT,
      resolved_by INTEGER,
      resolved_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_reports_open ON user_reports(status,id);
    CREATE TABLE IF NOT EXISTS backup_audit(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      path TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      bytes INTEGER
    );
    CREATE TABLE IF NOT EXISTS season_history(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      season INTEGER NOT NULL,
      player_id INTEGER NOT NULL,
      franchise_id TEXT,
      player_type TEXT NOT NULL,
      stats_json TEXT NOT NULL DEFAULT '{}',
      archived_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(season,player_id)
    );


    CREATE TABLE IF NOT EXISTS season_champions(
      season INTEGER PRIMARY KEY,
      franchise_id TEXT NOT NULL,
      archived_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );


    CREATE TABLE IF NOT EXISTS franchise_seasons(
      season INTEGER NOT NULL,
      franchise_id TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'DORMANT' CHECK(status IN ('ACTIVE','DORMANT')),
      division TEXT,
      conference TEXT,
      expansion_team INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(season,franchise_id)
    );
    CREATE INDEX IF NOT EXISTS idx_franchise_seasons_active
      ON franchise_seasons(season,status,franchise_id);


    CREATE TABLE IF NOT EXISTS franchise_season_history(
      season INTEGER NOT NULL,
      franchise_id TEXT NOT NULL,
      wins INTEGER NOT NULL DEFAULT 0,
      losses INTEGER NOT NULL DEFAULT 0,
      runs_for INTEGER NOT NULL DEFAULT 0,
      runs_against INTEGER NOT NULL DEFAULT 0,
      playoff_finish TEXT,
      champion INTEGER NOT NULL DEFAULT 0,
      archived_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(season,franchise_id)
    );


    CREATE TABLE IF NOT EXISTS player_championships(
      season INTEGER NOT NULL,
      player_id INTEGER NOT NULL,
      user_id INTEGER,
      franchise_id TEXT NOT NULL,
      player_name TEXT NOT NULL,
      archived_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(season,player_id)
    );


    CREATE TABLE IF NOT EXISTS friendships(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      requester_user_id INTEGER NOT NULL,
      addressee_user_id INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','ACCEPTED')),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(requester_user_id,addressee_user_id),
      CHECK(requester_user_id<>addressee_user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_friendships_addressee ON friendships(addressee_user_id,status);

    CREATE TABLE IF NOT EXISTS notifications(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      type TEXT NOT NULL,
      title TEXT NOT NULL,
      body TEXT NOT NULL DEFAULT '',
      ref_id TEXT,
      is_read INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id,is_read,id DESC);

    CREATE TABLE IF NOT EXISTS award_history(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      season INTEGER NOT NULL,
      period TEXT NOT NULL,
      award_code TEXT NOT NULL,
      award_name TEXT NOT NULL,
      player_id INTEGER NOT NULL,
      franchise_id TEXT,
      xp_awarded REAL NOT NULL DEFAULT 0,
      detail_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(season,period,award_code,player_id)
    );
""")

    # Safe in-place schema migrations for existing Railway databases.
    player_cols={r["name"] for r in c.execute("PRAGMA table_info(players)")}
    if "age" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN age INTEGER NOT NULL DEFAULT 18")

    # Baserunning attribute migration: preserve every existing build and add
    # the new skills at zero so no current player loses or gains spent XP.
    for row in c.execute("SELECT id,attributes_json FROM players WHERE type='H'").fetchall():
        try:
            attrs=json.loads(row["attributes_json"] or "{}")
        except Exception:
            attrs={}
        changed=False
        for key in ("BRIQ","LEAD"):
            if key not in attrs:
                attrs[key]=0
                changed=True
        if changed:
            c.execute("UPDATE players SET attributes_json=? WHERE id=?",(json.dumps(attrs),row["id"]))

    franchise_cols={r["name"] for r in c.execute("PRAGMA table_info(franchises)")}
    for col,ddl in [
        ("xp_reserve","REAL NOT NULL DEFAULT 0"),
        ("training_level","INTEGER NOT NULL DEFAULT 0"),
        ("stadium_level","INTEGER NOT NULL DEFAULT 0"),
        ("scouting_level","INTEGER NOT NULL DEFAULT 0"),
        ("performance_level","INTEGER NOT NULL DEFAULT 0"),
        ("hq_level","INTEGER NOT NULL DEFAULT 0"),
        ("established_season","INTEGER")
    ]:
        if col not in franchise_cols:
            c.execute(f"ALTER TABLE franchises ADD COLUMN {col} {ddl}")


    for username,password,role in [("coach","coach123","COACH"),("commish","commish123","COMMISSIONER")]:
        if not c.execute("SELECT 1 FROM users WHERE username=?",(username,)).fetchone():
            c.execute("INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",(username,pwhash(password),role))
    coach_id=c.execute("SELECT id FROM users WHERE username='coach'").fetchone()["id"]


    TEAM_NAMES = [
        "Atlanta Scouts",
        "New York Empires",
        "Los Angeles Stars",
        "Chicago Wind",
        "Houston Apollos",
        "Phoenix Firebirds",
        "Philadelphia Founders",
        "San Antonio Defenders",
        "San Diego Armada",
        "Dallas Wranglers",
        "Jacksonville Breakers",
        "Fort Worth Longhorns",
        "Austin Outlaws",
        "San Jose Circuit",
        "Columbus Aviators",
        "Charlotte Crowns",
        "Indianapolis Racers",
        "San Francisco Gold",
        "Seattle Evergreens",
        "Denver Summit",
        "Oklahoma City Twisters",
        "Nashville Sound",
        "Washington Eagles",
        "Las Vegas High Rollers",
        "Boston Minutemen",
        "Portland Pioneers",
        "Detroit Motors",
        "Louisville Thoroughbreds",
        "Memphis Kings",
        "Baltimore Clippers"
    ]


    for i in range(1,31):
        fid=f"EBL-F{i:02d}"
        name=TEAM_NAMES[i-1]
        owner=None


        c.execute("""INSERT OR IGNORE INTO franchises
        (id,name,owner_user_id,xp_budget,xp_spent,identity_locked,wins,losses,runs_for,runs_against)
        VALUES(?,?,?,?,0,1,0,0,0,0)""",(fid,name,owner,TEAM_BUDGET))


        # Rename franchises that already exist
        c.execute(
            "UPDATE franchises SET name=? WHERE id=?",
            (name,fid)
        )


        c.execute(
            "INSERT OR IGNORE INTO lineups(franchise_id) VALUES(?)",
            (fid,)
        )


        c.execute(
            "INSERT OR IGNORE INTO franchise_branding(franchise_id,display_name) VALUES(?,?)",
            (fid,name)
        )


        # Update display name for existing branding rows
        c.execute(
            "UPDATE franchise_branding SET display_name=? WHERE franchise_id=?",
            (name,fid)
        )


        c.execute(
            """INSERT OR IGNORE INTO team_strategy
            (franchise_id,bullpen_json,defense_json,bench_json,substitutions_json)
            VALUES(?,?,?,?,?)""",
            (
                fid,
                json.dumps({
                    "CL":None,
                    "SU1":None,
                    "SU2":None,
                    "MR":[],
                    "LR":[],
                    "EMERGENCY":[]
                }),
                json.dumps({
                    "default_shift":"STANDARD",
                    "vs_lhb":"STANDARD",
                    "vs_rhb":"STANDARD",
                    "corners_in":False,
                    "infield_in":False
                }),
                json.dumps({
                    "C":[],
                    "1B":[],
                    "2B":[],
                    "3B":[],
                    "SS":[],
                    "LF":[],
                    "CF":[],
                    "RF":[],
                    "DH":[]
                }),
                json.dumps({
                    "pinch_hit":[],
                    "pinch_run":[],
                    "def_replacement":[],
                    "catcher_backup":None,
                    "late_inning_defense_inning":8,
                    "pinch_hit_threshold":"MEDIUM",
                    "steal_aggression":"NORMAL",
                    "bunt_aggression":"NORMAL"
                })
            )
        )


        c.execute("INSERT OR IGNORE INTO league_state(k,v) VALUES('season','1')")
        c.execute("INSERT OR IGNORE INTO league_state(k,v) VALUES('league_day','0')")
        c.execute("INSERT OR IGNORE INTO league_state(k,v) VALUES('phase','REGULAR')")
        c.execute("INSERT OR IGNORE INTO league_state(k,v) VALUES('playoff_round','')")
        c.execute("INSERT OR IGNORE INTO league_state(k,v) VALUES('champion','')")


    current_season_row=c.execute("SELECT v FROM league_state WHERE k='season'").fetchone()
    ensure_season_membership(c,int(current_season_row["v"]) if current_season_row else 1)


    # Seed CPU roster filler so every team can play while human free agents join over time.
    if c.execute("SELECT COUNT(*) n FROM players").fetchone()["n"]==0:
        hseason={k:0 for k in ["G","PA","AB","H","1B","2B","3B","HR","BB","SO","R","RBI","SB","CS"]}
        pseason={k:0 for k in ["G","GS","OUTS","H","ER","BB","SO","W","L","SV"]}
        for ti in range(1,31):
            fid=f"EBL-F{ti:02d}"
            hids=[]
            pids=[]
            positions=["C","1B","2B","3B","SS","LF","CF","RF","DH"]
            for idx,pos in enumerate(positions,1):
                attrs=cpu_build(HITTER_ATTRS,pos,R)
                cur=c.execute("""INSERT INTO players(user_id,franchise_id,name,type,primary_pos,bats,throws,xp_wallet,attributes_json,season_json,status,active)
                                 VALUES(NULL,?,?,?,?,?,?,0,?,?,'SIGNED',1)""",
                              (fid,f"{FIRST_NAMES[((ti-1)*25+idx-1)%len(FIRST_NAMES)]} {LAST_NAMES[((ti-1)*25+idx*3)%len(LAST_NAMES)]}","H",pos,"R","R",json.dumps(attrs),json.dumps(hseason)))
                hids.append(cur.lastrowid)
            for idx,role in enumerate(["SP","SP","SP","SP","MR","SU","CL"],1):
                attrs=cpu_build(PITCHER_ATTRS,role,R)
                cur=c.execute("""INSERT INTO players(user_id,franchise_id,name,type,primary_pos,bats,throws,xp_wallet,attributes_json,season_json,status,active)
                                 VALUES(NULL,?,?,?,?,?,?,0,?,?,'SIGNED',1)""",
                              (fid,f"{FIRST_NAMES[((ti-1)*25+13+idx-1)%len(FIRST_NAMES)]} {LAST_NAMES[((ti-1)*25+39+idx*5)%len(LAST_NAMES)]}","P",role,"R","R",json.dumps(attrs),json.dumps(pseason)))
                pids.append(cur.lastrowid)
            c.execute("UPDATE lineups SET batting_order_json=?,rotation_json=? WHERE franchise_id=?",(json.dumps(hids[:9]),json.dumps(pids[:4]),fid))


        # Genesis schedule. Later seasons use generate_season_schedule().
        fids=[f"EBL-F{i:02d}" for i in range(1,31)]
        arr=list(range(30))
        rounds=[]
        for _ in range(29):
            rounds.append([(arr[i],arr[-1-i]) for i in range(15)])
            arr=[arr[0]]+[arr[-1]]+arr[1:-1]
        gid=1
        for day in range(1,82):
            pairs=list(rounds[(day-1)%29])
            if ((day-1)//29)%2:
                pairs=[(b,a) for a,b in pairs]
            for ai,bi in pairs:
                c.execute("INSERT OR IGNORE INTO games(id,season,league_day,away_id,home_id,status) VALUES(?,?,?,?,?,'SCHEDULED')",
                          (f"S01-G{gid:04d}",1,day,fids[ai],fids[bi]))
                gid+=1


        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('phase','RECRUITING')")
        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('alpha_cpu_fill','1')")
        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('auto_advance','0')")
        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('season_number','1')")
        # EBL active roster: 16 players/team = 480 total.
        # Nine everyday hitters + four starting pitchers + three relief pitchers.
        slot_template=["C","1B","2B","3B","SS","LF","CF","RF","DH","SP","SP","SP","SP","RP","RP","RP"]
        for fr in c.execute("SELECT id FROM franchises ORDER BY id").fetchall():
            fid=fr["id"]
            players=c.execute("SELECT id FROM players WHERE franchise_id=? ORDER BY id",(fid,)).fetchall()
            for i,posgrp in enumerate(slot_template,1):
                pid=players[i-1]["id"] if i-1<len(players) else None
                c.execute("""INSERT OR IGNORE INTO roster_slots(franchise_id,slot_no,position_group,player_id,occupant_type)
                             VALUES(?,?,?,?,?)""",(fid,i,posgrp,pid,"CPU" if pid else "OPEN"))
    # Normalize existing leagues to the current active-roster shape on startup.
    enforce_active_rosters(c)
    c.commit();c.close()


def session_user(headers):
    cookie=headers.get("Cookie","")
    for part in cookie.split(";"):
        s=part.strip()
        if s.startswith("sid="):return SESSIONS.get(s[4:])
    return None


def attr_cost(v): return 1 if v<25 else 2 if v<50 else 3 if v<70 else 5 if v<85 else 8 if v<95 else 12

def age_xp_surcharge(age):
    age=int(age or 18)
    if age<25:return 0
    if age<30:return 2
    if age<35:return 4
    if age==35:return 6
    return 6+(age-35)

def development_cost(value,age):
    return attr_cost(value)+age_xp_surcharge(age)

def annual_team_budget(fr):
    return round(TEAM_BUDGET
        +10*int(fr.get("training_level",0) or 0)
        +8*int(fr.get("stadium_level",0) or 0)
        +6*int(fr.get("scouting_level",0) or 0)
        +6*int(fr.get("performance_level",0) or 0)
        +5*int(fr.get("hq_level",0) or 0),3)

def reserve_cap(fr):
    return 150+50*int(fr.get("hq_level",0) or 0)

def upgrade_cost(level):
    return [40,75,125,200][min(3,max(0,int(level)))]

def notify_user(c,user_id,kind,title,body="",ref_id=None):
    if not user_id:return
    c.execute("INSERT INTO notifications(user_id,type,title,body,ref_id) VALUES(?,?,?,?,?)",
              (int(user_id),str(kind),str(title),str(body),None if ref_id is None else str(ref_id)))

def award_player(c,season,period,code,name,pid,xp,detail=None):
    pl=c.execute("SELECT id,user_id,franchise_id,name FROM players WHERE id=?",(pid,)).fetchone()
    if not pl:return False
    try:
        cur=c.execute("""INSERT INTO award_history(season,period,award_code,award_name,player_id,franchise_id,xp_awarded,detail_json)
                         VALUES(?,?,?,?,?,?,?,?)""",
                      (season,period,code,name,pid,pl["franchise_id"],xp,json.dumps(detail or {})))
    except sqlite3.IntegrityError:
        return False
    c.execute("UPDATE players SET xp_wallet=xp_wallet+? WHERE id=?",(xp,pid))
    c.execute("INSERT INTO xp_ledger(player_id,event_type,xp,detail_json) VALUES(?,?,?,?)",
              (pid,"AWARD",xp,json.dumps({"season":season,"period":period,"award":name,**(detail or {})})))
    notify_user(c,pl["user_id"],"AWARD",f"{name}: +{xp:g} XP",f"{pl['name']} earned {name}.",str(pid))
    return True

def process_quarter_awards(c,season,end_day):
    if end_day not in (20,40,60,81):return []
    start_day={20:1,40:21,60:41,81:61}[end_day]
    period=f"DAYS_{start_day}_{end_day}"
    if c.execute("SELECT 1 FROM award_history WHERE season=? AND period=? LIMIT 1",(season,period)).fetchone():
        return []
    hit={} ; pit={}
    games=c.execute("SELECT box_json FROM games WHERE season=? AND league_day BETWEEN ? AND ? AND status='FINAL'",(season,start_day,end_day)).fetchall()
    for gr in games:
        try:b=json.loads(gr["box_json"] or "{}")
        except Exception:continue
        for k,line in (b.get("hitters") or {}).items():
            d=hit.setdefault(int(k),{x:0 for x in ["PA","AB","H","1B","2B","3B","HR","BB","SO","R","RBI","SB","CS"]})
            for x in d:d[x]+=int(line.get(x,0) or 0)
        rawp=b.get("pitchers") or {}
        if isinstance(rawp,dict):
            for _team,rows in rawp.items():
                if isinstance(rows,list):
                    for line in rows:
                        pid=int(line.get("player_id",0) or 0)
                        if not pid:continue
                        d=pit.setdefault(pid,{x:0 for x in ["G","GS","OUTS","H","ER","BB","SO","W","L","SV"]})
                        for x in d:d[x]+=int(line.get(x,0) or 0)
    winners=[]
    if hit:
        def hscore(item):
            pid,line=item; ab=line["AB"]; pa=line["PA"]; h=line["H"]; bb=line["BB"]
            tb=line["1B"]+2*line["2B"]+3*line["3B"]+4*line["HR"]
            obp=(h+bb)/pa if pa else 0; slg=tb/ab if ab else 0
            return (obp+slg)*100+line["HR"]*1.2+line["RBI"]*.15+line["SB"]*.25
        pid,line=max(hit.items(),key=hscore)
        if award_player(c,season,period,"QUARTER_BATTER","Quarter-Season Batter",pid,5,{"days":[start_day,end_day]}):winners.append(pid)
    if pit:
        def pscore(item):
            pid,line=item; outs=line["OUTS"]
            return line["SO"]*1.2-line["ER"]*2.2-line["BB"]*.7+(outs/3)*.3
        pid,line=max(pit.items(),key=pscore)
        if award_player(c,season,period,"QUARTER_PITCHER","Quarter-Season Pitcher",pid,5,{"days":[start_day,end_day]}):winners.append(pid)
    return winners

def process_season_awards(c,season):
    period="REGULAR_SEASON"
    if c.execute("SELECT 1 FROM award_history WHERE season=? AND period=? LIMIT 1",(season,period)).fetchone():return []
    hitters=[];pitchers=[]
    for r in c.execute("SELECT id,primary_pos,attributes_json,season_json FROM players WHERE active=1"):
        st=json.loads(r["season_json"] or "{}")
        if "PA" in st:
            ab=st.get("AB",0);h=st.get("H",0);bb=st.get("BB",0);pa=st.get("PA",0);tb=st.get("1B",0)+2*st.get("2B",0)+3*st.get("3B",0)+4*st.get("HR",0)
            avg=h/ab if ab else 0;obp=(h+bb)/pa if pa else 0;slg=tb/ab if ab else 0
            hitters.append({"id":r["id"],"pos":r["primary_pos"],"avg":avg,"ops":obp+slg,"pa":pa,"hr":st.get("HR",0),"rbi":st.get("RBI",0),"sb":st.get("SB",0),"attrs":json.loads(r["attributes_json"] or "{}")})
        else:
            outs=st.get("OUTS",0);er=st.get("ER",0);bb=st.get("BB",0);hh=st.get("H",0);so=st.get("SO",0)
            score=so*1.2-er*2.2-bb*.7+(outs/3)*.3
            pitchers.append({"id":r["id"],"pos":r["primary_pos"],"outs":outs,"score":score,"sv":st.get("SV",0)})
    made=[]
    qualified=[x for x in hitters if x["pa"]>=162] or hitters
    if hitters:
        m=max(hitters,key=lambda x:(x["ops"]*100+x["hr"]*1.1+x["rbi"]*.12+x["sb"]*.35,x["pa"]))
        if award_player(c,season,period,"MVP","Most Valuable Player",m["id"],15):made.append("MVP")
    if qualified:
        b=max(qualified,key=lambda x:(x["avg"],x["pa"]))
        if award_player(c,season,period,"BATTING_TITLE","Batting Title",b["id"],10):made.append("BATTING_TITLE")
        sb=max(hitters,key=lambda x:(x["sb"],x["ops"]))
        if award_player(c,season,period,"SB_TITLE","Stolen Base Title",sb["id"],10):made.append("SB_TITLE")
        for pos in ["C","1B","2B","3B","SS","LF","CF","RF"]:
            pool=[x for x in hitters if x["pos"]==pos]
            if pool:
                f=max(pool,key=lambda x:(x["attrs"].get("FLD",0)*.45+x["attrs"].get("REAC",0)*.25+x["attrs"].get("ARM",0)*.15+x["attrs"].get("ACC",0)*.15,x["pa"]))
                if award_player(c,season,period,f"FIELD_{pos}",f"{pos} Fielding Title",f["id"],10):made.append(f"FIELD_{pos}")
    # End-of-season pitching awards have position-specific eligibility.
    # SPs compete only for Pitcher of the Season; RPs compete only for Reliever of the Season.
    starters=[x for x in pitchers if x["pos"]=="SP" and x["outs"]>0]
    if starters:
        pos=max(starters,key=lambda x:x["score"])
        if award_player(c,season,period,"PITCHER_OF_SEASON","Pitcher of the Season",pos["id"],15):
            made.append("PITCHER_OF_SEASON")
    rel=[x for x in pitchers if x["pos"]!="SP" and x["outs"]>0]
    if rel:
        rp=max(rel,key=lambda x:(x["score"]+x["sv"]*1.5,x["sv"]))
        if award_player(c,season,period,"RELIEVER_OF_SEASON","Reliever of the Season",rp["id"],10):
            made.append("RELIEVER_OF_SEASON")
    return made

MIN_ACTIVE_TEAMS=8

def _season_number(c):
    row=c.execute("SELECT v FROM league_state WHERE k='season'").fetchone()
    return int(row["v"]) if row else 1

def _division_labels(team_count):
    if team_count<=10:
        return ["Atlantic","Pacific"]
    if team_count<=16:
        return ["Atlantic","North","South","Pacific"]
    if team_count<=24:
        return ["Atlantic","North","Central","South"]
    return list(DIVISIONS)

def ensure_season_membership(c,season):
    existing=c.execute(
        "SELECT COUNT(*) n FROM franchise_seasons WHERE season=?",
        (season,)
    ).fetchone()["n"]
    if existing:
        return

    # Preserve an already-built season by activating every franchise that
    # actually appears on that season's schedule. Fresh seasons start with
    # the Original Eight.
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
        participants=[
            r["id"] for r in c.execute(
                "SELECT id FROM franchises ORDER BY id LIMIT ?",
                (MIN_ACTIVE_TEAMS,)
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
            c.execute(
                """INSERT OR IGNORE INTO franchise_seasons(
                       season,franchise_id,status,division,conference,expansion_team
                   ) VALUES(?,?, 'ACTIVE', ?, NULL, 0)""",
                (season,fid,div)
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
            expansion=1 if season>1 and fid not in previous_active else 0
            c.execute(
                """INSERT INTO franchise_seasons(
                       season,franchise_id,status,division,conference,expansion_team
                   ) VALUES(?,?, 'ACTIVE', ?, NULL, ?)""",
                (season,fid,div,expansion)
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

def season_division(c,season,fid):
    ensure_season_membership(c,season)
    row=c.execute(
        "SELECT division FROM franchise_seasons WHERE season=? AND franchise_id=?",
        (season,fid)
    ).fetchone()
    return row["division"] if row and row["division"] else division_for(fid)

def enforce_active_rosters(c,season=None):
    # 16-player active roster: every hitter has an everyday lineup job.
    template=["C","1B","2B","3B","SS","LF","CF","RF","DH","SP","SP","SP","SP","RP","RP","RP"]
    season=_season_number(c) if season is None else int(season)
    for fid in active_franchise_ids(c,season):
        rows=[dict(x) for x in c.execute("SELECT * FROM players WHERE franchise_id=? AND active=1 AND status='SIGNED' ORDER BY CASE WHEN user_id IS NOT NULL THEN 0 ELSE 1 END,id",(fid,))]
        humans=[x for x in rows if x.get("user_id") is not None]
        cpus=[x for x in rows if x.get("user_id") is None]
        slots=[None]*len(template)
        def group_for(pl):
            if pl["type"]=="P":return "SP" if pl["primary_pos"]=="SP" else "RP"
            return pl["primary_pos"] if pl["primary_pos"] in template[:9] else "UTIL"
        def place(pl):
            g=group_for(pl)
            choices=[i for i,t in enumerate(template) if t==g and slots[i] is None]
            if not choices and pl["type"]=="H":choices=[i for i,t in enumerate(template) if t=="UTIL" and slots[i] is None]
            if choices:
                slots[choices[0]]=pl;return True
            return False
        overflow=[]
        for pl in humans:
            if not place(pl):overflow.append(pl)
        for pl in cpus:
            if not place(pl):continue
        # Fill any missing slots with fresh CPU filler.
        hseason={k:0 for k in ["G","PA","AB","H","1B","2B","3B","HR","BB","SO","R","RBI","SB","CS"]}
        pseason={k:0 for k in ["G","GS","OUTS","H","ER","BB","SO","W","L","SV"]}
        for i,t in enumerate(template):
            if slots[i] is not None:continue
            ptype="P" if t in ("SP","RP") else "H"
            role=t if t!="UTIL" else "UTIL"
            attrs=cpu_build(PITCHER_ATTRS if ptype=="P" else HITTER_ATTRS,role,R)
            cur=c.execute("""INSERT INTO players(user_id,franchise_id,name,type,primary_pos,bats,throws,xp_wallet,attributes_json,season_json,status,active,age)
                             VALUES(NULL,?,?,?,?,?,?,0,?,?,'SIGNED',1,18)""",
                          (fid,f"{FIRST_NAMES[(i+int(fid[-2:])*7)%len(FIRST_NAMES)]} {LAST_NAMES[(i*5+int(fid[-2:])*11)%len(LAST_NAMES)]}",ptype,role,"R","R",json.dumps(attrs),json.dumps(pseason if ptype=="P" else hseason)))
            slots[i]=dict(c.execute("SELECT * FROM players WHERE id=?",(cur.lastrowid,)).fetchone())
        used={int(x["id"]) for x in slots if x}
        for pl in cpus:
            if int(pl["id"]) not in used:
                c.execute("UPDATE players SET active=0,status='RETIRED',franchise_id=NULL WHERE id=?",(pl["id"],))
        c.execute("DELETE FROM roster_slots WHERE franchise_id=?",(fid,))
        for i,(grp,pl) in enumerate(zip(template,slots),1):
            occ="HUMAN" if pl.get("user_id") is not None else "CPU"
            c.execute("INSERT INTO roster_slots(franchise_id,slot_no,position_group,player_id,occupant_type) VALUES(?,?,?,?,?)",(fid,i,grp,pl["id"],occ))
        hitter_ids=[int(slots[i]["id"]) for i in range(9)]
        sp_ids=[int(slots[i]["id"]) for i,t in enumerate(template) if t=="SP"]
        c.execute("UPDATE lineups SET batting_order_json=?,rotation_json=? WHERE franchise_id=?",(json.dumps(hitter_ids),json.dumps(sp_ids[:4]),fid))
        rp_ids=[int(slots[i]["id"]) for i,t in enumerate(template) if t=="RP"]
        bp={"CL":rp_ids[-1] if rp_ids else None,"SU1":rp_ids[-2] if len(rp_ids)>1 else None,"SU2":None,"MR":rp_ids[:1],"LR":[],"EMERGENCY":[]}
        c.execute("UPDATE team_strategy SET bullpen_json=? WHERE franchise_id=?",(json.dumps(bp),fid))
    return True

def gps_xp(g): return round(max(.25,min(.75,.25+.5*g/100)),3)
def generate_season_schedule(c,season):
    fids=active_franchise_ids(c,season)
    n=len(fids)
    if n<MIN_ACTIVE_TEAMS:
        raise ValueError("MINIMUM_8_TEAMS")
    if n%2:
        raise ValueError("EVEN_TEAM_COUNT_REQUIRED")

    # Circle-method round robin. Every active club plays once per league day.
    # Repeating the round sequence through Day 81 preserves the 81-game
    # per-team season at every supported even league size.
    arr=list(range(n))
    rounds=[]
    for _ in range(n-1):
        rounds.append([(arr[i],arr[-1-i]) for i in range(n//2)])
        arr=[arr[0]]+[arr[-1]]+arr[1:-1]

    gid=1
    for day in range(1,82):
        round_index=(day-1)%(n-1)
        pairs=list(rounds[round_index])

        # Flip home/away on alternate full round-robin cycles.
        if ((day-1)//(n-1))%2:
            pairs=[(b,a) for a,b in pairs]

        for ai,bi in pairs:
            game_id=f"S{season:02d}-G{gid:04d}"
            c.execute(
                """INSERT INTO games(
                       id,season,league_day,away_id,home_id,status
                   ) VALUES(?,?,?,?,?,'SCHEDULED')""",
                (game_id,season,day,fids[ai],fids[bi])
            )
            gid+=1

DIVISIONS=["Atlantic","North","Central","South","West","Pacific"]
def division_for(fid):
    try:
        n=int(fid.split("F")[-1])
    except: return "Unknown"
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
    
def _career_rates(stats,player_type):
    st=dict(stats or {})
    if player_type=="H":
        ab=int(st.get("AB",0) or 0); h=int(st.get("H",0) or 0); bb=int(st.get("BB",0) or 0); pa=int(st.get("PA",0) or 0)
        tb=int(st.get("1B",0) or 0)+2*int(st.get("2B",0) or 0)+3*int(st.get("3B",0) or 0)+4*int(st.get("HR",0) or 0)
        avg=h/ab if ab else 0.0; obp=(h+bb)/pa if pa else 0.0; slg=tb/ab if ab else 0.0
        return {"AVG":round(avg,3),"OBP":round(obp,3),"SLG":round(slg,3),"OPS":round(obp+slg,3)}
    outs=int(st.get("OUTS",0) or 0); er=int(st.get("ER",0) or 0); hh=int(st.get("H",0) or 0); bb=int(st.get("BB",0) or 0)
    innings=outs/3 if outs else 0.0
    era=(er*9/innings) if innings else 0.0; whip=((hh+bb)/innings) if innings else 0.0
    return {"IP_OUTS":outs,"ERA":round(era,2),"WHIP":round(whip,2)}


def career_summary(c,pid,current_stats=None,active=False):
    pl=c.execute("SELECT id,name,type,primary_pos,franchise_id,status,active,age FROM players WHERE id=?",(pid,)).fetchone()
    if not pl:return None
    ptype=pl["type"]
    hist=[]
    totals={}
    rows=c.execute(
        """SELECT sh.season,sh.franchise_id,sh.player_type,sh.stats_json,sh.archived_at,f.name team_name
           FROM season_history sh LEFT JOIN franchises f ON f.id=sh.franchise_id
           WHERE sh.player_id=? ORDER BY sh.season ASC""",(pid,)
    ).fetchall()
    for row in rows:
        try:st=json.loads(row["stats_json"] or "{}")
        except Exception:st={}
        for k,v in st.items():
            if isinstance(v,(int,float)):totals[k]=totals.get(k,0)+v
        hist.append({
            "season":row["season"],"franchise_id":row["franchise_id"],"team_name":row["team_name"] or row["franchise_id"] or "Free Agent",
            "player_type":row["player_type"],"stats":st,"rates":_career_rates(st,row["player_type"]),"archived_at":row["archived_at"]
        })

    current_season=int(c.execute("SELECT v FROM league_state WHERE k='season'").fetchone()["v"])
    current=None
    if active:
        st=dict(current_stats or {})
        for k,v in st.items():
            if isinstance(v,(int,float)):totals[k]=totals.get(k,0)+v
        fr=c.execute("SELECT name FROM franchises WHERE id=?",(pl["franchise_id"],)).fetchone() if pl["franchise_id"] else None
        current={
            "season":current_season,"franchise_id":pl["franchise_id"],"team_name":fr["name"] if fr else "Free Agent",
            "player_type":ptype,"stats":st,"rates":_career_rates(st,ptype),"current":True
        }

    awards=[dict(x) for x in c.execute(
        """SELECT a.season,a.period,a.award_code,a.award_name,a.franchise_id,a.xp_awarded,a.detail_json,f.name team_name
           FROM award_history a LEFT JOIN franchises f ON f.id=a.franchise_id
           WHERE a.player_id=? ORDER BY a.season DESC,a.id DESC""",(pid,)
    )]
    for a in awards:
        try:a["detail"]=json.loads(a.pop("detail_json") or "{}")
        except Exception:a["detail"]={}
    championships=[dict(x) for x in c.execute(
        """SELECT pc.season,pc.franchise_id,f.name team_name
           FROM player_championships pc LEFT JOIN franchises f ON f.id=pc.franchise_id
           WHERE pc.player_id=? ORDER BY pc.season DESC""",(pid,)
    )]
    totals_rates=_career_rates(totals,ptype)
    teams=[]; seen=set()
    for row in hist+([current] if current else []):
        key=row.get("franchise_id") or row.get("team_name")
        if key not in seen:
            seen.add(key);teams.append({"franchise_id":row.get("franchise_id"),"team_name":row.get("team_name")})
    return {
        "player_id":pid,"player_type":ptype,"position":pl["primary_pos"],"active":bool(pl["active"]),"status":pl["status"],"age":pl["age"],
        "seasons_completed":len(hist),"first_season":hist[0]["season"] if hist else current_season,
        "latest_season":current_season if current else (hist[-1]["season"] if hist else current_season),
        "history":list(reversed(hist)),"current_season":current,"career_totals":totals,"career_rates":totals_rates,
        "awards":awards,"award_count":len(awards),"championships":championships,"championship_count":len(championships),"teams":teams
    }


def player_obj(c,pid):
    r=c.execute("SELECT * FROM players WHERE id=?",(pid,)).fetchone()
    if not r:return None
    d=dict(r);d["attributes"]=json.loads(d.pop("attributes_json"));d["season"]=json.loads(d.pop("season_json"))
    con=c.execute("SELECT * FROM contracts WHERE player_id=?",(pid,)).fetchone()
    d["contract"]=dict(con) if con else None
    d["offers"]=[dict(x) for x in c.execute("SELECT * FROM offers WHERE player_id=? AND status IN ('OPEN','HELD') ORDER BY id DESC",(pid,))]
    d["ledger"]=[dict(x) for x in c.execute("SELECT event_type,xp,detail_json FROM xp_ledger WHERE player_id=? ORDER BY id DESC LIMIT 25",(pid,))]
    d["career"]=career_summary(c,pid,d.get("season"),bool(d.get("active")))
    d["career_seasons"]=d["career"]["seasons_completed"] if d.get("career") else 0
    d["championships"]=d["career"]["championship_count"] if d.get("career") else 0
    d["awards_count"]=d["career"]["award_count"] if d.get("career") else 0
    return d




def sim_player_obj(c,pid):
    r=c.execute("SELECT * FROM players WHERE id=?",(pid,)).fetchone()
    if not r:return None
    d=dict(r)
    d["attributes"]=json.loads(d.pop("attributes_json"))
    d["season"]=json.loads(d.pop("season_json"))
    con=c.execute("SELECT * FROM contracts WHERE player_id=?",(pid,)).fetchone()
    d["contract"]=dict(con) if con else None
    # Simulation does not need offers or ledger history on every PA.
    d["offers"]=[]
    d["ledger"]=[]
    return d


def save_player(c,p):
    c.execute("UPDATE players SET xp_wallet=?,attributes_json=?,season_json=? WHERE id=?",
              (p["xp_wallet"],json.dumps(p["attributes"]),json.dumps(p["season"]),p["id"]))


def hitter_gps(line):
    raw=line["1B"]*.45+line["2B"]*.75+line["3B"]*1.05+line["HR"]*1.35+line["BB"]*.32+line["RBI"]*.10+line["R"]*.08-line["SO"]*.12
    return 100/(1+math.exp(-(raw-1.05)*1.28))


def pitcher_gps(line,sp):
    ip=line["OUTS"]/3
    raw=max(-3,ip*.62-line["ER"]*.92)+line["SO"]*.14-line["BB"]*.18-line["H"]*.08
    if sp:raw+=max(0,ip-4)*.18
    return 100/(1+math.exp(-(raw-(.55 if sp else .45))*1.12))


def contract_for(c,pid):
    r=c.execute("SELECT * FROM contracts WHERE player_id=?",(pid,)).fetchone()
    return dict(r) if r else None




def team_strategy_for(c,fid):
    r=c.execute("SELECT * FROM team_strategy WHERE franchise_id=?",(fid,)).fetchone()
    if not r:
        return {"bullpen":{"CL":None,"SU1":None,"SU2":None,"MR":[],"LR":[],"EMERGENCY":[]},
                "defense":{"default_shift":"STANDARD","vs_lhb":"STANDARD","vs_rhb":"STANDARD","corners_in":False,"infield_in":False},
                "bench":{},"substitutions":{}}
    return {"bullpen":json.loads(r["bullpen_json"]),"defense":json.loads(r["defense_json"]),
            "bench":json.loads(r["bench_json"]),"substitutions":json.loads(r["substitutions_json"])}


def choose_reliever(c,fid,strategy,inning,lead_margin,used):
    bp=strategy["bullpen"]


    def valid(pid):
        if not pid or pid in used:
            return False


        return c.execute(
            "SELECT 1 FROM players WHERE id=? AND franchise_id=? AND type='P' AND active=1 AND primary_pos<>'SP'",
            (pid,fid)
        ).fetchone()


    # High leverage late innings
    if inning>=9 and 0<lead_margin<=3 and valid(bp.get("CL")):
        return int(bp["CL"]),"CL"


    if inning>=8 and abs(lead_margin)<=3:
        for k in ["SU1","SU2"]:
            if valid(bp.get(k)):
                return int(bp[k]),k


    # Long relief
    if inning<=6 or lead_margin<=-4:
        for pid in bp.get("LR",[]):
            if valid(pid):
                return int(pid),"LR"


    for pid in bp.get("MR",[]):
        if valid(pid):
            return int(pid),"MR"


    for pid in bp.get("EMERGENCY",[]):
        if valid(pid):
            return int(pid),"EMERGENCY"


    # Fallback: any unused NON-SP pitcher
    r=c.execute(
        "SELECT id FROM players WHERE franchise_id=? AND type='P' AND active=1 AND primary_pos<>'SP' ORDER BY id",
        (fid,)
    ).fetchall()


    for x in r:
        if x["id"] not in used:
            return x["id"],"RP"


    return None,None
def maybe_pinch_hit(c,fid,strategy,current_batter_id,inning,score_diff,used_bench):
    subs=strategy["substitutions"];th=subs.get("pinch_hit_threshold","MEDIUM")
    if inning<7:return current_batter_id,None
    chance={"CONSERVATIVE":.08,"MEDIUM":.18,"AGGRESSIVE":.32}[th]
    if score_diff<0: chance+=.08
    if R.random()>chance:return current_batter_id,None
    for pid in subs.get("pinch_hit",[]):
        pid=int(pid)
        if pid in used_bench:continue
        r=c.execute("SELECT id FROM players WHERE id=? AND franchise_id=? AND type='H' AND active=1",(pid,fid)).fetchone()
        if r:
            used_bench.add(pid);return pid,current_batter_id
    return current_batter_id,None


def maybe_pinch_run(c,fid,strategy,runner_id,inning,score_diff,used_bench):
    if inning<7 or score_diff>2:return runner_id,None
    for pid in strategy["substitutions"].get("pinch_run",[]):
        pid=int(pid)
        if pid in used_bench:continue
        r=c.execute("SELECT id FROM players WHERE id=? AND franchise_id=? AND type='H' AND active=1",(pid,fid)).fetchone()
        if r:
            used_bench.add(pid);return pid,runner_id
    return runner_id,None


def steal_attempt_probability(player,strategy):
    attrs=player["attributes"]
    spd=attrs.get("SPD",0)
    briq=attrs.get("BRIQ",attrs.get("BR",0))
    lead=attrs.get("LEAD",attrs.get("STEAL",0))
    # Speed creates opportunity, instincts choose the moment, and LEAD
    # represents getting an aggressive but controlled jump.
    base=.03 + spd*.0022 + briq*.0017 + lead*.0018
    mult={"LOW":.55,"NORMAL":1.0,"HIGH":1.65}.get(strategy["substitutions"].get("steal_aggression","NORMAL"),1.0)
    return max(.01,min(.48,base*mult))


def steal_success_probability(player):
    attrs=player["attributes"]
    spd=attrs.get("SPD",0)
    briq=attrs.get("BRIQ",attrs.get("BR",0))
    lead=attrs.get("LEAD",attrs.get("STEAL",0))
    return max(.30,min(.96,.48+spd*.0035+briq*.0027+lead*.0031))


def pickoff_probability(player):
    attrs=player["attributes"]
    briq=attrs.get("BRIQ",attrs.get("BR",0))
    lead=attrs.get("LEAD",attrs.get("STEAL",0))
    # Intentionally rare. Better instincts and lead technique reduce risk.
    return max(.0015,min(.012,.010-briq*.00010-lead*.00012))


def bunt_probability(strategy,inning,score_diff):
    base={"LOW":.01,"NORMAL":.035,"HIGH":.09}.get(strategy["substitutions"].get("bunt_aggression","NORMAL"),.035)
    if inning>=7 and abs(score_diff)<=1:base*=1.7
    return min(.18,base)


def defensive_shift_modifier(strategy,batter_bats):
    d=strategy["defense"]; mode=d.get("vs_lhb" if batter_bats=="L" else "vs_rhb",d.get("default_shift","STANDARD"))
    # small, transparent BIP outcome modifiers
    return {"STANDARD":0.0,"PULL":-.010,"OPPO":-.004,"NO_DOUBLES":-.006,"BUNT_DEFENSE":-.002,"INFIELD_IN":.004}.get(mode,0.0),mode




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


def record_championship(c,season,franchise_id,league_day):
    team=c.execute("SELECT name FROM franchises WHERE id=?",(franchise_id,)).fetchone()
    if not team:
        return
    c.execute("INSERT OR REPLACE INTO season_champions(season,franchise_id) VALUES(?,?)",(season,franchise_id))
    roster=c.execute(
        "SELECT id,user_id,name FROM players WHERE franchise_id=? AND active=1",
        (franchise_id,)
    ).fetchall()
    for pl in roster:
        c.execute(
            """INSERT OR IGNORE INTO player_championships(season,player_id,user_id,franchise_id,player_name)
               VALUES(?,?,?,?,?)""",
            (season,pl["id"],pl["user_id"],franchise_id,pl["name"])
        )
    post_news(
        c,"CHAMPIONSHIP",
        f"🏆 {team['name']} WIN THE EBL CHAMPIONSHIP!",
        f"{team['name']} are Season {season} EBL Champions. The title is now part of the franchise and player legacy records.",
        league_day,franchise_id,None,None,5
    )


def post_news(c,category,headline,body,league_day=0,franchise_id=None,player_id=None,game_id=None,importance=1):
    # Prevent exact duplicate headlines for the same league day.
    exists=c.execute("SELECT 1 FROM news WHERE league_day=? AND headline=?",(league_day,headline)).fetchone()
    if exists:return
    c.execute("""INSERT INTO news(league_day,category,headline,body,franchise_id,player_id,game_id,importance)
                 VALUES(?,?,?,?,?,?,?,?)""",
              (league_day,category,headline,body,franchise_id,player_id,game_id,importance))


def generate_game_news(c,g,score,winner,loser,box):
    day=g["league_day"]
    names={r["id"]:r["name"] for r in c.execute("SELECT id,name FROM franchises WHERE id IN (?,?)",(g["away_id"],g["home_id"]))}
    ar,hr=score[g["away_id"]],score[g["home_id"]]
    margin=abs(ar-hr)
    if margin==1:
        headline=f"{names[winner]} edge {names[loser]} in a one-run finish"
        body=f"{names[winner]} survived a tight game, {max(ar,hr)}-{min(ar,hr)}, on League Day {day}. Every late-inning decision mattered."
        imp=2
    elif margin>=6:
        headline=f"{names[winner]} erupt in convincing win"
        body=f"{names[winner]} powered past {names[loser]} {max(ar,hr)}-{min(ar,hr)} in one of the day's biggest statements."
        imp=2
    else:
        headline=f"{names[winner]} take down {names[loser]}"
        body=f"{names[winner]} earned a {max(ar,hr)}-{min(ar,hr)} victory over {names[loser]} on League Day {day}."
        imp=1
    post_news(c,"GAME",headline,body,day,winner,None,g["id"],imp)


    sev=box.get("strategy_events",[])
    if len(sev)>=8:
        post_news(c,"MANAGER",f"{names[winner]} lean on the dugout in tactical win",
                  f"The game featured {len(sev)} recorded strategy decisions, giving the EBL community plenty to debate after the final out.",
                  day,winner,None,g["id"],1)


def generate_daily_news(c,day):
    games=c.execute("SELECT * FROM games WHERE league_day=? AND status='FINAL'",(day,)).fetchall()
    if not games:return
    # Best run differential of the day.
    best=max(games,key=lambda x:abs(x["away_runs"]-x["home_runs"]))
    winner=best["away_id"] if best["away_runs"]>best["home_runs"] else best["home_id"]
    wn=c.execute("SELECT name FROM franchises WHERE id=?",(winner,)).fetchone()["name"]
    post_news(c,"AROUND_EBL",f"Around the EBL: {wn} make the loudest statement",
              f"League Day {day} is in the books. {len(games)} games reshaped the standings as the Genesis season continues to build its first rivalries and storylines.",
              day,winner,None,None,2)




def rivalry_pair(a,b): return (a,b) if a<b else (b,a)


def update_rivalry(c,a,b,winner,margin):
    ta,tb=rivalry_pair(a,b)
    r=c.execute("SELECT * FROM rivalries WHERE team_a=? AND team_b=?",(ta,tb)).fetchone()
    if not r:
        c.execute("INSERT INTO rivalries(team_a,team_b) VALUES(?,?)",(ta,tb))
        r=c.execute("SELECT * FROM rivalries WHERE team_a=? AND team_b=?",(ta,tb)).fetchone()
    intensity=min(100,float(r["intensity"])+1+(2.5 if margin==1 else 0)+(1 if margin<=3 else 0))
    c.execute("""UPDATE rivalries SET games=games+1,a_wins=a_wins+?,b_wins=b_wins+?,
                 one_run_games=one_run_games+?,intensity=? WHERE team_a=? AND team_b=?""",
              (1 if winner==ta else 0,1 if winner==tb else 0,1 if margin==1 else 0,intensity,ta,tb))
    return intensity


def maybe_rivalry_news(c,g,winner,loser,margin,intensity):
    if intensity<12:return
    names={r["id"]:r["name"] for r in c.execute("SELECT id,name FROM franchises WHERE id IN (?,?)",(winner,loser))}
    level="heated" if intensity<30 else "fierce" if intensity<60 else "classic"
    post_news(c,"RIVALRY",f"{names[winner]} add another chapter to a {level} rivalry",
              f"The matchup with {names[loser]} keeps gaining history. Rivalry intensity is now {intensity:.0f}/100.",
              g["league_day"],winner,None,g["id"],2 if intensity>=30 else 1)


def update_team_game_records(c,g,score):
    holder=max(score,key=score.get); high=score[holder]
    name=c.execute("SELECT name FROM franchises WHERE id=?",(holder,)).fetchone()["name"]
    old=c.execute("SELECT * FROM league_records WHERE record_key='TEAM_RUNS_GAME'").fetchone()
    if not old or high>old["record_value"]:
        c.execute("""INSERT OR REPLACE INTO league_records(record_key,record_label,record_value,holder_type,holder_id,game_id,league_day,detail)
                     VALUES('TEAM_RUNS_GAME','Most Runs — Team, Game',?,'TEAM',?,?,?,?)""",
                  (high,holder,g["id"],g["league_day"],f"{name} scored {high} runs"))
        post_news(c,"RECORD",f"New EBL record: {name} score {high}",
                  f"{name} establish the Genesis record for most runs by a team in one game with {high}.",
                  g["league_day"],holder,None,g["id"],3)


def weekly_recap(c,day):
    if day<=0 or day%7:return
    games=c.execute("SELECT COUNT(*) n FROM games WHERE league_day>? AND league_day<=? AND status='FINAL'",(day-7,day)).fetchone()["n"]
    if not games:return
    leader=c.execute("SELECT id,name,wins,losses FROM franchises ORDER BY wins DESC,losses ASC LIMIT 1").fetchone()
    post_news(c,"WEEKLY",f"EBL Week {day//7}: {leader['name']} set the pace",
              f"Seven more league days are complete. {leader['name']} lead at {leader['wins']}-{leader['losses']} as Genesis builds its first rivalries, records, and breakout stories.",
              day,leader["id"],None,None,3)




def rivalry_xp_multiplier(c,a,b):
    ta,tb=rivalry_pair(a,b)
    r=c.execute("SELECT * FROM rivalries WHERE team_a=? AND team_b=?",(ta,tb)).fetchone()
    intensity=float(r["intensity"]) if r else 0.0
    # Small performance-only boost: +2% baseline rivalry, scaling to max +8%.
    return min(1.08,1.02 + intensity*0.0006)


def simulate_game(c,g):
    away,home=g["away_id"],g["home_id"]
    team_names={r["id"]:r["name"] for r in c.execute("SELECT id,name FROM franchises")}
    lrows={fid:c.execute("SELECT * FROM lineups WHERE franchise_id=?",(fid,)).fetchone() for fid in [away,home]}
    lineups={fid:json.loads(lrows[fid]["batting_order_json"]) for fid in [away,home]}
        # Keep batting orders synced with active rosters.
    # Human position players who are signed and active should not be stranded
    # outside an old CPU-generated lineup.
    for fid in [away,home]:
        roster=list(c.execute("""
            SELECT id,user_id,primary_pos
            FROM players
            WHERE franchise_id=?
              AND active=1
              AND status='SIGNED'
              AND type='H'
            ORDER BY id
        """,(fid,)))


        by_id={int(r["id"]):r for r in roster}
        valid_ids=set(by_id.keys())


        # Remove invalid/duplicate players from an old saved lineup.
        clean=[]
        for pid in lineups[fid]:
            pid=int(pid)
            if pid in valid_ids and pid not in clean:
                clean.append(pid)


        human_ids=[
            int(r["id"])
            for r in roster
            if r["user_id"] is not None
        ]

        # Human playing-time protection: if a club has 10-11 human hitters,
        # rotate the two bench spots through the lineup by league day.
        if len(human_ids)>9:
            offset=(int(g["league_day"])-1)%len(human_ids)
            rotated=human_ids[offset:]+human_ids[:offset]
            protected=set(rotated[:9])
            clean=[pid for pid in clean if pid not in human_ids or pid in protected]
            human_ids=rotated[:9]


        # Put active human players into the lineup if an old CPU lineup omitted them.
        for human_id in human_ids:
            if human_id in clean:
                continue


            human_pos=by_id[human_id]["primary_pos"]
            replace_idx=None


            # First preference: replace a CPU player at the same position.
            for i,pid in enumerate(clean):
                r=by_id.get(pid)
                if (
                    r
                    and r["user_id"] is None
                    and r["primary_pos"]==human_pos
                ):
                    replace_idx=i
                    break


            # Otherwise replace the last CPU player in the order.
            if replace_idx is None:
                for i in range(len(clean)-1,-1,-1):
                    r=by_id.get(clean[i])
                    if r and r["user_id"] is None:
                        replace_idx=i
                        break


            if replace_idx is not None:
                clean[replace_idx]=human_id
            elif len(clean)<9:
                clean.append(human_id)


        # Fill any holes in the batting order.
        for r in roster:
            pid=int(r["id"])
            if len(clean)>=9:
                break
            if pid not in clean:
                clean.append(pid)


        lineups[fid]=clean[:9]
    rotations={fid:json.loads(lrows[fid]["rotation_json"]) for fid in [away,home]}
    strategies={fid:team_strategy_for(c,fid) for fid in [away,home]}
    score={away:0,home:0};events=[];box={"hitters":{},"pitchers":{},"xp":[],"strategy_events":[]}
    def hitter_line(pid):
        key=str(pid)


        if key not in box["hitters"]:
            box["hitters"][key]={
                "G":1,
                "PA":0,
                "AB":0,
                "H":0,
                "1B":0,
                "2B":0,
                "3B":0,
                "HR":0,
                "BB":0,
                "SO":0,
                "R":0,
                "RBI":0,
                "SB":0,
                "CS":0
            }


        return box["hitters"][key]


    pitcher_live={away:{},home:{}}
    def pitcher_line(fid,pid):
        pid=int(pid)
        if pid not in pitcher_live[fid]:
            starter_id=int(rotations[fid][(g["league_day"]-1)%4])
            pitcher_live[fid][pid]={
                "G":1,"GS":1 if pid==starter_id else 0,"OUTS":0,
                "H":0,"ER":0,"BB":0,"SO":0,"W":0,"L":0,"SV":0
            }
        return pitcher_live[fid][pid]


    used_pitchers={away:set(),home:set()};used_bench={away:set(),home:set()}
    base_runner={away:None,home:None}
    current_pitcher={}
    for fid,opp in [(away,home),(home,away)]:
        current_pitcher[fid]=rotations[fid][(g["league_day"]-1)%4]
        used_pitchers[fid].add(current_pitcher[fid])


    events.append({"type":"GAME_START","away":away,"home":home,"away_name":team_names[away],"home_name":team_names[home],"score":[0,0]})


    for inning in range(1,10):
        for half,fid,opp in [("TOP",away,home),("BOT",home,away)]:
            outs=0;idx=((inning-1)*4)%9
            # bullpen hook for defending team
            opp_diff=score[opp]-score[fid]
            if inning>=7:
                rp,role=choose_reliever(c,opp,strategies[opp],inning,opp_diff,used_pitchers[opp])
                if rp and rp!=current_pitcher[opp] and (inning>=8 or R.random()<.42):
                    current_pitcher[opp]=rp;used_pitchers[opp].add(rp)
                    ev={"type":"PITCHING_CHANGE","team":opp,"pitcher_id":rp,"role":role,"inning":inning,"half":half}
                    events.append(ev);box["strategy_events"].append(ev)
            while outs<3:
                starter_batter_id=lineups[fid][idx%9];idx+=1
                ph_id,replaced=maybe_pinch_hit(c,fid,strategies[fid],starter_batter_id,inning,score[fid]-score[opp],used_bench[fid])
                batter=sim_player_obj(c,ph_id)
                batline=hitter_line(batter["id"])
                if replaced:
                    ev={"type":"PINCH_HITTER","team":fid,"player_id":ph_id,"replaced_id":replaced,"inning":inning,"half":half}
                    events.append(ev);box["strategy_events"].append(ev)
                pitcher=sim_player_obj(c,current_pitcher[opp])
                pitchline=pitcher_line(opp,pitcher["id"])
                shift_adj,shift_mode=defensive_shift_modifier(strategies[opp],batter.get("bats","R"))
                if shift_mode!="STANDARD":
                    ev={"type":"DEFENSIVE_SHIFT","team":opp,"mode":shift_mode,"batter_id":batter["id"],"inning":inning,"half":half}
                    events.append(ev);box["strategy_events"].append(ev)
                # optional bunt attempt
                if bunt_probability(strategies[fid],inning,score[fid]-score[opp])>R.random():
                    success=R.random()<.58
                    events.append({"type":"BUNT_ATTEMPT","batter_id":batter["id"],"success":success,"inning":inning,"half":half})
                    if success:
                        outs+=1
                        pitchline["OUTS"]+=1
                        if base_runner[fid] is not None and R.random()<.55:
                            score[fid]+=1
                            pitchline["ER"]+=1
                            events.append({"type":"RUN","inning":inning,"half":half,"team":fid,"runs":1,"score":[score[away],score[home]],"note":"Bunt play"})
                            base_runner[fid]=None
                    else:
                        outs+=1
                        pitchline["OUTS"]+=1
                    events.append({"type":"PA_END","inning":inning,"half":half,"batter_id":batter["id"],"pitcher_id":pitcher["id"],"result":"SAC" if success else "BUNT_OUT","outs":outs,"score":[score[away],score[home]]})
                    continue
                batline["PA"]+=1
                events.append({"type":"PA_START","inning":inning,"half":half,"batter_id":batter["id"],"batter":batter["name"],
                               "pitcher_id":pitcher["id"],"pitcher":pitcher["name"],"outs":outs,"score":[score[away],score[home]]})
                balls=strikes=0;pitch_no=0
                while True:
                    pitch_no+=1
                    ptype=R.choice(["Four-Seam","Slider","Changeup","Sinker","Curve"])
                    vel=round(R.uniform(82,98),1)
                    px=round(R.uniform(.12,.88),3)
                    pz=round(R.uniform(.12,.88),3)
                    x=R.random()


                    if x<.10 and balls<3:
                        balls+=1;call="Ball"
                    elif x<.30 and strikes<2:
                        strikes+=1;call="Called Strike"
                    else:
                        if balls==3 and x<.17:
                            balls+=1;call="Ball"
                        elif strikes==2 and x<.28:
                            strikes+=1;call="Swinging Strike"
                        else:
                            call="In Play"


                    events.append({
                        "type":"PITCH","inning":inning,"half":half,
                        "pitch_no":pitch_no,"pitch_type":ptype,"velocity":vel,
                        "px":px,"pz":pz,"call":call,
                        "balls":min(balls,4),"strikes":min(strikes,3),
                        "batter_id":batter["id"],"pitcher_id":pitcher["id"]
                    })


                    if call=="In Play":
                        out_weight=max(.56,min(.78,.67-shift_adj))
                        result=R.choices(["OUT","1B","2B","HR"],weights=[out_weight,.22,.08,.03])[0]
                        exit_velo=round(R.uniform(78,111),1)
                        launch_angle=round(R.uniform(-8,34),1)
                        spray=round(R.uniform(-42,42),1)
                        events.append({
                            "type":"BALL_IN_PLAY","inning":inning,"half":half,
                            "batter_id":batter["id"],"pitcher_id":pitcher["id"],
                            "result":result,"exit_velocity":exit_velo,
                            "launch_angle":launch_angle,"spray_angle":spray,
                            "contact_quality":"Barrel" if exit_velo>103 and 18<=launch_angle<=32 else "Hard" if exit_velo>95 else "Normal",
                            "shift":shift_mode
                        })


                        batline["AB"]+=1


                        if result=="OUT":
                            outs+=1
                            pitchline["OUTS"]+=1
                            events.append({
                                "type":"OUT","inning":inning,"half":half,
                                "batter_id":batter["id"],"pitcher_id":pitcher["id"],
                                "outs":outs,
                                "out_type":R.choice(["Groundout","Flyout","Lineout"])
                            })
                        else:
                            batline["H"]+=1
                            batline[result]+=1
                            pitchline["H"]+=1


                            if result=="HR":
                                runs=1
                                batline["R"]+=1
                                batline["RBI"]+=1
                                if base_runner[fid] is not None:
                                    runner_id=base_runner[fid]
                                    hitter_line(runner_id)["R"]+=1
                                    batline["RBI"]+=1
                                    runs+=1
                                score[fid]+=runs
                                pitchline["ER"]+=runs
                                base_runner[fid]=None
                                events.append({
                                    "type":"RUN","inning":inning,"half":half,
                                    "team":fid,"runs":runs,
                                    "score":[score[away],score[home]],
                                    "batter_id":batter["id"]
                                })
                            else:
                                if base_runner[fid] is not None and R.random()<(.18 if result=="1B" else .48):
                                    runner_id=base_runner[fid]
                                    hitter_line(runner_id)["R"]+=1
                                    batline["RBI"]+=1
                                    score[fid]+=1
                                    pitchline["ER"]+=1
                                    events.append({
                                        "type":"RUN","inning":inning,"half":half,
                                        "team":fid,"runs":1,
                                        "score":[score[away],score[home]],
                                        "runner_id":runner_id,"batter_id":batter["id"]
                                    })
                                    base_runner[fid]=None


                                runner_id,replaced_runner=maybe_pinch_run(
                                    c,fid,strategies[fid],batter["id"],inning,
                                    score[fid]-score[opp],used_bench[fid]
                                )
                                if replaced_runner:
                                    ev2={
                                        "type":"PINCH_RUNNER","team":fid,
                                        "player_id":runner_id,"replaced_id":replaced_runner,
                                        "inning":inning,"half":half
                                    }
                                    events.append(ev2);box["strategy_events"].append(ev2)
                                base_runner[fid]=runner_id
                                runner=sim_player_obj(c,runner_id)
                                if runner and R.random()<pickoff_probability(runner):
                                    outs+=1
                                    pitchline["OUTS"]+=1
                                    base_runner[fid]=None
                                    ev_pick={
                                        "type":"PICKOFF","team":fid,
                                        "runner_id":runner_id,
                                        "inning":inning,"half":half
                                    }
                                    events.append(ev_pick);box["strategy_events"].append(ev_pick)
                                elif runner and R.random()<steal_attempt_probability(runner,strategies[fid]):
                                    safe=R.random()<steal_success_probability(runner)
                                    ev3={
                                        "type":"STEAL_ATTEMPT","team":fid,
                                        "runner_id":runner_id,"success":safe,
                                        "inning":inning,"half":half
                                    }
                                    events.append(ev3);box["strategy_events"].append(ev3)
                                    runner_line=hitter_line(runner_id)
                                    if safe:
                                        runner_line["SB"]+=1
                                    else:
                                        runner_line["CS"]+=1
                                        outs+=1
                                        pitchline["OUTS"]+=1
                                        base_runner[fid]=None
                                        events.append({
                                            "type":"OUT","inning":inning,"half":half,
                                            "runner_id":runner_id,"outs":outs,
                                            "out_type":"Caught Stealing"
                                        })


                        events.append({
                            "type":"PA_END","inning":inning,"half":half,
                            "batter_id":batter["id"],"pitcher_id":pitcher["id"],
                            "result":result,"outs":outs,
                            "score":[score[away],score[home]]
                        })
                        break


                    if balls>=4:
                        batline["BB"]+=1
                        pitchline["BB"]+=1
                        if base_runner[fid] is None:
                            base_runner[fid]=batter["id"]
                        events.append({
                            "type":"PA_END","inning":inning,"half":half,
                            "batter_id":batter["id"],"pitcher_id":pitcher["id"],
                            "result":"BB","outs":outs,
                            "score":[score[away],score[home]]
                        })
                        break


                    if strikes>=3:
                        batline["AB"]+=1
                        batline["SO"]+=1
                        pitchline["SO"]+=1
                        outs+=1
                        pitchline["OUTS"]+=1
                        events.append({
                            "type":"OUT","inning":inning,"half":half,
                            "batter_id":batter["id"],"pitcher_id":pitcher["id"],
                            "outs":outs,"out_type":"Strikeout"
                        })
                        events.append({
                            "type":"PA_END","inning":inning,"half":half,
                            "batter_id":batter["id"],"pitcher_id":pitcher["id"],
                            "result":"SO","outs":outs,
                            "score":[score[away],score[home]]
                        })
                        break
            events.append({"type":"INNING_END","inning":inning,"half":half,"score":[score[away],score[home]]})
        # late-inning defensive replacement marker for both teams
        for fid in [away,home]:
            subs=strategies[fid]["substitutions"]
            if inning==int(subs.get("late_inning_defense_inning",8)) and score[fid]>score[home if fid==away else away]:
                reps=subs.get("def_replacement",[])
                if reps:
                    ev={"type":"DEFENSIVE_REPLACEMENT_WINDOW","team":fid,"players":[int(x) for x in reps],"inning":inning}
                    events.append(ev);box["strategy_events"].append(ev)


    if score[away]==score[home]:
        winner=R.choice([away,home])
        loser=home if winner==away else away
        score[winner]+=1
        pitcher_line(loser,current_pitcher[loser])["ER"]+=1
        events.append({"type":"RUN","inning":9,"half":"TIEBREAK","team":winner,"runs":1,"score":[score[away],score[home]],"note":"Tiebreak"})
    winner=away if score[away]>score[home] else home;loser=home if winner==away else away
    events.append({"type":"GAME_END","winner":winner,"final_score":[score[away],score[home]]})


    # -------------------------------------------------
    # PARTICIPATION / STAT / XP LAYER
    # -------------------------------------------------


    for fid in [away,home]:
        opp=home if fid==away else away


        participant_ids=set(lineups[fid]) | used_bench[fid]


        # ---------------------------------------------
        # HITTERS
        # ---------------------------------------------


        for pid in participant_ids:
            p=sim_player_obj(c,pid)


            if not p or p["type"]!="H":
                continue


            line=box["hitters"].get(str(pid))


            if not line:
                continue


            # Add this game's actual hitter line to season stats.
            for k,v in line.items():
                p["season"][k]=p["season"].get(k,0)+v


            gps=hitter_gps(line)


            perf=round(
                gps_xp(gps) *
                rivalry_xp_multiplier(c,away,home),
                3
            )


            con=contract_for(c,pid)
            salary=float(con["salary"]) if con else .25
            if p.get("franchise_id"):
                c.execute("UPDATE franchises SET xp_spent=xp_spent+? WHERE id=?",(salary,p["franchise_id"]))


            p["xp_wallet"]=round(
                p["xp_wallet"]+salary+perf,
                3
            )


            c.execute(
                """
                INSERT INTO xp_ledger(
                    player_id,
                    event_type,
                    xp,
                    detail_json
                )
                VALUES(?,?,?,?)
                """,
                (
                    pid,
                    "SALARY",
                    salary,
                    json.dumps({
                        "game":g["id"]
                    })
                )
            )


            c.execute(
                """
                INSERT INTO xp_ledger(
                    player_id,
                    event_type,
                    xp,
                    detail_json
                )
                VALUES(?,?,?,?)
                """,
                (
                    pid,
                    "PERFORMANCE",
                    perf,
                    json.dumps({
                        "game":g["id"],
                        "gps":round(gps,1)
                    })
                )
            )


            save_player(c,p)


            box["xp"].append({
                "player_id":pid,
                "salary":salary,
                "performance":perf
            })


        # ---------------------------------------------
        # PITCHERS
        # ---------------------------------------------


        for spid in used_pitchers[fid]:
            p=sim_player_obj(c,spid)


            if not p:
                continue


            is_starter=(
                spid==rotations[fid][(g["league_day"]-1)%4]
            )


            pline=dict(pitcher_live[fid].get(int(spid),{
                "G":1,"GS":1 if is_starter else 0,"OUTS":0,
                "H":0,"ER":0,"BB":0,"SO":0,"W":0,"L":0,"SV":0
            }))
            pline["G"]=1
            pline["GS"]=1 if is_starter else 0
            pline["W"]=1 if fid==winner and is_starter else 0
            pline["L"]=1 if fid==loser and is_starter else 0
            pline["SV"]=1 if (
                not is_starter and fid==winner
                and int(spid)==int(strategies[fid]["bullpen"].get("CL") or -1)
                and pline.get("OUTS",0)>0
            ) else 0


            for k,v in pline.items():
                p["season"][k]=p["season"].get(k,0)+v


            gps=pitcher_gps(
                pline,
                is_starter
            )


            xp_mult=SP_XP_MULTIPLIER if is_starter else 1.0
            perf=round(
                gps_xp(gps) *
                rivalry_xp_multiplier(c,away,home) *
                xp_mult,
                3
            )


            con=contract_for(c,spid)
            base_salary=float(con["salary"]) if con else .25
            salary=round(base_salary*xp_mult,3)
            if p.get("franchise_id"):
                c.execute("UPDATE franchises SET xp_spent=xp_spent+? WHERE id=?",(salary,p["franchise_id"]))


            p["xp_wallet"]=round(
                p["xp_wallet"]+salary+perf,
                3
            )


            c.execute(
                """
                INSERT INTO xp_ledger(
                    player_id,
                    event_type,
                    xp,
                    detail_json
                )
                VALUES(?,?,?,?)
                """,
                (
                    spid,
                    "SALARY",
                    salary,
                    json.dumps({
                        "game":g["id"]
                    })
                )
            )


            c.execute(
                """
                INSERT INTO xp_ledger(
                    player_id,
                    event_type,
                    xp,
                    detail_json
                )
                VALUES(?,?,?,?)
                """,
                (
                    spid,
                    "PERFORMANCE",
                    perf,
                    json.dumps({
                        "game":g["id"],
                        "gps":round(gps,1)
                    })
                )
            )


            save_player(c,p)


            box["pitchers"].setdefault(fid,[]).append({
                "player_id":spid,
                **pline
            })


            box["xp"].append({
                "player_id":spid,
                "salary":salary,
                "performance":perf
            })
    
    # -------------------------------------------------
    # FINALIZE GAME
    # -------------------------------------------------


    postseason=int(g["league_day"])>81


    # Only regular-season games change standings.
    if not postseason:
        c.execute(
            """
            UPDATE franchises
            SET wins=wins+1,
                runs_for=runs_for+?,
                runs_against=runs_against+?
            WHERE id=?
            """,
            (
                score[winner],
                score[loser],
                winner
            )
        )


        c.execute(
            """
            UPDATE franchises
            SET losses=losses+1,
                runs_for=runs_for+?,
                runs_against=runs_against+?
            WHERE id=?
            """,
            (
                score[loser],
                score[winner],
                loser
            )
        )


    # Every game, including playoffs, becomes FINAL.
    c.execute(
        """
        UPDATE games
        SET away_runs=?,
            home_runs=?,
            status='FINAL',
            box_json=?,
            events_json=?
        WHERE id=?
        """,
        (
            score[away],
            score[home],
            json.dumps(box),
            json.dumps(events),
            g["id"]
        )
    )


    margin=abs(score[away]-score[home])


    heat=update_rivalry(
        c,
        away,
        home,
        winner,
        margin
    )


    update_team_game_records(
        c,
        g,
        score
    )


    maybe_rivalry_news(
        c,
        g,
        winner,
        loser,
        margin,
        heat
    )


    generate_game_news(
        c,
        g,
        score,
        winner,
        loser,
        box
    )


    return {
        "game_id":g["id"],
        "events":len(events),
        "winner":winner,
          "away_runs":score[away],
        "home_runs":score[home],
        "strategy_events":len(box["strategy_events"])
}
def recovery_hash(code):
    return hashlib.sha256(code.encode()).hexdigest()


def make_recovery_code():
    # Human-readable 20-char alpha-numeric token, shown once.
    alphabet="ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "-".join("".join(secrets.choice(alphabet) for _ in range(5)) for _ in range(4))


def valid_hex_color(x):
    return isinstance(x,str) and len(x)==7 and x.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in x[1:])




def league_cfg(c,k,default=None):
    r=c.execute("SELECT v FROM league_config WHERE k=?",(k,)).fetchone()
    return r["v"] if r else default


def set_league_cfg(c,k,v):
    c.execute("INSERT OR REPLACE INTO league_config(k,v) VALUES(?,?)",(k,str(v)))


def audit(c,action,detail=""):
    day=int(league_cfg(c,"league_day",0) or 0)
    c.execute("INSERT INTO commissioner_audit(league_day,action,detail) VALUES(?,?,?)",(day,action,detail))


def roster_readiness(c):
    total=c.execute("SELECT COUNT(*) n FROM roster_slots").fetchone()["n"]
    filled=c.execute("SELECT COUNT(*) n FROM roster_slots WHERE player_id IS NOT NULL").fetchone()["n"]
    human=c.execute("SELECT COUNT(*) n FROM roster_slots WHERE occupant_type='HUMAN'").fetchone()["n"]
    cpu=c.execute("SELECT COUNT(*) n FROM roster_slots WHERE occupant_type='CPU'").fetchone()["n"]
    open_n=total-filled
    bypos=[dict(x) for x in c.execute("""SELECT position_group,COUNT(*) total,
             SUM(CASE WHEN player_id IS NOT NULL THEN 1 ELSE 0 END) filled,
             SUM(CASE WHEN occupant_type='HUMAN' THEN 1 ELSE 0 END) human
             FROM roster_slots GROUP BY position_group ORDER BY position_group""")]
    return {"total":total,"filled":filled,"human":human,"cpu":cpu,"open":open_n,
            "ready":filled==total,"positions":bypos}


def position_demand(c):
    # Genesis demand is based on how many league roster slots at each
    # position are already occupied by human players. CPU players are
    # placeholders, so replacing one represents a real opportunity.
    rows=c.execute("""SELECT position_group,COUNT(*) total,
              SUM(CASE WHEN occupant_type='HUMAN' THEN 1 ELSE 0 END) human,
              SUM(CASE WHEN occupant_type='CPU' THEN 1 ELSE 0 END) cpu,
              SUM(CASE WHEN player_id IS NULL OR occupant_type='OPEN' THEN 1 ELSE 0 END) open
              FROM roster_slots
              GROUP BY position_group""").fetchall()
    raw={r["position_group"]:dict(r) for r in rows}
    out=[]
    for pos in ["C","1B","2B","3B","SS","LF","CF","RF","SP","RP"]:
        r=raw.get(pos,{"total":0,"human":0,"cpu":0,"open":0})
        total=int(r.get("total") or 0)
        human=int(r.get("human") or 0)
        cpu=int(r.get("cpu") or 0)
        open_n=int(r.get("open") or 0)
        opportunities=max(0,total-human)
        share=(human/total) if total else 1.0
        if opportunities<=0:
            level="FULL"
        elif share<.25:
            level="HIGH_NEED"
        elif share<.60:
            level="AVAILABLE"
        else:
            level="CROWDED"
        out.append({"position":pos,"level":level,"total_slots":total,
                    "human":human,"cpu":cpu,"open":open_n,
                    "opportunities":opportunities})
    return out




def token_hash(v): return hashlib.sha256(v.encode()).hexdigest()


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def iso_after(minutes):
    return (utc_now:=utcnow() + datetime.timedelta(minutes=minutes)).isoformat()


def parse_iso(v):
    try:return datetime.datetime.fromisoformat(v)
    except:return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


def new_session(c,user_id,handler=None):
    raw=secrets.token_urlsafe(32)
    expires=(utcnow()+datetime.timedelta(days=30)).isoformat()
    ua=handler.headers.get("User-Agent","")[:500] if handler else ""
    ip=get_client_ip(handler) if handler else ""
    c.execute("DELETE FROM persistent_sessions WHERE user_id=? AND expires_at<?",(user_id,utcnow().isoformat()))
    c.execute("""INSERT INTO persistent_sessions(token_hash,user_id,expires_at,user_agent,ip)
                 VALUES(?,?,?,?,?)""",(token_hash(raw),user_id,expires,ua,ip))
    return raw,expires


def session_user(*args):
    own=False
    if len(args)==1:
        headers=args[0]
        raw=None
        for part in headers.get("Cookie","").split(";"):
            if part.strip().startswith("sid="):
                raw=part.strip()[4:]
                break
        c=conn();own=True
    elif len(args)==2:
        c,raw=args
    else:
        return None
    try:
        if not raw:return None
        r=c.execute("""SELECT u.id,u.username,u.role
                       FROM persistent_sessions s JOIN users u ON u.id=s.user_id
                       WHERE s.token_hash=? AND s.expires_at>?""",
                    (token_hash(raw),utcnow().isoformat())).fetchone()
        if not r:return None
        c.execute("UPDATE persistent_sessions SET last_seen_at=CURRENT_TIMESTAMP WHERE token_hash=?",(token_hash(raw),))
        if own:c.commit()
        return dict(r)
    finally:
        if own:c.close()


def user_restricted(c,user_id):
    r=c.execute("SELECT muted_until,suspended_until FROM user_security WHERE user_id=?",(user_id,)).fetchone()
    if not r:return {"muted":False,"suspended":False,"muted_until":None,"suspended_until":None}
    now=utcnow()
    muted=bool(r["muted_until"] and parse_iso(r["muted_until"])>now)
    suspended=bool(r["suspended_until"] and parse_iso(r["suspended_until"])>now)
    return {"muted":muted,"suspended":suspended,"muted_until":r["muted_until"],"suspended_until":r["suspended_until"]}


def get_client_ip(handler):
    xf=handler.headers.get("X-Forwarded-For","").split(",")[0].strip()
    return xf or handler.client_address[0]


def rate_limit(c,key,limit,window_seconds):
    # Persist rate-limit buckets in SQLite so deploys/restarts do not reset abuse protection.
    now=int(time.time())
    with RATE_LOCK:
        r=c.execute("SELECT window_start,count FROM rate_limits WHERE bucket_key=?",(key,)).fetchone()
        if not r or now-int(r["window_start"])>=int(window_seconds):
            c.execute("""INSERT INTO rate_limits(bucket_key,window_start,count)
                         VALUES(?,?,1)
                         ON CONFLICT(bucket_key) DO UPDATE SET window_start=excluded.window_start,count=1""",
                      (key,now))
            return True
        if int(r["count"])>=int(limit):
            return False
        c.execute("UPDATE rate_limits SET count=count+1 WHERE bucket_key=?",(key,))
        return True


def secure_cookie_suffix():
    base=os.environ.get("PUBLIC_BASE_URL","").strip().lower()
    return "; Secure" if base.startswith("https://") else ""


def session_cookie(raw,max_age=2592000):
    return f"sid={raw}; HttpOnly; SameSite=Lax; Path=/; Max-Age={int(max_age)}"+secure_cookie_suffix()


def email_enabled():
    return bool(
        os.environ.get("RESEND_API_KEY")
        and os.environ.get("EMAIL_FROM")
    )


def ebl_email_html(title, message, action_text=None, action_url=None, footer=None):
    action=""
    if action_text and action_url:
        action=f"""
        <p style="margin:28px 0;text-align:center">
          <a href="{action_url}" style="display:inline-block;background:#d7262e;color:#ffffff;text-decoration:none;font-weight:800;padding:13px 22px;border-radius:8px">{action_text}</a>
        </p>
        <p style="font-size:12px;color:#6b7280;word-break:break-all">If the button does not work, copy and paste this link into your browser:<br>{action_url}</p>
        """
    footer=footer or "This message was sent by the Elite Baseball League account system."
    return f"""<!doctype html>
<html>
  <body style="margin:0;background:#eef2f6;font-family:Arial,Helvetica,sans-serif;color:#102a43">
    <div style="max-width:620px;margin:0 auto;padding:28px 14px">
      <div style="background:#071a31;color:#ffffff;border-radius:12px 12px 0 0;padding:24px;text-align:center">
        <div style="font-size:13px;letter-spacing:2px;font-weight:700;color:#d9e0e8">ELITE BASEBALL LEAGUE</div>
        <div style="font-size:28px;font-weight:900;margin-top:7px">{title}</div>
      </div>
      <div style="background:#ffffff;border:1px solid #d9e0e8;border-top:4px solid #d7262e;border-radius:0 0 12px 12px;padding:28px">
        <div style="font-size:16px;line-height:1.6">{message}</div>
        {action}
        <hr style="border:0;border-top:1px solid #e5e7eb;margin:28px 0 18px">
        <p style="margin:0;font-size:12px;line-height:1.5;color:#6b7280">{footer}</p>
      </div>
    </div>
  </body>
</html>"""


def send_mail(to, subject, body, html_body=None):
    print("EMAIL API: send_mail called")
    print("EMAIL API: enabled =", email_enabled())

    if not email_enabled():
        print("EMAIL API: missing configuration")
        return False

    try:
        payload_data={
            "from": os.environ["EMAIL_FROM"],
            "to": [to],
            "subject": subject,
            "text": body
        }
        if html_body:
            payload_data["html"]=html_body

        payload=json.dumps(payload_data).encode("utf-8")
        req=Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization":"Bearer "+os.environ["RESEND_API_KEY"],
                "Content-Type":"application/json",
                "User-Agent":"EBL/1.0 (elite-baseball.com)"
            },
            method="POST"
        )

        with urlopen(req,timeout=15) as response:
            result=response.read().decode("utf-8")
            print("EMAIL API: sent successfully",result)
            return 200 <= response.status < 300

    except HTTPError as e:
        detail=e.read().decode("utf-8",errors="replace")
        print("EMAIL API ERROR:",e.code,detail)
        return False
    except URLError as e:
        print("EMAIL API NETWORK ERROR:",str(e.reason))
        return False
    except Exception as e:
        print("EMAIL API ERROR:",type(e).__name__,str(e))
        return False


def storage_report():
    root=Path(DB).parent
    def fsize(path):
        try:return Path(path).stat().st_size
        except:return 0
    try:
        st=os.statvfs(root)
        free=st.f_bavail*st.f_frsize
        total=st.f_blocks*st.f_frsize
    except Exception:
        free=total=0
    backup_dir=Path(os.environ.get("EBL_BACKUP_DIR",os.path.join(ROOT,"backups")))
    backups=[]
    if backup_dir.exists():
        for f in sorted(backup_dir.glob("ebl_*.db"),reverse=True):
            try:backups.append({"name":f.name,"bytes":f.stat().st_size})
            except:pass
    return {
        "db_bytes":fsize(DB),
        "wal_bytes":fsize(str(DB)+"-wal"),
        "shm_bytes":fsize(str(DB)+"-shm"),
        "backup_bytes":sum(x["bytes"] for x in backups),
        "backup_count":len(backups),
        "backups":backups[:5],
        "free_bytes":free,
        "total_bytes":total,
    }


def trim_backup_files(keep=1):
    out=Path(os.environ.get("EBL_BACKUP_DIR",os.path.join(ROOT,"backups")))
    if not out.exists():return 0
    files=sorted(out.glob("ebl_*.db"),key=lambda x:x.stat().st_mtime,reverse=True)
    removed=0
    for f in files[max(0,keep):]:
        try:
            f.unlink();removed+=1
        except:pass
    return removed


def compact_historical_games(current_season,current_day,keep_full_days=STORAGE_KEEP_FULL_GAME_DAYS):
    c=conn()
    cutoff=max(0,int(current_day)-int(keep_full_days))
    rows=c.execute("""
        SELECT id,events_json FROM games
        WHERE status='FINAL' AND (season<? OR (season=? AND league_day<=?))
          AND length(events_json)>2
    """,(int(current_season),int(current_season),cutoff)).fetchall()
    changed=0
    for r in rows:
        try:events=json.loads(r["events_json"] or "[]")
        except:events=[]
        compact=compact_events_for_storage(events)
        new_json=json.dumps(compact,separators=(",",":"))
        if len(new_json)<len(r["events_json"] or ""):
            c.execute("UPDATE games SET events_json=? WHERE id=?",(new_json,r["id"]))
            changed+=1
    c.commit();c.close()
    return changed


def run_storage_maintenance(current_season=None,current_day=None,aggressive=False):
    removed_backups=trim_backup_files(keep=0 if aggressive else 1)
    compacted=0
    if current_season is not None and current_day is not None:
        compacted=compact_historical_games(current_season,current_day,0 if aggressive else STORAGE_KEEP_FULL_GAME_DAYS)
    checkpoint="ok"
    try:
        c=conn();c.execute("PRAGMA wal_checkpoint(TRUNCATE)");c.close()
    except Exception as e:
        checkpoint=str(e)
    vacuumed=False
    # VACUUM requires temporary free space, so only attempt when there is comfortable headroom.
    if aggressive:
        rep=storage_report()
        if rep["db_bytes"] and rep["free_bytes"] > rep["db_bytes"]*1.35:
            try:
                c=conn();c.execute("VACUUM");c.close();vacuumed=True
            except Exception:
                pass
    return {"removed_backups":removed_backups,"compacted_games":compacted,"checkpoint":checkpoint,"vacuumed":vacuumed,"storage":storage_report()}


class H(BaseHTTPRequestHandler):
    def out(self,obj,status=200,headers=None):
        b=json.dumps(obj).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",len(b))
        if headers:
            for k,v in headers.items():self.send_header(k,v)
        self.end_headers();self.wfile.write(b)
    def body(self):
        n=int(self.headers.get("Content-Length",0) or 0)
        return json.loads(self.rfile.read(n).decode()) if n else {}
    def auth(self,roles=None):
        raw=None
        for part in self.headers.get("Cookie","").split(";"):
            if part.strip().startswith("sid="):raw=part.strip()[4:]
        c=conn();u=session_user(c,raw)
        if not u:c.close();self.out({"error":"AUTH_REQUIRED"},401);return None
        sec=user_restricted(c,u["id"]);c.close()
        if sec["suspended"]:self.out({"error":"ACCOUNT_SUSPENDED"},403);return None
        if roles and u["role"] not in roles:self.out({"error":"FORBIDDEN"},403);return None
        return u
        
    def do_GET(self):
        p=urlparse(self.path).path


        if p=="/health" or p.startswith("/api/"):
            return self.api_get(p)


        if p in ("/", "/verify-email", "/reset-password"):
            p="/index.html"

        # Public EBL member profiles:
        # /profile/tmoney -> static/profile.html
        if p.startswith("/profile/"):
            username=p[len("/profile/"):].strip("/")
            if username:
                p="/profile.html"
            else:
                p="/index.html"


        fp=os.path.normpath(os.path.join(STATIC,p.lstrip("/")))


        if not fp.startswith(STATIC) or not os.path.isfile(fp):
            self.send_error(404)
            return


        b=open(fp,"rb").read()
        self.send_response(200)
        self.send_header(
            "Content-Type",
            mimetypes.guess_type(fp)[0] or "application/octet-stream"
        )
        self.send_header("Content-Length",len(b))
        self.end_headers()
        self.wfile.write(b)


    def do_POST(self):
        self.api_post(urlparse(self.path).path)
        
    def api_get(self,p):
        u=session_user(self.headers)
        if p in ("/health","/api/health"):
            return self.out({"ok":True,"service":"EBL","version":"1.2.0"})
        if p=="/api/me":return self.out({"user":u})
        if p=="/api/league":
            c=conn()


            season=int(c.execute(
              "SELECT v FROM league_state WHERE k='season'"
            ).fetchone()["v"])


            day=int(c.execute(
              "SELECT v FROM league_state WHERE k='league_day'"
            ).fetchone()["v"])


            phase_row=c.execute(
              "SELECT v FROM league_state WHERE k='phase'"
            ).fetchone()


            phase=phase_row["v"] if phase_row else "REGULAR"


            ensure_season_membership(c,season)
            teams=[dict(x) for x in c.execute(
                """SELECT f.id,f.name,f.wins,f.losses,f.runs_for,f.runs_against,
                          fs.division,fs.expansion_team,
                          b.display_name,b.logo_style,b.primary_color,b.secondary_color,b.accent_color
                   FROM franchises f
                   JOIN franchise_seasons fs
                     ON fs.franchise_id=f.id AND fs.season=? AND fs.status='ACTIVE'
                   LEFT JOIN franchise_branding b ON b.franchise_id=f.id
                   ORDER BY f.wins DESC,(f.runs_for-f.runs_against) DESC""",
                (season,)
            )]


            divisions=[]
            for t in teams:
                if t.get("division") and t["division"] not in divisions:
                    divisions.append(t["division"])


            c.close()


            return self.out({
                "season":season,
                "day":day,
                "phase":phase,
                "team_count":len(teams),
                "minimum_team_count":MIN_ACTIVE_TEAMS,
                "teams":teams,
                "divisions":divisions
    })
        if p=="/api/public-directory":
            c=conn()
            rows=[
                dict(x) for x in c.execute("""
                    SELECT
                        p.id AS player_id,
                        p.name,
                        p.user_id,
                        p.franchise_id,
                        p.primary_pos,
                        p.type,
                        p.active,
                        u.username
                    FROM players p
                    JOIN users u ON u.id=p.user_id
                    WHERE p.user_id IS NOT NULL
                    ORDER BY p.active DESC,p.name
                """)
            ]
            c.close()
            return self.out({"players":rows})

        if p.startswith("/api/team/"):
            fid=p.split("/")[-1].strip()
            c=conn()
            team=c.execute(
                "SELECT id,name,owner_user_id,wins,losses,runs_for,runs_against FROM franchises WHERE id=?",
                (fid,)
            ).fetchone()
            if not team:
                c.close()
                return self.out({"error":"TEAM_NOT_FOUND"},404)


            brand=c.execute("SELECT * FROM franchise_branding WHERE franchise_id=?",(fid,)).fetchone()
            roster=[]
            for row in c.execute(
                """SELECT p.id,p.user_id,p.name,p.type,p.primary_pos,p.bats,p.throws,p.xp_wallet,
                          p.season_json,p.status,p.active,u.username
                   FROM players p LEFT JOIN users u ON u.id=p.user_id
                   WHERE p.franchise_id=? AND p.active=1
                   ORDER BY CASE p.type WHEN 'H' THEN 0 ELSE 1 END,p.primary_pos,p.name""",
                (fid,)
            ):
                pl=dict(row)
                try:pl["stats"]=json.loads(pl.pop("season_json") or "{}")
                except Exception:pl["stats"]={}
                pl["is_human"]=bool(pl.get("user_id"))
                roster.append(pl)


            history=[dict(x) for x in c.execute(
                """SELECT season,wins,losses,runs_for,runs_against,playoff_finish,champion
                   FROM franchise_season_history WHERE franchise_id=? ORDER BY season DESC""",
                (fid,)
            )]
            champs=[dict(x) for x in c.execute(
                "SELECT season FROM season_champions WHERE franchise_id=? ORDER BY season DESC",
                (fid,)
            )]
            first_hist=c.execute("SELECT MIN(season) s FROM franchise_season_history WHERE franchise_id=?",(fid,)).fetchone()
            current_season=int(c.execute("SELECT v FROM league_state WHERE k='season'").fetchone()["v"])
            founded_season=int(first_hist["s"]) if first_hist and first_hist["s"] is not None else 1
            result={
                "team":dict(team),
                "branding":dict(brand) if brand else None,
                "division":division_for(fid),
                "roster":roster,
                "history":history,
                "championships":champs,
                "championship_count":len(champs),
                "founded_season":founded_season,
                "seasons_in_ebl":max(1,current_season-founded_season+1)
            }
            c.close()
            return self.out(result)


        if p.startswith("/api/profile/"):
            username=p.split("/")[-1].strip()
            c=conn()
            profile=c.execute(
                "SELECT id,username,role,created_at FROM users WHERE lower(username)=lower(?)",
                (username,)
            ).fetchone()
            if not profile:
                c.close()
                return self.out({"error":"USER_NOT_FOUND"},404)
            uid=profile["id"]
            players=[]
            for row in c.execute(
                """SELECT p.id,p.name,p.type,p.primary_pos,p.franchise_id,p.status,p.active,p.age,p.season_json,
                          f.name team_name
                   FROM players p LEFT JOIN franchises f ON f.id=p.franchise_id
                   WHERE p.user_id=? ORDER BY p.active DESC,p.id DESC""",
                (uid,)
            ):
                pl=dict(row)
                try:pl["stats"]=json.loads(pl.pop("season_json") or "{}")
                except Exception:pl["stats"]={}
                # Reuse the same career builder as /api/my-player so public profiles and
                # the owner's Player tab always tell the same historical story.
                pl["career"]=career_summary(c,pl["id"],pl.get("stats"),bool(pl.get("active")))
                players.append(pl)


            viewer=session_user(self.headers)
            friendship=None
            if viewer and viewer["id"]!=uid:
                fr=c.execute(
                    """SELECT id,requester_user_id,addressee_user_id,status FROM friendships
                       WHERE (requester_user_id=? AND addressee_user_id=?)
                          OR (requester_user_id=? AND addressee_user_id=?)
                       ORDER BY id DESC LIMIT 1""",
                    (viewer["id"],uid,uid,viewer["id"])
                ).fetchone()
                friendship=dict(fr) if fr else None


            championships=[dict(x) for x in c.execute(
                """SELECT DISTINCT pc.season,pc.franchise_id,f.name team_name
                   FROM player_championships pc LEFT JOIN franchises f ON f.id=pc.franchise_id
                   WHERE pc.user_id=? ORDER BY pc.season DESC""",(uid,)
            )]
            account_awards=sum(int((x.get("career") or {}).get("award_count",0) or 0) for x in players)
            account_seasons=sum(int((x.get("career") or {}).get("seasons_completed",0) or 0) for x in players)
            out={
                "profile":dict(profile),
                "players":players,
                "current_players":[x for x in players if x["active"]],
                "former_players":[x for x in players if not x["active"]],
                "championships":championships,
                "legacy":{"players":len(players),"completed_seasons":account_seasons,"awards":account_awards,"championships":len(championships)},
                "friendship":friendship,
                "is_self":bool(viewer and viewer["id"]==uid)
            }
            c.close()
            return self.out(out)


        if p=="/api/playoffs/bracket":
            c=conn()
            season=int(c.execute("SELECT v FROM league_state WHERE k='season'").fetchone()["v"])
            bracket=playoff_bracket(c,season)
            c.close()
            return self.out(bracket)


        if p=="/api/rivalries":
            c=conn();rows=[dict(x) for x in c.execute("""SELECT r.*,a.name team_a_name,b.name team_b_name FROM rivalries r
                JOIN franchises a ON a.id=r.team_a JOIN franchises b ON b.id=r.team_b ORDER BY r.intensity DESC,r.games DESC LIMIT 25""")]
            c.close();return self.out({"rivalries":rows})
        if p=="/api/records":
            c=conn();rows=[dict(x) for x in c.execute("SELECT * FROM league_records ORDER BY league_day DESC,record_value DESC")]
            for r in rows:
                x=c.execute("SELECT name FROM franchises WHERE id=?",(r["holder_id"],)).fetchone()
                r["holder_name"]=x["name"] if x else r["holder_id"]
            c.close();return self.out({"records":rows})
        if p=="/api/dm/contacts":
            u=self.auth()
            if not u:return
            c=conn()
            rows=[dict(x) for x in c.execute("""SELECT u.id,u.username,u.role,
                (SELECT name FROM players p WHERE p.user_id=u.id AND p.active=1 ORDER BY p.id DESC LIMIT 1) player_name,
                (SELECT f.name FROM players p JOIN franchises f ON f.id=p.franchise_id WHERE p.user_id=u.id AND p.active=1 ORDER BY p.id DESC LIMIT 1) team_name
                FROM users u WHERE u.id<>? ORDER BY u.username""",(u["id"],))]
            c.close();return self.out({"contacts":rows})
        if p.startswith("/api/dm/thread/"):
            u=self.auth()
            if not u:return
            try:other=int(p.split("/")[-1])
            except:return self.out({"error":"INVALID_USER"},400)
            c=conn()
            rows=[dict(x) for x in c.execute("""SELECT m.*,su.username sender_name,ru.username recipient_name
                FROM direct_messages m JOIN users su ON su.id=m.sender_user_id JOIN users ru ON ru.id=m.recipient_user_id
                WHERE (m.sender_user_id=? AND m.recipient_user_id=?) OR (m.sender_user_id=? AND m.recipient_user_id=?)
                ORDER BY m.id DESC LIMIT 100""",(u["id"],other,other,u["id"]))]
            rows.reverse()
            c.execute("UPDATE direct_messages SET read_at=CURRENT_TIMESTAMP WHERE recipient_user_id=? AND sender_user_id=? AND read_at IS NULL",(u["id"],other))
            c.commit();c.close();return self.out({"messages":rows})
        if p=="/api/account/security":
            u=self.auth()
            if not u:return
            c=conn();r=c.execute("SELECT email,email_verified,muted_until,suspended_until FROM user_security WHERE user_id=?",(u["id"],)).fetchone()
            c.close();return self.out({"security":dict(r) if r else None})
        if p=="/api/commish/storage-status":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            rep=storage_report()
            c=conn()
            try:
                rep["final_games"]=c.execute("SELECT COUNT(*) n FROM games WHERE status='FINAL'").fetchone()["n"]
                rep["events_bytes"]=c.execute("SELECT COALESCE(SUM(length(events_json)),0) n FROM games").fetchone()["n"]
                rep["box_bytes"]=c.execute("SELECT COALESCE(SUM(length(box_json)),0) n FROM games").fetchone()["n"]
            finally:c.close()
            return self.out({"ok":True,"storage":rep})
        if p=="/api/commish/validate-league":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn()
            season=int(c.execute("SELECT v FROM league_state WHERE k='season'").fetchone()["v"])
            day=int(c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()["v"])
            phase_row=c.execute("SELECT v FROM league_state WHERE k='phase'").fetchone()
            phase=phase_row["v"] if phase_row else "REGULAR"


            ensure_season_membership(c,season)
            team_count=len(active_franchise_ids(c,season))
            total_franchises=c.execute("SELECT COUNT(*) n FROM franchises").fetchone()["n"]
            player_count=c.execute("SELECT COUNT(*) n FROM players WHERE active=1").fetchone()["n"]
            slot_count=c.execute("SELECT COUNT(*) n FROM roster_slots").fetchone()["n"]
            season_games=c.execute("SELECT COUNT(*) n FROM games WHERE season=?",(season,)).fetchone()["n"]
            regular_games=c.execute("SELECT COUNT(*) n FROM games WHERE season=? AND league_day BETWEEN 1 AND 81",(season,)).fetchone()["n"]
            final_games=c.execute("SELECT COUNT(*) n FROM games WHERE season=? AND status='FINAL'",(season,)).fetchone()["n"]
            scheduled_games=c.execute("SELECT COUNT(*) n FROM games WHERE season=? AND status='SCHEDULED'",(season,)).fetchone()["n"]
            next_day_games=c.execute("SELECT COUNT(*) n FROM games WHERE season=? AND league_day=? AND status='SCHEDULED'",(season,day+1)).fetchone()["n"] if day<81 else 0


            missing_slots=[]
            for fid in active_franchise_ids(c,season):
                n=c.execute("SELECT COUNT(*) n FROM roster_slots WHERE franchise_id=?",(fid,)).fetchone()["n"]
                if n!=18:missing_slots.append({"franchise_id":fid,"slots":n})


            duplicate_slots=[dict(x) for x in c.execute(
                """SELECT player_id,COUNT(*) slot_count FROM roster_slots
                   WHERE player_id IS NOT NULL GROUP BY player_id HAVING COUNT(*)>1"""
            )]


            lineup_issues=[]
            for row in c.execute("SELECT franchise_id,batting_order_json,rotation_json FROM lineups ORDER BY franchise_id"):
                try:batting=json.loads(row["batting_order_json"] or "[]")
                except Exception:batting=[]
                try:rotation=json.loads(row["rotation_json"] or "[]")
                except Exception:rotation=[]
                if len(batting)!=9 or len(rotation)!=4:
                    lineup_issues.append({
                        "franchise_id":row["franchise_id"],
                        "batting_order":len(batting),
                        "rotation":len(rotation)
                    })


            issues=[]
            expected_slots=team_count*18
            expected_games=team_count*81//2
            expected_daily=team_count//2
            if team_count<MIN_ACTIVE_TEAMS:issues.append(f"League requires at least {MIN_ACTIVE_TEAMS} active franchises, found {team_count}")
            if team_count%2:issues.append(f"Active franchise count must be even, found {team_count}")
            active_slot_count=c.execute(
                """SELECT COUNT(*) n FROM roster_slots
                   WHERE franchise_id IN (
                       SELECT franchise_id FROM franchise_seasons
                       WHERE season=? AND status='ACTIVE'
                   )""",(season,)
            ).fetchone()["n"]
            if active_slot_count!=expected_slots:issues.append(f"Expected {expected_slots} active-team roster slots, found {active_slot_count}")
            if regular_games!=expected_games:issues.append(f"Expected {expected_games} regular-season games for Season {season}, found {regular_games}")
            if missing_slots:issues.append(f"{len(missing_slots)} franchises do not have exactly 18 roster slots")
            if duplicate_slots:issues.append(f"{len(duplicate_slots)} players occupy more than one roster slot")
            if lineup_issues:issues.append(f"{len(lineup_issues)} teams have an incomplete batting order or rotation")
            if phase=="REGULAR" and day<81 and next_day_games!=expected_daily:
                issues.append(f"Expected {expected_daily} scheduled games on Day {day+1}, found {next_day_games}")


            out={
                "ok":not issues,
                "season":season,"day":day,"phase":phase,
                "counts":{
                    "franchises":total_franchises,"active_franchises":team_count,"active_players":player_count,"roster_slots":slot_count,
                    "season_games":season_games,"regular_games":regular_games,
                    "final_games":final_games,"scheduled_games":scheduled_games,
                    "next_day_scheduled":next_day_games
                },
                "issues":issues,
                "missing_slots":missing_slots,
                "duplicate_slots":duplicate_slots,
                "lineup_issues":lineup_issues
            }
            c.close()
            return self.out(out)


        if p=="/api/commish/season-membership":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn()
            try:
                current=_season_number(c)
                ensure_season_membership(c,current)
                phase_row=c.execute("SELECT v FROM league_state WHERE k='phase'").fetchone()
                phase=phase_row["v"] if phase_row else "REGULAR"
                next_season=current+1
                rows=[dict(x) for x in c.execute(
                    """SELECT f.id,f.name,f.established_season,
                              cur.status current_status,cur.division current_division,
                              nxt.status next_status,nxt.division next_division,
                              COALESCE(nxt.expansion_team,0) expansion_team
                       FROM franchises f
                       LEFT JOIN franchise_seasons cur
                         ON cur.franchise_id=f.id AND cur.season=?
                       LEFT JOIN franchise_seasons nxt
                         ON nxt.franchise_id=f.id AND nxt.season=?
                       ORDER BY f.id""",
                    (current,next_season)
                )]
                return self.out({
                    "season":current,
                    "next_season":next_season,
                    "phase":phase,
                    "minimum_active_teams":MIN_ACTIVE_TEAMS,
                    "current_active":sum(1 for r in rows if r["current_status"]=="ACTIVE"),
                    "next_active":sum(1 for r in rows if r["next_status"]=="ACTIVE"),
                    "franchises":rows
                })
            finally:
                c.close()

        if p=="/api/commish/reports":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn();rows=[dict(x) for x in c.execute("""SELECT r.*,a.username reporter,b.username reported
                FROM user_reports r JOIN users a ON a.id=r.reporter_user_id
                LEFT JOIN users b ON b.id=r.reported_user_id ORDER BY CASE r.status WHEN 'OPEN' THEN 0 ELSE 1 END,r.id DESC LIMIT 300""")]
            c.close();return self.out({"reports":rows})
        if p=="/api/league/readiness":
            c=conn();r=roster_readiness(c);r["phase"]=league_cfg(c,"phase","RECRUITING");r["alpha_cpu_fill"]=league_cfg(c,"alpha_cpu_fill","1")=="1"
            c.close();return self.out(r)
        if p=="/api/league/position-demand":
            c=conn();rows=position_demand(c);c.close()
            return self.out({"positions":rows,"advisory_only":True})
        if p=="/api/commish/audit":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn();rows=[dict(x) for x in c.execute("SELECT * FROM commissioner_audit ORDER BY id DESC LIMIT 250")]
            c.close();return self.out({"audit":rows})
        if p=="/api/news":
            c=conn()
            rows=[dict(x) for x in c.execute("""SELECT n.*,f.name franchise_name,p.name player_name
                FROM news n LEFT JOIN franchises f ON f.id=n.franchise_id
                LEFT JOIN players p ON p.id=n.player_id
                ORDER BY n.league_day DESC,n.importance DESC,n.id DESC LIMIT 60""")]
            c.close();return self.out({"news":rows})
        if p=="/api/schedule":
            c=conn()


            season=int(c.execute(
                "SELECT v FROM league_state WHERE k='season'"
            ).fetchone()["v"])


            rows=[dict(x) for x in c.execute(
                "SELECT id,season,league_day,away_id,home_id,away_runs,home_runs,status FROM games WHERE season=? ORDER BY league_day,id",
                (season,)
            )]


            c.close()
            return self.out({"season":season,"games":rows})
            gid=p.split("/")[-1]
            c=conn()


            g=c.execute(
                "SELECT * FROM games WHERE id=?",
                (gid,)
            ).fetchone()


            if not g:
                c.close()
                return self.out({"error":"GAME_NOT_FOUND"},404)


            d=dict(g)
            d["box"]=json.loads(d.pop("box_json") or "{}")
            d["events"]=json.loads(d.pop("events_json") or "[]")


            # Team names
            away_team=c.execute(
                "SELECT id,name FROM franchises WHERE id=?",
                (d["away_id"],)
            ).fetchone()


            home_team=c.execute(
                "SELECT id,name FROM franchises WHERE id=?",
                (d["home_id"],)
            ).fetchone()


            d["away_name"]=away_team["name"] if away_team else d["away_id"]
            d["home_name"]=home_team["name"] if home_team else d["home_id"]


            # Inning-by-inning line score from GameCast events
            inning_runs={
                d["away_id"]:{str(i):0 for i in range(1,10)},
                d["home_id"]:{str(i):0 for i in range(1,10)}
            }


            previous={
                d["away_id"]:0,
                d["home_id"]:0
            }


            for ev in d["events"]:
                if ev.get("type")=="INNING_END":
                    inning=int(ev.get("inning",0))
                    half=ev.get("half")
                    score=ev.get("score",[0,0])


                    if 1<=inning<=9 and len(score)>=2:
                        if half=="TOP":
                            total=int(score[0])
                            inning_runs[d["away_id"]][str(inning)]=max(
                                0,
                                total-previous[d["away_id"]]
                            )
                            previous[d["away_id"]]=total


                        elif half=="BOT":
                            total=int(score[1])
                            inning_runs[d["home_id"]][str(inning)]=max(
                                0,
                                total-previous[d["home_id"]]
                            )
                            previous[d["home_id"]]=total


            d["line_score"]={
                "away":inning_runs[d["away_id"]],
                "home":inning_runs[d["home_id"]]
            }


            # Enrich hitters with names/team
            hitter_rows=[]


            for pid,line in d["box"].get("hitters",{}).items():
                pl=c.execute(
                    "SELECT id,name,franchise_id FROM players WHERE id=?",
                    (int(pid),)
                ).fetchone()


                hitter_rows.append({
                    "player_id":int(pid),
                    "name":pl["name"] if pl else "Unknown Player",
                    "team_id":pl["franchise_id"] if pl else None,
                    **line
                })


            d["box"]["hitter_rows"]=hitter_rows


            # Enrich pitchers with names
            pitcher_rows=[]


            for fid,rows in d["box"].get("pitchers",{}).items():
                for line in rows:
                    pid=int(line["player_id"])


                    pl=c.execute(
                    "SELECT id,name FROM players WHERE id=?",
                        (pid,)
                    ).fetchone()


                    pitcher_rows.append({
                        "player_id":pid,
                        "name":pl["name"] if pl else "Unknown Pitcher",
                        "team_id":fid,
                        **line
                    })


                    d["box"]["pitcher_rows"]=pitcher_rows


                    # Simple R/H/E totals
                    away_hits=sum(
                        x.get("H",0)
                        for x in hitter_rows
                        if x.get("team_id")==d["away_id"]
                    )


                    home_hits=sum(
                        x.get("H",0)
                        for x in hitter_rows
                        if x.get("team_id")==d["home_id"]
                    )


                    d["totals"]={
                        "away":{
                            "R":d.get("away_runs",0),
                            "H":away_hits,
                            "E":0
                        },
                        "home":{
                            "R":d.get("home_runs",0),
                            "H":home_hits,
                            "E":0
                        }
                    }


                    c.close()
                    return self.out({"game":d})         
        if p.startswith("/api/game/"):
            gid=p.split("/")[-1].strip()


            c=conn()


            g=c.execute(
                "SELECT * FROM games WHERE id=?",
                (gid,)
            ).fetchone()


            if not g:
                c.close()
                return self.out({"error":"GAME_NOT_FOUND"},404)


            game=dict(g)


            # ---------------------------------------------
            # EVENTS
            # ---------------------------------------------


            try:
                game["events"]=json.loads(
                    game.get("events_json") or "[]"
                )
            except Exception:
                game["events"]=[]


            # ---------------------------------------------
            # RAW BOX SCORE
            # ---------------------------------------------


            try:
                raw_box=json.loads(
                    game.get("box_json") or "{}"
                )
            except Exception:
                raw_box={}


            # ---------------------------------------------
            # BUILD GAMECAST-FRIENDLY HITTER ROWS
            # ---------------------------------------------


            hitter_rows=[]


            for pid,line in raw_box.get("hitters",{}).items():
                player=c.execute(
                    """
                    SELECT id,name,franchise_id
                    FROM players
                    WHERE id=?
                    """,
                    (int(pid),)
                ).fetchone()


                if not player:
                    continue


                hitter_rows.append({
                    "player_id":int(pid),
                    "name":player["name"],
                    "team_id":player["franchise_id"],
                    **line
                })


            # ---------------------------------------------
            # BUILD GAMECAST-FRIENDLY PITCHER ROWS
            # ---------------------------------------------


            pitcher_rows=[]


            for team_id,rows in raw_box.get("pitchers",{}).items():
                for line in rows:
                    pid=line.get("player_id")


                    player=c.execute(
                        """
                        SELECT name
                        FROM players
                        WHERE id=?
                        """,
                        (pid,)
                    ).fetchone()


                    pitcher_rows.append({
                        "player_id":pid,
                        "name":player["name"] if player else f"Player {pid}",
                        "team_id":team_id,
                        **line
                    })


            # ---------------------------------------------
            # COMPLETE BOX SCORE
            # ---------------------------------------------


            game["box"]={
                **raw_box,
                "hitter_rows":hitter_rows,
                "pitcher_rows":pitcher_rows
            }


            # ---------------------------------------------
            # BUILD LINE SCORE FROM RUN EVENTS
            # ---------------------------------------------


            away_line={str(i):0 for i in range(1,10)}
            home_line={str(i):0 for i in range(1,10)}


            for ev in game["events"]:
                if ev.get("type")!="RUN":
                    continue


                inning=str(ev.get("inning",9))
                runs=int(ev.get("runs",0) or 0)
                team=ev.get("team")


                if team==game["away_id"]:
                    away_line[inning]=away_line.get(inning,0)+runs


                elif team==game["home_id"]:
                    home_line[inning]=home_line.get(inning,0)+runs


            game["line_score"]={
                "away":away_line,
                "home":home_line
            }


            # ---------------------------------------------
            # GAME TOTALS
            # ---------------------------------------------


            game["totals"]={
                "away":{
                    "R":game["away_runs"] or 0,
                    "H":sum(
                        int(x.get("H",0) or 0)
                        for x in hitter_rows
                        if x["team_id"]==game["away_id"]
                    ),
                    "E":0
                },
                "home":{
                    "R":game["home_runs"] or 0,
                    "H":sum(
                        int(x.get("H",0) or 0)
                        for x in hitter_rows
                        if x["team_id"]==game["home_id"]
                    ),
                    "E":0
                }
            }


            c.close()


            return self.out({
                "game":game
            })  
        if p=="/api/my-player":
            u=self.auth()
            if not u:return
            c=conn()
            active_row=c.execute(
                "SELECT id FROM players WHERE user_id=? AND active=1 ORDER BY id DESC LIMIT 1",
                (u["id"],)
            ).fetchone()
            pl=player_obj(c,active_row["id"]) if active_row else None
            if pl and pl.get("franchise_id"):
                f=c.execute(
                    "SELECT id,name,wins,losses,runs_for,runs_against FROM franchises WHERE id=?",
                    (pl["franchise_id"],)
                ).fetchone()
                if f:
                    pl["team"]=dict(f);pl["team"]["division"]=division_for(pl["franchise_id"])
            former=[]
            for row in c.execute(
                "SELECT id FROM players WHERE user_id=? AND active=0 ORDER BY id DESC",
                (u["id"],)
            ).fetchall():
                fp=player_obj(c,row["id"])
                if fp: former.append(fp)
            c.close()
            return self.out({"player":pl,"careers":former})
        if p=="/api/coach/free-agents":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            c=conn();rows=[player_obj(c,x["id"]) for x in c.execute("SELECT id FROM players WHERE status='FREE_AGENT' AND active=1 ORDER BY id DESC LIMIT 100")];c.close();return self.out({"players":rows})
        if p=="/api/coach/team":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            c=conn();f=c.execute("SELECT * FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"team":None})
            roster=[dict(x) for x in c.execute(
                """SELECT p.id,p.user_id,p.name,p.type,p.primary_pos,p.xp_wallet,p.status,u.username,
                          co.salary,co.bonus,co.years_remaining
                   FROM players p
                   LEFT JOIN users u ON u.id=p.user_id
                   LEFT JOIN contracts co ON co.player_id=p.id
                   WHERE p.franchise_id=? AND p.active=1
                   ORDER BY CASE p.type WHEN 'H' THEN 0 ELSE 1 END,p.primary_pos,p.id""",(f["id"],))]
            l=c.execute("SELECT * FROM lineups WHERE franchise_id=?",(f["id"],)).fetchone()
            strat=c.execute("SELECT * FROM team_strategy WHERE franchise_id=?",(f["id"],)).fetchone()
            offers=[dict(x) for x in c.execute("""SELECT o.*,p.name,p.primary_pos,u.username FROM offers o
                       JOIN players p ON p.id=o.player_id LEFT JOIN users u ON u.id=p.user_id
                       WHERE o.franchise_id=? AND o.status IN ('OPEN','HELD') ORDER BY o.id DESC""",(f["id"],))]
            brand=c.execute("SELECT * FROM franchise_branding WHERE franchise_id=?",(f["id"],)).fetchone()
            contracts=[dict(x) for x in c.execute(
                """SELECT co.id,co.player_id,co.bonus,co.salary,co.years_remaining,co.signed_at,
                          p.name,p.primary_pos,p.type,u.username
                   FROM contracts co JOIN players p ON p.id=co.player_id
                   LEFT JOIN users u ON u.id=p.user_id
                   WHERE co.franchise_id=? AND p.active=1
                   ORDER BY p.type,p.primary_pos,p.name""",(f["id"],))]
            state={x["k"]:x["v"] for x in c.execute("SELECT k,v FROM league_state WHERE k IN ('season','league_day','phase')")}
            season=int(state.get("season",2));day=int(state.get("league_day",0))
            next_game=c.execute(
                """SELECT id,season,league_day,away_id,home_id,status
                   FROM games WHERE season=? AND league_day>? AND status='SCHEDULED'
                     AND (away_id=? OR home_id=?)
                   ORDER BY league_day,id LIMIT 1""",(season,day,f["id"],f["id"])).fetchone()
            reserved=float(c.execute("SELECT COALESCE(SUM(bonus),0) x FROM offers WHERE franchise_id=? AND status IN ('OPEN','HELD')",(f["id"],)).fetchone()["x"] or 0)
            salary_rate=sum(float(x.get("salary") or 0) for x in contracts)
            team=dict(f)
            team["xp_available"]=max(0.0,float(team.get("xp_budget") or 0)-float(team.get("xp_spent") or 0)-reserved)
            team["reserved_offers"]=reserved
            team["salary_rate"]=round(salary_rate,3)
            team["spend_pct"]=round((float(team.get("xp_spent") or 0)/float(team.get("xp_budget") or 1))*100,1)
            c.close()
            return self.out({"team":team,"branding":dict(brand) if brand else None,"roster":roster,
                             "lineup":json.loads(l["batting_order_json"]) if l else [],
                             "rotation":json.loads(l["rotation_json"]) if l else [],
                             "strategy":{"bullpen":json.loads(strat["bullpen_json"]) if strat else {},
                                         "defense":json.loads(strat["defense_json"]) if strat else {},
                                         "bench":json.loads(strat["bench_json"]) if strat else {},
                                         "substitutions":json.loads(strat["substitutions_json"]) if strat else {}},
                             "offers":offers,"contracts":contracts,
                             "next_game":dict(next_game) if next_game else None,
                             "league_day":day,"phase":state.get("phase","REGULAR")})
        if p=="/api/friends":
            u=self.auth()
            if not u:return
            c=conn()
            accepted=[dict(x) for x in c.execute(
                """SELECT f.id,
                          CASE WHEN f.requester_user_id=? THEN f.addressee_user_id ELSE f.requester_user_id END user_id,
                          u.username,p.name player_name,p.franchise_id
                   FROM friendships f
                   JOIN users u ON u.id=CASE WHEN f.requester_user_id=? THEN f.addressee_user_id ELSE f.requester_user_id END
                   LEFT JOIN players p ON p.user_id=u.id AND p.active=1
                   WHERE f.status='ACCEPTED' AND (f.requester_user_id=? OR f.addressee_user_id=?)
                   ORDER BY LOWER(u.username)""",(u["id"],u["id"],u["id"],u["id"]))]
            incoming=[dict(x) for x in c.execute(
                """SELECT f.id,f.requester_user_id user_id,u.username,p.name player_name,p.franchise_id,f.created_at
                   FROM friendships f JOIN users u ON u.id=f.requester_user_id
                   LEFT JOIN players p ON p.user_id=u.id AND p.active=1
                   WHERE f.addressee_user_id=? AND f.status='PENDING' ORDER BY f.id DESC""",(u["id"],))]
            outgoing=[dict(x) for x in c.execute(
                """SELECT f.id,f.addressee_user_id user_id,u.username,p.name player_name,p.franchise_id,f.created_at
                   FROM friendships f JOIN users u ON u.id=f.addressee_user_id
                   LEFT JOIN players p ON p.user_id=u.id AND p.active=1
                   WHERE f.requester_user_id=? AND f.status='PENDING' ORDER BY f.id DESC""",(u["id"],))]
            c.close();return self.out({"friends":accepted,"incoming":incoming,"outgoing":outgoing})
        if p=="/api/notifications":
            u=self.auth()
            if not u:return
            c=conn()
            rows=[dict(x) for x in c.execute("SELECT id,type,title,body,ref_id,is_read,created_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50",(u["id"],))]
            unread=sum(1 for x in rows if not x["is_read"])
            c.close();return self.out({"notifications":rows,"unread":unread})

        if p=="/api/awards":
            c=conn(); hitters=[]; pitchers=[]
            for r in c.execute("""SELECT p.id,p.name,p.franchise_id,p.primary_pos,p.season_json,u.username
                                  FROM players p LEFT JOIN users u ON u.id=p.user_id WHERE p.active=1"""):
                st=json.loads(r["season_json"])
                if "PA" in st:
                    ab=st.get("AB",0);h=st.get("H",0);bb=st.get("BB",0);pa=st.get("PA",0)
                    tb=st.get("1B",0)+2*st.get("2B",0)+3*st.get("3B",0)+4*st.get("HR",0)
                    avg=h/ab if ab else 0;obp=(h+bb)/pa if pa else 0;slg=tb/ab if ab else 0
                    # MVP proxy deliberately broad: offense + speed/base value; defensive detail expands as event engine records it.
                    mvp=(obp+slg)*100 + st.get("HR",0)*1.1 + st.get("SB",0)*.35 + st.get("RBI",0)*.12
                    hitters.append({"id":r["id"],"name":r["name"],"username":r["username"],"team":r["franchise_id"],"pos":r["primary_pos"],
                                    "avg":avg,"obp":obp,"slg":slg,"ops":obp+slg,"hr":st.get("HR",0),"rbi":st.get("RBI",0),
                                    "sb":st.get("SB",0),"pa":pa,"mvp":mvp})
                else:
                    outs=st.get("OUTS",0);er=st.get("ER",0);bb=st.get("BB",0);h=st.get("H",0);so=st.get("SO",0)
                    era=er*27/outs if outs else 99.0;whip=(bb+h)/(outs/3) if outs else 99.0
                    score=(so*1.2)-(er*2.2)-(bb*.7)+(outs/3)*.3
                    pitchers.append({"id":r["id"],"name":r["name"],"username":r["username"],"team":r["franchise_id"],"pos":r["primary_pos"],
                                     "era":era,"whip":whip,"so":so,"sv":st.get("SV",0),"outs":outs,"score":score})
            qualified=[x for x in hitters if x["pa"]>=max(1,int(c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()["v"])*2)]
            batting=sorted(qualified or hitters,key=lambda x:(x["avg"],x["pa"]),reverse=True)[:10]
            mvp=sorted(hitters,key=lambda x:x["mvp"],reverse=True)[:10]
            hr=sorted(hitters,key=lambda x:(x["hr"],x["ops"]),reverse=True)[:10]
            sb=sorted(hitters,key=lambda x:(x["sb"],x["obp"]),reverse=True)[:10]
            starting_pitching=sorted(
                [x for x in pitchers if x["pos"]=="SP" and x["outs"]>0],
                key=lambda x:(-x["score"],x["era"])
            )[:10]
            relief_pitching=sorted(
                [x for x in pitchers if x["pos"]!="SP" and x["outs"]>0],
                key=lambda x:(-(x["score"]+x.get("sv",0)*1.5),-x.get("sv",0),x["era"])
            )[:10]
            pitching=starting_pitching + relief_pitching
            # Fielding titles are position race placeholders until complete fielding events populate OAA/DRS.
            fielding={}
            for pos in ["C","1B","2B","3B","SS","LF","CF","RF"]:
                pool=[x for x in hitters if x["pos"]==pos]
                fielding[pos]=sorted(pool,key=lambda x:(x["pa"],x["ops"]),reverse=True)[:5]
            history=[dict(x) for x in c.execute("""SELECT ah.*,p.name player_name,u.username,f.name team_name FROM award_history ah
                LEFT JOIN players p ON p.id=ah.player_id LEFT JOIN users u ON u.id=p.user_id LEFT JOIN franchises f ON f.id=ah.franchise_id
                ORDER BY ah.season DESC,ah.id DESC LIMIT 100""")]
            c.close();return self.out({
                "mvp":mvp,
                "batting":batting,
                "home_runs":hr,
                "stolen_bases":sb,
                "pitching":pitching,
                "starting_pitching":starting_pitching,
                "relief_pitching":relief_pitching,
                "fielding":fielding,
                "xp_values":{
                    "MVP":15,
                    "BATTING_TITLE":10,
                    "PITCHER_OF_SEASON":15,
                    "RELIEVER_OF_SEASON":10,
                    "SB_TITLE":10,
                    "FIELDING":10,
                    "QUARTER_BATTER":5,
                    "QUARTER_PITCHER":5
                },
                "history":history
            })
        if p.startswith("/api/chat/"):
            u=self.auth()
            if not u:return
            channel=p.split("/")[-1].upper()
            if channel not in ("EBL","TEAM"):return self.out({"error":"INVALID_CHANNEL"},400)
            c=conn();team_id=None
            # Public/team chat is intentionally temporary. Private DMs are stored separately.
            c.execute(
                "DELETE FROM chat_messages WHERE created_at < datetime('now', ?)",
                (f"-{CHAT_RETENTION_HOURS} hours",)
            )
            c.commit()
            if channel=="TEAM":
                pr=c.execute("SELECT franchise_id FROM players WHERE user_id=? AND active=1 ORDER BY id DESC LIMIT 1",(u["id"],)).fetchone()
                team_id=pr["franchise_id"] if pr else None
                if not team_id:c.close();return self.out({"messages":[]})
            rows=[dict(x) for x in c.execute("""SELECT m.id,m.channel,m.team_id,m.message,m.created_at,u.username
                    FROM chat_messages m JOIN users u ON u.id=m.user_id
                    WHERE m.channel=? AND (? IS NULL OR m.team_id=?)
                    ORDER BY m.id DESC LIMIT 50""",(channel,team_id,team_id))]
            rows.reverse();c.close();return self.out({"messages":rows})
        if p=="/api/simulation-lab":
            fp=os.path.join(ROOT,"simulation_lab_report.json")
            with open(fp,"r") as f: return self.out(json.load(f))
        if p=="/api/analytics":
            u=self.auth()
            if not u:return
            c=conn()
            day=int(c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()["v"])
            finals=c.execute("SELECT COUNT(*) n FROM games WHERE status='FINAL'").fetchone()["n"]
            runs=c.execute("SELECT COALESCE(SUM(away_runs+home_runs),0) n FROM games WHERE status='FINAL'").fetchone()["n"]
            hitters=[]; pitchers=[]
            for r in c.execute("""SELECT p.id,p.name,p.primary_pos,p.xp_wallet,p.attributes_json,p.season_json,p.franchise_id,u.username
                                  FROM players p LEFT JOIN users u ON u.id=p.user_id WHERE p.active=1"""):
                d=dict(r); st=json.loads(d["season_json"]); at=json.loads(d["attributes_json"])
                if "PA" in st:
                    ab=st.get("AB",0);h=st.get("H",0);bb=st.get("BB",0)
                    avg=h/ab if ab else 0
                    obp=(h+bb)/(st.get("PA",0)) if st.get("PA",0) else 0
                    tb=st.get("1B",0)+2*st.get("2B",0)+3*st.get("3B",0)+4*st.get("HR",0)
                    slg=tb/ab if ab else 0
                    hitters.append({"id":d["id"],"name":d["name"],"username":d.get("username"),"team":d["franchise_id"],"pos":d["primary_pos"],"xp":d["xp_wallet"],"avg":avg,"obp":obp,"slg":slg,"ops":obp+slg,"hr":st.get("HR",0),"so":st.get("SO",0),"bb":bb,"pa":st.get("PA",0),"attr_total":sum(at.values())})
                else:
                    outs=st.get("OUTS",0); er=st.get("ER",0); bb=st.get("BB",0); h=st.get("H",0)
                    era=er*27/outs if outs else 0
                    whip=(bb+h)/(outs/3) if outs else 0
                    pitchers.append({"id":d["id"],"name":d["name"],"username":d.get("username"),"team":d["franchise_id"],"pos":d["primary_pos"],"xp":d["xp_wallet"],"era":era,"whip":whip,"so":st.get("SO",0),"bb":bb,"outs":outs,"attr_total":sum(at.values())})
            active_h=[x for x in hitters if x["pa"]>0]; active_p=[x for x in pitchers if x["outs"]>0]
            total_pa=sum(x["pa"] for x in active_h); total_h=sum(json.loads(c.execute("SELECT season_json FROM players WHERE id=?",(x["id"],)).fetchone()[0]).get("H",0) for x in active_h)
            total_bb=sum(x["bb"] for x in active_h); total_so=sum(x["so"] for x in active_h); total_hr=sum(x["hr"] for x in active_h)
            league={"games":finals,"runs_per_game":runs/finals if finals else 0,"avg":total_h/max(1,sum(json.loads(c.execute("SELECT season_json FROM players WHERE id=?",(x["id"],)).fetchone()[0]).get("AB",0) for x in active_h)) if active_h else 0,
                    "bb_pct":total_bb/total_pa if total_pa else 0,"k_pct":total_so/total_pa if total_pa else 0,"hr_pct":total_hr/total_pa if total_pa else 0}
            xp={}
            if u["role"]=="COMMISSIONER":
                xp_rows=c.execute("SELECT event_type,COALESCE(SUM(xp),0) total,COUNT(*) n FROM xp_ledger GROUP BY event_type").fetchall()
                xp={x["event_type"]:{"total":round(x["total"],3),"events":x["n"]} for x in xp_rows}
            season=_season_number(c)
            active_ids=active_franchise_ids(c,season)
            q=",".join("?" for _ in active_ids)
            teams=[dict(x) for x in c.execute(
                f"SELECT id,name,wins,losses,runs_for,runs_against FROM franchises WHERE id IN ({q}) ORDER BY wins DESC,(runs_for-runs_against) DESC LIMIT 10",
                active_ids
            )]
            c.close()
            return self.out({"season":season,"day":day,"league":league,"xp":xp,
                "leaders":{"ops":sorted(active_h,key=lambda x:x["ops"],reverse=True)[:10],
                           "hr":sorted(active_h,key=lambda x:(x["hr"],x["ops"]),reverse=True)[:10],
                           "pitching":sorted(active_p,key=lambda x:(x["era"],-x["so"]))[:10]},
                "teams":teams})
        return self.out({"error":"NOT_FOUND"},404)


    def api_post(self,p):
        if p=="/api/register":
            d=self.body();username=str(d.get("username","")).strip();password=str(d.get("password",""));email=str(d.get("email","")).strip().lower()
            if len(username)<3 or len(username)>24:return self.out({"error":"INVALID_USERNAME"},400)
            if len(password)<8:return self.out({"error":"PASSWORD_TOO_SHORT"},400)
            if "@" not in email or "." not in email.split("@")[-1]:return self.out({"error":"INVALID_EMAIL"},400)
            c=conn();ip=get_client_ip(self)
            if not rate_limit(c,f"register:{ip}",5,3600):c.commit();c.close();return self.out({"error":"RATE_LIMITED"},429)
            if c.execute("SELECT 1 FROM users WHERE username=?",(username,)).fetchone():c.close();return self.out({"error":"USERNAME_TAKEN"},409)
            if c.execute("SELECT 1 FROM user_security WHERE email=?",(email,)).fetchone():c.close();return self.out({"error":"EMAIL_IN_USE"},409)
            c.execute("INSERT INTO users(username,password_hash,role) VALUES(?,?,'PLAYER')",(username,pwhash(password)))
            uid=c.execute("SELECT id FROM users WHERE username=?",(username,)).fetchone()["id"]
            raw_verify=secrets.token_urlsafe(24)
            c.execute("""INSERT INTO user_security(user_id,email,email_verified,email_token_hash,email_token_expires)
                         VALUES(?,?,0,?,?)""",(uid,email,token_hash(raw_verify),iso_after(60)))
            sid,_=new_session(c,uid,self)
            c.commit();c.close()
            verify_url=os.environ.get("PUBLIC_BASE_URL","http://127.0.0.1:8000").rstrip("/")+"/verify-email?token="+raw_verify+"&user="+str(uid)
            sent=send_mail(
                email,
                "Confirm your Elite Baseball League account",
                f"Welcome to the Elite Baseball League.\n\nConfirm your email within 60 minutes:\n{verify_url}\n\nIf you did not create this account, you can ignore this email.",
                ebl_email_html(
                    "Confirm Your Account",
                    "Welcome to the <strong>Elite Baseball League</strong>. Confirm your email address to activate your player account. This link expires in 60 minutes.",
                    "Confirm Email",
                    verify_url,
                    "If you did not create an EBL account, no action is required."
                )
            )
            return self.out({"user":{"id":uid,"username":username,"role":"PLAYER"},"verification_email_sent":sent},200,{"Set-Cookie":session_cookie(sid)})
        if p=="/api/login":
            d=self.body();username=str(d.get("username","")).strip();password=str(d.get("password",""))
            c=conn();ip=get_client_ip(self)
            if not rate_limit(c,f"login:{ip}",20,900):c.commit();c.close();return self.out({"error":"RATE_LIMITED"},429)
            r=c.execute("SELECT id,username,role,password_hash FROM users WHERE username=?",(username,)).fetchone()
            if not r or not pwcheck(password,r["password_hash"]):c.commit();c.close();return self.out({"error":"INVALID_LOGIN"},401)
            sec=user_restricted(c,r["id"])
            if sec["suspended"]:c.close();return self.out({"error":"ACCOUNT_SUSPENDED"},403)
            sid,_=new_session(c,r["id"],self)
            c.commit();c.close()
            return self.out({"user":{"id":r["id"],"username":r["username"],"role":r["role"]}},200,{"Set-Cookie":session_cookie(sid)})
        if p=="/api/logout":
            raw=None
            for part in self.headers.get("Cookie","").split(";"):
                if part.strip().startswith("sid="):raw=part.strip()[4:]
            if raw:
                c=conn();c.execute("DELETE FROM persistent_sessions WHERE token_hash=?",(token_hash(raw),));c.commit();c.close()
            return self.out({"ok":True},200,{"Set-Cookie":session_cookie("",0)})
        if p=="/api/account/recover":
            d=self.body();username=str(d.get("username","")).strip();code=str(d.get("recovery_code","")).strip();newpw=str(d.get("new_password",""))
            if len(newpw)<8:return self.out({"error":"PASSWORD_TOO_SHORT"},400)
            c=conn();ip=get_client_ip(self)
            if not rate_limit(c,f"recovery:{ip}",8,3600):
                c.commit();c.close();return self.out({"error":"RATE_LIMITED"},429)
            u=c.execute("SELECT id FROM users WHERE username=?",(username,)).fetchone()
            if not u:c.commit();c.close();return self.out({"error":"INVALID_RECOVERY"},400)
            r=c.execute("SELECT recovery_hash FROM account_recovery WHERE user_id=?",(u["id"],)).fetchone()
            if not r or not hmac.compare_digest(r["recovery_hash"],recovery_hash(code)):
                c.commit();c.close();return self.out({"error":"INVALID_RECOVERY"},400)
            c.execute("UPDATE users SET password_hash=? WHERE id=?",(pwhash(newpw),u["id"]))
            newcode=make_recovery_code()
            c.execute("UPDATE account_recovery SET recovery_hash=?,created_at=CURRENT_TIMESTAMP WHERE user_id=?",(recovery_hash(newcode),u["id"]))
            c.execute("DELETE FROM persistent_sessions WHERE user_id=?",(u["id"],))
            c.commit();c.close();return self.out({"ok":True,"new_recovery_code":newcode})
        if p=="/api/account/rotate-recovery":
            u=self.auth()
            if not u:return
            code=make_recovery_code();c=conn()
            c.execute("INSERT OR REPLACE INTO account_recovery(user_id,recovery_hash,created_at) VALUES(?,?,CURRENT_TIMESTAMP)",(u["id"],recovery_hash(code)))
            c.commit();c.close();return self.out({"ok":True,"recovery_code":code})
        if p=="/api/account/verify-email":
            d=self.body()
            try:uid=int(d.get("user_id",0))
            except:return self.out({"error":"INVALID_TOKEN"},400)
            token=str(d.get("token",""));c=conn()
            r=c.execute("SELECT * FROM user_security WHERE user_id=?",(uid,)).fetchone()
            if not r or not r["email_token_hash"] or parse_iso(r["email_token_expires"])<utcnow() or not hmac.compare_digest(r["email_token_hash"],token_hash(token)):
                c.close();return self.out({"error":"INVALID_OR_EXPIRED_TOKEN"},400)
            c.execute("UPDATE user_security SET email_verified=1,email_token_hash=NULL,email_token_expires=NULL,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",(uid,))
            c.commit();c.close();return self.out({"ok":True})
        if p=="/api/account/request-password-reset":
            d=self.body();email=str(d.get("email","")).strip().lower();c=conn();ip=get_client_ip(self)
            if not rate_limit(c,f"pwreset:{ip}",8,3600):c.commit();c.close();return self.out({"ok":True})
            r=c.execute("SELECT s.user_id,u.username FROM user_security s JOIN users u ON u.id=s.user_id WHERE s.email=? AND s.email_verified=1",(email,)).fetchone()
            if r:
                raw=secrets.token_urlsafe(28)
                c.execute("UPDATE user_security SET reset_token_hash=?,reset_token_expires=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",(token_hash(raw),iso_after(30),r["user_id"]))
                c.commit()
                url=os.environ.get("PUBLIC_BASE_URL","http://127.0.0.1:8000").rstrip("/")+"/reset-password?token="+raw+"&user="+str(r["user_id"])
                send_mail(
                    email,
                    "Reset your Elite Baseball League password",
                    f"A password reset was requested for {r['username']}.\n\nThis link expires in 30 minutes:\n{url}\n\nIf you did not request this reset, you can ignore this email.",
                    ebl_email_html(
                        "Reset Your Password",
                        "We received a request to reset your <strong>Elite Baseball League</strong> password. This secure link expires in 30 minutes.",
                        "Reset Password",
                        url,
                        "If you did not request a password reset, you can safely ignore this email."
                    )
                )
            else:c.commit()
            c.close();return self.out({"ok":True})
        if p=="/api/account/reset-password":
            d=self.body()
            try:uid=int(d.get("user_id",0))
            except:return self.out({"error":"INVALID_TOKEN"},400)
            token=str(d.get("token",""));pw=str(d.get("new_password",""))
            if len(pw)<8:return self.out({"error":"PASSWORD_TOO_SHORT"},400)
            c=conn();r=c.execute("SELECT * FROM user_security WHERE user_id=?",(uid,)).fetchone()
            if not r or not r["reset_token_hash"] or parse_iso(r["reset_token_expires"])<utcnow() or not hmac.compare_digest(r["reset_token_hash"],token_hash(token)):
                c.close();return self.out({"error":"INVALID_OR_EXPIRED_TOKEN"},400)
            c.execute("UPDATE users SET password_hash=? WHERE id=?",(pwhash(pw),uid))
            c.execute("UPDATE user_security SET reset_token_hash=NULL,reset_token_expires=NULL,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",(uid,))
            c.execute("DELETE FROM persistent_sessions WHERE user_id=?",(uid,))
            c.commit();c.close();return self.out({"ok":True})
        if p=="/api/account/resend-verification":
            u=self.auth()
            if not u:return
            c=conn();ip=get_client_ip(self)
            r=c.execute("SELECT email,email_verified FROM user_security WHERE user_id=?",(u["id"],)).fetchone()
            if not r or r["email_verified"]:c.close();return self.out({"ok":True})
            if not rate_limit(c,f"verify-resend:user:{u['id']}",3,3600) or not rate_limit(c,f"verify-resend:ip:{ip}",10,3600):
                c.commit();c.close();return self.out({"error":"RATE_LIMITED"},429)
            raw=secrets.token_urlsafe(24)
            c.execute("UPDATE user_security SET email_token_hash=?,email_token_expires=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",(token_hash(raw),iso_after(60),u["id"]))
            c.commit();email=r["email"];c.close()
            url=os.environ.get("PUBLIC_BASE_URL","http://127.0.0.1:8000").rstrip("/")+"/verify-email?token="+raw+"&user="+str(u["id"])
            sent=send_mail(
                email,
                "Confirm your Elite Baseball League account",
                f"Confirm your EBL email within 60 minutes:\n{url}",
                ebl_email_html(
                    "Confirm Your Account",
                    "Use the button below to confirm your email address. This link expires in 60 minutes.",
                    "Confirm Email",
                    url,
                    "If you did not request this message, no action is required."
                )
            )
            return self.out({"ok":True,"sent":sent})
        if p=="/api/player/create":
            u=self.auth(["PLAYER","COMMISSIONER"])
            if not u:return
            d=self.body();name=str(d.get("name","")).strip();pos=d.get("position");bats=d.get("bats");throws=d.get("throws");attrs=d.get("attributes",{})
            c=conn()
            if u["role"]=="PLAYER":
                sec=c.execute("SELECT email_verified FROM user_security WHERE user_id=?",(u["id"],)).fetchone()
                if not sec or not sec["email_verified"]:
                    c.close();return self.out({"error":"EMAIL_NOT_VERIFIED"},403)
            if c.execute("SELECT COUNT(*) n FROM players WHERE user_id=? AND active=1",(u["id"],)).fetchone()["n"]>=1:c.close();return self.out({"error":"ACTIVE_PLAYER_LIMIT_REACHED"},400)
            ptype="P" if pos in ["SP","RP"] else "H";valid=PITCHER_ATTRS if ptype=="P" else HITTER_ATTRS
            if not name or bats not in ["R","L","S"] or throws not in ["R","L"] or set(attrs)!=set(valid) or sum(attrs.values())!=50 or any(not isinstance(v,int) or v<0 for v in attrs.values()):
                c.close();return self.out({"error":"INVALID_50_XP_BUILD"},400)
            season={k:0 for k in (["G","GS","OUTS","H","ER","BB","SO","W","L","SV"] if ptype=="P" else ["G","PA","AB","H","1B","2B","3B","HR","BB","SO","R","RBI","SB","CS"])}
            face_id=int(d.get("face_id",1));hair_id=int(d.get("hair_id",1))
            if face_id not in range(1,11) or hair_id not in range(1,11):
                c.close();return self.out({"error":"INVALID_APPEARANCE"},400)
            cur=c.execute("""INSERT INTO players(user_id,name,type,primary_pos,bats,throws,xp_wallet,attributes_json,season_json,status,active,face_id,hair_id)
                             VALUES(?,?,?,?,?,?,0,?,?,'FREE_AGENT',1,?,?)""",(u["id"],name,ptype,pos,bats,throws,json.dumps(attrs),json.dumps(season),face_id,hair_id))
            c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",("PLAYER_CREATED",u["id"],json.dumps({"player_id":cur.lastrowid})));c.commit();pl=player_obj(c,cur.lastrowid);c.close();return self.out({"player":pl})
        if p=="/api/player/retire":
            u=self.auth(["PLAYER","COMMISSIONER"])
            if not u:return
            d=self.body()
            if d.get("confirm") is not True:
                return self.out({"error":"RETIREMENT_CONFIRMATION_REQUIRED"},400)
            c=conn()
            try:
                phase_row=c.execute("SELECT v FROM league_state WHERE k='phase'").fetchone()
                phase=phase_row["v"] if phase_row else "REGULAR"
                if phase!="OFFSEASON":
                    return self.out({"error":"RETIREMENT_WINDOW_CLOSED","phase":phase},400)
                pl=c.execute("SELECT * FROM players WHERE user_id=? AND active=1 ORDER BY id DESC LIMIT 1",(u["id"],)).fetchone()
                if not pl:
                    return self.out({"error":"PLAYER_NOT_FOUND"},404)
                pid=pl["id"]
                old_team=pl["franchise_id"]
                season_row=c.execute("SELECT v FROM league_state WHERE k='season'").fetchone()
                current_season=int(season_row["v"]) if season_row else 1
                c.execute(
                    """INSERT OR IGNORE INTO season_history(
                           season,player_id,franchise_id,player_type,stats_json
                       ) VALUES(?,?,?,?,?)""",
                    (current_season,pid,old_team,pl["type"],pl["season_json"] or "{}")
                )
                c.execute("DELETE FROM contracts WHERE player_id=?",(pid,))
                c.execute("UPDATE offers SET status='CANCELLED_RETIRED' WHERE player_id=? AND status IN ('OPEN','HELD')",(pid,))
                c.execute("UPDATE roster_slots SET player_id=NULL,occupant_type='OPEN' WHERE player_id=?",(pid,))
                c.execute("UPDATE players SET active=0,status='RETIRED',franchise_id=NULL WHERE id=?",(pid,))
                c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                          ("PLAYER_RETIRED",u["id"],json.dumps({"player_id":pid,"player_name":pl["name"],"franchise_id":old_team,"reason":"VOLUNTARY"})))
                enforce_active_rosters(c)
                c.commit()
                return self.out({"ok":True,"player_id":pid,"player_name":pl["name"],"status":"RETIRED"})
            finally:
                c.close()

        if p=="/api/player/spend-xp":
            u=self.auth()
            if not u:return
            attr=self.body().get("attribute");c=conn();r=c.execute("SELECT id FROM players WHERE user_id=? AND active=1",(u["id"],)).fetchone()
            if not r:c.close();return self.out({"error":"PLAYER_NOT_FOUND"},404)
            pl=player_obj(c,r["id"])
            if attr not in pl["attributes"]:c.close();return self.out({"error":"INVALID_ATTRIBUTE"},400)
            cc=development_cost(pl["attributes"][attr],pl.get("age",18))
            if pl["xp_wallet"]<cc:c.close();return self.out({"error":"INSUFFICIENT_XP","cost":cc,"age":pl.get("age",18)},400)
            old=pl["attributes"][attr];pl["attributes"][attr]+=1;pl["xp_wallet"]=round(pl["xp_wallet"]-cc,3);save_player(c,pl)
            c.execute("INSERT INTO xp_ledger(player_id,event_type,xp,detail_json) VALUES(?,?,?,?)",(pl["id"],"ATTRIBUTE_UPGRADE",-cc,json.dumps({"attribute":attr,"from":old,"to":old+1,"age":pl.get("age",18),"cost":cc})));c.commit();c.close();return self.out({"ok":True})
        if p=="/api/player/request-cpu-market":
            u=self.auth(["PLAYER","COMMISSIONER"])
            if not u:return
            c=conn();pr=c.execute("SELECT * FROM players WHERE user_id=? AND active=1",(u["id"],)).fetchone()
            if not pr or pr["status"]!="FREE_AGENT":c.close();return self.out({"error":"PLAYER_NOT_FREE_AGENT"},400)
            # CPU franchises evaluate positional need and make 3 varied, affordable offers.
            existing=c.execute("SELECT COUNT(*) n FROM offers WHERE player_id=? AND status IN ('OPEN','HELD')",(pr["id"],)).fetchone()["n"]
            if existing:c.close();return self.out({"error":"ACTIVE_OFFERS_ALREADY_EXIST"},400)
            attrs=json.loads(pr["attributes_json"]);overall=sum(attrs.values())/max(1,len(attrs))
            season=_season_number(c)
            active_ids=active_franchise_ids(c,season)
            q=",".join("?" for _ in active_ids)
            teams=[dict(x) for x in c.execute(f"SELECT * FROM franchises WHERE id IN ({q}) ORDER BY id",active_ids)]
            scored=[]
            for f in teams:
                need=R.uniform(0,12)
                roster_n=c.execute("SELECT COUNT(*) n FROM players WHERE franchise_id=? AND primary_pos=?",(f["id"],pr["primary_pos"])).fetchone()["n"]
                need+=max(0,4-roster_n)*2.5
                scored.append((need+overall*.12+R.uniform(0,4),f))
            scored.sort(key=lambda x:x[0],reverse=True)
            made=[]
            for rank,(_,f) in enumerate(scored[:3]):
                bonus=round(min(25,6+overall*.45+R.uniform(0,7)-rank),1)
                salary=SALARY_TIERS[min(4,max(0,int((overall+R.uniform(0,8))/4)))]
                years=R.choice([1,2,2,3])
                cur=c.execute("INSERT INTO offers(franchise_id,player_id,bonus,salary,years,status) VALUES(?,?,?,?,?,'OPEN')",(f["id"],pr["id"],bonus,salary,years))
                made.append({"offer_id":cur.lastrowid,"team":f["name"],"franchise_id":f["id"],"bonus":bonus,"salary":salary,"years":years})
            c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",("CPU_MARKET_OFFERS",u["id"],json.dumps({"player_id":pr["id"],"offers":made})))
            for off in made:
                notify_user(c,u["id"],"CONTRACT",f"Contract offer from {off['team']}",f"{off['bonus']:g} XP bonus • {off['salary']:g} XP/game • {off['years']} year(s)",str(off["offer_id"]))
            c.commit();c.close();return self.out({"ok":True,"offers":made})
        if p=="/api/coach/offer":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            d=self.body();pid=int(d.get("player_id",0));bonus=float(d.get("bonus",0));salary=float(d.get("salary",0));years=int(d.get("years",0))
            if bonus<0 or bonus>BONUS_CAP or salary not in SALARY_TIERS or years not in [1,2,3]:return self.out({"error":"INVALID_OFFER"},400)
            c=conn();f=c.execute("SELECT * FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            pl=c.execute("SELECT * FROM players WHERE id=?",(pid,)).fetchone()
            if not pl or pl["status"]!="FREE_AGENT":c.close();return self.out({"error":"PLAYER_NOT_FREE_AGENT"},400)
            if pl["user_id"]==u["id"]:c.close();return self.out({"error":"CANNOT_SIGN_OWN_PLAYER"},403)
            reserved=c.execute("SELECT COALESCE(SUM(bonus),0) x FROM offers WHERE franchise_id=? AND status IN ('OPEN','HELD')",(f["id"],)).fetchone()["x"]
            if bonus>f["xp_budget"]-f["xp_spent"]-reserved:c.close();return self.out({"error":"INSUFFICIENT_TEAM_XP"},400)
            cur=c.execute("INSERT INTO offers(franchise_id,player_id,bonus,salary,years,status) VALUES(?,?,?,?,?,'OPEN')",(f["id"],pid,bonus,salary,years))
            owner=c.execute("SELECT user_id,name FROM players WHERE id=?",(pid,)).fetchone()
            if owner and owner["user_id"]:
                notify_user(c,owner["user_id"],"CONTRACT",f"Contract offer from {f['name']}",f"{bonus:g} XP bonus • {salary:g} XP/game • {years} year(s)",str(cur.lastrowid))
            c.commit();oid=cur.lastrowid;c.close();return self.out({"ok":True,"offer_id":oid})
        if p=="/api/player/respond-offer":
            u=self.auth()
            if not u:return
            d=self.body();oid=int(d.get("offer_id",0));action=d.get("action")
            if action not in ["ACCEPT","HOLD","REJECT"]:return self.out({"error":"INVALID_ACTION"},400)
            c=conn();pl=c.execute(
            "SELECT id,primary_pos,type FROM players WHERE user_id=? AND active=1",
            (u["id"],)
             ).fetchone()
            if not pl:c.close();return self.out({"error":"PLAYER_NOT_FOUND"},404)
            off=c.execute("SELECT * FROM offers WHERE id=? AND player_id=?",(oid,pl["id"])).fetchone()
            if not off or off["status"] not in ["OPEN","HELD"]:c.close();return self.out({"error":"OFFER_NOT_AVAILABLE"},400)
            if action=="HOLD":
                c.execute("UPDATE offers SET status='HELD' WHERE id=?",(oid,))
                c.commit()
                c.close()
                return self.out({"ok":True,"status":"HELD"})
            elif action=="REJECT":
                c.execute("UPDATE offers SET status='REJECTED' WHERE id=?",(oid,))
                c.commit()
                c.close()
                return self.out({"ok":True,"status":"REJECTED"})
            else:
                f=c.execute(
                    "SELECT * FROM franchises WHERE id=?",
                    (off["franchise_id"],)
                ).fetchone()


                if f["xp_spent"]+off["bonus"]>f["xp_budget"]:
                    c.close()
                    return self.out({"error":"TEAM_BUDGET_CHANGED"},400)


                # Human players must take an actual roster slot.
                slot=c.execute("""
                    SELECT slot_no,player_id,occupant_type
                    FROM roster_slots
                    WHERE franchise_id=?
                      AND position_group=?
                      AND occupant_type IN ('OPEN','CPU')
                    ORDER BY
                        CASE occupant_type WHEN 'OPEN' THEN 0 ELSE 1 END,
                        slot_no
                    LIMIT 1
                """,(off["franchise_id"],pl["primary_pos"])).fetchone()


                if not slot:
                    c.close()
                    return self.out({"error":"ROSTER_POSITION_FULL"},400)


                displaced_id=slot["player_id"]


                # There are no inactive bench-hitter slots in the 16-player roster.
                # A human signing directly replaces the CPU occupying that position.
                if displaced_id:
                    c.execute("""
                        UPDATE players
                        SET franchise_id=NULL,status='FREE_AGENT'
                        WHERE id=?
                    """,(displaced_id,))


                # Human now owns the proper roster position.
                c.execute("""
                    UPDATE roster_slots
                    SET player_id=?,occupant_type='HUMAN'
                    WHERE franchise_id=? AND slot_no=?
                """,(pl["id"],off["franchise_id"],slot["slot_no"]))


                # Keep saved batting order / rotation synchronized.
                lr=c.execute(
                    "SELECT batting_order_json,rotation_json FROM lineups WHERE franchise_id=?",
                    (off["franchise_id"],)
                ).fetchone()


                if lr and displaced_id:
                    if pl["type"]=="H":
                        order=json.loads(lr["batting_order_json"])


                        if displaced_id in order:
                            order=[
                                pl["id"] if pid==displaced_id else pid
                                for pid in order
                            ]


                        c.execute(
                            "UPDATE lineups SET batting_order_json=? WHERE franchise_id=?",
                            (json.dumps(order),off["franchise_id"])
                        )


                    elif pl["primary_pos"]=="SP":
                        rotation=json.loads(lr["rotation_json"])


                        if displaced_id in rotation:
                            rotation=[
                                pl["id"] if pid==displaced_id else pid
                                for pid in rotation
                            ]


                        c.execute(
                            "UPDATE lineups SET rotation_json=? WHERE franchise_id=?",
                            (json.dumps(rotation),off["franchise_id"])
                        )


                c.execute(
                    "UPDATE offers SET status='ACCEPTED' WHERE id=?",
                    (oid,)
                )


                c.execute("""
                    UPDATE offers
                    SET status='CANCELLED_PLAYER_SIGNED'
                    WHERE player_id=? AND id<>?
                      AND status IN ('OPEN','HELD')
                """,(pl["id"],oid))


                c.execute("""
                    INSERT INTO contracts(
                        player_id,franchise_id,bonus,salary,years_remaining
                    )
                    VALUES(?,?,?,?,?)
                """,(
                    pl["id"],
                    off["franchise_id"],
                    off["bonus"],
                    off["salary"],
                    off["years"]
                ))


                c.execute("""
                    UPDATE players
                    SET franchise_id=?,
                        status='SIGNED',
                        xp_wallet=xp_wallet+?
                    WHERE id=?
                """,(
                    off["franchise_id"],
                    off["bonus"],
                    pl["id"]
                ))


                c.execute("""
                    UPDATE franchises
                    SET xp_spent=xp_spent+?
                    WHERE id=?
                """,(off["bonus"],off["franchise_id"]))
                c.commit()
                c.close()
                return self.out({"ok":True})
            
        if p=="/api/notifications/read":
            u=self.auth()
            if not u:return
            d=self.body();c=conn()
            nid=d.get("id")
            if nid:
                c.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?",(int(nid),u["id"]))
            else:
                c.execute("UPDATE notifications SET is_read=1 WHERE user_id=?",(u["id"],))
            c.commit();c.close();return self.out({"ok":True})

        if p=="/api/coach/franchise-upgrade":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            kind=str(self.body().get("kind","")).lower()
            cols={"training":"training_level","stadium":"stadium_level","scouting":"scouting_level","performance":"performance_level","hq":"hq_level"}
            if kind not in cols:return self.out({"error":"INVALID_UPGRADE"},400)
            c=conn();fr=c.execute("SELECT * FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not fr:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            level=int(fr[cols[kind]] or 0)
            if level>=4:c.close();return self.out({"error":"MAX_LEVEL"},400)
            cost=upgrade_cost(level)
            if float(fr["xp_reserve"] or 0)<cost:c.close();return self.out({"error":"INSUFFICIENT_RESERVE","cost":cost},400)
            c.execute(f"UPDATE franchises SET {cols[kind]}={cols[kind]}+1,xp_reserve=xp_reserve-? WHERE id=?",(cost,fr["id"]))
            fr2=dict(c.execute("SELECT * FROM franchises WHERE id=?",(fr["id"],)).fetchone())
            c.execute("UPDATE franchises SET xp_budget=? WHERE id=?",(annual_team_budget(fr2),fr["id"]))
            c.commit();c.close();return self.out({"ok":True,"kind":kind,"level":level+1,"cost":cost})

        if p=="/api/coach/set-strategy":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            d=self.body();c=conn();f=c.execute("SELECT id FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            fid=f["id"];bullpen=d.get("bullpen",{});defense=d.get("defense",{});bench=d.get("bench",{});subs=d.get("substitutions",{})
            roster={x["id"]:dict(x) for x in c.execute("SELECT id,type,primary_pos FROM players WHERE franchise_id=? AND active=1",(fid,))}
            # validate bullpen role assignments
            ids=[]
            for k in ["CL","SU1","SU2"]:
                v=bullpen.get(k)
                if v is not None: ids.append(int(v))
            for k in ["MR","LR","EMERGENCY"]:
                ids += [int(x) for x in bullpen.get(k,[])]
            if len(ids)!=len(set(ids)) or any(i not in roster or roster[i]["type"]!="P" for i in ids):
                c.close();return self.out({"error":"INVALID_BULLPEN"},400)
            # depth chart may contain repeated players across positions, but each listed id must be a hitter on roster.
            for pos,lst in (bench or {}).items():
                for x in lst:
                    i=int(x)
                    if i not in roster or roster[i]["type"]!="H":
                        c.close();return self.out({"error":"INVALID_DEPTH_CHART"},400)
            for key in ["pinch_hit","pinch_run","def_replacement"]:
                for x in subs.get(key,[]):
                    i=int(x)
                    if i not in roster or roster[i]["type"]!="H":
                        c.close();return self.out({"error":"INVALID_SUBSTITUTION_LIST"},400)
            cb=subs.get("catcher_backup")
            if cb is not None and (int(cb) not in roster or roster[int(cb)]["type"]!="H"):
                c.close();return self.out({"error":"INVALID_CATCHER_BACKUP"},400)
            allowed={"STANDARD","PULL","OPPO","NO_DOUBLES","BUNT_DEFENSE","INFIELD_IN"}
            for k in ["default_shift","vs_lhb","vs_rhb"]:
                if defense.get(k,"STANDARD") not in allowed:
                    c.close();return self.out({"error":"INVALID_DEFENSE"},400)
            if subs.get("pinch_hit_threshold","MEDIUM") not in {"CONSERVATIVE","MEDIUM","AGGRESSIVE"}:
                c.close();return self.out({"error":"INVALID_PINCH_HIT_THRESHOLD"},400)
            if subs.get("steal_aggression","NORMAL") not in {"LOW","NORMAL","HIGH"}:
                c.close();return self.out({"error":"INVALID_STEAL_AGGRESSION"},400)
            if subs.get("bunt_aggression","NORMAL") not in {"LOW","NORMAL","HIGH"}:
                c.close();return self.out({"error":"INVALID_BUNT_AGGRESSION"},400)
            inning=int(subs.get("late_inning_defense_inning",8))
            if inning<6 or inning>9:
                c.close();return self.out({"error":"INVALID_LATE_INNING"},400)
            c.execute("UPDATE team_strategy SET bullpen_json=?,defense_json=?,bench_json=?,substitutions_json=?,updated_at=CURRENT_TIMESTAMP WHERE franchise_id=?",
                      (json.dumps(bullpen),json.dumps(defense),json.dumps(bench),json.dumps(subs),fid))
            c.commit();c.close();return self.out({"ok":True})
        if p=="/api/coach/cancel-offer":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            oid=int(self.body().get("offer_id",0));c=conn();f=c.execute("SELECT id FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            r=c.execute("UPDATE offers SET status='CANCELLED_COACH' WHERE id=? AND franchise_id=? AND status IN ('OPEN','HELD')",(oid,f["id"]))
            c.commit();c.close();return self.out({"ok":r.rowcount==1})
        if p=="/api/coach/branding":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            d=self.body();c=conn();f=c.execute("SELECT id FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            name=str(d.get("display_name","")).strip()
            if not (3<=len(name)<=40):c.close();return self.out({"error":"INVALID_TEAM_NAME"},400)
            logo_style=int(d.get("logo_style",1))
            if logo_style not in range(1,11):c.close();return self.out({"error":"INVALID_LOGO_STYLE"},400)
            pc,sc,ac=d.get("primary_color"),d.get("secondary_color"),d.get("accent_color")
            if not all(valid_hex_color(x) for x in [pc,sc,ac]):c.close();return self.out({"error":"INVALID_COLORS"},400)
            home=str(d.get("uniform_home","WHITE")).upper();away=str(d.get("uniform_away","NAVY")).upper()
            allowed={"WHITE","NAVY","RED","GRAY","BLACK","CREAM"}
            if home not in allowed or away not in allowed:c.close();return self.out({"error":"INVALID_UNIFORM"},400)
            c.execute("""INSERT OR REPLACE INTO franchise_branding(franchise_id,display_name,logo_style,primary_color,secondary_color,accent_color,uniform_home,uniform_away,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",(f["id"],name,logo_style,pc,sc,ac,home,away))
            c.execute("UPDATE franchises SET name=? WHERE id=?",(name,f["id"]))
            c.commit();c.close();return self.out({"ok":True})
        if p=="/api/coach/set-lineup":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            ids=self.body().get("batting_order",[])
            if len(ids)!=9 or len(set(ids))!=9:return self.out({"error":"INVALID_LINEUP"},400)
            c=conn();f=c.execute("SELECT id FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            valid={x["id"] for x in c.execute("SELECT id FROM players WHERE franchise_id=? AND type='H' AND active=1",(f["id"],))}
            if any(i not in valid for i in ids):c.close();return self.out({"error":"PLAYER_NOT_ON_ROSTER"},400)
            c.execute("UPDATE lineups SET batting_order_json=? WHERE franchise_id=?",(json.dumps(ids),f["id"]));c.commit();c.close();return self.out({"ok":True})
        if p=="/api/coach/set-rotation":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            ids=self.body().get("rotation",[])
            if len(ids)!=5 or len(set(ids))!=5:return self.out({"error":"INVALID_ROTATION"},400)
            c=conn();f=c.execute("SELECT id FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            valid={x["id"] for x in c.execute("SELECT id FROM players WHERE franchise_id=? AND type='P' AND primary_pos='SP' AND active=1",(f["id"],))}
            if any(i not in valid for i in ids):c.close();return self.out({"error":"STARTER_NOT_ON_ROSTER"},400)
            c.execute("UPDATE lineups SET rotation_json=? WHERE franchise_id=?",(json.dumps(ids),f["id"]));c.commit();c.close();return self.out({"ok":True})
        if p=="/api/chat/send":
            u=self.auth()
            if not u:return
            d=self.body();channel=str(d.get("channel","")).upper();msg=str(d.get("message","")).strip()
            if channel not in ("EBL","TEAM"):return self.out({"error":"INVALID_CHANNEL"},400)
            if not msg or len(msg)>300:return self.out({"error":"INVALID_MESSAGE"},400)
            rlc=conn();sec=user_restricted(rlc,u["id"])
            if sec["muted"]:rlc.close();return self.out({"error":"ACCOUNT_MUTED"},403)
            if not rate_limit(rlc,f"chat:{u['id']}",12,60):rlc.commit();rlc.close();return self.out({"error":"RATE_LIMITED"},429)
            rlc.commit();rlc.close()
            c=conn();team_id=None
            if channel=="TEAM":
                pr=c.execute("SELECT franchise_id FROM players WHERE user_id=? AND active=1 ORDER BY id DESC LIMIT 1",(u["id"],)).fetchone()
                team_id=pr["franchise_id"] if pr else None
                if not team_id:c.close();return self.out({"error":"NO_TEAM"},400)
            # simple anti-spam: max 1 message per second/account
            recent=c.execute("SELECT created_at FROM chat_messages WHERE user_id=? ORDER BY id DESC LIMIT 1",(u["id"],)).fetchone()
            c.execute("INSERT INTO chat_messages(user_id,channel,team_id,message) VALUES(?,?,?,?)",(u["id"],channel,team_id,msg))
            c.commit();c.close();return self.out({"ok":True})
        if p=="/api/friends/request":
            u=self.auth()
            if not u:return
            d=self.body()
            try:other=int(d.get("user_id",0))
            except:return self.out({"error":"INVALID_USER"},400)
            if other<=0 or other==u["id"]:return self.out({"error":"INVALID_USER"},400)
            c=conn()
            if not c.execute("SELECT 1 FROM users WHERE id=?",(other,)).fetchone():
                c.close();return self.out({"error":"USER_NOT_FOUND"},404)
            if c.execute("""SELECT 1 FROM user_blocks WHERE
                         (blocker_user_id=? AND blocked_user_id=?) OR
                         (blocker_user_id=? AND blocked_user_id=?)""",(u["id"],other,other,u["id"])).fetchone():
                c.close();return self.out({"error":"FRIEND_REQUEST_UNAVAILABLE"},403)
            reverse=c.execute(
                "SELECT id,status FROM friendships WHERE requester_user_id=? AND addressee_user_id=?",
                (other,u["id"])
            ).fetchone()
            if reverse:
                if reverse["status"]=="PENDING":
                    c.execute("UPDATE friendships SET status='ACCEPTED',updated_at=CURRENT_TIMESTAMP WHERE id=?",(reverse["id"],))
                    c.commit();c.close();return self.out({"ok":True,"status":"ACCEPTED"})
                c.close();return self.out({"ok":True,"status":"ACCEPTED"})
            existing=c.execute(
                "SELECT id,status FROM friendships WHERE requester_user_id=? AND addressee_user_id=?",
                (u["id"],other)
            ).fetchone()
            if existing:
                c.close();return self.out({"ok":True,"status":existing["status"]})
            c.execute("INSERT INTO friendships(requester_user_id,addressee_user_id) VALUES(?,?)",(u["id"],other))
            notify_user(c,other,"FRIEND",f"Friend request from {u['username']}","Open Community to accept or view their profile.",str(u["id"]))
            c.commit();c.close();return self.out({"ok":True,"status":"PENDING"})


        if p=="/api/friends/accept":
            u=self.auth()
            if not u:return
            d=self.body()
            try:other=int(d.get("user_id",0))
            except:return self.out({"error":"INVALID_USER"},400)
            c=conn()
            cur=c.execute(
                """UPDATE friendships SET status='ACCEPTED',updated_at=CURRENT_TIMESTAMP
                   WHERE requester_user_id=? AND addressee_user_id=? AND status='PENDING'""",
                (other,u["id"])
            )
            if cur.rowcount!=1:
                c.close();return self.out({"error":"FRIEND_REQUEST_NOT_FOUND"},404)
            notify_user(c,other,"FRIEND",f"{u['username']} accepted your friend request","You are now EBL friends.",str(u["id"]))
            c.commit();c.close();return self.out({"ok":True,"status":"ACCEPTED"})


        if p=="/api/friends/remove":
            u=self.auth()
            if not u:return
            d=self.body()
            try:other=int(d.get("user_id",0))
            except:return self.out({"error":"INVALID_USER"},400)
            c=conn()
            c.execute(
                """DELETE FROM friendships WHERE
                   (requester_user_id=? AND addressee_user_id=?) OR
                   (requester_user_id=? AND addressee_user_id=?)""",
                (u["id"],other,other,u["id"])
            )
            c.commit();c.close();return self.out({"ok":True})


        if p=="/api/dm/send":
            u=self.auth()
            if not u:return
            d=self.body()
            try:other=int(d.get("recipient_user_id",0))
            except:return self.out({"error":"INVALID_RECIPIENT"},400)
            msg=str(d.get("message","")).strip()
            if other<=0 or other==u["id"]:return self.out({"error":"INVALID_RECIPIENT"},400)
            if not msg or len(msg)>500:return self.out({"error":"INVALID_MESSAGE"},400)
            rlc=conn();sec=user_restricted(rlc,u["id"])
            if sec["muted"]:rlc.close();return self.out({"error":"ACCOUNT_MUTED"},403)
            if not rate_limit(rlc,f"dm:{u['id']}",20,60):rlc.commit();rlc.close();return self.out({"error":"RATE_LIMITED"},429)
            rlc.commit();rlc.close()
            c=conn()
            if not c.execute("SELECT 1 FROM users WHERE id=?",(other,)).fetchone():
                c.close();return self.out({"error":"USER_NOT_FOUND"},404)
            cur=c.execute("INSERT INTO direct_messages(sender_user_id,recipient_user_id,message) VALUES(?,?,?)",(u["id"],other,msg))
            notify_user(c,other,"DM",f"New message from {u['username']}",msg[:120],str(u["id"]))
            c.commit();c.close();return self.out({"ok":True,"message_id":cur.lastrowid})
        if p=="/api/commish/activate":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn();r=roster_readiness(c)
            if not r["ready"]:c.close();return self.out({"error":"ROSTERS_NOT_FULL","readiness":r},409)
            set_league_cfg(c,"phase","ACTIVE");audit(c,"LEAGUE_ACTIVATED",f"Season {league_cfg(c,'season_number','1')} activated with {r['human']} human and {r['cpu']} CPU roster slots.")
            c.commit();c.close();return self.out({"ok":True,"phase":"ACTIVE"})
        if p=="/api/commish/cpu-fill":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            d=self.body();enabled=bool(d.get("enabled",True));c=conn()
            set_league_cfg(c,"alpha_cpu_fill","1" if enabled else "0");audit(c,"CPU_FILL_CHANGED",f"enabled={enabled}")
            c.commit();c.close();return self.out({"ok":True,"enabled":enabled})
        if p=="/api/safety/block":
            u=self.auth()
            if not u:return
            d=self.body()
            try:other=int(d.get("user_id",0))
            except:return self.out({"error":"INVALID_USER"},400)
            if other<=0 or other==u["id"]:return self.out({"error":"INVALID_USER"},400)
            c=conn();c.execute("INSERT OR IGNORE INTO user_blocks(blocker_user_id,blocked_user_id) VALUES(?,?)",(u["id"],other));c.commit();c.close();return self.out({"ok":True})
        if p=="/api/safety/report":
            u=self.auth()
            if not u:return
            d=self.body();reason=str(d.get("reason","OTHER"))[:40];detail=str(d.get("detail","")).strip()[:500]
            try:other=int(d.get("user_id",0)) if d.get("user_id") else None
            except:return self.out({"error":"INVALID_USER"},400)
            try:mid=int(d.get("message_id",0)) if d.get("message_id") else None
            except:return self.out({"error":"INVALID_MESSAGE"},400)
            c=conn();c.execute("""INSERT INTO user_reports(reporter_user_id,reported_user_id,message_id,channel,reason,detail)
                                  VALUES(?,?,?,?,?,?)""",(u["id"],other,mid,str(d.get("channel",""))[:20],reason,detail))
            c.commit();c.close();return self.out({"ok":True})
        if p=="/api/commish/moderate":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            d=self.body()
            try:target=int(d.get("user_id",0))
            except:return self.out({"error":"INVALID_USER"},400)
            action=str(d.get("action","")).upper();reason=str(d.get("reason",""))[:500]
            minutes=int(d.get("minutes",0) or 0);expires=(utcnow()+datetime.timedelta(minutes=minutes)).isoformat() if minutes>0 else None
            if action not in {"MUTE","SUSPEND","UNMUTE","UNSUSPEND"}:return self.out({"error":"INVALID_ACTION"},400)
            c=conn()
            if action=="MUTE":c.execute("INSERT OR IGNORE INTO user_security(user_id) VALUES(?)",(target,));c.execute("UPDATE user_security SET muted_until=? WHERE user_id=?",(expires,target))
            elif action=="SUSPEND":c.execute("INSERT OR IGNORE INTO user_security(user_id) VALUES(?)",(target,));c.execute("UPDATE user_security SET suspended_until=? WHERE user_id=?",(expires,target));c.execute("DELETE FROM persistent_sessions WHERE user_id=?",(target,))
            elif action=="UNMUTE":c.execute("UPDATE user_security SET muted_until=NULL WHERE user_id=?",(target,))
            elif action=="UNSUSPEND":c.execute("UPDATE user_security SET suspended_until=NULL WHERE user_id=?",(target,))
            c.execute("INSERT INTO moderation_actions(moderator_user_id,target_user_id,action,reason,expires_at) VALUES(?,?,?,?,?)",(u["id"],target,action,reason,expires))
            c.commit();c.close();return self.out({"ok":True})
        if p=="/api/commish/resolve-report":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            d=self.body()
            try:rid=int(d.get("report_id",0))
            except:return self.out({"error":"INVALID_REPORT"},400)
            resolution=str(d.get("resolution",""))[:500];c=conn()
            c.execute("""UPDATE user_reports SET status='RESOLVED',resolution=?,resolved_by=?,resolved_at=CURRENT_TIMESTAMP WHERE id=?""",(resolution,u["id"],rid))
            c.commit();c.close();return self.out({"ok":True})
        if p=="/api/commish/optimize-storage":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn()
            try:
                season=int(c.execute("SELECT v FROM league_state WHERE k='season'").fetchone()["v"])
                day=int(c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()["v"])
            finally:c.close()
            result=run_storage_maintenance(season,day,aggressive=True)
            return self.out({"ok":True,**result})
        if p=="/api/commish/backup-now":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            dst=perform_backup(DB,os.environ.get("EBL_BACKUP_DIR",os.path.join(ROOT,"backups")))
            c=conn();c.execute("INSERT INTO backup_audit(path,bytes) VALUES(?,?)",(str(dst),dst.stat().st_size));c.commit();c.close()
            return self.out({"ok":True,"path":str(dst)})
        if p=="/api/commish/season-membership":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            d=self.body()
            active_ids=d.get("active_franchise_ids") or []
            c=conn()
            try:
                phase_row=c.execute("SELECT v FROM league_state WHERE k='phase'").fetchone()
                phase=phase_row["v"] if phase_row else "REGULAR"
                if phase!="OFFSEASON":
                    return self.out({"error":"EXPANSION_WINDOW_CLOSED","phase":phase},400)
                current=_season_number(c)
                next_season=current+1
                if c.execute("SELECT 1 FROM games WHERE season=? LIMIT 1",(next_season,)).fetchone():
                    return self.out({"error":"NEXT_SEASON_ALREADY_SCHEDULED","season":next_season},409)
                try:
                    set_season_membership(c,next_season,active_ids)
                except ValueError as e:
                    return self.out({"error":str(e)},400)
                c.execute(
                    "INSERT INTO commissioner_audit(league_day,action,detail) VALUES(?,?,?)",
                    (int(c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()["v"]),
                     "SET_NEXT_SEASON_MEMBERSHIP",
                     json.dumps({"season":next_season,"active_franchise_ids":active_ids}))
                )
                c.commit()
                return self.out({
                    "ok":True,
                    "season":next_season,
                    "active_team_count":len(active_ids),
                    "active_franchise_ids":active_ids
                })
            finally:
                c.close()

        if p=="/api/commish/playoff-debug":
            u=self.auth(["COMMISSIONER"])
            if not u:return


            c=conn()


            season=int(c.execute(
                "SELECT v FROM league_state WHERE k='season'"
            ).fetchone()["v"])


            state={
                x["k"]:x["v"]
                for x in c.execute(
                    "SELECT k,v FROM league_state WHERE k IN ('season','league_day','phase','playoff_round','champion')"
                )
            }


            games=[dict(x) for x in c.execute(
                """
                SELECT id,season,league_day,away_id,home_id,
                       away_runs,home_runs,status
                FROM games
                WHERE season=?
                  AND league_day>81
                ORDER BY league_day,id
                """,
                (season,)
            )]


            c.close()


            return self.out({
                "ok":True,
                "state":state,
                "games":games
            })
        if p=="/api/commish/sim-day":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn();day=int(c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()["v"])+1
            if day>81:
                season=int(c.execute(
                    "SELECT v FROM league_state WHERE k='season'"
                ).fetchone()["v"])


                phase_row=c.execute(
                    "SELECT v FROM league_state WHERE k='phase'"
                ).fetchone()


                phase=phase_row["v"] if phase_row else "REGULAR"


                # -------------------------------------------------
                # CREATE PLAYOFF FIELD
                # -------------------------------------------------


                if phase=="REGULAR":
                    seeds=playoff_teams(c)


                    if len(seeds)!=8:
                        c.close()
                        return self.out({"error":"PLAYOFF_SEEDING_FAILED"},500)


                    matchups=[
                        ("QF1",seeds[0],seeds[7]),
                        ("QF2",seeds[3],seeds[4]),
                        ("QF3",seeds[1],seeds[6]),
                        ("QF4",seeds[2],seeds[5])
                    ]


                    for code,high,low in matchups:
                        schedule_series_game(
                            c,season,code,1,82,
                            high["id"],low["id"]
                        )


                    c.execute(
                        "UPDATE league_state SET v='PLAYOFFS' WHERE k='phase'"
                    )


                    c.execute(
                        "UPDATE league_state SET v='QUARTERFINALS' WHERE k='playoff_round'"
                    )


                    c.commit()
                    c.close()


                    return self.out({
                        "ok":True,
                        "day":81,
                        "results":[],
                        "phase":"PLAYOFFS",
                        "round":"QUARTERFINALS",
                        "message":"PLAYOFFS_CREATED"
                    })


                # -------------------------------------------------
                # SIMULATE PLAYOFF DAY
                # -------------------------------------------------


                if phase=="PLAYOFFS":
                    next_row=c.execute(
                       """
                        SELECT MIN(league_day) AS next_day
                        FROM games
                        WHERE season=?
                         AND league_day>81
                          AND status='SCHEDULED'
                        """,
                        (season,)
                    ).fetchone()


                    if not next_row or next_row["next_day"] is None:
                        c.close()
                        return self.out({"error":"NO_PLAYOFF_GAMES_SCHEDULED"},400)


                    # Always simulate the earliest unfinished playoff day.
                    # This also repairs a league_day counter that got ahead.
                    day=int(next_row["next_day"])


                    games=[dict(x) for x in c.execute(
                        """
                        SELECT *
                        FROM games
                        WHERE season=?
                          AND league_day=?
                          AND status='SCHEDULED'
                        ORDER BY id
                        """,
                        (season,day)
                    )]


                    results=[]


                    for g in games:
                        result=simulate_game(c,g)
                        results.append(result)


                        # Persist each playoff game immediately.
                        c.commit()


                        # Verify the game actually saved as FINAL.
                        saved=c.execute(
                            """
                            SELECT status,away_runs,home_runs
                            FROM games
                            WHERE id=?
                            """,
                            (g["id"],)
                        ).fetchone()


                        if not saved or saved["status"]!="FINAL":
                            c.close()
                            return self.out({
                                "error":"PLAYOFF_GAME_NOT_SAVED",
                                "game_id":g["id"]
                            },500)


                    round_row=c.execute(
                        "SELECT v FROM league_state WHERE k='playoff_round'"
                    ).fetchone()


                    playoff_round=round_row["v"] if round_row else "QUARTERFINALS"


                    # ---------------------------------------------
                    # QUARTERFINALS - BEST OF 3
                    # ---------------------------------------------


                    if playoff_round=="QUARTERFINALS":
                        codes=["QF1","QF2","QF3","QF4"]
                        winners=[]
                        unfinished=[]


                        for code in codes:
                            winner=playoff_series_winner(c,season,code,2)


                            if winner:
                                winners.append(winner)
                            else:
                                unfinished.append(code)


                        if len(winners)==4:
                            schedule_series_game(
                                c,season,"SF1",1,day+1,
                                winners[0],winners[1]
                            )


                            schedule_series_game(
                                c,season,"SF2",1,day+1,
                                winners[2],winners[3]
                            )


                            c.execute(
                                "UPDATE league_state SET v='SEMIFINALS' WHERE k='playoff_round'"
                            )


                        else:
                            for code in unfinished:
                                sg=playoff_series_games(c,season,code)


                                finals=[x for x in sg if x["status"]=="FINAL"]
                                scheduled=[x for x in sg if x["status"]=="SCHEDULED"]


                                if not scheduled and len(finals)<3:
                                    first=sg[0]
                                    game_no=len(finals)+1


                                    high=first["home_id"]
                                    low=first["away_id"]


                                    schedule_series_game(
                                        c,season,code,game_no,day+1,
                                        high,low
                                    )


                    # ---------------------------------------------
                    # SEMIFINALS - BEST OF 5
                    # ---------------------------------------------


                    elif playoff_round=="SEMIFINALS":
                        codes=["SF1","SF2"]
                        winners=[]
                        unfinished=[]


                        for code in codes:
                            winner=playoff_series_winner(c,season,code,3)


                            if winner:
                                winners.append(winner)
                            else:
                                unfinished.append(code)


                        if len(winners)==2:
                            schedule_series_game(
                                c,season,"CH",1,day+1,
                                winners[0],winners[1]
                            )


                            c.execute(
                                "UPDATE league_state SET v='CHAMPIONSHIP' WHERE k='playoff_round'"
                            )


                        else:
                            for code in unfinished:
                                sg=playoff_series_games(c,season,code)


                                finals=[x for x in sg if x["status"]=="FINAL"]
                                scheduled=[x for x in sg if x["status"]=="SCHEDULED"]


                                if not scheduled and len(finals)<5:
                                    first=sg[0]
                                    game_no=len(finals)+1


                                    high=first["home_id"]
                                    low=first["away_id"]


                                    schedule_series_game(
                                        c,season,code,game_no,day+1,
                                        high,low
                                    )


                    # ---------------------------------------------
                    # EBL CHAMPIONSHIP - BEST OF 7
                    # ---------------------------------------------


                    elif playoff_round=="CHAMPIONSHIP":
                        winner=playoff_series_winner(c,season,"CH",4)


                        if winner:
                            c.execute(
                                "UPDATE league_state SET v='OFFSEASON' WHERE k='phase'"
                            )
                            c.execute(
                                "UPDATE league_state SET v=? WHERE k='champion'",
                                (winner,)
                            )
                            c.execute(
                                "UPDATE league_state SET v='COMPLETE' WHERE k='playoff_round'"
                            )
                            record_championship(c,season,winner,day)


                        else:
                            sg=playoff_series_games(c,season,"CH")
                            finals=[x for x in sg if x["status"]=="FINAL"]
                            scheduled=[x for x in sg if x["status"]=="SCHEDULED"]


                            if not scheduled and len(finals)<7:
                                first=sg[0]
                                game_no=len(finals)+1


                                high=first["home_id"]
                                low=first["away_id"]


                                schedule_series_game(
                                    c,season,"CH",game_no,day+1,
                                    high,low
                                )


                    c.execute(
                        "UPDATE league_state SET v=? WHERE k='league_day'",
                        (str(day),)
                    )


                    c.commit()
                    c.close()


                    return self.out({
                        "ok":True,
                        "day":day,
                        "results":results,
                        "phase":"PLAYOFFS"
                    })


                if phase=="OFFSEASON":
                    c.close()
                    return self.out({
                        "error":"SEASON_COMPLETE"
                    },400)
            season=int(c.execute("SELECT v FROM league_state WHERE k='season'").fetchone()["v"])
            games=[dict(x) for x in c.execute(
                "SELECT * FROM games WHERE season=? AND league_day=? AND status='SCHEDULED' ORDER BY id",
                (season,day)
            )]
            if not games:
                c.close()
                return self.out({"error":"NO_GAMES_SCHEDULED","season":season,"day":day},400)
            # Notify human players that their club is taking the field.
            for g in games:
                for fid in (g["away_id"],g["home_id"]):
                    for ur in c.execute("SELECT DISTINCT user_id FROM players WHERE franchise_id=? AND active=1 AND user_id IS NOT NULL",(fid,)).fetchall():
                        notify_user(c,ur["user_id"],"GAME",f"Game Day: {team_name(c,g['away_id'])} @ {team_name(c,g['home_id'])}",f"League Day {day}",g["id"])
            results=[simulate_game(c,g) for g in games]
            process_quarter_awards(c,season,day)
            if day==81:
                process_season_awards(c,season)
            c.execute("UPDATE league_state SET v=? WHERE k='league_day'",(str(day),))
            c.commit();c.close()
            try:
                run_storage_maintenance(season,day,aggressive=False)
            except Exception:
                pass
            if day%7==0:
                try:
                    dst=perform_backup(DB,os.environ.get("EBL_BACKUP_DIR",os.path.join(ROOT,"backups")))
                    bc=conn()
                    bc.execute("INSERT INTO backup_audit(path,bytes) VALUES(?,?)",(str(dst),dst.stat().st_size))
                    bc.commit()
                    bc.close()
                except Exception:
                    pass


            return self.out({"ok":True,"day":day,"results":results})
          
    
                
                        


        if p=="/api/commish/reset-league":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn()
            try:
                # Genesis reset: return the closed-alpha league to Season 1, Day 0.
                # Accounts, player identity/attributes, friendships and contracts stay intact.
                # Earned XP, XP ledger history and temporary public/team chat are reset.
                c.execute("DELETE FROM games")
                c.execute("DELETE FROM season_history")
                c.execute("DELETE FROM season_champions")
                c.execute("DELETE FROM franchise_season_history")
                c.execute("DELETE FROM player_championships")
                c.execute("DELETE FROM award_history")
                c.execute("DELETE FROM rivalries")
                c.execute("DELETE FROM league_records")
                c.execute("DELETE FROM news")
                c.execute("DELETE FROM xp_ledger")
                c.execute("DELETE FROM chat_messages")
                c.execute("DELETE FROM notifications WHERE type IN ('GAME','AWARD')")

                c.execute("UPDATE players SET xp_wallet=0")
                c.execute("UPDATE franchises SET wins=0,losses=0,runs_for=0,runs_against=0,xp_spent=0")
                enforce_active_rosters(c)

                # Reset every club to its infrastructure-adjusted annual XP pool.
                for fr in c.execute("SELECT * FROM franchises").fetchall():
                    c.execute("UPDATE franchises SET xp_budget=? WHERE id=?",(annual_team_budget(dict(fr)),fr["id"]))

                # Clear current-season stat lines without touching career identity or progression.
                players=c.execute("SELECT id,type FROM players").fetchall()
                for pl in players:
                    if pl["type"]=="H":
                        stats={"G":0,"PA":0,"AB":0,"H":0,"1B":0,"2B":0,"3B":0,"HR":0,"BB":0,"SO":0,"R":0,"RBI":0,"SB":0,"CS":0}
                    else:
                        stats={"G":0,"GS":0,"OUTS":0,"H":0,"ER":0,"BB":0,"SO":0,"W":0,"L":0,"SV":0}
                    c.execute("UPDATE players SET season_json=? WHERE id=?",(json.dumps(stats),pl["id"]))

                # Build a completely clean Season 1 schedule using the
                # configured active franchise pool (minimum eight).
                if not c.execute("SELECT 1 FROM franchise_seasons WHERE season=1 LIMIT 1").fetchone():
                    set_season_membership(
                        c,1,[r["id"] for r in c.execute(
                            "SELECT id FROM franchises ORDER BY id LIMIT ?",
                            (MIN_ACTIVE_TEAMS,)
                        ).fetchall()]
                    )
                generate_season_schedule(c,1)

                for key,value in (("season","1"),("league_day","0"),("phase","REGULAR"),("playoff_round",""),("champion","")):
                    c.execute(
                        "INSERT INTO league_state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                        (key,value)
                    )
                c.execute(
                    "INSERT INTO league_config(k,v) VALUES('season_number','1') ON CONFLICT(k) DO UPDATE SET v='1'"
                )

                c.commit()
                return self.out({
                    "ok":True,
                    "season":1,
                    "day":0,
                    "phase":"REGULAR",
                    "games_created":c.execute("SELECT COUNT(*) n FROM games WHERE season=1").fetchone()["n"],
                    "rivalries_reset":True,
                    "history_reset":True
                })
            finally:
                c.close()


        if p=="/api/commish/next-season":
            u=self.auth(["COMMISSIONER"])
            if not u:
                return

            c=conn()
            try:
                season_row=c.execute("SELECT v FROM league_state WHERE k='season'").fetchone()
                phase_row=c.execute("SELECT v FROM league_state WHERE k='phase'").fetchone()
                champion_row=c.execute("SELECT v FROM league_state WHERE k='champion'").fetchone()
                current_season=int(season_row["v"]) if season_row else 1
                phase=phase_row["v"] if phase_row else "REGULAR"
                champion=champion_row["v"] if champion_row else ""
                if phase!="OFFSEASON":
                    return self.out({"error":"SEASON_NOT_COMPLETE","phase":phase},400)

                next_season=current_season+1
                summary={"contracts_expired":0,"contracts_advanced":0,"retired":0,"retired_names":[],"free_agents":[],"offers_expired":0,"rosters_rebuilt":False}

                # Active players are archived here. Voluntary offseason retirees
                # are archived by /api/player/retire at retirement time.
                players=c.execute("SELECT id,user_id,franchise_id,name,type,season_json,age,active FROM players WHERE active=1").fetchall()
                for pl in players:
                    c.execute("""INSERT OR IGNORE INTO season_history(season,player_id,franchise_id,player_type,stats_json)
                                 VALUES(?,?,?,?,?)""",
                              (current_season,pl["id"],pl["franchise_id"],pl["type"],pl["season_json"] or "{}"))

                if champion:
                    c.execute("INSERT OR REPLACE INTO season_champions(season,franchise_id) VALUES(?,?)",(current_season,champion))

                current_active=active_franchise_ids(c,current_season)
                q_active=",".join("?" for _ in current_active)
                for fr in c.execute(
                    f"SELECT id,wins,losses,runs_for,runs_against FROM franchises WHERE id IN ({q_active})",
                    current_active
                ).fetchall():
                    finish="CHAMPION" if champion and fr["id"]==champion else None
                    c.execute("""INSERT OR REPLACE INTO franchise_season_history(
                                   season,franchise_id,wins,losses,runs_for,runs_against,playoff_finish,champion
                               ) VALUES(?,?,?,?,?,?,?,?)""",
                              (current_season,fr["id"],fr["wins"],fr["losses"],fr["runs_for"],fr["runs_against"],finish,1 if finish else 0))

                expiring_offers=c.execute("SELECT COUNT(*) n FROM offers WHERE status IN ('OPEN','HELD')").fetchone()["n"]
                if expiring_offers:
                    c.execute("UPDATE offers SET status='EXPIRED_OFFSEASON' WHERE status IN ('OPEN','HELD')")
                summary["offers_expired"]=expiring_offers

                contracts=c.execute("SELECT * FROM contracts ORDER BY id").fetchall()
                for con in contracts:
                    remaining=int(con["years_remaining"] or 0)-1
                    pid=con["player_id"]
                    if remaining<=0:
                        pl=c.execute("SELECT user_id,name FROM players WHERE id=?",(pid,)).fetchone()
                        c.execute("DELETE FROM contracts WHERE player_id=?",(pid,))
                        c.execute("UPDATE roster_slots SET player_id=NULL,occupant_type='OPEN' WHERE player_id=?",(pid,))
                        c.execute("UPDATE players SET franchise_id=NULL,status='FREE_AGENT' WHERE id=? AND active=1",(pid,))
                        summary["contracts_expired"]+=1
                        if pl:
                            summary["free_agents"].append(pl["name"])
                            if pl["user_id"]:
                                notify_user(c,pl["user_id"],"CONTRACT","Contract expired",f"{pl['name']} is now an EBL free agent.",str(pid))
                    else:
                        c.execute("UPDATE contracts SET years_remaining=? WHERE player_id=?",(remaining,pid))
                        summary["contracts_advanced"]+=1

                c.execute("UPDATE players SET age=age+1 WHERE active=1")

                cap_rows=c.execute("""SELECT p.id,p.user_id,p.name,p.franchise_id,p.age,COUNT(sh.season) seasons_played
                                      FROM players p JOIN season_history sh ON sh.player_id=p.id
                                      WHERE p.active=1 GROUP BY p.id HAVING COUNT(sh.season)>=12""").fetchall()
                for pl in cap_rows:
                    pid=pl["id"]
                    c.execute("DELETE FROM contracts WHERE player_id=?",(pid,))
                    c.execute("UPDATE offers SET status='CANCELLED_RETIRED' WHERE player_id=? AND status IN ('OPEN','HELD')",(pid,))
                    c.execute("UPDATE roster_slots SET player_id=NULL,occupant_type='OPEN' WHERE player_id=?",(pid,))
                    c.execute("UPDATE players SET active=0,status='RETIRED',franchise_id=NULL WHERE id=?",(pid,))
                    summary["retired"]+=1
                    if pl["user_id"]:
                        summary["retired_names"].append(pl["name"])
                    c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                              ("PLAYER_RETIRED",pl["user_id"],json.dumps({"player_id":pid,"player_name":pl["name"],"franchise_id":pl["franchise_id"],"reason":"12_SEASON_CAP"})))
                    if pl["user_id"]:
                        notify_user(c,pl["user_id"],"CAREER","EBL career complete",f"{pl['name']} has completed the 12-season maximum EBL career.",str(pid))

                for frrow in c.execute("SELECT * FROM franchises").fetchall():
                    fr=dict(frrow);budget=float(fr.get("xp_budget",TEAM_BUDGET) or TEAM_BUDGET);spent=float(fr.get("xp_spent",0) or 0)
                    unused=max(0.0,budget-spent);rollover=unused if spent>=budget*.70 else 0.0
                    reserve=min(reserve_cap(fr),float(fr.get("xp_reserve",0) or 0)+rollover);fr["xp_reserve"]=reserve
                    next_budget=annual_team_budget(fr)
                    c.execute("""UPDATE franchises SET wins=0,losses=0,runs_for=0,runs_against=0,
                               xp_reserve=?,xp_spent=0,xp_budget=? WHERE id=?""",(reserve,next_budget,fr["id"]))

                if not c.execute("SELECT 1 FROM franchise_seasons WHERE season=? LIMIT 1",(next_season,)).fetchone():
                    set_season_membership(c,next_season,current_active)

                enforce_active_rosters(c,next_season)
                summary["rosters_rebuilt"]=True

                active_players=c.execute("SELECT id,type FROM players WHERE active=1").fetchall()
                for pl in active_players:
                    if pl["type"]=="H":
                        new_stats={"G":0,"PA":0,"AB":0,"H":0,"1B":0,"2B":0,"3B":0,"HR":0,"BB":0,"SO":0,"R":0,"RBI":0,"SB":0,"CS":0}
                    else:
                        new_stats={"G":0,"GS":0,"OUTS":0,"H":0,"ER":0,"BB":0,"SO":0,"W":0,"L":0,"SV":0}
                    c.execute("UPDATE players SET season_json=? WHERE id=?",(json.dumps(new_stats),pl["id"]))

                if c.execute("SELECT 1 FROM games WHERE season=? LIMIT 1",(next_season,)).fetchone():
                    return self.out({"error":"NEXT_SEASON_ALREADY_EXISTS","season":next_season},409)
                generate_season_schedule(c,next_season)

                for key,value in (("season",str(next_season)),("league_day","0"),("phase","REGULAR"),("playoff_round",""),("champion","")):
                    c.execute("INSERT INTO league_state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(key,value))
                c.execute("INSERT INTO league_config(k,v) VALUES('season_number',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(str(next_season),))
                c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                          ("SEASON_ADVANCED",u["id"],json.dumps({"from":current_season,"to":next_season,**summary})))

                c.commit()
                return self.out({"ok":True,"previous_season":current_season,"season":next_season,"day":0,"phase":"REGULAR",
                                 "games_created":c.execute("SELECT COUNT(*) n FROM games WHERE season=?",(next_season,)).fetchone()["n"],
                                 "offseason":summary})
            finally:
                c.close()


        if p=="/api/commish/repair-human-rosters":
            u=self.auth(["COMMISSIONER"])
            if not u:return


            c=conn()
            repaired=[]
            skipped=[]


            humans=c.execute(
                "SELECT id,name,franchise_id,primary_pos,type FROM players WHERE user_id IS NOT NULL AND active=1 AND status='SIGNED' AND franchise_id IS NOT NULL ORDER BY id"
            ).fetchall()


            for pl in humans:
                current=c.execute(
                    "SELECT slot_no,position_group FROM roster_slots WHERE player_id=? LIMIT 1",
                    (pl["id"],)
                ).fetchone()


                if current and current["position_group"]==pl["primary_pos"]:
                    skipped.append(pl["name"])
                else:
                    target=c.execute(
                        "SELECT slot_no,player_id FROM roster_slots WHERE franchise_id=? AND position_group=? AND occupant_type IN ('CPU','OPEN') ORDER BY CASE occupant_type WHEN 'CPU' THEN 0 ELSE 1 END,slot_no LIMIT 1",
                        (pl["franchise_id"],pl["primary_pos"])
                    ).fetchone()


                    if target:
                        displaced_id=target["player_id"]


                        if current:
                            c.execute(
                                "UPDATE roster_slots SET player_id=NULL,occupant_type='OPEN' WHERE franchise_id=? AND slot_no=?",
                                (pl["franchise_id"],current["slot_no"])
                            )


                        if displaced_id:
                            c.execute(
                                "UPDATE players SET franchise_id=NULL,status='FREE_AGENT' WHERE id=? AND user_id IS NULL",
                                (displaced_id,)
                            )


                        c.execute(
                            "UPDATE roster_slots SET player_id=?,occupant_type='HUMAN' WHERE franchise_id=? AND slot_no=?",
                            (pl["id"],pl["franchise_id"],target["slot_no"])
                        )


                        lr=c.execute(
                            "SELECT batting_order_json,rotation_json FROM lineups WHERE franchise_id=?",
                            (pl["franchise_id"],)
                        ).fetchone()


                        if lr and displaced_id and pl["type"]=="H":
                            order=json.loads(lr["batting_order_json"])
                            order=[pl["id"] if int(pid)==int(displaced_id) else pid for pid in order]
                            c.execute(
                                "UPDATE lineups SET batting_order_json=? WHERE franchise_id=?",
                                (json.dumps(order),pl["franchise_id"])
                            )


                        if lr and displaced_id and pl["primary_pos"]=="SP":
                            rotation=json.loads(lr["rotation_json"])
                            rotation=[pl["id"] if int(pid)==int(displaced_id) else pid for pid in rotation]
                            c.execute(
                                "UPDATE lineups SET rotation_json=? WHERE franchise_id=?",
                                (json.dumps(rotation),pl["franchise_id"])
                            )


                        repaired.append(pl["name"])
                    else:
                        skipped.append(pl["name"])


            c.commit()
            c.close()


            return self.out({
                "ok":True,
                "repaired":repaired,
                "skipped":skipped
            })
            
        if p=="/api/commish/reset-test-account":
            u=self.auth(["COMMISSIONER"])
            if not u:return


            d=self.body()
            target=str(d.get("target","")).strip().lower()
            if not target:
                return self.out({"error":"TARGET_REQUIRED"},400)


            c=conn()


            row=c.execute(
                "SELECT u.id,u.username,u.role,s.email FROM users u LEFT JOIN user_security s ON s.user_id=u.id WHERE lower(u.username)=? OR lower(s.email)=?",
                (target,target)
            ).fetchone()
            if not row:
                c.close()
                return self.out({"error":"ACCOUNT_NOT_FOUND"},404)


            if row["role"] in ("COMMISSIONER","COACH"):
                c.close()
                return self.out({"error":"PROTECTED_ACCOUNT"},403)


            uid=row["id"]


            players=c.execute(
                "SELECT id,franchise_id FROM players WHERE user_id=?",
                (uid,)
            ).fetchall()


            removed_players=0
            restored_slots=0


            for p_row in players:
                pid=p_row["id"]


                slots=c.execute(
                    "SELECT franchise_id,slot_no FROM roster_slots WHERE player_id=?",
                    (pid,)
                ).fetchall()


                for slot in slots:
                    c.execute(
                        "UPDATE roster_slots SET player_id=NULL,occupant_type='OPEN' WHERE franchise_id=? AND slot_no=?",
                        (slot["franchise_id"],slot["slot_no"])
                    )
                    restored_slots+=1


            c.execute("DELETE FROM players WHERE id=?",(pid,))
            removed_players+=1
            c.execute("DELETE FROM persistent_sessions WHERE user_id=?",(uid,))
            c.execute("DELETE FROM account_recovery WHERE user_id=?",(uid,))
            c.execute("DELETE FROM user_security WHERE user_id=?",(uid,))
            c.execute(
                "DELETE FROM direct_messages WHERE sender_user_id=? OR recipient_user_id=?",
                (uid,uid)
            )
            c.execute(
                "DELETE FROM user_blocks WHERE blocker_user_id=? OR blocked_user_id=?",
                (uid,uid)
            )
            c.execute(
                "DELETE FROM user_reports WHERE reporter_user_id=? OR reported_user_id=?",
                (uid,uid)
            )
            c.execute(
                "DELETE FROM moderation_actions WHERE target_user_id=? OR moderator_user_id=?",
                (uid,uid)
            )
            c.execute("DELETE FROM users WHERE id=?",(uid,))


            c.commit()
            c.close()


            return self.out({
                "ok":True,
                "username":row["username"],
                "email":row["email"],
                "removed_players":removed_players,
                "restored_slots":restored_slots
            })


if __name__=="__main__":
    init_db()
    port=int(os.environ.get("PORT","8000"))
    print(f"EBL v7.5 Unified Closed Alpha: http://127.0.0.1:{port}")
    print("coach/coach123 | commish/commish123 | register player accounts in UI")
    host=os.environ.get("HOST","0.0.0.0")
    ThreadingHTTPServer((host,port),H).serve_forever()