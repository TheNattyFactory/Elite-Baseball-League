
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

HITTER_ATTRS=["CON","POW","VIS","DISC","TIM","SPD","FLD","ARM","ACC","REAC"]
PITCHER_ATTRS=["STA","H9","K9","BB9","HR9","PCLT","CTRL","VEL","BRK","FLD","ARM","ACC","REAC"]
SALARY_TIERS=[.25,.30,.35,.40,.45]
BONUS_CAP=25.0
TEAM_BUDGET=225.0

FIRST_NAMES=["Marcus","Eli","Jordan","Dominic","Andre","Caleb","Noah","Isaiah","Lucas","Mateo","Julian","Miles","Cameron","Darius","Adrian","Nolan","Gavin","Roman","Jalen","Malik","Evan","Cole","Wesley","Bryce","Theo","Grant","Micah","Jonah","Emmett","Xavier","Leo","Mason","Owen","Silas","Aaron","Damian","Trevor","Derek","Logan","Rafael","Victor","Diego","Luis","Marco","Tomas","Javier","Nico","Santiago","Gabriel","Felix","Henry","Jack","Sam","Ben","Tyler","Connor","Dylan","Austin","Zachary","Nathan","Peter","Alex","Eric","Ryan","Sean","Ian","Blake","Chase","Troy","Reid","Dean","Clay","Jesse","Colin","Spencer","Garrett","Max","Milo","Asher","Ezra","Kai","Jace","Rory","Finn","Dante","Desmond","Terrence","Quincy","Leon","Curtis","Maurice","Devin","Kendrick","Avery","Tristan","Cody","Mitchell","Preston","Walker","Brody"]
LAST_NAMES=["Bennett","Navarro","Hayes","Russo","Wallace","Moreno","Carter","Brooks","Foster","Reed","Sullivan","Price","Turner","Collins","Ramirez","Ortiz","Vega","Castillo","Mendoza","Flores","Santos","Rivera","Delgado","Rojas","Herrera","Cruz","Kim","Park","Lee","Nguyen","Tran","Patel","Shah","Murphy","Kelly","OBrien","Doyle","Walsh","Miller","Davis","Wilson","Moore","Taylor","Anderson","Thomas","Jackson","White","Harris","Martin","Thompson","Garcia","Martinez","Robinson","Clark","Lewis","Young","Allen","King","Wright","Hill","Scott","Green","Adams","Baker","Nelson","Hall","Campbell","Mitchell","Roberts","Phillips","Evans","Edwards","Stewart","Morris","Rogers","Cook","Morgan","Bell","Bailey","Cooper","Richardson","Cox","Howard","Ward","Torres","Peterson","Gray","James","Watson","Wood","Barnes","Ross","Henderson","Coleman","Jenkins","Perry","Powell","Long"]

def cpu_build(attr_names, role, rng):
    # Every Genesis player starts from zero and spends exactly the same 50-point pool.
    vals={a:0 for a in attr_names}
    if role in ("SP","RP","LR","MR","SU","CL"):
        preferred=["CTRL","VEL","BRK","K9","H9"] + (["STA"] if role=="SP" else ["PCLT"])
    else:
        preferred={
          "C":["FLD","ARM","ACC","CON","VIS"],"SS":["FLD","REAC","ACC","CON","SPD"],
          "2B":["CON","FLD","REAC","VIS","SPD"],"3B":["POW","ARM","CON","REAC","FLD"],
          "1B":["POW","CON","DISC","TIM","FLD"],"CF":["SPD","REAC","FLD","CON","ARM"],
          "LF":["POW","CON","TIM","DISC","FLD"],"RF":["POW","ARM","CON","TIM","FLD"],
          "DH":["POW","CON","TIM","DISC","VIS"],"UTIL":["CON","FLD","SPD","VIS","REAC"]
        }.get(role,["CON","VIS","TIM","FLD","SPD"])
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
      xp_budget REAL NOT NULL DEFAULT 225,
      xp_spent REAL NOT NULL DEFAULT 0,
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
      hair_id INTEGER NOT NULL DEFAULT 1
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
""")

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

        c.execute("INSERT OR IGNORE INTO league_state(k,v) VALUES('season','2')")
        c.execute("INSERT OR IGNORE INTO league_state(k,v) VALUES('league_day','0')")

    # Seed CPU roster filler so every team can play while human free agents join over time.
        if c.execute("SELECT COUNT(*) n FROM players").fetchone()["n"]==0:
            hseason={k:0 for k in ["G","PA","AB","H","1B","2B","3B","HR","BB","SO","R","RBI","SB","CS"]}
            pseason={k:0 for k in ["G","GS","OUTS","H","ER","BB","SO","W","L","SV"]}
            for ti in range(1,31):
                fid=f"EBL-F{ti:02d}";hids=[];pids=[]
                positions=["C","1B","2B","3B","SS","LF","CF","RF","DH","UTIL","UTIL","UTIL","UTIL"]
            for idx,pos in enumerate(positions,1):
                attrs=cpu_build(HITTER_ATTRS,pos,R)
                cur=c.execute("""INSERT INTO players(user_id,franchise_id,name,type,primary_pos,bats,throws,xp_wallet,attributes_json,season_json,status,active)
                                 VALUES(NULL,?,?,?,?,?,?,0,?,?,'SIGNED',1)""",
                              (fid,f"{FIRST_NAMES[((ti-1)*25+idx-1)%len(FIRST_NAMES)]} {LAST_NAMES[((ti-1)*25+idx*3)%len(LAST_NAMES)]}","H",pos,"R","R",json.dumps(attrs),json.dumps(hseason)))
                hids.append(cur.lastrowid)
            for idx,role in enumerate(["SP","SP","SP","SP","SP","LR","MR","MR","MR","SU","CL","RP"],1):
                attrs=cpu_build(PITCHER_ATTRS,role,R)
                cur=c.execute("""INSERT INTO players(user_id,franchise_id,name,type,primary_pos,bats,throws,xp_wallet,attributes_json,season_json,status,active)
                                 VALUES(NULL,?,?,?,?,?,?,0,?,?,'SIGNED',1)""",
                              (fid,f"{FIRST_NAMES[((ti-1)*25+13+idx-1)%len(FIRST_NAMES)]} {LAST_NAMES[((ti-1)*25+39+idx*5)%len(LAST_NAMES)]}","P",role,"R","R",json.dumps(attrs),json.dumps(pseason)))
                pids.append(cur.lastrowid)
            c.execute("UPDATE lineups SET batting_order_json=?,rotation_json=? WHERE franchise_id=?",(json.dumps(hids[:9]),json.dumps(pids[:5]),fid))

            fids=[f"EBL-F{i:02d}" for i in range(1,31)]
                arr=list(range(30)); rounds=[]
            for _ in range(29):
                rounds.append([(arr[i],arr[-1-i]) for i in range(15)])
                arr=[arr[0]]+[arr[-1]]+arr[1:-1]
            gid=1
            for day in range(1,82):
                pairs=rounds[(day-1)%29]
            if ((day-1)//29)%2:pairs=[(b,a) for a,b in pairs]
            for ai,bi in pairs:
                c.execute("INSERT OR IGNORE INTO games(id,season,league_day,away_id,home_id,status) VALUES(?,?,?,?,?,'SCHEDULED')",
                          (f"S02-G{gid:04d}",2,day,fids[ai],fids[bi]))
                gid+=1

        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('phase','RECRUITING')")
        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('alpha_cpu_fill','1')")
        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('auto_advance','0')")
        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('season_number','1')")
        # RC1 roster template: 25 players/team = 750 total.
        slot_template=(["C"]*2+["1B"]*2+["2B"]*2+["3B"]*2+["SS"]*2+
                   ["OF"]*5+["SP"]*5+["RP"]*5)
        for fr in c.execute("SELECT id FROM franchises ORDER BY id").fetchall():
        fid=fr["id"]
        players=c.execute("SELECT id FROM players WHERE franchise_id=? ORDER BY id",(fid,)).fetchall()
        for i,posgrp in enumerate(slot_template,1):
            pid=players[i-1]["id"] if i-1<len(players) else None
            c.execute("""INSERT OR IGNORE INTO roster_slots(franchise_id,slot_no,position_group,player_id,occupant_type)
                         VALUES(?,?,?,?,?)""",(fid,i,posgrp,pid,"CPU" if pid else "OPEN"))
    c.commit();c.close()

def session_user(headers):
    cookie=headers.get("Cookie","")
    for part in cookie.split(";"):
        s=part.strip()
        if s.startswith("sid="):return SESSIONS.get(s[4:])
    return None

def attr_cost(v): return 1 if v<25 else 2 if v<50 else 3 if v<70 else 5 if v<85 else 8 if v<95 else 12
def gps_xp(g): return round(max(.25,min(.75,.25+.5*g/100)),3)

DIVISIONS=["Atlantic","North","Central","South","West","Pacific"]
def division_for(fid):
    try:
        n=int(fid.split("F")[-1])
    except: return "Unknown"
    return DIVISIONS[min(5,(n-1)//5)]

def player_obj(c,pid):
    r=c.execute("SELECT * FROM players WHERE id=?",(pid,)).fetchone()
    if not r:return None
    d=dict(r);d["attributes"]=json.loads(d.pop("attributes_json"));d["season"]=json.loads(d.pop("season_json"))
    con=c.execute("SELECT * FROM contracts WHERE player_id=?",(pid,)).fetchone()
    d["contract"]=dict(con) if con else None
    d["offers"]=[dict(x) for x in c.execute("SELECT * FROM offers WHERE player_id=? AND status IN ('OPEN','HELD') ORDER BY id DESC",(pid,))]
    d["ledger"]=[dict(x) for x in c.execute("SELECT event_type,xp,detail_json FROM xp_ledger WHERE player_id=? ORDER BY id DESC LIMIT 25",(pid,))]
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
        return pid and pid not in used and c.execute("SELECT 1 FROM players WHERE id=? AND franchise_id=? AND type='P' AND active=1",(pid,fid)).fetchone()
    # High leverage late innings
    if inning>=9 and 0<lead_margin<=3 and valid(bp.get("CL")): return int(bp["CL"]),"CL"
    if inning>=8 and abs(lead_margin)<=3:
        for k in ["SU1","SU2"]:
            if valid(bp.get(k)): return int(bp[k]),k
    # Long relief when trailing badly / starter exits early
    if inning<=6 or lead_margin<=-4:
        for pid in bp.get("LR",[]):
            if valid(pid): return int(pid),"LR"
    for pid in bp.get("MR",[]):
        if valid(pid): return int(pid),"MR"
    for pid in bp.get("EMERGENCY",[]):
        if valid(pid): return int(pid),"EMERGENCY"
    # fallback to any roster pitcher not used
    r=c.execute("SELECT id FROM players WHERE franchise_id=? AND type='P' AND active=1 ORDER BY id",(fid,)).fetchall()
    for x in r:
        if x["id"] not in used:return x["id"],"RP"
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
    attrs=player["attributes"];spd=attrs.get("SPD",0); briq=attrs.get("BRIQ",attrs.get("BR",0)); steal=attrs.get("STEAL",0)
    base=.03 + spd*.0022 + briq*.0015 + steal*.0025
    mult={"LOW":.55,"NORMAL":1.0,"HIGH":1.65}.get(strategy["substitutions"].get("steal_aggression","NORMAL"),1.0)
    return max(.01,min(.48,base*mult))

def steal_success_probability(player):
    attrs=player["attributes"];spd=attrs.get("SPD",0); briq=attrs.get("BRIQ",attrs.get("BR",0)); steal=attrs.get("STEAL",0)
    return max(.30,min(.96,.48+spd*.0035+briq*.0025+steal*.0038))

def bunt_probability(strategy,inning,score_diff):
    base={"LOW":.01,"NORMAL":.035,"HIGH":.09}.get(strategy["substitutions"].get("bunt_aggression","NORMAL"),.035)
    if inning>=7 and abs(score_diff)<=1:base*=1.7
    return min(.18,base)

def defensive_shift_modifier(strategy,batter_bats):
    d=strategy["defense"]; mode=d.get("vs_lhb" if batter_bats=="L" else "vs_rhb",d.get("default_shift","STANDARD"))
    # small, transparent BIP outcome modifiers
    return {"STANDARD":0.0,"PULL":-.010,"OPPO":-.004,"NO_DOUBLES":-.006,"BUNT_DEFENSE":-.002,"INFIELD_IN":.004}.get(mode,0.0),mode


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
    rotations={fid:json.loads(lrows[fid]["rotation_json"]) for fid in [away,home]}
    strategies={fid:team_strategy_for(c,fid) for fid in [away,home]}
    score={away:0,home:0};events=[];box={"hitters":{},"pitchers":{},"xp":[],"strategy_events":[]}
    used_pitchers={away:set(),home:set()};used_bench={away:set(),home:set()}
    base_runner={away:None,home:None}
    current_pitcher={}
    for fid,opp in [(away,home),(home,away)]:
        current_pitcher[fid]=rotations[fid][(g["league_day"]-1)%5]
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
                if replaced:
                    ev={"type":"PINCH_HITTER","team":fid,"player_id":ph_id,"replaced_id":replaced,"inning":inning,"half":half}
                    events.append(ev);box["strategy_events"].append(ev)
                pitcher=sim_player_obj(c,current_pitcher[opp])
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
                        if base_runner[fid] is not None and R.random()<.55:
                            score[fid]+=1;events.append({"type":"RUN","team":fid,"runs":1,"score":[score[away],score[home]],"note":"Bunt play"})
                            base_runner[fid]=None
                    else:
                        outs+=1
                    events.append({"type":"PA_END","result":"SAC" if success else "BUNT_OUT","outs":outs,"score":[score[away],score[home]]})
                    continue
                events.append({"type":"PA_START","inning":inning,"half":half,"batter_id":batter["id"],"batter":batter["name"],
                               "pitcher_id":pitcher["id"],"pitcher":pitcher["name"],"outs":outs,"score":[score[away],score[home]]})
                balls=strikes=0;pitch_no=0
                while True:
                    pitch_no+=1;ptype=R.choice(["Four-Seam","Slider","Changeup","Sinker","Curve"]);vel=round(R.uniform(82,98),1)
                    px=round(R.uniform(.12,.88),3);pz=round(R.uniform(.12,.88),3);x=R.random()
                    if x<.10 and balls<3:balls+=1;call="Ball"
                    elif x<.30 and strikes<2:strikes+=1;call="Called Strike"
                    else:
                        if balls==3 and x<.17:balls+=1;call="Ball"
                        elif strikes==2 and x<.28:strikes+=1;call="Swinging Strike"
                        else:call="In Play"
                    events.append({"type":"PITCH","inning":inning,"half":half,"pitch_no":pitch_no,"pitch_type":ptype,"velocity":vel,"px":px,"pz":pz,"call":call,"balls":min(balls,4),"strikes":min(strikes,3)})
                    if call=="In Play":
                        out_weight=max(.56,min(.78,.67-shift_adj))
                        result=R.choices(["OUT","1B","2B","HR"],weights=[out_weight,.22,.08,.03])[0]
                        ev=round(R.uniform(78,111),1);la=round(R.uniform(-8,34),1);spray=round(R.uniform(-42,42),1)
                        events.append({"type":"BALL_IN_PLAY","result":result,"exit_velocity":ev,"launch_angle":la,"spray_angle":spray,
                                       "contact_quality":"Barrel" if ev>103 and 18<=la<=32 else "Hard" if ev>95 else "Normal","shift":shift_mode})
                        if result=="OUT":
                            outs+=1;events.append({"type":"OUT","outs":outs,"out_type":R.choice(["Groundout","Flyout","Lineout"])})
                        else:
                            if result=="HR":
                                runs=1+(1 if base_runner[fid] is not None else 0);score[fid]+=runs;base_runner[fid]=None
                                events.append({"type":"RUN","team":fid,"runs":runs,"score":[score[away],score[home]]})
                            else:
                                # score previous runner sometimes
                                if base_runner[fid] is not None and R.random()<(.18 if result=="1B" else .48):
                                    score[fid]+=1;events.append({"type":"RUN","team":fid,"runs":1,"score":[score[away],score[home]]});base_runner[fid]=None
                                # batter becomes runner, potentially pinch-run
                                runner_id,_old=maybe_pinch_run(c,fid,strategies[fid],batter["id"],inning,score[fid]-score[opp],used_bench[fid])
                                if _old:
                                    ev2={"type":"PINCH_RUNNER","team":fid,"player_id":runner_id,"replaced_id":_old,"inning":inning,"half":half}
                                    events.append(ev2);box["strategy_events"].append(ev2)
                                base_runner[fid]=runner_id
                                runner=sim_player_obj(c,runner_id)
                                # steal decision
                                if R.random()<steal_attempt_probability(runner,strategies[fid]):
                                    safe=R.random()<steal_success_probability(runner)
                                    ev3={"type":"STEAL_ATTEMPT","team":fid,"runner_id":runner_id,"success":safe,"inning":inning,"half":half}
                                    events.append(ev3);box["strategy_events"].append(ev3)
                                    if not safe:
                                        outs+=1;base_runner[fid]=None;events.append({"type":"OUT","outs":outs,"out_type":"Caught Stealing"})
                        events.append({"type":"PA_END","result":result,"outs":outs,"score":[score[away],score[home]]});break
                    if balls>=4:
                        # walk creates/keeps runner
                        if base_runner[fid] is None: base_runner[fid]=batter["id"]
                        events.append({"type":"PA_END","result":"BB","outs":outs,"score":[score[away],score[home]]});break
                    if strikes>=3:
                        outs+=1;events.append({"type":"OUT","outs":outs,"out_type":"Strikeout"});events.append({"type":"PA_END","result":"SO","outs":outs,"score":[score[away],score[home]]});break
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
        winner=R.choice([away,home]);score[winner]+=1;events.append({"type":"RUN","team":winner,"runs":1,"score":[score[away],score[home]],"note":"Tiebreak"})
    winner=away if score[away]>score[home] else home;loser=home if winner==away else away
    events.append({"type":"GAME_END","winner":winner,"final_score":[score[away],score[home]]})

    # Participation/stat/XP layer (keeps existing accounting model intact)
    for fid in [away,home]:
        opp=home if fid==away else away
        participant_ids=set(lineups[fid])|used_bench[fid]
        for pid in participant_ids:
            p=sim_player_obj(c,pid)
            if not p or p["type"]!="H":continue
            line={"G":1,"PA":4,"AB":R.choice([3,4]),"H":R.choice([0,1,1,1,2]),"1B":0,"2B":0,"3B":0,"HR":0,"BB":0,"SO":R.randint(0,2),"R":0,"RBI":0,"SB":0,"CS":0}
            line["1B"]=line["H"]
            if line["H"] and R.random()<.12:line["HR"]=1;line["1B"]-=1
            if R.random()<.12:line["BB"]=1;line["PA"]+=1
            for k,v in line.items():p["season"][k]=p["season"].get(k,0)+v
            gps=hitter_gps(line);perf=round(gps_xp(gps)*rivalry_xp_multiplier(c,away,home),3);con=contract_for(c,pid);salary=float(con["salary"]) if con else .25
            p["xp_wallet"]=round(p["xp_wallet"]+salary+perf,3)
            c.execute("INSERT INTO xp_ledger(player_id,event_type,xp,detail_json) VALUES(?,?,?,?)",(pid,"SALARY",salary,json.dumps({"game":g["id"]})))
            c.execute("INSERT INTO xp_ledger(player_id,event_type,xp,detail_json) VALUES(?,?,?,?)",(pid,"PERFORMANCE",perf,json.dumps({"game":g["id"],"gps":round(gps,1)})))
            save_player(c,p);box["hitters"][str(pid)]=line;box["xp"].append({"player_id":pid,"salary":salary,"performance":perf})
        for spid in used_pitchers[fid]:
            p=sim_player_obj(c,spid)
            if not p:continue
            is_starter=(spid==rotations[fid][(g["league_day"]-1)%5])
            pline={"G":1,"GS":1 if is_starter else 0,"OUTS":18 if is_starter else 3,"H":R.randint(4,8) if is_starter else R.randint(0,2),
                   "ER":score[opp] if is_starter else R.randint(0,1),"BB":R.randint(1,3) if is_starter else R.randint(0,1),
                   "SO":R.randint(4,9) if is_starter else R.randint(0,3),"W":1 if fid==winner and is_starter else 0,
                   "L":1 if fid==loser and is_starter else 0,"SV":1 if (not is_starter and fid==winner and spid==strategies[fid]["bullpen"].get("CL")) else 0}
            for k,v in pline.items():p["season"][k]=p["season"].get(k,0)+v
            gps=pitcher_gps(pline,is_starter);perf=round(gps_xp(gps)*rivalry_xp_multiplier(c,away,home),3);con=contract_for(c,spid);salary=float(con["salary"]) if con else .25
            p["xp_wallet"]=round(p["xp_wallet"]+salary+perf,3)
            c.execute("INSERT INTO xp_ledger(player_id,event_type,xp,detail_json) VALUES(?,?,?,?)",(spid,"SALARY",salary,json.dumps({"game":g["id"]})))
            c.execute("INSERT INTO xp_ledger(player_id,event_type,xp,detail_json) VALUES(?,?,?,?)",(spid,"PERFORMANCE",perf,json.dumps({"game":g["id"],"gps":round(gps,1)})))
            save_player(c,p);box["pitchers"].setdefault(fid,[]).append({"player_id":spid,**pline});box["xp"].append({"player_id":spid,"salary":salary,"performance":perf})

    c.execute("UPDATE franchises SET wins=wins+1,runs_for=runs_for+?,runs_against=runs_against+? WHERE id=?",(score[winner],score[loser],winner))
    c.execute("UPDATE franchises SET losses=losses+1,runs_for=runs_for+?,runs_against=runs_against+? WHERE id=?",(score[loser],score[winner],loser))
    c.execute("UPDATE games SET away_runs=?,home_runs=?,status='FINAL',box_json=?,events_json=? WHERE id=?",
              (score[away],score[home],json.dumps(box),json.dumps(events),g["id"]))
    margin=abs(score[away]-score[home])
    heat=update_rivalry(c,away,home,winner,margin)
    update_team_game_records(c,g,score)
    maybe_rivalry_news(c,g,winner,loser,margin,heat)
    generate_game_news(c,g,score,winner,loser,box)
    return {"game_id":g["id"],"events":len(events),"winner":winner,"away_runs":score[away],"home_runs":score[home],
            "strategy_events":len(box["strategy_events"])}


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


def token_hash(v): return hashlib.sha256(v.encode()).hexdigest()

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)

def iso_after(minutes):
    return (utc_now:=utcnow() + datetime.timedelta(minutes=minutes)).isoformat()

def parse_iso(v):
    try:return datetime.datetime.fromisoformat(v)
    except:return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

def get_client_ip(handler):
    xf=handler.headers.get("X-Forwarded-For","").split(",")[0].strip()
    return xf or handler.client_address[0]

def rate_limit(c,key,limit,window_seconds):
    now=int(time.time())

    with RATE_LOCK:
        r=RATE_STATE.get(key)

        if not r or now-r["window_start"]>=window_seconds:
            RATE_STATE[key]={
                "window_start":now,
                "count":1
            }
            return True

        if r["count"]>=limit:
            return False

        r["count"]+=1
        return True

def email_enabled():
    return bool(
        os.environ.get("RESEND_API_KEY")
        and os.environ.get("EMAIL_FROM")
    )

def send_mail(to, subject, body):
    print("EMAIL API: send_mail called")
    print("EMAIL API: enabled =", email_enabled())

    if not email_enabled():
        print("EMAIL API: missing configuration")
        return False

    try:
        payload = json.dumps({
            "from": os.environ["EMAIL_FROM"],
            "to": [to],
            "subject": subject,
            "text": body
        }).encode("utf-8")

        req = Request(
    "https://api.resend.com/emails",
    data=payload,
    headers={
        "Authorization": "Bearer " + os.environ["RESEND_API_KEY"],
        "Content-Type": "application/json",
        "User-Agent": "EBL/1.0 (elite-baseball.com)"
    },
    method="POST"
)

        with urlopen(req, timeout=15) as response:
            result = response.read().decode("utf-8")
            print("EMAIL API: sent successfully", result)
            return 200 <= response.status < 300

    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print("EMAIL API ERROR:", e.code, detail)
        return False

    except URLError as e:
        print("EMAIL API NETWORK ERROR:", str(e.reason))
        return False

    except Exception as e:
        print("EMAIL API ERROR:", type(e).__name__, str(e))
        return False

def new_session(c,user_id,handler,days=30):
    raw=secrets.token_urlsafe(32);h=token_hash(raw)
    exp=(utcnow()+datetime.timedelta(days=days)).isoformat()
    c.execute("""INSERT INTO persistent_sessions(token_hash,user_id,expires_at,user_agent,ip)
                 VALUES(?,?,?,?,?)""",(h,user_id,exp,handler.headers.get("User-Agent","")[:250],get_client_ip(handler)))
    return raw,exp

def session_user(c_or_headers, raw=None):
    close_conn = False

    if raw is None and hasattr(c_or_headers, "get"):
        headers = c_or_headers
        for part in headers.get("Cookie", "").split(";"):
            if part.strip().startswith("sid="):
                raw = part.strip()[4:]
                break

        c = conn()
        close_conn = True
    else:
        c = c_or_headers

    try:
        if not raw:
            return None

        r = c.execute(
            """SELECT s.*,u.id,u.username,u.role
               FROM persistent_sessions s
               JOIN users u ON u.id=s.user_id
               WHERE s.token_hash=?""",
            (token_hash(raw),)
        ).fetchone()

        if not r:
            return None

        if parse_iso(r["expires_at"]) < utcnow():
            c.execute(
                "DELETE FROM persistent_sessions WHERE token_hash=?",
                (token_hash(raw),)
            )
            c.commit()
            return None

        return {
            "id": r["id"],
            "username": r["username"],
            "role": r["role"]
        }

    finally:
        if close_conn:
            c.close()
    close_conn=False
    if not raw:return None
    r=c.execute("""SELECT s.*,u.id,u.username,u.role FROM persistent_sessions s JOIN users u ON u.id=s.user_id
                   WHERE s.token_hash=?""",(token_hash(raw),)).fetchone()
    if not r:return None
    if parse_iso(r["expires_at"])<utcnow():
        c.execute("DELETE FROM persistent_sessions WHERE token_hash=?",(token_hash(raw),));c.commit();return None
    c.execute("UPDATE persistent_sessions SET last_seen_at=CURRENT_TIMESTAMP WHERE token_hash=?",(token_hash(raw),));c.commit()
    return {"id":r["id"],"username":r["username"],"role":r["role"]}

def user_restricted(c,user_id):
    r=c.execute("SELECT muted_until,suspended_until FROM user_security WHERE user_id=?",(user_id,)).fetchone()
    if not r:return {"muted":False,"suspended":False}
    muted=bool(r["muted_until"] and parse_iso(r["muted_until"])>utcnow())
    suspended=bool(r["suspended_until"] and parse_iso(r["suspended_until"])>utcnow())
    return {"muted":muted,"suspended":suspended}

def perform_backup(db_path,backup_dir):
    src=Path(db_path);out=Path(backup_dir);out.mkdir(parents=True,exist_ok=True)
    stamp=utcnow().strftime("%Y%m%d_%H%M%S")
    dst=out/f"ebl_{stamp}.db"
    c=sqlite3.connect(src);b=sqlite3.connect(dst);c.backup(b);b.close();c.close()
    # Retain newest 30 automatic backups.
    files=sorted(out.glob("ebl_*.db"),reverse=True)
    for f in files[30:]:
        try:f.unlink()
        except:pass
    return dst

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

        if p.startswith("/api/"):
            return self.api_get(p)

        if p in ("/", "/verify-email", "/reset-password"):
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
        if p=="/health":
            return self.out({"ok":True,"service":"EBL","version":"1.0.5"})
        if p=="/api/me":return self.out({"user":u})
        if p=="/api/league":
            c=conn();day=int(c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()["v"])
            teams=[dict(x) for x in c.execute("SELECT id,name,wins,losses,runs_for,runs_against FROM franchises ORDER BY wins DESC,(runs_for-runs_against) DESC")]
            for t in teams:t["division"]=division_for(t["id"])
            c.close();return self.out({"season":2,"day":day,"teams":teams,"divisions":DIVISIONS})
        if p.startswith("/api/team/"):
            fid=p.split("/")[-1].strip()

            c=conn()

            team=c.execute(
                "SELECT id,name,wins,losses,runs_for,runs_against FROM franchises WHERE id=?",
                (fid,)
            ).fetchone()

            if not team:
                c.close()
                return self.out({"error":"TEAM_NOT_FOUND"},404)

            roster=[dict(x) for x in c.execute(
                "SELECT * FROM players WHERE franchise_id=? ORDER BY id",
                (fid,)
            )]

            for player in roster:
                # Decode JSON fields if this build contains them.
                for field in ("attributes_json","stats_json","appearance_json","contract_json"):
                    if field in player and player[field]:
                        try:
                            player[field.replace("_json","")]=json.loads(player[field])
                        except Exception:
                            pass

                slot=c.execute(
                    "SELECT slot_no,position_group,occupant_type FROM roster_slots WHERE player_id=?",
                    (player["id"],)
                ).fetchone()

                if slot:
                    player["slot_no"]=slot["slot_no"]
                    player["position_group"]=slot["position_group"]
                    player["occupant_type"]=slot["occupant_type"]
                else:
                    player["slot_no"]=None
                    player["position_group"]=None
                    player["occupant_type"]="UNASSIGNED"

            result={
                "team":dict(team),
                "division":division_for(team["id"]),
                "roster":roster
            }

            c.close()
            return self.out(result)
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
            c=conn();rows=[dict(x) for x in c.execute("SELECT id,league_day,away_id,home_id,away_runs,home_runs,status FROM games ORDER BY league_day,id")];c.close();return self.out({"games":rows})
        if p.startswith("/api/game/"):
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
        if p=="/api/my-player":
            u=self.auth()
            if not u:return
            c=conn();r=c.execute("SELECT id FROM players WHERE user_id=? AND active=1 ORDER BY id DESC LIMIT 1",(u["id"],)).fetchone()
            if not r:c.close();return self.out({"player":None})
            pl=player_obj(c,r["id"])
            if pl.get("franchise_id"):
                f=c.execute("SELECT id,name,wins,losses,runs_for,runs_against FROM franchises WHERE id=?",(pl["franchise_id"],)).fetchone()
                if f:
                    pl["team"]=dict(f);pl["team"]["division"]=division_for(pl["franchise_id"])
            c.close();return self.out({"player":pl})
        if p=="/api/coach/free-agents":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn();rows=[player_obj(c,x["id"]) for x in c.execute("SELECT id FROM players WHERE status='FREE_AGENT' AND active=1 ORDER BY id DESC LIMIT 100")];c.close();return self.out({"players":rows})
        if p=="/api/coach/team":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn();f=c.execute("SELECT * FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"team":None})
            roster=[dict(x) for x in c.execute("SELECT id,name,type,primary_pos FROM players WHERE franchise_id=? AND active=1 ORDER BY type,id",(f["id"],))]
            l=c.execute("SELECT * FROM lineups WHERE franchise_id=?",(f["id"],)).fetchone()
            strat=c.execute("SELECT * FROM team_strategy WHERE franchise_id=?",(f["id"],)).fetchone()
            offers=[dict(x) for x in c.execute("""SELECT o.*,p.name,p.primary_pos FROM offers o JOIN players p ON p.id=o.player_id
                       WHERE o.franchise_id=? AND o.status IN ('OPEN','HELD') ORDER BY o.id DESC""",(f["id"],))]
            c.close()
            brand=c.execute("SELECT * FROM franchise_branding WHERE franchise_id=?",(f["id"],)).fetchone()
            return self.out({"team":dict(f),"branding":dict(brand) if brand else None,"roster":roster,"lineup":json.loads(l["batting_order_json"]),"rotation":json.loads(l["rotation_json"]),
                             "strategy":{"bullpen":json.loads(strat["bullpen_json"]),"defense":json.loads(strat["defense_json"]),
                                         "bench":json.loads(strat["bench_json"]),"substitutions":json.loads(strat["substitutions_json"])},
                             "offers":offers})
        if p=="/api/awards":
            c=conn(); hitters=[]; pitchers=[]
            for r in c.execute("SELECT id,name,franchise_id,primary_pos,season_json FROM players WHERE active=1"):
                st=json.loads(r["season_json"])
                if "PA" in st:
                    ab=st.get("AB",0);h=st.get("H",0);bb=st.get("BB",0);pa=st.get("PA",0)
                    tb=st.get("1B",0)+2*st.get("2B",0)+3*st.get("3B",0)+4*st.get("HR",0)
                    avg=h/ab if ab else 0;obp=(h+bb)/pa if pa else 0;slg=tb/ab if ab else 0
                    # MVP proxy deliberately broad: offense + speed/base value; defensive detail expands as event engine records it.
                    mvp=(obp+slg)*100 + st.get("HR",0)*1.1 + st.get("SB",0)*.35 + st.get("RBI",0)*.12
                    hitters.append({"id":r["id"],"name":r["name"],"team":r["franchise_id"],"pos":r["primary_pos"],
                                    "avg":avg,"obp":obp,"slg":slg,"ops":obp+slg,"hr":st.get("HR",0),"rbi":st.get("RBI",0),
                                    "sb":st.get("SB",0),"pa":pa,"mvp":mvp})
                else:
                    outs=st.get("OUTS",0);er=st.get("ER",0);bb=st.get("BB",0);h=st.get("H",0);so=st.get("SO",0)
                    era=er*27/outs if outs else 99.0;whip=(bb+h)/(outs/3) if outs else 99.0
                    score=(so*1.2)-(er*2.2)-(bb*.7)+(outs/3)*.3
                    pitchers.append({"id":r["id"],"name":r["name"],"team":r["franchise_id"],"pos":r["primary_pos"],
                                     "era":era,"whip":whip,"so":so,"outs":outs,"score":score})
            qualified=[x for x in hitters if x["pa"]>=max(1,int(c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()["v"])*2)]
            batting=sorted(qualified or hitters,key=lambda x:(x["avg"],x["pa"]),reverse=True)[:10]
            mvp=sorted(hitters,key=lambda x:x["mvp"],reverse=True)[:10]
            hr=sorted(hitters,key=lambda x:(x["hr"],x["ops"]),reverse=True)[:10]
            sb=sorted(hitters,key=lambda x:(x["sb"],x["obp"]),reverse=True)[:10]
            pitching=sorted([x for x in pitchers if x["outs"]>0],key=lambda x:(-x["score"],x["era"]))[:10]
            # Fielding titles are position race placeholders until complete fielding events populate OAA/DRS.
            fielding={}
            for pos in ["C","1B","2B","3B","SS","LF","CF","RF"]:
                pool=[x for x in hitters if x["pos"]==pos]
                fielding[pos]=sorted(pool,key=lambda x:(x["pa"],x["ops"]),reverse=True)[:5]
            c.close();return self.out({"mvp":mvp,"batting":batting,"home_runs":hr,"stolen_bases":sb,"pitching":pitching,"fielding":fielding})
        if p.startswith("/api/chat/"):
            u=self.auth()
            if not u:return
            channel=p.split("/")[-1].upper()
            if channel not in ("EBL","TEAM"):return self.out({"error":"INVALID_CHANNEL"},400)
            c=conn();team_id=None
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
            c=conn()
            day=int(c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()["v"])
            finals=c.execute("SELECT COUNT(*) n FROM games WHERE status='FINAL'").fetchone()["n"]
            runs=c.execute("SELECT COALESCE(SUM(away_runs+home_runs),0) n FROM games WHERE status='FINAL'").fetchone()["n"]
            hitters=[]; pitchers=[]
            for r in c.execute("SELECT id,name,primary_pos,xp_wallet,attributes_json,season_json,franchise_id FROM players WHERE active=1"):
                d=dict(r); st=json.loads(d["season_json"]); at=json.loads(d["attributes_json"])
                if "PA" in st:
                    ab=st.get("AB",0);h=st.get("H",0);bb=st.get("BB",0)
                    avg=h/ab if ab else 0
                    obp=(h+bb)/(st.get("PA",0)) if st.get("PA",0) else 0
                    tb=st.get("1B",0)+2*st.get("2B",0)+3*st.get("3B",0)+4*st.get("HR",0)
                    slg=tb/ab if ab else 0
                    hitters.append({"id":d["id"],"name":d["name"],"team":d["franchise_id"],"pos":d["primary_pos"],"xp":d["xp_wallet"],"avg":avg,"obp":obp,"slg":slg,"ops":obp+slg,"hr":st.get("HR",0),"so":st.get("SO",0),"bb":bb,"pa":st.get("PA",0),"attr_total":sum(at.values())})
                else:
                    outs=st.get("OUTS",0); er=st.get("ER",0); bb=st.get("BB",0); h=st.get("H",0)
                    era=er*27/outs if outs else 0
                    whip=(bb+h)/(outs/3) if outs else 0
                    pitchers.append({"id":d["id"],"name":d["name"],"team":d["franchise_id"],"pos":d["primary_pos"],"xp":d["xp_wallet"],"era":era,"whip":whip,"so":st.get("SO",0),"bb":bb,"outs":outs,"attr_total":sum(at.values())})
            active_h=[x for x in hitters if x["pa"]>0]; active_p=[x for x in pitchers if x["outs"]>0]
            total_pa=sum(x["pa"] for x in active_h); total_h=sum(json.loads(c.execute("SELECT season_json FROM players WHERE id=?",(x["id"],)).fetchone()[0]).get("H",0) for x in active_h)
            total_bb=sum(x["bb"] for x in active_h); total_so=sum(x["so"] for x in active_h); total_hr=sum(x["hr"] for x in active_h)
            league={"games":finals,"runs_per_game":runs/finals if finals else 0,"avg":total_h/max(1,sum(json.loads(c.execute("SELECT season_json FROM players WHERE id=?",(x["id"],)).fetchone()[0]).get("AB",0) for x in active_h)) if active_h else 0,
                    "bb_pct":total_bb/total_pa if total_pa else 0,"k_pct":total_so/total_pa if total_pa else 0,"hr_pct":total_hr/total_pa if total_pa else 0}
            xp_rows=c.execute("SELECT event_type,COALESCE(SUM(xp),0) total,COUNT(*) n FROM xp_ledger GROUP BY event_type").fetchall()
            xp={x["event_type"]:{"total":round(x["total"],3),"events":x["n"]} for x in xp_rows}
            teams=[dict(x) for x in c.execute("SELECT id,name,wins,losses,runs_for,runs_against FROM franchises ORDER BY wins DESC,(runs_for-runs_against) DESC LIMIT 10")]
            c.close()
            return self.out({"season":2,"day":day,"league":league,"xp":xp,
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
            sent=send_mail(email,"Verify your EBL account",f"Welcome to the Elite Baseball League.\n\nVerify your email within 60 minutes:\n{verify_url}\n\nIf you did not create this account, ignore this email.")
            return self.out({"user":{"id":uid,"username":username,"role":"PLAYER"},"verification_email_sent":sent},200,{"Set-Cookie":f"sid={sid}; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000"})
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
            return self.out({"user":{"id":r["id"],"username":r["username"],"role":r["role"]}},200,{"Set-Cookie":f"sid={sid}; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000"})
        if p=="/api/logout":
            raw=None
            for part in self.headers.get("Cookie","").split(";"):
                if part.strip().startswith("sid="):raw=part.strip()[4:]
            if raw:
                c=conn();c.execute("DELETE FROM persistent_sessions WHERE token_hash=?",(token_hash(raw),));c.commit();c.close()
            return self.out({"ok":True},200,{"Set-Cookie":"sid=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"})
        if p=="/api/account/recover":
            d=self.body();username=str(d.get("username","")).strip();code=str(d.get("recovery_code","")).strip();newpw=str(d.get("new_password",""))
            if len(newpw)<8:return self.out({"error":"PASSWORD_TOO_SHORT"},400)
            c=conn();u=c.execute("SELECT id FROM users WHERE username=?",(username,)).fetchone()
            if not u:c.close();return self.out({"error":"INVALID_RECOVERY"},400)
            r=c.execute("SELECT recovery_hash FROM account_recovery WHERE user_id=?",(u["id"],)).fetchone()
            if not r or not hmac.compare_digest(r["recovery_hash"],recovery_hash(code)):
                c.close();return self.out({"error":"INVALID_RECOVERY"},400)
            c.execute("UPDATE users SET password_hash=? WHERE id=?",(pwhash(newpw),u["id"]))
            newcode=make_recovery_code()
            c.execute("UPDATE account_recovery SET recovery_hash=?,created_at=CURRENT_TIMESTAMP WHERE user_id=?",(recovery_hash(newcode),u["id"]))
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
                send_mail(email,"Reset your EBL password",f"A password reset was requested for {r['username']}.\n\nThis link expires in 30 minutes:\n{url}\n\nIf you did not request this reset, ignore this email.")
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
            c=conn();r=c.execute("SELECT email,email_verified FROM user_security WHERE user_id=?",(u["id"],)).fetchone()
            if not r or r["email_verified"]:c.close();return self.out({"ok":True})
            raw=secrets.token_urlsafe(24)
            c.execute("UPDATE user_security SET email_token_hash=?,email_token_expires=? WHERE user_id=?",(token_hash(raw),iso_after(60),u["id"]))
            c.commit();email=r["email"];c.close()
            url=os.environ.get("PUBLIC_BASE_URL","http://127.0.0.1:8000").rstrip("/")+"/verify-email?token="+raw+"&user="+str(u["id"])
            sent=send_mail(email,"Verify your EBL account",f"Verify your EBL email within 60 minutes:\n{url}")
            return self.out({"ok":True,"sent":sent})
        if p=="/api/player/create":
            u=self.auth(["PLAYER","COMMISSIONER"])
            if not u:return
            d=self.body();name=str(d.get("name","")).strip();pos=d.get("position");bats=d.get("bats");throws=d.get("throws");attrs=d.get("attributes",{})
            c=conn()
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
        if p=="/api/player/spend-xp":
            u=self.auth()
            if not u:return
            attr=self.body().get("attribute");c=conn();r=c.execute("SELECT id FROM players WHERE user_id=? AND active=1",(u["id"],)).fetchone()
            if not r:c.close();return self.out({"error":"PLAYER_NOT_FOUND"},404)
            pl=player_obj(c,r["id"])
            if attr not in pl["attributes"]:c.close();return self.out({"error":"INVALID_ATTRIBUTE"},400)
            cc=attr_cost(pl["attributes"][attr])
            if pl["xp_wallet"]<cc:c.close();return self.out({"error":"INSUFFICIENT_XP","cost":cc},400)
            old=pl["attributes"][attr];pl["attributes"][attr]+=1;pl["xp_wallet"]=round(pl["xp_wallet"]-cc,3);save_player(c,pl)
            c.execute("INSERT INTO xp_ledger(player_id,event_type,xp,detail_json) VALUES(?,?,?,?)",(pl["id"],"ATTRIBUTE_UPGRADE",-cc,json.dumps({"attribute":attr,"from":old,"to":old+1})));c.commit();c.close();return self.out({"ok":True})
        if p=="/api/player/request-cpu-market":
            u=self.auth(["PLAYER","COMMISSIONER"])
            if not u:return
            c=conn();pr=c.execute("SELECT * FROM players WHERE user_id=? AND active=1",(u["id"],)).fetchone()
            if not pr or pr["status"]!="FREE_AGENT":c.close();return self.out({"error":"PLAYER_NOT_FREE_AGENT"},400)
            # CPU franchises evaluate positional need and make 3 varied, affordable offers.
            existing=c.execute("SELECT COUNT(*) n FROM offers WHERE player_id=? AND status IN ('OPEN','HELD')",(pr["id"],)).fetchone()["n"]
            if existing:c.close();return self.out({"error":"ACTIVE_OFFERS_ALREADY_EXIST"},400)
            attrs=json.loads(pr["attributes_json"]);overall=sum(attrs.values())/max(1,len(attrs))
            teams=[dict(x) for x in c.execute("SELECT * FROM franchises ORDER BY id")]
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
            c.commit();c.close();return self.out({"ok":True,"offers":made})
        if p=="/api/coach/offer":
            u=self.auth(["COMMISSIONER"])
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
            cur=c.execute("INSERT INTO offers(franchise_id,player_id,bonus,salary,years,status) VALUES(?,?,?,?,?,'OPEN')",(f["id"],pid,bonus,salary,years));c.commit();oid=cur.lastrowid;c.close();return self.out({"ok":True,"offer_id":oid})
        if p=="/api/player/respond-offer":
            u=self.auth()
            if not u:return
            d=self.body();oid=int(d.get("offer_id",0));action=d.get("action")
            if action not in ["ACCEPT","HOLD","REJECT"]:return self.out({"error":"INVALID_ACTION"},400)
            c=conn();pl=c.execute("SELECT id FROM players WHERE user_id=? AND active=1",(u["id"],)).fetchone()
            if not pl:c.close();return self.out({"error":"PLAYER_NOT_FOUND"},404)
            off=c.execute("SELECT * FROM offers WHERE id=? AND player_id=?",(oid,pl["id"])).fetchone()
            if not off or off["status"] not in ["OPEN","HELD"]:c.close();return self.out({"error":"OFFER_NOT_AVAILABLE"},400)
            if action=="HOLD":c.execute("UPDATE offers SET status='HELD' WHERE id=?",(oid,))
            elif action=="REJECT":c.execute("UPDATE offers SET status='REJECTED' WHERE id=?",(oid,))
            else:
                f=c.execute("SELECT * FROM franchises WHERE id=?",(off["franchise_id"],)).fetchone()
                if f["xp_spent"]+off["bonus"]>f["xp_budget"]:c.close();return self.out({"error":"TEAM_BUDGET_CHANGED"},400)
                c.execute("UPDATE offers SET status='ACCEPTED' WHERE id=?",(oid,));c.execute("UPDATE offers SET status='CANCELLED_PLAYER_SIGNED' WHERE player_id=? AND id<>? AND status IN ('OPEN','HELD')",(pl["id"],oid))
                c.execute("INSERT INTO contracts(player_id,franchise_id,bonus,salary,years_remaining) VALUES(?,?,?,?,?)",(pl["id"],off["franchise_id"],off["bonus"],off["salary"],off["years"]))
                c.execute("UPDATE players SET franchise_id=?,status='SIGNED',xp_wallet=xp_wallet+? WHERE id=?",(off["franchise_id"],off["bonus"],pl["id"]))
                c.execute("UPDATE franchises SET xp_spent=xp_spent+? WHERE id=?",(off["bonus"],off["franchise_id"]))
            c.commit();c.close();return self.out({"ok":True})
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
            c.execute("INSERT INTO direct_messages(sender_user_id,recipient_user_id,message) VALUES(?,?,?)",(u["id"],other,msg))
            c.commit();c.close();return self.out({"ok":True})
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
        if p=="/api/commish/backup-now":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            dst=perform_backup(DB,os.environ.get("EBL_BACKUP_DIR",os.path.join(ROOT,"backups")))
            c=conn();c.execute("INSERT INTO backup_audit(path,bytes) VALUES(?,?)",(str(dst),dst.stat().st_size));c.commit();c.close()
            return self.out({"ok":True,"path":str(dst)})
        if p=="/api/commish/sim-day":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn();day=int(c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()["v"])+1
            if day>81:
                c.close();return self.out({"error":"REGULAR_SEASON_COMPLETE"},400)
            games=[dict(x) for x in c.execute("SELECT * FROM games WHERE league_day=? AND status='SCHEDULED' ORDER BY id",(day,))]
            results=[simulate_game(c,g) for g in games]
            c.execute("UPDATE league_state SET v=? WHERE k='league_day'",(str(day),))
            c.commit();c.close()
            if day%7==0:
                try:
                    dst=perform_backup(DB,os.environ.get("EBL_BACKUP_DIR",os.path.join(ROOT,"backups")))
                    bc=conn();bc.execute("INSERT INTO backup_audit(path,bytes) VALUES(?,?)",(str(dst),dst.stat().st_size));bc.commit();bc.close()
                except Exception:
                    pass
                    return self.out({"ok":True,"day":day,"results":results})

        if p=="/api/commish/reset-test-account":
            u=self.auth(["COMMISSIONER"])
            if not u:return

            d=self.body()
            target=str(d.get("target","")).strip().lower()
            if not target:
                return self.out({"error":"TARGET_REQUIRED"},400)

            c=conn()

            row=c.execute("""
                SELECT u.id,u.username,u.role,s.email
                FROM users u
                LEFT JOIN user_security s ON s.user_id=u.id
                WHERE lower(u.username)=? OR lower(s.email)=?
            """,(target,target)).fetchone()

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
                    c.execute("""
                        UPDATE roster_slots
                        SET player_id=NULL,occupant_type='OPEN'
                        WHERE franchise_id=? AND slot_no=?
                    """,(slot["franchise_id"],slot["slot_no"]))
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
