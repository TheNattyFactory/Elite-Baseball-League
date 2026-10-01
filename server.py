from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
import sqlite3, json, secrets, hashlib, os, mimetypes, hmac, random, math, smtplib, ssl, datetime, time, threading, base64
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
AUTO_ADVANCE_TOKEN=secrets.token_urlsafe(32)
AUTO_ADVANCE_LOCK=threading.Lock()
















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
# RC113: CPU-generated rookie offers use one league-standard entry contract.
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
# RC90: contract renewal human identity is carried through the coach contract payload.
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
EBL_SUPPORTER_PROFILE_CUSTOMIZATION_RC106=True
RENEWAL_OPEN_DAY=70
MAX_REQUEST_BYTES=20*1024*1024
MAX_TEAM_LOGO_DATA_URL_CHARS=7_100_000
MAX_PROFILE_PHOTO_DATA_URL_CHARS=900_000
BETA_MODE=str(os.environ.get("EBL_BETA_MODE","1")).strip().lower() not in ("0","false","off","no")
COACH_APPLICATIONS_OPEN=str(os.environ.get("EBL_COACH_APPLICATIONS_OPEN","0")).strip().lower() in ("1","true","on","yes")
EBL_SUPPORTER_LEGACY_RC107="RC107"
EBL_SUPPORTER_PRICE_RC108="RC108"
EBL_ONBOARDING_RC110="RC110"
EBL_DB_MIGRATION_RC111="RC111"
AGE_REQUIREMENT=13








# RC109: recurring Supporter subscriptions are configured at deploy time.
# Checkout stays on Stripe-hosted pages; EBL attaches a one-time account reference
# and grants access only after signed Stripe webhooks confirm the subscription.
def _safe_support_url(value):
    value=str(value or "").strip()
    return value if value.startswith(("https://","http://")) else ""








def stripe_support_plans():
    currency=str(os.environ.get("EBL_STRIPE_EXPECTED_CURRENCY","usd") or "usd").strip().lower()
    mode=str(os.environ.get("EBL_STRIPE_MODE","test") or "test").strip().lower()
    monthly={
        "key":"monthly",
        "label":"Monthly",
        "url":_safe_support_url(os.environ.get("EBL_SUPPORT_MONTHLY_URL","")),
        "payment_link_id":str(os.environ.get("EBL_STRIPE_MONTHLY_PAYMENT_LINK_ID","") or "").strip(),
        "price_id":str(os.environ.get("EBL_STRIPE_MONTHLY_PRICE_ID","") or "").strip(),
        "amount":int(os.environ.get("EBL_STRIPE_MONTHLY_AMOUNT","500") or 500),
        "currency":currency,
        "interval":"month"
    }
    yearly={
        "key":"yearly",
        "label":"Yearly",
        "url":_safe_support_url(os.environ.get("EBL_SUPPORT_YEARLY_URL","")),
        "payment_link_id":str(os.environ.get("EBL_STRIPE_YEARLY_PAYMENT_LINK_ID","") or "").strip(),
        "price_id":str(os.environ.get("EBL_STRIPE_YEARLY_PRICE_ID","") or "").strip(),
        "amount":int(os.environ.get("EBL_STRIPE_YEARLY_AMOUNT","5400") or 5400),
        "currency":currency,
        "interval":"year"
    }
    return {"monthly":monthly,"yearly":yearly,"mode":mode}








def support_public_config():
    plans=stripe_support_plans()
    provider=str(os.environ.get("EBL_SUPPORT_PROVIDER","Stripe").strip() or "Stripe")[:40]
    portal_url=_safe_support_url(os.environ.get("EBL_SUPPORT_PORTAL_URL",""))
    available={}
    for key in ("monthly","yearly"):
        p=plans[key]
        if p["url"] and p["payment_link_id"]:
            available[key]={
                "label":p["label"],
                "price_usd":round(max(0,p["amount"])/100,2),
                "interval":p["interval"]
            }
    monthly_amt=int(plans["monthly"]["amount"])
    yearly_amt=int(plans["yearly"]["amount"])
    full_year=monthly_amt*12
    savings=max(0,full_year-yearly_amt)
    savings_pct=round((savings/full_year)*100) if full_year else 0
    return {
        "enabled":bool(available),
        "provider":provider,
        "checkout_path":"/api/support/checkout" if available else "",
        "verified_checkout":bool(available),
        "mode":"test" if plans["mode"]=="test" else ("live" if plans["mode"]=="live" else ""),
        "plans":available,
        "yearly_savings_usd":round(savings/100,2),
        "yearly_savings_pct":savings_pct,
        "portal_url":portal_url,
        "currency":"USD"
    }








def registration_age_eligible(value, minimum_age=AGE_REQUIREMENT):
    """Validate 13+ eligibility without persisting the submitted birth date."""
    try:
        dob=datetime.date.fromisoformat(str(value or "").strip())
    except Exception:
        return False
    today=datetime.datetime.now(datetime.timezone.utc).date()
    if dob>today:
        return False
    try:
        cutoff=today.replace(year=today.year-int(minimum_age))
    except ValueError:
        cutoff=today.replace(year=today.year-int(minimum_age),day=28)
    return dob<=cutoff








# RC84: official EBL baseline branding. These are lightweight league defaults
# for CPU/unclaimed franchises. Existing uploaded/custom artwork is never overwritten.
OFFICIAL_BRAND_SEED_KEY="official_franchise_branding_rc114_logo_sets_v1"
OFFICIAL_FRANCHISE_BRANDS={
    "EBL-F01":{"city":"Atlanta","team":"Scouts","primary":"#173F35","secondary":"#D7C7A1","accent":"#0A1D2A","style":4,"home":"CREAM","away":"NAVY"},
    "EBL-F02":{"city":"New York","team":"Empires","primary":"#111827","secondary":"#D4AF37","accent":"#F2F0E8","style":8,"home":"WHITE","away":"BLACK"},
    "EBL-F03":{"city":"Los Angeles","team":"Stars","primary":"#1E3A8A","secondary":"#F5C542","accent":"#FFFFFF","style":2,"home":"WHITE","away":"NAVY"},
    "EBL-F04":{"city":"Chicago","team":"Wind","primary":"#5BC0EB","secondary":"#1B365D","accent":"#FFFFFF","style":6,"home":"WHITE","away":"NAVY"},
    "EBL-F05":{"city":"Houston","team":"Apollos","primary":"#0B1F3A","secondary":"#F47C20","accent":"#F4F1EA","style":5,"home":"WHITE","away":"NAVY"},
    "EBL-F06":{"city":"Phoenix","team":"Firebirds","primary":"#7A1E2C","secondary":"#F47B20","accent":"#F7D08A","style":5,"home":"CREAM","away":"RED"},
    "EBL-F07":{"city":"Philadelphia","team":"Founders","primary":"#17324D","secondary":"#A61B2B","accent":"#E7D9B5","style":7,"home":"CREAM","away":"NAVY"},
    "EBL-F08":{"city":"San Antonio","team":"Defenders","primary":"#171717","secondary":"#A7A9AC","accent":"#8C1D24","style":4,"home":"WHITE","away":"BLACK"},
    "EBL-F09":{"city":"Birmingham","team":"Hammers","primary":"#15191F","secondary":"#B7372F","accent":"#D9DDE2","style":3,"home":"GRAY","away":"BLACK"},
    "EBL-F10":{"city":"Dallas","team":"Wranglers","primary":"#17365D","secondary":"#A65A2E","accent":"#F2E6C9","style":1,"home":"CREAM","away":"NAVY"},
    "EBL-F11":{"city":"Jacksonville","team":"Breakers","primary":"#007C91","secondary":"#0A2342","accent":"#F2F7F7","style":6,"home":"WHITE","away":"NAVY"},
    "EBL-F12":{"city":"Fort Worth","team":"Longhorns","primary":"#A44A1F","secondary":"#4B2E1E","accent":"#F2E1C2","style":4,"home":"CREAM","away":"BLACK"},
    "EBL-F13":{"city":"Austin","team":"Outlaws","primary":"#151515","secondary":"#B87333","accent":"#F4E8D0","style":3,"home":"CREAM","away":"BLACK"},
    "EBL-F14":{"city":"San Jose","team":"Circuit","primary":"#0A6F7A","secondary":"#111827","accent":"#A7F3D0","style":9,"home":"WHITE","away":"BLACK"},
    "EBL-F15":{"city":"Columbus","team":"Aviators","primary":"#123B63","secondary":"#5DADE2","accent":"#D9E0E8","style":6,"home":"WHITE","away":"NAVY"},
    "EBL-F16":{"city":"Charlotte","team":"Crowns","primary":"#4B2E83","secondary":"#D4AF37","accent":"#111111","style":5,"home":"WHITE","away":"BLACK"},
    "EBL-F17":{"city":"Indianapolis","team":"Racers","primary":"#C1121F","secondary":"#1D3557","accent":"#F1FAEE","style":3,"home":"WHITE","away":"NAVY"},
    "EBL-F18":{"city":"San Francisco","team":"Gold","primary":"#1A1A1A","secondary":"#C99700","accent":"#F5F0E1","style":2,"home":"CREAM","away":"BLACK"},
    "EBL-F19":{"city":"Seattle","team":"Evergreens","primary":"#0B5D3B","secondary":"#203A43","accent":"#DDE9E4","style":6,"home":"WHITE","away":"NAVY"},
    "EBL-F20":{"city":"Denver","team":"Summit","primary":"#1E4E8C","secondary":"#7D8790","accent":"#F4F8FB","style":6,"home":"WHITE","away":"NAVY"},
    "EBL-F21":{"city":"Oklahoma City","team":"Twisters","primary":"#123B63","secondary":"#D7262E","accent":"#F7F9FC","style":7,"home":"WHITE","away":"NAVY"},
    "EBL-F22":{"city":"Nashville","team":"Sound","primary":"#14213D","secondary":"#D4AF37","accent":"#F6F1E1","style":7,"home":"CREAM","away":"NAVY"},
    "EBL-F23":{"city":"Washington","team":"Eagles","primary":"#0D2B4E","secondary":"#7D1D2A","accent":"#C8CED4","style":5,"home":"WHITE","away":"NAVY"},
    "EBL-F24":{"city":"Las Vegas","team":"High Rollers","primary":"#111111","secondary":"#B11226","accent":"#D4AF37","style":3,"home":"BLACK","away":"RED"},
    "EBL-F25":{"city":"Boston","team":"Minutemen","primary":"#0B2545","secondary":"#A61B2B","accent":"#D8C3A5","style":7,"home":"CREAM","away":"NAVY"},
    "EBL-F26":{"city":"Portland","team":"Pioneers","primary":"#285943","secondary":"#6B4F2A","accent":"#E8E0C8","style":6,"home":"CREAM","away":"NAVY"},
    "EBL-F27":{"city":"Detroit","team":"Motors","primary":"#2B2F33","secondary":"#BFC5CA","accent":"#1F4E79","style":4,"home":"GRAY","away":"BLACK"},
    "EBL-F28":{"city":"Louisville","team":"Thoroughbreds","primary":"#0B5D3B","secondary":"#111111","accent":"#D4AF37","style":5,"home":"WHITE","away":"BLACK"},
    "EBL-F29":{"city":"Memphis","team":"Kings","primary":"#4B2E83","secondary":"#A7A9AC","accent":"#111111","style":5,"home":"WHITE","away":"BLACK"},
    "EBL-F30":{"city":"Baltimore","team":"Clippers","primary":"#0C2D48","secondary":"#C96A2B","accent":"#F1E3C6","style":6,"home":"CREAM","away":"NAVY"},
}
















# RC114: league-wide production logo sets. These SVG data URIs give every
# franchise a coherent PRIMARY / SECONDARY / WORDMARK system while preserving
# any artwork a coach or commissioner has already uploaded.
def _brand_svg_escape(value):
    return (str(value or "")
            .replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            .replace('"',"&quot;").replace("'","&apos;"))








def _brand_svg_uri(svg):
    raw=base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return "data:image/svg+xml;base64,"+raw








def _brand_city_code(city):
    bits=[x for x in str(city or "").replace("-"," ").split() if x]
    if not bits:return "EBL"
    if len(bits)==1:return bits[0][:3].upper()
    return "".join(x[0] for x in bits).upper()[:3]








def _brand_team_code(team):
    bits=[x for x in str(team or "").replace("-"," ").split() if x]
    if not bits:return "E"
    return ("".join(x[0] for x in bits) if len(bits)>1 else bits[0][:2]).upper()[:3]








def _brand_star_points(cx,cy,r1,r2,n=5):
    pts=[]
    for i in range(n*2):
        a=-math.pi/2+i*math.pi/n
        r=r1 if i%2==0 else r2
        pts.append(f"{cx+math.cos(a)*r:.1f},{cy+math.sin(a)*r:.1f}")
    return " ".join(pts)








def _brand_motif(team,primary,secondary,accent):
    t=str(team or "").lower()
    if any(k in t for k in ("empire","crown","king")):
        return f'<path d="M176 206 L198 132 L238 171 L256 112 L274 171 L314 132 L336 206 Z" fill="{secondary}" stroke="{accent}" stroke-width="10" stroke-linejoin="round"/><rect x="180" y="205" width="152" height="38" rx="12" fill="{primary}" stroke="{accent}" stroke-width="9"/>'
    if "star" in t:
        return f'<polygon points="{_brand_star_points(256,180,82,34)}" fill="{secondary}" stroke="{accent}" stroke-width="10"/>'
    if any(k in t for k in ("wind","twister","breaker")):
        return f'<path d="M154 164 C205 102 322 108 350 163 C310 139 274 145 248 171 C224 196 218 232 236 263 C185 247 150 211 154 164Z" fill="none" stroke="{secondary}" stroke-width="24" stroke-linecap="round"/><path d="M205 178 C238 149 295 151 314 182 C286 171 263 181 252 202 C240 225 248 247 267 260" fill="none" stroke="{accent}" stroke-width="16" stroke-linecap="round"/>'
    if "apollo" in t:
        return f'<ellipse cx="256" cy="182" rx="112" ry="52" fill="none" stroke="{secondary}" stroke-width="16" transform="rotate(-20 256 182)"/><circle cx="256" cy="182" r="44" fill="{primary}" stroke="{accent}" stroke-width="10"/><polygon points="{_brand_star_points(350,125,30,12)}" fill="{accent}"/>'
    if "firebird" in t:
        return f'<path d="M260 88 C334 144 335 202 292 250 C291 215 270 192 247 180 C266 220 250 258 210 281 C218 232 181 210 194 165 C203 134 229 120 260 88Z" fill="{secondary}" stroke="{accent}" stroke-width="10" stroke-linejoin="round"/><path d="M251 145 C274 173 274 202 252 225 C254 198 238 187 225 177 C229 160 239 151 251 145Z" fill="{accent}"/>'
    if "founder" in t:
        return f'<path d="M216 108 H296 L306 160 C339 190 324 244 277 253 H235 C188 244 173 190 206 160Z" fill="{secondary}" stroke="{accent}" stroke-width="10"/><path d="M256 92 V269" stroke="{primary}" stroke-width="16"/><path d="M210 185 H302" stroke="{primary}" stroke-width="13"/><circle cx="256" cy="270" r="14" fill="{accent}"/>'
    if "defender" in t:
        return f'<path d="M256 89 L347 126 V198 C347 250 309 290 256 315 C203 290 165 250 165 198 V126Z" fill="{primary}" stroke="{secondary}" stroke-width="16"/><path d="M201 145 H311 V184 H289 V226 H223 V184 H201Z" fill="{accent}"/>'
    if "hammer" in t:
        return f'<g transform="rotate(-28 256 185)"><rect x="241" y="105" width="30" height="168" rx="10" fill="{accent}"/><path d="M185 92 H315 V137 H285 L270 158 H242 L227 137 H185Z" fill="{secondary}" stroke="{accent}" stroke-width="8"/></g><g transform="rotate(28 256 185)"><rect x="241" y="105" width="30" height="168" rx="10" fill="{accent}"/><path d="M185 92 H315 V137 H285 L270 158 H242 L227 137 H185Z" fill="{primary}" stroke="{accent}" stroke-width="8"/></g>'
    if any(k in t for k in ("wrangler","outlaw")):
        return f'<polygon points="{_brand_star_points(256,184,91,39)}" fill="{secondary}" stroke="{accent}" stroke-width="10"/><circle cx="256" cy="184" r="40" fill="{primary}" stroke="{accent}" stroke-width="8"/>'
    if "longhorn" in t:
        return f'<path d="M170 155 C198 120 230 135 256 163 C282 135 314 120 342 155 C323 148 306 158 291 180 C277 201 273 226 256 249 C239 226 235 201 221 180 C206 158 189 148 170 155Z" fill="{secondary}" stroke="{accent}" stroke-width="11"/><path d="M169 153 C145 132 132 111 135 87 C160 105 181 111 208 112 M343 153 C367 132 380 111 377 87 C352 105 331 111 304 112" fill="none" stroke="{accent}" stroke-width="13" stroke-linecap="round"/>'
    if any(k in t for k in ("circuit","motor")):
        return f'<circle cx="256" cy="184" r="78" fill="none" stroke="{secondary}" stroke-width="22" stroke-dasharray="28 14"/><circle cx="256" cy="184" r="30" fill="{accent}"/><path d="M256 74 V110 M256 258 V294 M146 184 H182 M330 184 H366" stroke="{accent}" stroke-width="14" stroke-linecap="round"/>'
    if any(k in t for k in ("aviator","eagle")):
        return f'<path d="M256 142 C224 116 185 113 151 128 C181 148 196 169 206 198 C179 190 157 194 135 208 C176 231 214 234 256 216 C298 234 336 231 377 208 C355 194 333 190 306 198 C316 169 331 148 361 128 C327 113 288 116 256 142Z" fill="{secondary}" stroke="{accent}" stroke-width="9"/><polygon points="{_brand_star_points(256,184,37,15)}" fill="{primary}"/>'
    if "racer" in t:
        return f'<path d="M160 133 H329 L307 165 H185Z" fill="{secondary}"/><path d="M139 181 H307 L285 213 H164Z" fill="{accent}"/><path d="M179 229 H337 L315 261 H154Z" fill="{secondary}"/><g fill="{primary}"><rect x="303" y="116" width="26" height="26"/><rect x="329" y="142" width="26" height="26"/><rect x="303" y="168" width="26" height="26"/><rect x="329" y="194" width="26" height="26"/></g>'
    if any(k in t for k in ("gold","summit","pioneer")):
        return f'<path d="M142 261 L226 126 L258 176 L298 111 L376 261Z" fill="{secondary}" stroke="{accent}" stroke-width="10" stroke-linejoin="round"/><path d="M218 138 L242 176 L257 157 L275 183 L299 121" fill="none" stroke="{primary}" stroke-width="16" stroke-linecap="round"/>'
    if "evergreen" in t:
        return f'<path d="M256 90 L197 172 H226 L179 234 H221 L165 306 H347 L291 234 H333 L286 172 H315Z" fill="{secondary}" stroke="{accent}" stroke-width="10" stroke-linejoin="round"/><rect x="244" y="277" width="24" height="48" fill="{primary}"/>'
    if "sound" in t:
        return f'<path d="M230 104 V239 C208 224 172 233 164 260 C156 289 190 307 219 292 C243 279 252 255 252 224 V151 L331 132 V213 C310 198 274 207 266 234 C257 264 291 282 320 267 C344 254 353 230 353 199 V91Z" fill="{secondary}" stroke="{accent}" stroke-width="8"/>'
    if "high roller" in t:
        return f'<rect x="174" y="105" width="164" height="164" rx="24" fill="{primary}" stroke="{secondary}" stroke-width="14" transform="rotate(8 256 187)"/><circle cx="215" cy="150" r="13" fill="{accent}"/><circle cx="298" cy="150" r="13" fill="{accent}"/><circle cx="256" cy="188" r="13" fill="{accent}"/><circle cx="215" cy="226" r="13" fill="{accent}"/><circle cx="298" cy="226" r="13" fill="{accent}"/>'
    if "minutemen" in t:
        return f'<path d="M166 130 H346" stroke="{secondary}" stroke-width="18" stroke-linecap="round"/><path d="M190 102 C228 79 284 79 322 102 L307 145 H205Z" fill="{secondary}" stroke="{accent}" stroke-width="9"/><path d="M256 146 V277" stroke="{accent}" stroke-width="14"/><path d="M205 277 H307" stroke="{secondary}" stroke-width="18" stroke-linecap="round"/>'
    if "thoroughbred" in t:
        return f'<path d="M192 108 C224 96 288 106 313 139 C329 160 326 187 305 207 C290 221 278 239 281 270 H221 C225 237 214 216 194 198 C172 178 169 145 192 108Z" fill="{secondary}" stroke="{accent}" stroke-width="10"/><path d="M218 146 C238 131 267 130 289 145" fill="none" stroke="{primary}" stroke-width="12" stroke-linecap="round"/><circle cx="278" cy="160" r="7" fill="{accent}"/>'
    if "clipper" in t:
        return f'<path d="M256 91 V277 M201 137 H311 M185 213 C205 260 230 281 256 293 C282 281 307 260 327 213 M185 213 H221 M327 213 H291" fill="none" stroke="{secondary}" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/><circle cx="256" cy="117" r="27" fill="none" stroke="{accent}" stroke-width="12"/>'
    return f'<polygon points="{_brand_star_points(256,184,79,34)}" fill="{secondary}" stroke="{accent}" stroke-width="10"/>'








def official_brand_art(brand):
    city=str(brand.get("city") or "Elite")
    team=str(brand.get("team") or "Baseball")
    primary=str(brand.get("primary") or "#153c63")
    secondary=str(brand.get("secondary") or "#d7262e")
    accent=str(brand.get("accent") or "#f7f7f7")
    style=int(brand.get("style") or 1)
    city_code=_brand_city_code(city)
    team_code=_brand_team_code(team)
    city_e=_brand_svg_escape(city.upper())
    team_e=_brand_svg_escape(team.upper())
    monogram=_brand_svg_escape((city_code[:1]+team_code[:1])[:2])
    motif=_brand_motif(team,primary,secondary,accent)
    if style in (3,4):
        badge=f'<path d="M256 34 L432 104 V254 C432 358 359 433 256 480 C153 433 80 358 80 254 V104Z" fill="{primary}" stroke="{accent}" stroke-width="16"/>'
    elif style in (5,8):
        badge=f'<circle cx="256" cy="256" r="214" fill="{primary}" stroke="{accent}" stroke-width="16"/><circle cx="256" cy="256" r="184" fill="none" stroke="{secondary}" stroke-width="8"/>'
    elif style in (6,9):
        badge=f'<polygon points="256,34 433,137 433,342 256,478 79,342 79,137" fill="{primary}" stroke="{accent}" stroke-width="16"/>'
    else:
        badge=f'<path d="M256 30 L464 256 L256 482 L48 256Z" fill="{primary}" stroke="{accent}" stroke-width="16"/>'
    primary_svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><g>{badge}{motif}<text x="256" y="384" text-anchor="middle" font-family="Arial Black,Arial,sans-serif" font-size="72" font-weight="900" fill="{accent}" stroke="{primary}" stroke-width="5" paint-order="stroke">{monogram}</text><text x="256" y="430" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="25" font-weight="800" letter-spacing="4" fill="{secondary}">{team_e}</text></g></svg>'
    secondary_svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><g><circle cx="256" cy="256" r="210" fill="{primary}" stroke="{secondary}" stroke-width="22"/><circle cx="256" cy="256" r="170" fill="none" stroke="{accent}" stroke-width="8"/><text x="256" y="296" text-anchor="middle" font-family="Arial Black,Arial,sans-serif" font-size="150" font-weight="900" letter-spacing="-10" fill="{accent}" stroke="{primary}" stroke-width="8" paint-order="stroke">{monogram}</text><path d="M151 344 H361" stroke="{secondary}" stroke-width="16" stroke-linecap="round"/><text x="256" y="390" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="28" font-weight="900" letter-spacing="5" fill="{secondary}">{city_code}</text></g></svg>'
    wordmark_svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="360" viewBox="0 0 1200 360"><g><text x="600" y="112" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="62" font-weight="900" letter-spacing="16" fill="{secondary}">{city_e}</text><text x="600" y="242" text-anchor="middle" font-family="Arial Black,Arial,sans-serif" font-size="138" font-style="italic" font-weight="900" letter-spacing="-3" fill="{primary}" stroke="{accent}" stroke-width="12" paint-order="stroke">{team_e}</text><path d="M190 287 H1010" stroke="{secondary}" stroke-width="18" stroke-linecap="round"/><path d="M365 319 H835" stroke="{accent}" stroke-width="8" stroke-linecap="round"/></g></svg>'
    return {
        "primary":_brand_svg_uri(primary_svg),
        "secondary":_brand_svg_uri(secondary_svg),
        "wordmark":_brand_svg_uri(wordmark_svg),
    }








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
    """RC57: authoritative 16-man EBL roster capacity."""
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
















FIRST_NAMES=["Marcus","Eli","Jordan","Dominic","Andre","Caleb","Noah","Isaiah","Lucas","Mateo","Julian","Miles","Cameron","Darius","Adrian","Nolan","Gavin","Roman","Jalen","Malik","Evan","Cole","Wesley","Bryce","Theo","Grant","Micah","Jonah","Emmett","Xavier","Leo","Mason","Owen","Silas","Aaron","Damian","Trevor","Derek","Logan","Rafael","Victor","Diego","Luis","Marco","Tomas","Javier","Nico","Santiago","Gabriel","Felix","Henry","Jack","Sam","Ben","Tyler","Connor","Dylan","Austin","Zachary","Nathan","Peter","Alex","Eric","Ryan","Sean","Ian","Blake","Chase","Troy","Reid","Dean","Clay","Jesse","Colin","Spencer","Garrett","Max","Milo","Asher","Ezra","Kai","Jace","Rory","Finn","Dante","Desmond","Terrence","Quincy","Leon","Curtis","Maurice","Devin","Kendrick","Avery","Tristan","Cody","Mitchell","Preston","Walker","Brody"]
LAST_NAMES=["Bennett","Navarro","Hayes","Russo","Wallace","Moreno","Carter","Brooks","Foster","Reed","Sullivan","Price","Turner","Collins","Ramirez","Ortiz","Vega","Castillo","Mendoza","Flores","Santos","Rivera","Delgado","Rojas","Herrera","Cruz","Kim","Park","Lee","Nguyen","Tran","Patel","Shah","Murphy","Kelly","OBrien","Doyle","Walsh","Miller","Davis","Wilson","Moore","Taylor","Anderson","Thomas","Jackson","White","Harris","Martin","Thompson","Garcia","Martinez","Robinson","Clark","Lewis","Young","Allen","King","Wright","Hill","Scott","Green","Adams","Baker","Nelson","Hall","Campbell","Mitchell","Roberts","Phillips","Evans","Edwards","Stewart","Morris","Rogers","Cook","Morgan","Bell","Bailey","Cooper","Richardson","Cox","Howard","Ward","Torres","Peterson","Gray","James","Watson","Wood","Barnes","Ross","Henderson","Coleman","Jenkins","Perry","Powell","Long"]
















def cpu_build(attr_names, role, rng):
    # Every Genesis player starts from zero and spends exactly the same 50-point pool.
    vals={a:0 for a in attr_names}
    if role in ("SP","RP","LR","MR","SU","CL"):
        preferred=(
            ["CTRL","CMD","VEL","BRK","MOV","SEQ","STA","DEC","PCLT"]
            if role=="SP" else
            ["VEL","BRK","DEC","CMD","PCLT","MOV","SEQ","CTRL","STA"]
        )
    else:
        preferred={
          "C":["CALL","ARM","ACC","REAC","FLD","CON","VIS"],"SS":["FLD","REAC","ACC","CON","SPD","BRIQ"],
          "2B":["CON","FLD","REAC","VIS","SPD","BRIQ"],"3B":["POW","ARM","CON","REAC","FLD"],
          "1B":["POW","CON","DISC","TIM","FLD"],"CF":["SPD","BRIQ","LEAD","REAC","FLD"],
          "LF":["POW","CON","TIM","DISC","FLD"],"RF":["POW","ARM","CON","TIM","FLD"],
          "DH":["POW","CON","TIM","DISC","VIS"],"UTIL":["CON","FLD","SPD","BRIQ","REAC"]
        }.get(role,["CON","VIS","TIM","FLD","SPD","BRIQ"])
    weights={a:1.0 for a in attr_names}
    if "CALL" in weights and role!="C":weights["CALL"]=0.0
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
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      beta_member INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS coach_applications(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      preferred_franchise_id TEXT,
      experience TEXT NOT NULL DEFAULT '',
      reason TEXT NOT NULL DEFAULT '',
      philosophy TEXT NOT NULL DEFAULT '',
      rules_ack INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','APPROVED','DENIED')),
      review_note TEXT NOT NULL DEFAULT '',
      submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      reviewed_at TEXT,
      reviewed_by INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_coach_applications_user ON coach_applications(user_id,id);
    CREATE INDEX IF NOT EXISTS idx_coach_applications_status ON coach_applications(status,id);
    CREATE TABLE IF NOT EXISTS franchises(
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      owner_user_id INTEGER,
      xp_budget REAL NOT NULL DEFAULT 480,
      xp_spent REAL NOT NULL DEFAULT 0,
      xp_reserve REAL NOT NULL DEFAULT 0,
      training_level INTEGER NOT NULL DEFAULT 0,
      stadium_level INTEGER NOT NULL DEFAULT 0,
      scouting_level INTEGER NOT NULL DEFAULT 0,
      performance_level INTEGER NOT NULL DEFAULT 0,
      hq_level INTEGER NOT NULL DEFAULT 0,
      revenue_level INTEGER NOT NULL DEFAULT 0,
      seating_level INTEGER NOT NULL DEFAULT 0,
      concessions_level INTEGER NOT NULL DEFAULT 0,
      marketing_level INTEGER NOT NULL DEFAULT 0,
      sponsorships_level INTEGER NOT NULL DEFAULT 0,
      merchandising_level INTEGER NOT NULL DEFAULT 0,
      media_level INTEGER NOT NULL DEFAULT 0,
      recovery_level INTEGER NOT NULL DEFAULT 0,
      finish_reward REAL NOT NULL DEFAULT 0,
      development_bonus REAL NOT NULL DEFAULT 0,
      funding_growth REAL NOT NULL DEFAULT 0,
      last_pool_growth REAL NOT NULL DEFAULT 0,
      identity_locked INTEGER NOT NULL DEFAULT 1,
      wins INTEGER NOT NULL DEFAULT 0,
      losses INTEGER NOT NULL DEFAULT 0,
      runs_for INTEGER NOT NULL DEFAULT 0,
      runs_against INTEGER NOT NULL DEFAULT 0
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_nocase ON users(username COLLATE NOCASE);
    CREATE TABLE IF NOT EXISTS players(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      franchise_id TEXT,
      name TEXT NOT NULL,
      first_name TEXT NOT NULL DEFAULT '',
      last_name TEXT NOT NULL DEFAULT '',
      hometown_city TEXT NOT NULL DEFAULT '',
      hometown_region TEXT NOT NULL DEFAULT '',
      type TEXT NOT NULL CHECK(type IN ('H','P')),
      primary_pos TEXT NOT NULL,
      position_group TEXT NOT NULL DEFAULT 'INF',
      bats TEXT NOT NULL,
      throws TEXT NOT NULL,
      xp_wallet REAL NOT NULL DEFAULT 0,
      attributes_json TEXT NOT NULL,
      season_json TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'FREE_AGENT',
      active INTEGER NOT NULL DEFAULT 1,
      face_id INTEGER NOT NULL DEFAULT 1,
      hair_id INTEGER NOT NULL DEFAULT 1,
      facial_hair_id INTEGER NOT NULL DEFAULT 1,
      eye_color_id INTEGER NOT NULL DEFAULT 6,
      nose_id INTEGER NOT NULL DEFAULT 1,
      eye_shape_id INTEGER NOT NULL DEFAULT 1,
      mouth_id INTEGER NOT NULL DEFAULT 1,
      ear_size_id INTEGER NOT NULL DEFAULT 2,
      hair_color_id INTEGER NOT NULL DEFAULT 3,
      eye_black_id INTEGER NOT NULL DEFAULT 1,
      eyewear_id INTEGER NOT NULL DEFAULT 1,
      chain_id INTEGER NOT NULL DEFAULT 1,
      sleeve_id INTEGER NOT NULL DEFAULT 1,
      body_build_id INTEGER NOT NULL DEFAULT 1,
      jersey_number INTEGER NOT NULL DEFAULT 24,
      age INTEGER NOT NULL DEFAULT 18,
      hometown TEXT NOT NULL DEFAULT '',
      skin_color_id INTEGER NOT NULL DEFAULT 1,
      career_extension_through INTEGER NOT NULL DEFAULT 12
    );
    CREATE TABLE IF NOT EXISTS offers(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      franchise_id TEXT NOT NULL,
      player_id INTEGER NOT NULL,
      bonus REAL NOT NULL,
      salary REAL NOT NULL,
      years INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'OPEN',
      offer_type TEXT NOT NULL DEFAULT 'FREE_AGENT',
      message TEXT NOT NULL DEFAULT '',
      effective_season INTEGER,
      salary_basis TEXT NOT NULL DEFAULT '',
      proposed_role TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS contracts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      player_id INTEGER UNIQUE NOT NULL,
      franchise_id TEXT NOT NULL,
      bonus REAL NOT NULL,
      salary REAL NOT NULL,
      years_remaining INTEGER NOT NULL,
      years_total INTEGER NOT NULL DEFAULT 1,
      starting_salary REAL NOT NULL DEFAULT 0.30,
      signed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS contract_history(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      player_id INTEGER NOT NULL,
      franchise_id TEXT NOT NULL,
      bonus REAL NOT NULL DEFAULT 0,
      salary REAL NOT NULL,
      years INTEGER NOT NULL,
      signed_at TEXT,
      ended_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_contract_history_player_team
      ON contract_history(player_id,franchise_id,id);
    CREATE TABLE IF NOT EXISTS team_sponsorships(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      franchise_id TEXT NOT NULL,
      attribute TEXT NOT NULL,
      bonus INTEGER NOT NULL DEFAULT 1,
      start_season INTEGER NOT NULL,
      end_season INTEGER NOT NULL,
      cost REAL NOT NULL DEFAULT 25,
      status TEXT NOT NULL DEFAULT 'ACTIVE',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_team_sponsorships_team ON team_sponsorships(franchise_id,status,end_season);
    CREATE TABLE IF NOT EXISTS team_development_coaches(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      franchise_id TEXT NOT NULL,
      season INTEGER NOT NULL,
      coach_slot INTEGER NOT NULL DEFAULT 1,
      coach_type TEXT NOT NULL,
      attribute TEXT NOT NULL,
      cost REAL NOT NULL DEFAULT 0,
      is_free INTEGER NOT NULL DEFAULT 0,
      intensity INTEGER NOT NULL DEFAULT 1,
      checkpoint_days_json TEXT NOT NULL DEFAULT '[0,49,95]',
      applied_days_json TEXT NOT NULL DEFAULT '[]',
      hired_day INTEGER NOT NULL DEFAULT 0,
      start_applied INTEGER NOT NULL DEFAULT 0,
      midseason_applied INTEGER NOT NULL DEFAULT 0,
      endseason_applied INTEGER NOT NULL DEFAULT 0,
      hired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(franchise_id,season,coach_slot),
      UNIQUE(franchise_id,season,coach_type)
    );
    CREATE INDEX IF NOT EXISTS idx_team_development_coaches_team_season
      ON team_development_coaches(franchise_id,season);
    CREATE TABLE IF NOT EXISTS xp_ledger(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      player_id INTEGER NOT NULL,
      event_type TEXT NOT NULL,
      xp REAL NOT NULL,
      detail_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS team_practice(
      player_id INTEGER NOT NULL,
      practice_date TEXT NOT NULL,
      season INTEGER NOT NULL,
      league_day INTEGER NOT NULL,
      franchise_id TEXT NOT NULL,
      xp REAL NOT NULL DEFAULT 0.25,
      joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY(player_id,practice_date)
    );
    CREATE INDEX IF NOT EXISTS idx_team_practice_team_date
      ON team_practice(franchise_id,practice_date);
    CREATE TABLE IF NOT EXISTS lineups(
      franchise_id TEXT PRIMARY KEY,
      batting_order_json TEXT NOT NULL DEFAULT '[]',
      rotation_json TEXT NOT NULL DEFAULT '[]',
      field_positions_json TEXT NOT NULL DEFAULT '{}'
    );
    CREATE TABLE IF NOT EXISTS team_strategy(
      franchise_id TEXT PRIMARY KEY,
      bullpen_json TEXT NOT NULL DEFAULT '{}',
      defense_json TEXT NOT NULL DEFAULT '{}',
      bench_json TEXT NOT NULL DEFAULT '[]',
      substitutions_json TEXT NOT NULL DEFAULT '{}',
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS pitcher_workload(
      pitcher_id INTEGER PRIMARY KEY,
      fatigue REAL NOT NULL DEFAULT 0,
      last_league_day INTEGER NOT NULL DEFAULT 0,
      last_outs INTEGER NOT NULL DEFAULT 0,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
































    CREATE TABLE IF NOT EXISTS news(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      season INTEGER NOT NULL DEFAULT 1,
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
    CREATE INDEX IF NOT EXISTS idx_games_season_day_id ON games(season,league_day,id);








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
      player_id INTEGER,
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
      primary_logo TEXT NOT NULL DEFAULT '',
      secondary_logo TEXT NOT NULL DEFAULT '',
      jersey_wordmark TEXT NOT NULL DEFAULT '',
      inseason_edit_season INTEGER,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
















    CREATE TABLE IF NOT EXISTS franchise_identity_history(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      franchise_id TEXT NOT NULL,
      season INTEGER NOT NULL,
      city TEXT NOT NULL DEFAULT '',
      team_name TEXT NOT NULL DEFAULT '',
      display_name TEXT NOT NULL,
      primary_color TEXT,
      secondary_color TEXT,
      accent_color TEXT,
      primary_logo TEXT,
      secondary_logo TEXT,
      jersey_wordmark TEXT,
      started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    CREATE TABLE IF NOT EXISTS beta_feedback(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      category TEXT NOT NULL DEFAULT 'FEEDBACK',
      page TEXT NOT NULL DEFAULT '',
      detail TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'OPEN',
      user_agent TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      reviewed_at TEXT,
      reviewed_by INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_beta_feedback_status ON beta_feedback(status,id);
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








    CREATE TABLE IF NOT EXISTS player_bonus_history(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      season INTEGER NOT NULL,
      bonus_code TEXT NOT NULL,
      player_id INTEGER NOT NULL,
      franchise_id TEXT,
      xp_awarded REAL NOT NULL DEFAULT 0,
      detail_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(season,bonus_code,player_id)
    );








    CREATE TABLE IF NOT EXISTS all_star_games(
      season INTEGER PRIMARY KEY,
      league_day INTEGER NOT NULL,
      gold_runs INTEGER NOT NULL DEFAULT 0,
      red_runs INTEGER NOT NULL DEFAULT 0,
      gold_roster_json TEXT NOT NULL DEFAULT '[]',
      red_roster_json TEXT NOT NULL DEFAULT '[]',
      box_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );








    CREATE TABLE IF NOT EXISTS supporter_entitlement_history(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      event_type TEXT NOT NULL,
      old_tier TEXT NOT NULL DEFAULT 'FREE',
      new_tier TEXT NOT NULL DEFAULT 'FREE',
      source TEXT NOT NULL DEFAULT '',
      external_ref TEXT NOT NULL DEFAULT '',
      note TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_supporter_history_user ON supporter_entitlement_history(user_id,id);








    CREATE TABLE IF NOT EXISTS support_checkout_refs(
      token TEXT PRIMARY KEY,
      user_id INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'PENDING',
      plan TEXT NOT NULL DEFAULT '',
      stripe_session_id TEXT UNIQUE,
      stripe_payment_intent TEXT,
      stripe_subscription_id TEXT,
      stripe_customer_id TEXT,
      stripe_price_id TEXT,
      payment_status TEXT NOT NULL DEFAULT '',
      amount_total INTEGER,
      currency TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      completed_at TEXT,
      refunded_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_support_checkout_user ON support_checkout_refs(user_id,created_at);
    CREATE INDEX IF NOT EXISTS idx_support_checkout_pi ON support_checkout_refs(stripe_payment_intent);
    -- RC111: idx_support_checkout_sub is intentionally created AFTER the in-place
    -- RC109 column migration below so older databases can upgrade safely.








    CREATE TABLE IF NOT EXISTS support_subscriptions(
      stripe_subscription_id TEXT PRIMARY KEY,
      user_id INTEGER NOT NULL,
      stripe_customer_id TEXT NOT NULL DEFAULT '',
      plan TEXT NOT NULL DEFAULT '',
      stripe_price_id TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT '',
      current_period_end TEXT,
      cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_support_subscriptions_user ON support_subscriptions(user_id,status);








    CREATE TABLE IF NOT EXISTS stripe_webhook_events(
      event_id TEXT PRIMARY KEY,
      event_type TEXT NOT NULL,
      object_id TEXT NOT NULL DEFAULT '',
      result TEXT NOT NULL DEFAULT '',
      processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
""")








    # Safe in-place schema migrations for existing Railway databases.
    user_cols={r["name"] for r in c.execute("PRAGMA table_info(users)")}
    if "display_name" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT ''")
    if "profile_bio" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN profile_bio TEXT NOT NULL DEFAULT ''")
    if "profile_motto" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN profile_motto TEXT NOT NULL DEFAULT ''")
    if "profile_photo" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN profile_photo TEXT NOT NULL DEFAULT ''")
    if "profile_accent" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN profile_accent TEXT NOT NULL DEFAULT '#d4af37'")
    if "profile_theme" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN profile_theme TEXT NOT NULL DEFAULT 'CLASSIC'")
    if "profile_banner" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN profile_banner TEXT NOT NULL DEFAULT 'CLASSIC'")
    if "profile_card_frame" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN profile_card_frame TEXT NOT NULL DEFAULT 'CLASSIC'")
    if "profile_featured_accolade" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN profile_featured_accolade TEXT NOT NULL DEFAULT ''")
    if "featured_player_id" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN featured_player_id INTEGER")
    if "beta_member" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN beta_member INTEGER NOT NULL DEFAULT 0")
    if "support_tier" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN support_tier TEXT NOT NULL DEFAULT 'FREE'")
    if "supporter_since" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN supporter_since TEXT")
    if "supporter_expires_at" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN supporter_expires_at TEXT")
    if "supporter_source" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN supporter_source TEXT NOT NULL DEFAULT ''")
    if "founding_supporter" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN founding_supporter INTEGER NOT NULL DEFAULT 0")
    if "founding_supporter_since" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN founding_supporter_since TEXT")
    if "founding_supporter_ref" not in user_cols:
        c.execute("ALTER TABLE users ADD COLUMN founding_supporter_ref TEXT NOT NULL DEFAULT ''")








    # RC109 recurring-support migrations.
    checkout_cols={r["name"] for r in c.execute("PRAGMA table_info(support_checkout_refs)").fetchall()}
    for col,ddl in {
        "plan":"TEXT NOT NULL DEFAULT ''",
        "stripe_subscription_id":"TEXT",
        "stripe_customer_id":"TEXT",
        "stripe_price_id":"TEXT"
    }.items():
        if col not in checkout_cols:
            c.execute(f"ALTER TABLE support_checkout_refs ADD COLUMN {col} {ddl}")
    c.execute("CREATE INDEX IF NOT EXISTS idx_support_checkout_sub ON support_checkout_refs(stripe_subscription_id)")
    c.execute("""CREATE TABLE IF NOT EXISTS support_subscriptions(
        stripe_subscription_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        stripe_customer_id TEXT NOT NULL DEFAULT '',
        plan TEXT NOT NULL DEFAULT '',
        stripe_price_id TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT '',
        current_period_end TEXT,
        cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_support_subscriptions_user ON support_subscriptions(user_id,status)")








    player_cols={r["name"] for r in c.execute("PRAGMA table_info(players)")}
    if "age" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN age INTEGER NOT NULL DEFAULT 18")
    if "hometown" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN hometown TEXT NOT NULL DEFAULT ''")
    if "first_name" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN first_name TEXT NOT NULL DEFAULT ''")
    if "last_name" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN last_name TEXT NOT NULL DEFAULT ''")
    if "hometown_city" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN hometown_city TEXT NOT NULL DEFAULT ''")
    if "hometown_region" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN hometown_region TEXT NOT NULL DEFAULT ''")
    # Backfill simple legacy identity fields without changing canonical name/hometown.
    c.execute("""UPDATE players SET
                   first_name=CASE WHEN first_name='' THEN
                     CASE WHEN instr(trim(name),' ')>0 THEN substr(trim(name),1,instr(trim(name),' ')-1) ELSE trim(name) END
                     ELSE first_name END,
                   last_name=CASE WHEN last_name='' THEN
                     CASE WHEN instr(trim(name),' ')>0 THEN substr(trim(name),instr(trim(name),' ')+1) ELSE '' END
                     ELSE last_name END
                 WHERE first_name='' OR last_name=''""")
    c.execute("""UPDATE players SET
                   hometown_city=CASE WHEN hometown_city='' THEN
                     CASE WHEN instr(hometown,',')>0 THEN trim(substr(hometown,1,instr(hometown,',')-1)) ELSE trim(hometown) END
                     ELSE hometown_city END,
                   hometown_region=CASE WHEN hometown_region='' THEN
                     CASE WHEN instr(hometown,',')>0 THEN trim(substr(hometown,instr(hometown,',')+1)) ELSE '' END
                     ELSE hometown_region END
                 WHERE hometown_city='' OR hometown_region=''""")
    if "skin_color_id" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN skin_color_id INTEGER NOT NULL DEFAULT 1")
    if "position_group" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN position_group TEXT NOT NULL DEFAULT 'INF'")
    if "facial_hair_id" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN facial_hair_id INTEGER NOT NULL DEFAULT 1")
        c.execute("UPDATE players SET facial_hair_id=2 WHERE face_id IN (2,7)")
        c.execute("UPDATE players SET facial_hair_id=4 WHERE face_id IN (4,9)")
        c.execute("UPDATE players SET facial_hair_id=3 WHERE face_id IN (5,10)")
    if "eye_color_id" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN eye_color_id INTEGER NOT NULL DEFAULT 6")
    if "nose_id" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN nose_id INTEGER NOT NULL DEFAULT 1")
    if "eye_shape_id" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN eye_shape_id INTEGER NOT NULL DEFAULT 1")
    if "mouth_id" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN mouth_id INTEGER NOT NULL DEFAULT 1")
    if "ear_size_id" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN ear_size_id INTEGER NOT NULL DEFAULT 2")
    if "hair_color_id" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN hair_color_id INTEGER NOT NULL DEFAULT 3")
    if "eye_black_id" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN eye_black_id INTEGER NOT NULL DEFAULT 1")
    if "eyewear_id" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN eyewear_id INTEGER NOT NULL DEFAULT 1")
    if "chain_id" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN chain_id INTEGER NOT NULL DEFAULT 1")
    if "sleeve_id" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN sleeve_id INTEGER NOT NULL DEFAULT 1")
    if "body_build_id" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN body_build_id INTEGER NOT NULL DEFAULT 1")
    if "jersey_number" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN jersey_number INTEGER NOT NULL DEFAULT 24")
        # Give every existing player a stable number immediately. Signed players
        # are made unique within their current franchise; free agents get a
        # deterministic preferred number that can travel with them.
        for fr in c.execute("SELECT id FROM franchises ORDER BY id").fetchall():
            used=set()
            rows=c.execute("SELECT id FROM players WHERE franchise_id=? AND active=1 ORDER BY id",(fr["id"],)).fetchall()
            for idx,row in enumerate(rows,1):
                num=((idx-1)%99)+1
                while num in used:
                    num=(num%99)+1
                used.add(num)
                c.execute("UPDATE players SET jersey_number=? WHERE id=?",(num,row["id"]))
        c.execute("UPDATE players SET jersey_number=((id*7)%99)+1 WHERE franchise_id IS NULL")
    if "career_extension_through" not in player_cols:
        c.execute("ALTER TABLE players ADD COLUMN career_extension_through INTEGER NOT NULL DEFAULT 12")








    chat_cols={r["name"] for r in c.execute("PRAGMA table_info(chat_messages)").fetchall()}
    if "player_id" not in chat_cols:
        c.execute("ALTER TABLE chat_messages ADD COLUMN player_id INTEGER")








    # RC81 contract-renewal negotiation metadata. Existing free-agent offers remain
    # valid and default to FREE_AGENT; renewals use the same player-facing offer flow.
    offer_cols={r["name"] for r in c.execute("PRAGMA table_info(offers)").fetchall()}
    for col,ddl in {
        "offer_type":"TEXT NOT NULL DEFAULT 'FREE_AGENT'",
        "message":"TEXT NOT NULL DEFAULT ''",
        "effective_season":"INTEGER",
        "salary_basis":"TEXT NOT NULL DEFAULT ''",
        "proposed_role":"TEXT NOT NULL DEFAULT ''"
    }.items():
        if col not in offer_cols:
            c.execute(f"ALTER TABLE offers ADD COLUMN {col} {ddl}")








    news_cols={r["name"] for r in c.execute("PRAGMA table_info(news)").fetchall()}
    if "season" not in news_cols:
        c.execute("ALTER TABLE news ADD COLUMN season INTEGER NOT NULL DEFAULT 1")
        c.execute("""UPDATE news
                     SET season=(SELECT g.season FROM games g WHERE g.id=news.game_id)
                     WHERE game_id IS NOT NULL
                       AND EXISTS(SELECT 1 FROM games g WHERE g.id=news.game_id)""")








    lineup_cols={r["name"] for r in c.execute("PRAGMA table_info(lineups)").fetchall()}
    if "field_positions_json" not in lineup_cols:
        c.execute("ALTER TABLE lineups ADD COLUMN field_positions_json TEXT NOT NULL DEFAULT '{}'")
    branding_cols={r["name"] for r in c.execute("PRAGMA table_info(franchise_branding)").fetchall()}
    for col,ddl in {
        "city":"TEXT NOT NULL DEFAULT ''",
        "team_name":"TEXT NOT NULL DEFAULT ''",
        "primary_logo":"TEXT NOT NULL DEFAULT ''",
        "secondary_logo":"TEXT NOT NULL DEFAULT ''",
        "jersey_wordmark":"TEXT NOT NULL DEFAULT ''",
        "inseason_edit_season":"INTEGER"
    }.items():
        if col not in branding_cols:
            c.execute(f"ALTER TABLE franchise_branding ADD COLUMN {col} {ddl}")
    identity_history_cols={r["name"] for r in c.execute("PRAGMA table_info(franchise_identity_history)").fetchall()}
    if "jersey_wordmark" not in identity_history_cols:
        c.execute("ALTER TABLE franchise_identity_history ADD COLUMN jersey_wordmark TEXT")








    for row in c.execute("SELECT id,primary_pos,position_group FROM players").fetchall():
        expected=position_group_for_pos(row["primary_pos"])
        if not row["position_group"] or str(row["position_group"]).upper() not in POSITION_GROUPS or (row["position_group"]=="INF" and expected!="INF"):
            c.execute("UPDATE players SET position_group=? WHERE id=?",(expected,row["id"]))








    # Baserunning attribute migration: preserve every existing build and add
    # the new skills at zero so no current player loses or gains spent XP.
    for row in c.execute("SELECT id,attributes_json FROM players WHERE type='H'").fetchall():
        try:
            attrs=json.loads(row["attributes_json"] or "{}")
        except Exception:
            attrs={}
        changed=False
        for key in ("BRIQ","LEAD","CALL"):
            if key not in attrs:
                attrs[key]=0
                changed=True
        if changed:
            c.execute("UPDATE players SET attributes_json=? WHERE id=?",(json.dumps(attrs),row["id"]))








    # Genesis pitching model migration: H9/K9/BB9/HR9 are no longer
    # spendable outcome ratings. Preserve every previously spent point by
    # converting legacy points into physical pitching skills.
    for row in c.execute("SELECT id,attributes_json FROM players WHERE type='P'").fetchall():
        try:
            attrs=json.loads(row["attributes_json"] or "{}")
        except Exception:
            attrs={}
        legacy=sum(float(attrs.get(k,0) or 0) for k in ("H9","K9","BB9","HR9"))
        if legacy>0 or any(k in attrs for k in ("H9","K9","BB9","HR9")):
            h9=float(attrs.pop("H9",0) or 0)
            k9=float(attrs.pop("K9",0) or 0)
            bb9=float(attrs.pop("BB9",0) or 0)
            hr9=float(attrs.pop("HR9",0) or 0)
            ctrl_add=bb9+.25*h9+.40*hr9
            vel_add=.25*h9+.50*k9
            brk_add=legacy-ctrl_add-vel_add
            attrs["CTRL"]=float(attrs.get("CTRL",0) or 0)+ctrl_add
            attrs["VEL"]=float(attrs.get("VEL",0) or 0)+vel_add
            attrs["BRK"]=float(attrs.get("BRK",0) or 0)+brk_add
            c.execute("UPDATE players SET attributes_json=? WHERE id=?",(json.dumps(attrs),row["id"]))








    # Pitching depth expansion: new craft ratings are additive. Existing pitchers
    # receive them at zero, so their established CTRL/VEL/BRK behavior is preserved.
    for row in c.execute("SELECT id,attributes_json FROM players WHERE type='P'").fetchall():
        try:
            attrs=json.loads(row["attributes_json"] or "{}")
        except Exception:
            attrs={}
        changed=False
        for key in ("CMD","MOV","DEC","SEQ"):
            if key not in attrs:
                attrs[key]=0
                changed=True
        if changed:
            c.execute("UPDATE players SET attributes_json=? WHERE id=?",(json.dumps(attrs),row["id"]))








    # RC82: development-coach system now supports one free seasonal specialist plus
    # additional paid specialists with selectable intensity. Older databases used a
    # UNIQUE(franchise_id,season) table, so rebuild it in place while preserving every
    # historical coach and its already-applied milestones.
    development_coach_cols={r["name"] for r in c.execute("PRAGMA table_info(team_development_coaches)").fetchall()}
    development_coach_sql=(c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='team_development_coaches'").fetchone() or {"sql":""})["sql"] or ""
    needs_dev_coach_rebuild=(
        "coach_slot" not in development_coach_cols
        or "checkpoint_days_json" not in development_coach_cols
        or "UNIQUE(franchise_id,season)" in development_coach_sql.replace(" ","")
    )
    if needs_dev_coach_rebuild:
        old_rows=[dict(r) for r in c.execute("SELECT * FROM team_development_coaches ORDER BY season,franchise_id,id").fetchall()]
        c.execute("DROP TABLE IF EXISTS team_development_coaches_rc82")
        c.execute("""CREATE TABLE team_development_coaches_rc82(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          franchise_id TEXT NOT NULL,
          season INTEGER NOT NULL,
          coach_slot INTEGER NOT NULL DEFAULT 1,
          coach_type TEXT NOT NULL,
          attribute TEXT NOT NULL,
          cost REAL NOT NULL DEFAULT 0,
          is_free INTEGER NOT NULL DEFAULT 0,
          intensity INTEGER NOT NULL DEFAULT 1,
          checkpoint_days_json TEXT NOT NULL DEFAULT '[0,49,95]',
          applied_days_json TEXT NOT NULL DEFAULT '[]',
          hired_day INTEGER NOT NULL DEFAULT 0,
          start_applied INTEGER NOT NULL DEFAULT 0,
          midseason_applied INTEGER NOT NULL DEFAULT 0,
          endseason_applied INTEGER NOT NULL DEFAULT 0,
          hired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(franchise_id,season,coach_slot),
          UNIQUE(franchise_id,season,coach_type)
        )""")
        slots={}
        for row in old_rows:
            key=(str(row.get("franchise_id")),int(row.get("season") or 1))
            slot=slots.get(key,0)+1;slots[key]=slot
            applied=[]
            if int(row.get("start_applied") or 0): applied.append(0)
            if int(row.get("midseason_applied") or 0): applied.append(40)
            if int(row.get("endseason_applied") or 0): applied.append(REGULAR_SEASON_CALENDAR_DAYS)
            c.execute("""INSERT INTO team_development_coaches_rc82(
                         id,franchise_id,season,coach_slot,coach_type,attribute,cost,is_free,intensity,
                         checkpoint_days_json,applied_days_json,hired_day,start_applied,midseason_applied,endseason_applied,hired_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(
                         row.get("id"),row.get("franchise_id"),int(row.get("season") or 1),slot,
                         row.get("coach_type") or "SPEED",row.get("attribute") or "SPD",float(row.get("cost") or 0),
                         0,1,json.dumps([0,ALL_STAR_BREAK_DAY,REGULAR_SEASON_CALENDAR_DAYS]),json.dumps(applied),0,
                         int(row.get("start_applied") or 0),int(row.get("midseason_applied") or 0),int(row.get("endseason_applied") or 0),
                         row.get("hired_at") or datetime.datetime.utcnow().isoformat()))
        c.execute("DROP TABLE team_development_coaches")
        c.execute("ALTER TABLE team_development_coaches_rc82 RENAME TO team_development_coaches")
        c.execute("CREATE INDEX IF NOT EXISTS idx_team_development_coaches_team_season ON team_development_coaches(franchise_id,season)")








    franchise_cols={r["name"] for r in c.execute("PRAGMA table_info(franchises)")}
    for col,ddl in [
        ("xp_reserve","REAL NOT NULL DEFAULT 0"),
        ("training_level","INTEGER NOT NULL DEFAULT 0"),
        ("stadium_level","INTEGER NOT NULL DEFAULT 0"),
        ("scouting_level","INTEGER NOT NULL DEFAULT 0"),
        ("performance_level","INTEGER NOT NULL DEFAULT 0"),
        ("hq_level","INTEGER NOT NULL DEFAULT 0"),
        ("revenue_level","INTEGER NOT NULL DEFAULT 0"),
        ("seating_level","INTEGER NOT NULL DEFAULT 0"),
        ("concessions_level","INTEGER NOT NULL DEFAULT 0"),
        ("marketing_level","INTEGER NOT NULL DEFAULT 0"),
        ("sponsorships_level","INTEGER NOT NULL DEFAULT 0"),
        ("merchandising_level","INTEGER NOT NULL DEFAULT 0"),
        ("media_level","INTEGER NOT NULL DEFAULT 0"),
        ("recovery_level","INTEGER NOT NULL DEFAULT 0"),
        ("established_season","INTEGER")
    ]:
        if col not in franchise_cols:
            c.execute(f"ALTER TABLE franchises ADD COLUMN {col} {ddl}")
















    # Production-safe bootstrap accounts. Existing accounts are never changed.
    # A fresh database only creates these privileged users when an explicit
    # environment password is supplied; there are no predictable defaults.
    for username,env_key,role in [
        ("coach","EBL_BOOTSTRAP_COACH_PASSWORD","COACH"),
        ("commish","EBL_BOOTSTRAP_COMMISH_PASSWORD","COMMISSIONER")
    ]:
        if not c.execute("SELECT 1 FROM users WHERE username=?",(username,)).fetchone():
            password=os.environ.get(env_key,"").strip()
            if password:
                c.execute("INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",(username,pwhash(password),role))
















    TEAM_NAMES = [
        "Atlanta Scouts",
        "New York Empires",
        "Los Angeles Stars",
        "Chicago Wind",
        "Houston Apollos",
        "Phoenix Firebirds",
        "Philadelphia Founders",
        "San Antonio Defenders",
        "Birmingham Hammers",
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
















        # Preserve coach-created franchise identities across deploys/restarts.
        # Defaults only fill a truly blank legacy row; they never overwrite a rebrand.
        c.execute(
            "UPDATE franchises SET name=? WHERE id=? AND (name IS NULL OR TRIM(name)='')",
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
















        # Preserve an existing custom display name.
        c.execute(
            "UPDATE franchise_branding SET display_name=? WHERE franchise_id=? AND (display_name IS NULL OR TRIM(display_name)='')",
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
















    # RC84 one-time official branding seed. This fills only franchises that do not
    # already have uploaded artwork, so Atlanta/Birmingham/OKC and future coach
    # rebrands remain untouched. The seed key prevents later restarts from
    # re-applying league defaults over a coach's color-only customization.
    seeded=c.execute("SELECT v FROM league_config WHERE k=?",(OFFICIAL_BRAND_SEED_KEY,)).fetchone()
    if not seeded:
        for fid,brand in OFFICIAL_FRANCHISE_BRANDS.items():
            row=c.execute("""SELECT primary_logo,secondary_logo,jersey_wordmark,display_name,city,team_name,
                                    primary_color,secondary_color,accent_color
                               FROM franchise_branding WHERE franchise_id=?""",(fid,)).fetchone()
            art=official_brand_art(brand)
            existing_primary=str(row["primary_logo"] or "").strip() if row else ""
            existing_secondary=str(row["secondary_logo"] or "").strip() if row else ""
            existing_wordmark=str(row["jersey_wordmark"] or "").strip() if row else ""
            has_uploaded=bool(existing_primary or existing_secondary or existing_wordmark)
            display=(str(row["display_name"] or "").strip() if row and has_uploaded else "") or f"{brand['city']} {brand['team']}".strip()
            city=(str(row["city"] or "").strip() if row and has_uploaded else "") or brand["city"]
            team_name=(str(row["team_name"] or "").strip() if row and has_uploaded else "") or brand["team"]
            pc=(str(row["primary_color"] or "").strip() if row and has_uploaded else "") or brand["primary"]
            sc=(str(row["secondary_color"] or "").strip() if row and has_uploaded else "") or brand["secondary"]
            ac=(str(row["accent_color"] or "").strip() if row and has_uploaded else "") or brand["accent"]
            c.execute("""UPDATE franchise_branding
                         SET display_name=?,city=?,team_name=?,logo_style=?,
                             primary_logo=?,secondary_logo=?,jersey_wordmark=?,
                             primary_color=?,secondary_color=?,accent_color=?,
                             uniform_home=?,uniform_away=?,updated_at=CURRENT_TIMESTAMP
                         WHERE franchise_id=?""",
                      (display,city,team_name,int(brand["style"]),
                       existing_primary or art["primary"],existing_secondary or art["secondary"],existing_wordmark or art["wordmark"],
                       pc,sc,ac,brand["home"],brand["away"],fid))
            if not has_uploaded:
                c.execute("UPDATE franchises SET name=? WHERE id=?",(display,fid))
        c.execute("INSERT OR REPLACE INTO league_config(k,v) VALUES(?,?)",(OFFICIAL_BRAND_SEED_KEY,"1"))








    # RC98: division names are identities, not geography. Preserve team membership
    # while migrating old Atlantic/North/Central/South/West/Pacific labels in place.
    for old_div,new_div in DIVISION_RENAMES.items():
        c.execute("UPDATE franchise_seasons SET division=? WHERE division=?",(new_div,old_div))








    current_season_row=c.execute("SELECT v FROM league_state WHERE k='season'").fetchone()
    current_season=int(current_season_row["v"]) if current_season_row else 1
    ensure_season_membership(c,current_season)








    # One-time/defensive fatigue epoch migration. Older builds stored pitcher workload
    # without a season key, which could leak fatigue across a calendar rollover.
    workload_epoch=c.execute("SELECT v FROM league_state WHERE k='pitcher_workload_season'").fetchone()
    if not workload_epoch or int(workload_epoch["v"] or 0)!=current_season:
        c.execute("DELETE FROM pitcher_workload")
        c.execute("INSERT INTO league_state(k,v) VALUES('pitcher_workload_season',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(str(current_season),))
















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
                cur=c.execute("""INSERT INTO players(user_id,franchise_id,name,type,primary_pos,position_group,bats,throws,xp_wallet,attributes_json,season_json,status,active)
                                 VALUES(NULL,?,?,?,?,?,?,?,0,?,?,'SIGNED',1)""",
                              (fid,f"{FIRST_NAMES[((ti-1)*25+idx-1)%len(FIRST_NAMES)]} {LAST_NAMES[((ti-1)*25+idx*3)%len(LAST_NAMES)]}","H",pos,position_group_for_pos(pos),"R","R",json.dumps(attrs),json.dumps(hseason)))
                hids.append(cur.lastrowid)
            for idx,role in enumerate(["SP","SP","SP","SP","MR","SU","CL"],1):
                attrs=cpu_build(PITCHER_ATTRS,role,R)
                cur=c.execute("""INSERT INTO players(user_id,franchise_id,name,type,primary_pos,position_group,bats,throws,xp_wallet,attributes_json,season_json,status,active)
                                 VALUES(NULL,?,?,?,?,?,?,?,0,?,?,'SIGNED',1)""",
                              (fid,f"{FIRST_NAMES[((ti-1)*25+13+idx-1)%len(FIRST_NAMES)]} {LAST_NAMES[((ti-1)*25+39+idx*5)%len(LAST_NAMES)]}","P",role,position_group_for_pos(role),"R","R",json.dumps(attrs),json.dumps(pseason)))
                pids.append(cur.lastrowid)
            c.execute("UPDATE lineups SET batting_order_json=?,rotation_json=? WHERE franchise_id=?",(json.dumps(auto_batting_order(c,hids[:9])),json.dumps(pids[:4]),fid))
















        # RC98 Genesis schedule: the full 30-club EBL opens with 27 three-game
        # series across a 95-day calendar. Rebuild membership here because the
        # earlier defensive membership seed may have created an Original-Eight
        # placeholder before the fresh database had any schedule to inspect.
        genesis_ids=[f"EBL-F{i:02d}" for i in range(1,31)]
        c.execute("DELETE FROM franchise_seasons WHERE season=1")
        set_season_membership(c,1,genesis_ids)
        c.execute("INSERT INTO league_config(k,v) VALUES('active_team_count','30') ON CONFLICT(k) DO UPDATE SET v='30'")
        generate_season_schedule(c,1)
















        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('phase','RECRUITING')")
        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('alpha_cpu_fill','1')")
        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('auto_advance','0')")
        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('auto_advance_per_day','1')")
        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('auto_advance_next_at','0')")
        c.execute("INSERT OR IGNORE INTO league_config(k,v) VALUES('auto_advance_last_at','0')")
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
    # RC89 economy: active multi-year salary rises +0.01 XP/game at each season rollover.
    contract_cols={r["name"] for r in c.execute("PRAGMA table_info(contracts)").fetchall()}
    if "years_total" not in contract_cols:
        c.execute("ALTER TABLE contracts ADD COLUMN years_total INTEGER NOT NULL DEFAULT 1")
        c.execute("UPDATE contracts SET years_total=MAX(1,years_remaining)")
    if "starting_salary" not in contract_cols:
        c.execute("ALTER TABLE contracts ADD COLUMN starting_salary REAL NOT NULL DEFAULT 0.30")
        c.execute("UPDATE contracts SET starting_salary=salary")








    # Franchise economy migration.
    franchise_cols={r["name"] for r in c.execute("PRAGMA table_info(franchises)").fetchall()}
    for col,ddl in [("revenue_level","INTEGER NOT NULL DEFAULT 0"),("finish_reward","REAL NOT NULL DEFAULT 0"),("development_bonus","REAL NOT NULL DEFAULT 0"),("funding_growth","REAL NOT NULL DEFAULT 0"),("last_pool_growth","REAL NOT NULL DEFAULT 0")]:
        if col not in franchise_cols:
            c.execute(f"ALTER TABLE franchises ADD COLUMN {col} {ddl}")
    # RC73: startup/deploys must never reset an established club treasury.
    # xp_budget already has a schema default for brand-new franchises, and the
    # explicit Genesis reset / season rollover paths are responsible for
    # intentionally establishing a new season's treasury.
    # Preserving this value here protects multi-season XP banking across restarts.








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








def career_xp_surcharge(seasons_completed):
    # Career progression curve: first four completed seasons have no surcharge.
    # Seasons 5-8 cost +2 XP per attribute point; Season 9 costs +4,
    # then the surcharge rises by +1 XP for every additional season.
    seasons=max(0,int(seasons_completed or 0))
    if seasons<4:return 0
    if seasons<8:return 2
    return 4+(seasons-8)








def player_seasons_completed(c,player_id):
    row=c.execute(
        "SELECT COUNT(DISTINCT season) n FROM season_history WHERE player_id=?",
        (player_id,)
    ).fetchone()
    return int(row["n"] if row else 0)








def development_cost(value,seasons_completed):
    return attr_cost(value)+career_xp_surcharge(seasons_completed)








def veteran_extension_cost(seasons_completed):
    """Personal XP required to guarantee one more season after 12 completed years."""
    seasons=max(0,int(seasons_completed or 0))
    schedule={12:25.0,13:35.0,14:50.0,15:70.0,16:95.0,17:125.0}
    if seasons<12:return 0.0
    if seasons in schedule:return schedule[seasons]
    return 125.0 + 35.0*(seasons-17)








def extension_completed_seasons(c,player_id):
    completed=player_seasons_completed(c,player_id)
    state={r["k"]:r["v"] for r in c.execute("SELECT k,v FROM league_state WHERE k IN ('season','phase')")}
    if str(state.get("phase","REGULAR")).upper()=="OFFSEASON":
        season=int(state.get("season",1) or 1)
        already=c.execute("SELECT 1 FROM season_history WHERE player_id=? AND season=?",(player_id,season)).fetchone()
        pl=c.execute("SELECT active FROM players WHERE id=?",(player_id,)).fetchone()
        if pl and int(pl["active"] or 0)==1 and not already:
            completed+=1
    return completed








def veteran_retirement_due(c,player_id):
    row=c.execute("SELECT user_id,career_extension_through,active FROM players WHERE id=?",(player_id,)).fetchone()
    if not row or not int(row["active"] or 0):return False
    completed=player_seasons_completed(c,player_id)
    if completed<12:return False
    if row["user_id"] is None:return True
    through=int(row["career_extension_through"] or 12)
    return through < completed+1








REVENUE_BRANCH_COLUMNS={
    "seating":"seating_level",
    "concessions":"concessions_level",
    "marketing":"marketing_level",
    "sponsorships":"sponsorships_level",
    "merchandising":"merchandising_level",
    "media":"media_level",
}
def revenue_upgrade_levels(fr):
    # Total purchased branch levels, retained for coach UI/history.
    legacy=int(fr.get("revenue_level",0) or 0)
    branches=sum(int(fr.get(col,0) or 0) for col in REVENUE_BRANCH_COLUMNS.values())
    return legacy+branches








def revenue_upgrade_bonus(fr):
    """RC92: permanent annual revenue generated by franchise investments.








    Each named branch has five levels. Its annual funding at Levels 1-5 is
    +5, +10, +20, +40, +80 XP respectively. Legacy generic revenue levels
    retain their historical +5 XP/level value so old saves are never nerfed.
    """
    legacy=5.0*int(fr.get("revenue_level",0) or 0)
    branch_bonus=0.0
    for col in REVENUE_BRANCH_COLUMNS.values():
        level=max(0,min(REVENUE_BRANCH_MAX,int(fr.get(col,0) or 0)))
        branch_bonus+=REVENUE_UPGRADE_BONUSES[level]
    return round(legacy+branch_bonus,3)








def annual_team_budget(fr):
    growth=float(fr.get("funding_growth",0) or 0)
    return round(TEAM_BUDGET + growth + revenue_upgrade_bonus(fr),3)








def signing_pool_state(c, fid, exclude_offer_id=None):
    """RC61: dynamic annual club economy.








    xp_budget is the club's complete spendable amount for the season after
    annual funding, revenue upgrades, finish rewards and prior-year rollover.
    Actual signed contract salaries are protected for the full 81-game season.
    Empty/CPU roster jobs are protected at league minimum. OPEN/HELD offers
    reserve their bonus plus any salary obligation above the salary already
    protected for the roster job they would occupy.
    """
    fr=c.execute("SELECT xp_budget FROM franchises WHERE id=?",(fid,)).fetchone()
    budget=float(fr["xp_budget"] if fr else TEAM_BUDGET)








    contracts=c.execute(
        """SELECT co.player_id,co.salary,p.type
           FROM contracts co
           LEFT JOIN players p ON p.id=co.player_id
           WHERE co.franchise_id=?""",(fid,)
    ).fetchall()
    signed_count=len(contracts)
    signed_payroll=sum(float(r["salary"] or SALARY_MIN)*REGULAR_SEASON_GAMES for r in contracts)
    open_jobs=max(0,ACTIVE_ROSTER_SIZE-signed_count)
    open_job_floor=open_jobs*SALARY_MIN*REGULAR_SEASON_GAMES
    protected_payroll=signed_payroll+open_job_floor








    q="""SELECT COALESCE(SUM(
             bonus +
             CASE WHEN salary>? THEN (salary-?)*? ELSE 0 END
           ),0) x
         FROM offers
         WHERE franchise_id=? AND status IN ('OPEN','HELD')
           AND UPPER(COALESCE(offer_type,'FREE_AGENT'))!='RENEWAL'"""
    args=[SALARY_MIN,SALARY_MIN,REGULAR_SEASON_GAMES,fid]
    if exclude_offer_id is not None:
        q += " AND id<>?"; args.append(int(exclude_offer_id))
    offered=c.execute(q,tuple(args)).fetchone()
    reserved=float(offered["x"] or 0)








    available=max(0.0,budget-protected_payroll-reserved)
    return {
        "budget":round(budget,3),
        "signed_payroll":round(signed_payroll,3),
        "open_job_minimum_reserve":round(open_job_floor,3),
        "protected_payroll":round(protected_payroll,3),
        "reserved":round(reserved,3),
        "available":round(available,3)
    }
















def team_finance_snapshot(c,fid):
    """RC61 finance card values: funding, payroll floor, commitments, spending room."""
    state=signing_pool_state(c,fid)
    fr=c.execute("SELECT xp_spent,revenue_level,finish_reward FROM franchises WHERE id=?",(fid,)).fetchone()
    state.update({
        "xp_spent_to_date":round(float(fr["xp_spent"] or 0),3) if fr else 0.0,
        "revenue_level":int(fr["revenue_level"] or 0) if fr else 0,
        "finish_reward":round(float(fr["finish_reward"] or 0),3) if fr else 0.0
    })
    return state








def reserve_cap(fr):
    return float("inf")








def upgrade_cost(level):
    level=max(0,min(REVENUE_BRANCH_MAX-1,int(level or 0)))
    return REVENUE_UPGRADE_COSTS[level]








def franchise_development_multiplier(c,fid):
    # Rebuild/development bonuses are earned from a completed season and therefore
    # cannot affect Genesis Season 1. This guard also neutralizes stale alpha data
    # that may survive an older reset.
    if _season_number(c)<=1:
        return 1.0
    row=c.execute("SELECT development_bonus FROM franchises WHERE id=?",(fid,)).fetchone()
    return 1.0 + (float(row["development_bonus"] or 0) if row else 0.0)








def apply_finish_economy(c,season,active_ids):
    ids=list(active_ids or [])
    if not ids:return []
    champ_row=c.execute("SELECT v FROM league_state WHERE k='champion'").fetchone()
    champion=str(champ_row["v"] or "") if champ_row else ""
    standings=[]
    for fid in ids:
        r=c.execute("SELECT wins,losses FROM franchises WHERE id=?",(fid,)).fetchone()
        standings.append((fid,int(r["wins"] or 0),int(r["losses"] or 0)))
    standings.sort(key=lambda x:(x[1],-x[2]),reverse=True)
    if champion and champion in ids:
        standings=[x for x in standings if x[0]==champion]+[x for x in standings if x[0]!=champion]
    n=len(standings);out=[]
    top_cut=max(1,math.ceil(n/3))
    middle_cut=max(top_cut,math.ceil(2*n/3))
    for rank,(fid,w,l) in enumerate(standings,1):
        frac=0.0 if n<=1 else (n-rank)/(n-1)
        reward=round(FINISH_REWARD_MIN + (FINISH_REWARD_MAX-FINISH_REWARD_MIN)*frac,3)
        dev=round(REBUILD_XP_MAX*(1.0-frac),5)
        growth=POOL_GROWTH_TOP if rank<=top_cut else POOL_GROWTH_MIDDLE if rank<=middle_cut else POOL_GROWTH_BOTTOM
        c.execute("""UPDATE franchises
                     SET xp_reserve=xp_reserve+?,finish_reward=?,development_bonus=?,
                         funding_growth=funding_growth+?,last_pool_growth=?
                     WHERE id=?""",(reward,reward,dev,growth,growth,fid))
        out.append({"franchise_id":fid,"rank":rank,"reward":reward,"development_bonus":dev,"pool_growth":growth})
    return out








def notify_user(c,user_id,kind,title,body="",ref_id=None):
    if not user_id:return
    c.execute("INSERT INTO notifications(user_id,type,title,body,ref_id) VALUES(?,?,?,?,?)",
              (int(user_id),str(kind),str(title),str(body),None if ref_id is None else str(ref_id)))








def award_player(c,season,period,code,name,pid,xp,detail=None,announce=True):
    pl=c.execute("SELECT id,user_id,franchise_id,name FROM players WHERE id=?",(pid,)).fetchone()
    if not pl:return False
    awarded_xp=float(xp) if pl["user_id"] is not None else 0.0
    try:
        cur=c.execute("""INSERT INTO award_history(season,period,award_code,award_name,player_id,franchise_id,xp_awarded,detail_json)
                         VALUES(?,?,?,?,?,?,?,?)""",
                      (season,period,code,name,pid,pl["franchise_id"],awarded_xp,json.dumps(detail or {})))
    except sqlite3.IntegrityError:
        return False
    # RC76: CPU fillers may produce stats, but they are infrastructure rather than
    # developing careers. Only human-owned players receive award XP.
    if awarded_xp:
        c.execute("UPDATE players SET xp_wallet=xp_wallet+? WHERE id=?",(awarded_xp,pid))
        c.execute("INSERT INTO xp_ledger(player_id,event_type,xp,detail_json) VALUES(?,?,?,?)",
                  (pid,"AWARD",awarded_xp,json.dumps({"season":season,"period":period,"award":name,**(detail or {})})))
    notify_user(c,pl["user_id"],"AWARD",f"{name}: +{awarded_xp:g} XP",f"{pl['name']} earned {name}.",str(pid))
    if announce:
        team=c.execute("SELECT name FROM franchises WHERE id=?",(pl["franchise_id"],)).fetchone() if pl["franchise_id"] else None
        team_name=team["name"] if team else "Free Agent"
        if detail and isinstance(detail.get("days"),list) and detail.get("days"):
            news_day=int(detail["days"][-1])
        else:
            news_day=REGULAR_SEASON_CALENDAR_DAYS if period=="REGULAR_SEASON" else int((c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone() or {'v':0})["v"] or 0)
        post_news(c,"AWARD",f"🏆 {pl['name']} wins {name}",
                  f"{pl['name']} of the {team_name} has been named {name} for Season {season}" + (f" and earns +{awarded_xp:g} XP." if awarded_xp else "."),
                  news_day,pl["franchise_id"],pid,None,4,season=season)
    return True
















def grant_player_bonus_once(c,season,bonus_code,pid,xp,detail=None,title=None):
    """Idempotent human-player bonus used for postseason advancement and exhibitions."""
    pl=c.execute("SELECT id,user_id,franchise_id,name FROM players WHERE id=?",(int(pid),)).fetchone()
    if not pl or pl["user_id"] is None:return False
    try:
        c.execute("""INSERT INTO player_bonus_history(season,bonus_code,player_id,franchise_id,xp_awarded,detail_json)
                     VALUES(?,?,?,?,?,?)""",
                  (int(season),str(bonus_code),int(pid),pl["franchise_id"],float(xp),json.dumps(detail or {})))
    except sqlite3.IntegrityError:
        return False
    c.execute("UPDATE players SET xp_wallet=xp_wallet+? WHERE id=?",(float(xp),int(pid)))
    c.execute("INSERT INTO xp_ledger(player_id,event_type,xp,detail_json) VALUES(?,?,?,?)",
              (int(pid),"BONUS",float(xp),json.dumps({"season":int(season),"code":str(bonus_code),**(detail or {})})))
    label=title or str(bonus_code).replace("_"," ").title()
    notify_user(c,pl["user_id"],"BONUS",f"{label}: +{float(xp):g} XP",f"{pl['name']} earned +{float(xp):g} XP.",str(pid))
    return True
















def grant_roster_bonus(c,season,bonus_code,franchise_ids,xp,label,league_day):
    team_ids=[str(x) for x in franchise_ids if x]
    if not team_ids:return 0
    q=",".join("?" for _ in team_ids)
    rows=c.execute(f"""SELECT DISTINCT p.id,p.franchise_id
                       FROM roster_slots rs JOIN players p ON p.id=rs.player_id
                       WHERE rs.franchise_id IN ({q}) AND p.active=1 AND p.status='SIGNED' AND p.user_id IS NOT NULL""",team_ids).fetchall()
    made=0
    for row in rows:
        if grant_player_bonus_once(c,season,bonus_code,row["id"],xp,{"stage":label,"league_day":int(league_day)},label):made+=1
    names=[r["name"] for r in c.execute(f"SELECT name FROM franchises WHERE id IN ({q}) ORDER BY name",team_ids)]
    if names:
        post_news(c,"POSTSEASON",label,f"{', '.join(names)} — qualifying human roster players receive +{float(xp):g} XP.",league_day,None,None,None,3,season=season)
    return made
















def _all_star_hitter_score(st):
    pa=int(st.get("PA",0) or 0);ab=int(st.get("AB",0) or 0);h=int(st.get("H",0) or 0);bb=int(st.get("BB",0) or 0)
    tb=int(st.get("1B",0) or 0)+2*int(st.get("2B",0) or 0)+3*int(st.get("3B",0) or 0)+4*int(st.get("HR",0) or 0)
    obp=(h+bb)/pa if pa else 0;slg=tb/ab if ab else 0
    return (obp+slg)*100+int(st.get("HR",0) or 0)*1.1+int(st.get("RBI",0) or 0)*.12+int(st.get("SB",0) or 0)*.25
















def _all_star_pitcher_score(st):
    outs=int(st.get("OUTS",0) or 0)
    return int(st.get("SO",0) or 0)*1.2-int(st.get("ER",0) or 0)*2.2-int(st.get("BB",0) or 0)*.7+(outs/3)*.3+int(st.get("SV",0) or 0)*.7
















def _all_star_pool(c):
    rows=[]
    for r in c.execute("""SELECT p.id,p.name,p.user_id,u.username,p.franchise_id,p.type,p.primary_pos,p.attributes_json,p.season_json
                          FROM players p LEFT JOIN users u ON u.id=p.user_id
                          WHERE p.active=1 AND p.status='SIGNED'"""):
        d=dict(r)
        try:d["stats"]=json.loads(d.pop("season_json") or "{}")
        except Exception:d["stats"]={}
        try:d["attrs"]=json.loads(d.pop("attributes_json") or "{}")
        except Exception:d["attrs"]={}
        d["score"]=_all_star_pitcher_score(d["stats"]) if d["type"]=="P" else _all_star_hitter_score(d["stats"])
        rows.append(d)
    return rows
















def _select_all_stars(c):
    pool=_all_star_pool(c);hit=[x for x in pool if x["type"]=="H"];pit=[x for x in pool if x["type"]=="P"]
    selected=[];used=set()
    # Two representatives at each field position gives each side a real starting nine.
    for pos in ("C","1B","2B","3B","SS","LF","CF","RF"):
        cand=sorted([x for x in hit if x["primary_pos"]==pos],key=lambda x:x["score"],reverse=True)
        for x in cand[:2]:
            if x["id"] not in used:selected.append(x);used.add(x["id"])
    for x in sorted(hit,key=lambda x:x["score"],reverse=True):
        if len(selected)>=18:break
        if x["id"] not in used:selected.append(x);used.add(x["id"])
    sp=sorted([x for x in pit if x["primary_pos"]=="SP"],key=lambda x:x["score"],reverse=True)[:8]
    rp=sorted([x for x in pit if x["primary_pos"]!="SP"],key=lambda x:x["score"],reverse=True)[:4]
    pitchers=sp+rp
    if len(pitchers)<12:
        have={x["id"] for x in pitchers}
        pitchers += [x for x in sorted(pit,key=lambda x:x["score"],reverse=True) if x["id"] not in have][:12-len(pitchers)]
    # Alternate ranked pairs to keep Gold/Red reasonably balanced.
    gold_h=[];red_h=[]
    for i,x in enumerate(selected[:18]):(gold_h if i%2==0 else red_h).append(x)
    gold_p=[];red_p=[]
    for i,x in enumerate(pitchers[:12]):(gold_p if i%2==0 else red_p).append(x)
    return {"GOLD":{"hitters":gold_h,"pitchers":gold_p},"RED":{"hitters":red_h,"pitchers":red_p}}
















def _clamp(v,lo,hi):return max(lo,min(hi,v))
















def _simulate_all_star_side(c,batters,pitchers,opp_pitchers,rng):
    hlines={x["id"]:{"PA":4,"AB":0,"H":0,"1B":0,"2B":0,"3B":0,"HR":0,"BB":0,"SO":0,"R":0,"RBI":0,"SB":0,"CS":0} for x in batters}
    plines={x["id"]:{"G":1,"GS":1 if i==0 else 0,"OUTS":6 if i<3 else 3,"H":0,"ER":0,"BB":0,"SO":0,"W":0,"L":0,"SV":0} for i,x in enumerate(pitchers)}
    runs=0
    for i,b in enumerate(batters):
        line=hlines[b["id"]];a=b.get("attrs",{});opp=opp_pitchers[i%len(opp_pitchers)] if opp_pitchers else {"attrs":{}}
        pa=4+rng.randint(0,1);line["PA"]=pa
        pa_attrs=opp.get("attrs",{})
        con=float(a.get("CON",0) or 0);powr=float(a.get("POW",0) or 0);disc=float(a.get("DISC",0) or 0);tim=float(a.get("TIM",0) or 0)
        ctrl=float(pa_attrs.get("CTRL",0) or 0);mov=float(pa_attrs.get("MOV",0) or 0);brk=float(pa_attrs.get("BRK",0) or 0)
        for _ in range(pa):
            walk=_clamp(.07+(disc-ctrl)*.0012,.03,.16)
            hit=_clamp(.205+(con+tim-mov-brk)*.0010,.12,.36)
            hr=_clamp(.018+(powr-mov)*.0009,.005,.10)
            r=rng.random()
            if r<walk:
                line["BB"]+=1
            else:
                line["AB"]+=1
                if r<walk+hr:
                    line["H"]+=1;line["HR"]+=1;line["R"]+=1;line["RBI"]+=1;runs+=1
                elif r<walk+hit:
                    line["H"]+=1
                    x=rng.random()
                    if x<.18:line["2B"]+=1
                    elif x<.205:line["3B"]+=1
                    else:line["1B"]+=1
                    if rng.random()<.22:line["R"]+=1;runs+=1
                    if rng.random()<.28:line["RBI"]+=1
                elif rng.random()<.30:
                    line["SO"]+=1
        if rng.random()<.18 and float(a.get("SPD",0) or 0)>=15:line["SB"]+=1
    # Make pitcher lines reflect the exhibition run environment closely enough for GPS.
    total_outs=sum(x["OUTS"] for x in plines.values()) or 27
    for p in pitchers:
        line=plines[p["id"]];share=line["OUTS"]/total_outs;attrs=p.get("attrs",{})
        line["ER"]=max(0,int(round(runs*share+rng.uniform(-.5,.5))))
        line["H"]=max(line["ER"],int(round((5+runs*.65)*share+rng.uniform(0,1))))
        line["BB"]=max(0,int(round((2.5-float(attrs.get("CTRL",0) or 0)*.015)*share+rng.uniform(0,.7))))
        line["SO"]=max(0,int(round((6+float(attrs.get("VEL",0) or 0)*.03+float(attrs.get("BRK",0) or 0)*.02)*share+rng.uniform(0,1))))
    return runs,hlines,plines
















def process_all_star_game(c,season,league_day):
    if int(league_day)!=ALL_STAR_BREAK_DAY:return None
    existing=c.execute("SELECT * FROM all_star_games WHERE season=?",(int(season),)).fetchone()
    if existing:return dict(existing)
    sides=_select_all_stars(c)
    if len(sides["GOLD"]["hitters"])<9 or len(sides["RED"]["hitters"])<9 or not sides["GOLD"]["pitchers"] or not sides["RED"]["pitchers"]:
        return None
    all_selected=sides["GOLD"]["hitters"]+sides["GOLD"]["pitchers"]+sides["RED"]["hitters"]+sides["RED"]["pitchers"]
    for pl in all_selected:
        award_player(c,season,"ALL_STAR","ALL_STAR_SELECTION","EBL All-Star",pl["id"],ALL_STAR_SELECTION_XP,{"league_day":int(league_day)},announce=False)
    rng=random.Random(int(season)*100003+int(league_day)*97)
    gr,gh,gp=_simulate_all_star_side(c,sides["GOLD"]["hitters"],sides["GOLD"]["pitchers"],sides["RED"]["pitchers"],rng)
    rr,rh,rp=_simulate_all_star_side(c,sides["RED"]["hitters"],sides["RED"]["pitchers"],sides["GOLD"]["pitchers"],rng)
    if gr==rr:gr+=1
    # Pitcher GPS must reflect runs allowed by the opponent, not runs scored by his own side.
    for pitlines,pitchers,runs_allowed in ((gp,sides["GOLD"]["pitchers"],rr),(rp,sides["RED"]["pitchers"],gr)):
        total_outs=sum(int(x.get("OUTS",0) or 0) for x in pitlines.values()) or 27
        for pch in pitchers:
            line=pitlines[pch["id"]];share=int(line.get("OUTS",0) or 0)/total_outs;attrs=pch.get("attrs",{})
            line["ER"]=max(0,int(round(runs_allowed*share+rng.uniform(-.5,.5))))
            line["H"]=max(line["ER"],int(round((5+runs_allowed*.65)*share+rng.uniform(0,1))))
            line["BB"]=max(0,int(round((2.5-float(attrs.get("CTRL",0) or 0)*.015)*share+rng.uniform(0,.7))))
            line["SO"]=max(0,int(round((6+float(attrs.get("VEL",0) or 0)*.03+float(attrs.get("BRK",0) or 0)*.02)*share+rng.uniform(0,1))))
    winner="GOLD" if gr>rr else "RED"
    for side,hitlines,pitlines in (("GOLD",gh,gp),("RED",rh,rp)):
        by_id={x["id"]:x for x in sides[side]["hitters"]+sides[side]["pitchers"]}
        for pid,line in hitlines.items():
            xp=gps_xp(hitter_gps(line))
            grant_player_bonus_once(c,season,"ALL_STAR_GAME",pid,xp,{"side":side,"gps":round(hitter_gps(line),1),"league_day":int(league_day)},"All-Star Game XP")
        for pid,line in pitlines.items():
            pl=by_id.get(pid,{});sp=str(pl.get("primary_pos",""))=="SP";xp=round(gps_xp(pitcher_gps(line,sp))*(SP_XP_MULTIPLIER if sp else RP_XP_MULTIPLIER),3)
            grant_player_bonus_once(c,season,"ALL_STAR_GAME",pid,xp,{"side":side,"gps":round(pitcher_gps(line,sp),1),"league_day":int(league_day)},"All-Star Game XP")
    def slim(rows):return [{"id":x["id"],"name":x["name"],"username":x.get("username"),"franchise_id":x["franchise_id"],"type":x["type"],"primary_pos":x["primary_pos"]} for x in rows]
    box={"gold":{"hitters":gh,"pitchers":gp},"red":{"hitters":rh,"pitchers":rp},"winner":winner}
    c.execute("""INSERT INTO all_star_games(season,league_day,gold_runs,red_runs,gold_roster_json,red_roster_json,box_json)
                 VALUES(?,?,?,?,?,?,?)""",(int(season),int(league_day),int(gr),int(rr),json.dumps(slim(sides["GOLD"]["hitters"]+sides["GOLD"]["pitchers"])),json.dumps(slim(sides["RED"]["hitters"]+sides["RED"]["pitchers"])),json.dumps(box)))
    post_news(c,"ALL_STAR",f"⭐ Gold All-Stars {gr}, Red All-Stars {rr}",f"Season {season}'s EBL All-Star Game is final. Every selection earns +{ALL_STAR_SELECTION_XP:g} XP and an All-Star badge; human participants also earn game-performance XP.",int(league_day),None,None,None,4,season=season)
    return {"season":season,"league_day":league_day,"gold_runs":gr,"red_runs":rr,"winner":winner}
















def process_quarter_awards(c,season,end_day):
    # RC98 calendar checkpoints land only after every club has completed a full
    # series block: 21, 42, 60 and 81 games respectively. Off days therefore
    # never give one club an extra award-window game.
    windows={24:1,49:25,70:50,95:71}
    if end_day not in windows:return []
    start_day=windows[end_day]
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








def fielding_award_metrics(st):
    fg=int(st.get("FG",0) or 0)
    po=int(st.get("PO",0) or 0)
    assists=int(st.get("A",0) or 0)
    errors=int(st.get("E",0) or 0)
    dp=int(st.get("DP",0) or 0)
    chances=po+assists+errors
    fld_pct=((po+assists)/chances) if chances else None
    oaa=float(st.get("OAA",0) or 0)
    score=(
        oaa*4.0
        + ((fld_pct-.900)*12.0 if fld_pct is not None else 0.0)
        - errors*.35
        + dp*.08
        + min(chances,300)*.002
    )
    return {
        "fg":fg,"po":po,"a":assists,"e":errors,"dp":dp,"ch":chances,
        "fld_pct":fld_pct,"oaa":oaa,"fielding_score":round(score,4)
    }








def fielding_award_min_games(team_games):
    return max(1,int((max(1,int(team_games))+1)*.5))








def fielding_award_sort_key(x):
    return (
        float(x.get("fielding_score",0) or 0),
        float(x.get("oaa",0) or 0),
        float(x.get("fld_pct_num",-1) if x.get("fld_pct_num") is not None else -1),
        -int(x.get("e",0) or 0),
        int(x.get("dp",0) or 0),
        int(x.get("ch",0) or 0)
    )








def process_season_awards(c,season):
    period="REGULAR_SEASON"
    if c.execute("SELECT 1 FROM award_history WHERE season=? AND period=? LIMIT 1",(season,period)).fetchone():return []
    hitters=[];pitchers=[]
    for r in c.execute("SELECT id,primary_pos,attributes_json,season_json FROM players WHERE active=1"):
        st=json.loads(r["season_json"] or "{}")
        if "PA" in st:
            ab=st.get("AB",0);h=st.get("H",0);bb=st.get("BB",0);pa=st.get("PA",0);tb=st.get("1B",0)+2*st.get("2B",0)+3*st.get("3B",0)+4*st.get("HR",0)
            avg=h/ab if ab else 0;obp=(h+bb)/pa if pa else 0;slg=tb/ab if ab else 0
            fm=fielding_award_metrics(st)
            hitters.append({"id":r["id"],"pos":r["primary_pos"],"avg":avg,"ops":obp+slg,"pa":pa,"hr":st.get("HR",0),"rbi":st.get("RBI",0),"sb":st.get("SB",0),
                            "oaa":fm["oaa"],"e":fm["e"],"fg":fm["fg"],"po":fm["po"],"a":fm["a"],"dp":fm["dp"],"ch":fm["ch"],
                            "fld_pct_num":fm["fld_pct"],"fielding_score":fm["fielding_score"],"attrs":json.loads(r["attributes_json"] or "{}")})
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
        field_min_games=fielding_award_min_games(81)
        for pos in ["C","1B","2B","3B","SS","LF","CF","RF"]:
            pool=[x for x in hitters if x["pos"]==pos and x.get("fg",0)>=field_min_games]
            if not pool:
                pool=[x for x in hitters if x["pos"]==pos and x.get("fg",0)>0]
            if pool:
                f=max(pool,key=fielding_award_sort_key)
                if award_player(c,season,period,f"FIELD_{pos}",f"{pos} Fielding Title",f["id"],10,{
                    "FG":f.get("fg",0),"CH":f.get("ch",0),"PO":f.get("po",0),"A":f.get("a",0),"E":f.get("e",0),
                    "DP":f.get("dp",0),"OAA":f.get("oaa",0),"FLD_PCT":f.get("fld_pct_num"),"FIELDING_SCORE":f.get("fielding_score",0)
                }):made.append(f"FIELD_{pos}")
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
        return ["Heritage","Pioneer"]
    if team_count<=16:
        return ["Heritage","Liberty","Frontier","Pioneer"]
    if team_count<=24:
        return ["Heritage","Liberty","Union","Frontier"]
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
        # Fresh/rebuilt seasons honor the Commissioner-selected league size.
        # Fall back to the Original Eight only when no preference has been saved.
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








def auto_batting_order(c,hitter_ids):
    """Build a baseball-style batting order from the nine active hitters.








    The goal is not to simply mirror defensive positions. We favor on-base ability
    and speed at the top, the best complete bats in the 2/3 holes, power in the
    heart of the order, then sort the remaining bats by offensive quality.
    Coaches can still overwrite this order manually.
    """
    hitters=[]
    for pid in hitter_ids:
        r=c.execute("SELECT id,attributes_json FROM players WHERE id=?",(int(pid),)).fetchone()
        if not r:
            continue
        a=json.loads(r["attributes_json"] or "{}")
        con=float(a.get("CON",0) or 0); powr=float(a.get("POW",0) or 0)
        vis=float(a.get("VIS",0) or 0); disc=float(a.get("DISC",0) or 0)
        tim=float(a.get("TIM",0) or 0); spd=float(a.get("SPD",0) or 0)
        briq=float(a.get("BRIQ",0) or 0); lead=float(a.get("LEAD",0) or 0)
        onbase=con*.34+vis*.26+disc*.26+tim*.14
        contact=con*.40+vis*.30+tim*.20+disc*.10
        power=powr*.62+tim*.18+con*.12+disc*.08
        speed=spd*.60+briq*.25+lead*.15
        offense=con*.24+powr*.25+vis*.16+disc*.14+tim*.16+spd*.05
        hitters.append({"id":int(pid),"onbase":onbase,"contact":contact,"power":power,"speed":speed,"offense":offense})
    if len(hitters)!=9:
        return [int(x) for x in hitter_ids][:9]








    remaining=hitters[:]
    def take(key):
        best=max(remaining,key=key)
        remaining.remove(best)
        return best["id"]








    # 1: reach base + speed. 2: best bat-to-ball/on-base blend.
    # 3: best complete hitter. 4/5: power core. Remaining hitters descend by offense.
    order=[]
    order.append(take(lambda h:h["onbase"]*.72+h["speed"]*.28))
    order.append(take(lambda h:h["contact"]*.56+h["onbase"]*.34+h["speed"]*.10))
    order.append(take(lambda h:h["offense"]*.72+h["onbase"]*.28))
    order.append(take(lambda h:h["power"]*.72+h["offense"]*.28))
    order.append(take(lambda h:h["power"]*.55+h["offense"]*.45))
    remaining.sort(key=lambda h:h["offense"],reverse=True)
    order.extend(h["id"] for h in remaining)
    return order
















def auto_pitching_plan(c,fid):
    """Return an unmanaged club's rotation and bullpen ranked by pitcher OVR.








    Starting-pitcher roster slots compete with other SP slots; relief-pitcher
    roster slots compete with other RP slots. This keeps a human RP who joins a
    CPU-managed team from being stranded outside stale bullpen JSON.
    """
    rows=c.execute(
        """SELECT rs.position_group,p.id,p.primary_pos,p.attributes_json
             FROM roster_slots rs
             JOIN players p ON p.id=rs.player_id
            WHERE rs.franchise_id=?
              AND rs.position_group IN ('SP','RP')
              AND p.type='P' AND p.active=1 AND p.status='SIGNED'""",
        (fid,)
    ).fetchall()
    starters=[]; relievers=[]
    for r in rows:
        attrs=json.loads(r["attributes_json"] or "{}")
        pid=int(r["id"])
        if r["position_group"]=="SP":
            ovr=player_overall_from_attrs(attrs,"P","SP")
            starters.append((ovr,pid))
        else:
            role=r["primary_pos"] if r["primary_pos"] in ("RP","MR","LR","SU","CL") else "RP"
            ovr=player_overall_from_attrs(attrs,"P",role)
            relievers.append((ovr,pid))
    starters.sort(reverse=True)
    relievers.sort(reverse=True)
    rotation=[pid for _,pid in starters[:5]]
    rp=[pid for _,pid in relievers]
    bullpen={
        "CL":rp[0] if len(rp)>0 else None,
        "SU1":rp[1] if len(rp)>1 else None,
        "SU2":None,
        "MR":[rp[2]] if len(rp)>2 else ([rp[1]] if len(rp)>1 else rp[:1]),
        "LR":[rp[2]] if len(rp)>2 else rp[-1:] if rp else [],
        "EMERGENCY":list(reversed(rp))
    }
    return rotation,bullpen
















def enforce_active_rosters(c,season=None):
    # 16-player active roster: every hitter has an everyday lineup job.
    template=["C","1B","2B","3B","SS","LF","CF","RF","DH","SP","SP","SP","SP","RP","RP","RP"]
    season=_season_number(c) if season is None else int(season)
    for fid in active_franchise_ids(c,season):
        # Preserve the club's current fielding/roster role for human players. Preferred
        # position is player identity; roster_slots is the coach/team assignment.
        existing_roles={int(x["player_id"]):str(x["position_group"] or "").upper() for x in c.execute("SELECT player_id,position_group FROM roster_slots WHERE franchise_id=? AND player_id IS NOT NULL",(fid,)).fetchall()}
        rows=[dict(x) for x in c.execute("SELECT * FROM players WHERE franchise_id=? AND active=1 AND status='SIGNED' ORDER BY CASE WHEN user_id IS NOT NULL THEN 0 ELSE 1 END,id",(fid,))]
        humans=[x for x in rows if x.get("user_id") is not None]
        cpus=[x for x in rows if x.get("user_id") is None]
        # RC76: CPU fillers are fixed rookie infrastructure. Purge any legacy XP
        # they may have accumulated under older builds.
        if cpus:
            c.executemany("UPDATE players SET xp_wallet=0 WHERE id=?",[(x["id"],) for x in cpus])
            for x in cpus:x["xp_wallet"]=0
        slots=[None]*len(template)
        def place(pl):
            allowed=eligible_roster_slot_groups(pl)
            current_role=existing_roles.get(int(pl["id"])) if pl.get("user_id") is not None else None
            if current_role in allowed:
                allowed=[current_role]+[x for x in allowed if x!=current_role]
            choices=[]
            for grp in allowed:
                choices.extend(i for i,t in enumerate(template) if t==grp and slots[i] is None and i not in choices)
            if choices:
                slots[choices[0]]=pl;return True
            return False
        overflow=[]
        for pl in humans:
            if not place(pl):overflow.append(pl)
        # RC57: impossible legacy overflow cannot remain as a hidden bench.
        for pl in overflow:
            c.execute("DELETE FROM contracts WHERE player_id=?",(pl["id"],))
            c.execute("UPDATE players SET franchise_id=NULL,status='FREE_AGENT' WHERE id=?",(pl["id"],))
            c.execute("UPDATE offers SET status='CANCELLED_ROSTER_FULL' WHERE player_id=? AND status IN ('OPEN','HELD')",(pl["id"],))
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
            cur=c.execute("""INSERT INTO players(user_id,franchise_id,name,type,primary_pos,position_group,bats,throws,xp_wallet,attributes_json,season_json,status,active,age)
                             VALUES(NULL,?,?,?,?,?,?,?,0,?,?,'SIGNED',1,18)""",
                          (fid,f"{FIRST_NAMES[(i+int(fid[-2:])*7)%len(FIRST_NAMES)]} {LAST_NAMES[(i*5+int(fid[-2:])*11)%len(LAST_NAMES)]}",ptype,role,position_group_for_pos(role),"R","R",json.dumps(attrs),json.dumps(pseason if ptype=="P" else hseason)))
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
        pitcher_ids={int(slots[i]["id"]) for i in range(9,16)}
        fr_owner=c.execute("SELECT owner_user_id FROM franchises WHERE id=?",(fid,)).fetchone()
        managed=bool(fr_owner and fr_owner["owner_user_id"] is not None)
        existing_lineup=c.execute("SELECT batting_order_json,rotation_json FROM lineups WHERE franchise_id=?",(fid,)).fetchone()








        if managed:
            # A roster integrity pass must never become a silent manager. Preserve the
            # coach's exact batting order across deploys/restarts whenever the same nine
            # hitters are still on the active roster. If a signing/replacement changed
            # the roster, retain every still-valid saved slot and fill only the hole.
            try:
                saved_order=[int(x) for x in json.loads(existing_lineup["batting_order_json"] or "[]")] if existing_lineup else []
            except Exception:
                saved_order=[]
            clean_order=[]
            for pid in saved_order:
                if pid in hitter_ids and pid not in clean_order:
                    clean_order.append(pid)
            for pid in hitter_ids:
                if pid not in clean_order:
                    clean_order.append(pid)
            batting_order=clean_order[:9] if len(clean_order)>=9 else auto_batting_order(c,hitter_ids)








            try:
                saved_rotation=[int(x) for x in json.loads(existing_lineup["rotation_json"] or "[]")] if existing_lineup else []
            except Exception:
                saved_rotation=[]
            clean_rotation=[]
            for pid in saved_rotation:
                if pid in pitcher_ids and pid not in clean_rotation:
                    clean_rotation.append(pid)
            auto_rotation,_auto_bp=auto_pitching_plan(c,fid)
            if not (3<=len(clean_rotation)<=5):
                for pid in auto_rotation:
                    if pid in pitcher_ids and pid not in clean_rotation:
                        clean_rotation.append(pid)
                    if len(clean_rotation)>=4:
                        break
            rotation=clean_rotation[:5]








            c.execute("UPDATE lineups SET batting_order_json=?,rotation_json=? WHERE franchise_id=?",
                      (json.dumps(batting_order),json.dumps(rotation),fid))
            # Preserve the coach's bullpen hierarchy too. Roster integrity can repair the
            # active roster, but it should not rewrite strategy on every process restart.
        else:
            generated_order=auto_batting_order(c,hitter_ids)
            rotation,bp=auto_pitching_plan(c,fid)
            c.execute("UPDATE lineups SET batting_order_json=?,rotation_json=? WHERE franchise_id=?",
                      (json.dumps(generated_order),json.dumps(rotation[:5]),fid))
            c.execute("UPDATE team_strategy SET bullpen_json=? WHERE franchise_id=?",(json.dumps(bp),fid))
    return True








def gps_xp(g): return round(max(.25,min(.75,.25+.5*g/100)),3)








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
















def _division_heavy_series_rounds_30(season):
    """27 series/team: 16 division series + 11 non-division series.








    Every division rival is faced four times (48 division games). Each club then
    gets eleven cross-division series (33 games), for exactly 81 games total.
    """
    from collections import Counter
    import itertools
    target=Counter()
    # Six five-team divisions. Every intra-division pairing occurs four times.
    for div in range(6):
        teams=list(range(div*5,div*5+5))
        for a,b in itertools.combinations(teams,2):
            target[(a,b)]+=4
    # Two cross-division series against every other division (10 series/team).
    for da,db in itertools.combinations(range(6),2):
        for shift in (0,1):
            for i in range(5):
                a=da*5+i;b=db*5+((i+shift)%5)
                target[tuple(sorted((a,b)))]+=1
    # One extra cross-division series/team completes the 11-series non-division slate.
    for da,db in ((0,1),(2,3),(4,5)):
        for i in range(5):
            a=da*5+i;b=db*5+((i+2)%5)
            target[tuple(sorted((a,b)))]+=1








    for attempt in range(40):
        rng=random.Random(7500831+int(season)*997+attempt*104729)
        remaining=target.copy();rounds=[];failed=False
        for _ in range(REGULAR_SEASON_SERIES):
            match=_perfect_matching_from_multiset(remaining,30,rng)
            if not match:
                failed=True;break
            match=[tuple(sorted(x)) for x in match]
            rounds.append(match)
            for edge in match:remaining[edge]-=1
        if not failed and not any(remaining.values()):
            return rounds
    raise RuntimeError("SERIES_SCHEDULE_DECOMPOSITION_FAILED")
















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








    # Full EBL uses a division-heavy 48/33 split. Smaller test leagues retain a
    # balanced circle-method opponent rotation but use the exact same 27-series,
    # 95-calendar-day rhythm.
    rounds=_division_heavy_series_rounds_30(season) if n==30 else _circle_series_rounds(n)
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
    contracts=[dict(x) for x in c.execute(
        """SELECT ch.franchise_id,f.name team_name,ch.salary,ch.bonus,ch.years,ch.signed_at,ch.ended_at
           FROM contract_history ch LEFT JOIN franchises f ON f.id=ch.franchise_id
           WHERE ch.player_id=? ORDER BY ch.id DESC""",(pid,)
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
        "awards":awards,"award_count":sum(1 for a in awards if a.get("award_code")!="ALL_STAR_SELECTION"),
        "all_star_count":sum(1 for a in awards if a.get("award_code")=="ALL_STAR_SELECTION"),
        "championships":championships,"championship_count":len(championships),"teams":teams,"contract_history":contracts
    }
























def recent_game_for_player(c, player):
    if not player or not player.get("franchise_id"):
        return None
    pid=int(player["id"])
    rows=c.execute(
        """SELECT id,league_day,away_id,home_id,away_runs,home_runs,box_json
           FROM games
           WHERE status='FINAL' AND (away_id=? OR home_id=?)
           ORDER BY league_day DESC,id DESC
           LIMIT 120""",
        (player["franchise_id"],player["franchise_id"])
    ).fetchall()
    for g in rows:
        try:
            box=json.loads(g["box_json"] or "{}")
        except Exception:
            box={}
        if player.get("type")=="H":
            line=(box.get("hitters") or {}).get(str(pid))
            if line:
                return {"game_id":g["id"],"league_day":g["league_day"],"stats":line,
                        "away_id":g["away_id"],"home_id":g["home_id"],
                        "away_runs":g["away_runs"],"home_runs":g["home_runs"]}
        else:
            for staff in (box.get("pitchers") or {}).values():
                for line in staff or []:
                    if int(line.get("player_id",0) or 0)==pid:
                        stats={k:v for k,v in line.items() if k!="player_id"}
                        return {"game_id":g["id"],"league_day":g["league_day"],"stats":stats,
                                "away_id":g["away_id"],"home_id":g["home_id"],
                                "away_runs":g["away_runs"],"home_runs":g["home_runs"]}
    return None








def player_obj(c,pid):
    r=c.execute("SELECT * FROM players WHERE id=?",(pid,)).fetchone()
    if not r:return None
    d=dict(r);d["attributes"]=json.loads(d.pop("attributes_json"));d["season"]=json.loads(d.pop("season_json"));d["overall"]=player_overall(d)
    owner=c.execute("SELECT username FROM users WHERE id=?",(d.get("user_id"),)).fetchone() if d.get("user_id") else None
    d["username"]=owner["username"] if owner else None
    con=c.execute("SELECT * FROM contracts WHERE player_id=?",(pid,)).fetchone()
    d["contract"]=dict(con) if con else None
    roster_slot=c.execute("SELECT position_group,slot_no FROM roster_slots WHERE player_id=? LIMIT 1",(pid,)).fetchone()
    d["roster_role"]=str(roster_slot["position_group"]) if roster_slot else None
    d["roster_slot_no"]=int(roster_slot["slot_no"]) if roster_slot else None
    last_contract=c.execute("""SELECT ch.*,f.name team_name
                              FROM contract_history ch
                              LEFT JOIN franchises f ON f.id=ch.franchise_id
                              WHERE ch.player_id=?
                              ORDER BY ch.id DESC LIMIT 1""",(pid,)).fetchone()
    d["former_team"]={"franchise_id":last_contract["franchise_id"],"team_name":last_contract["team_name"],"salary":last_contract["salary"]} if last_contract else None
    d["offers"]=[]
    # Contract offers carry their franchise identity with them. The client should never
    # have to expose an internal id (EBL-F01, etc.) while waiting for /api/league.
    # Branding display_name is preferred, with franchises.name as the canonical fallback.
    for row in c.execute(
        """SELECT o.*,f.name AS team_name,
                  COALESCE(NULLIF(b.display_name,''),f.name) AS team_display_name
           FROM offers o
           JOIN franchises f ON f.id=o.franchise_id
           LEFT JOIN franchise_branding b ON b.franchise_id=o.franchise_id
           WHERE o.player_id=? AND o.status IN ('OPEN','HELD')
           ORDER BY o.id DESC""",
        (pid,)
    ):
        off=dict(row)
        off["returning_offer"]=bool(str(off.get("offer_type") or "FREE_AGENT").upper()!="RENEWAL" and last_contract and off.get("franchise_id")==last_contract["franchise_id"])
        d["offers"].append(off)
    agreed=c.execute(
        """SELECT o.*,f.name AS team_name,COALESCE(NULLIF(b.display_name,''),f.name) AS team_display_name
           FROM offers o JOIN franchises f ON f.id=o.franchise_id
           LEFT JOIN franchise_branding b ON b.franchise_id=o.franchise_id
           WHERE o.player_id=? AND o.offer_type='RENEWAL' AND o.status='ACCEPTED'
           ORDER BY o.id DESC LIMIT 1""",(pid,)
    ).fetchone()
    d["renewal_agreement"]=dict(agreed) if agreed else None
    renewal_waiting=next((x for x in d["offers"] if str(x.get("offer_type") or "").upper()=="RENEWAL"),None)
    d["action_required"]={"type":"RENEWAL","offer_id":renewal_waiting["id"],"title":"Contract decision waiting"} if renewal_waiting else None
    d["ledger"]=[dict(x) for x in c.execute("SELECT event_type,xp,detail_json FROM xp_ledger WHERE player_id=? ORDER BY id DESC LIMIT 25",(pid,))]
    d["career"]=career_summary(c,pid,d.get("season"),bool(d.get("active")))
    d["career_seasons"]=d["career"]["seasons_completed"] if d.get("career") else 0
    d["championships"]=d["career"]["championship_count"] if d.get("career") else 0
    d["awards_count"]=d["career"]["award_count"] if d.get("career") else 0
    state={x["k"]:x["v"] for x in c.execute("SELECT k,v FROM league_state WHERE k IN ('phase','league_day')")}
    phase=str(state.get("phase","REGULAR")).upper()
    effective_completed=extension_completed_seasons(c,pid) if d.get("active") else int(d.get("career_seasons") or 0)
    extension_through=int(d.get("career_extension_through") or 12)
    veteran_eligible=bool(d.get("active") and effective_completed>=12)
    next_career_season=effective_completed+1
    extension_paid=bool(veteran_eligible and extension_through>=next_career_season)
    d["veteran_extension"]={"eligible":veteran_eligible,"window_open":bool(veteran_eligible and phase=="OFFSEASON"),"required":bool(veteran_eligible and phase=="OFFSEASON" and not extension_paid),"paid":extension_paid,"completed_seasons":effective_completed,"next_career_season":next_career_season,"covered_through":extension_through,"cost":veteran_extension_cost(effective_completed) if veteran_eligible else 0.0}
    d["position_group_change_open"]=bool(d.get("status")=="FREE_AGENT" and (phase=="OFFSEASON" or int(state.get("league_day","0") or 0)==0))
    # Preferred position may be changed within the current roster family even while signed.
    # The actual team role remains the roster-slot assignment controlled by the club.
    d["preferred_position_change_open"]=bool(d.get("active"))
    d["position_change_open"]=d["position_group_change_open"]
    return d
































def player_identity_payload(row):
    """Canonical public player identity used by league-wide surfaces.








    Team assignment always comes from players.franchise_id. Appearance is copied from
    the same player row so Team, Awards, Analytics and other public views do not invent
    separate versions of a player after a signing or trade.
    """
    d=dict(row) if row is not None else {}
    fid=d.get("franchise_id")
    out={
        "id":d.get("id"),
        "player_id":d.get("id"),
        "name":d.get("name"),
        "username":d.get("username"),
        "team":fid,
        "franchise_id":fid,
        "pos":d.get("primary_pos"),
        "primary_pos":d.get("primary_pos"),
        "jersey_number":d.get("jersey_number"),
        "bats":d.get("bats"),
        "throws":d.get("throws")
    }
    for key in ("face_id","skin_color_id","hair_id","hair_color_id","facial_hair_id",
                "eye_color_id","nose_id","eye_shape_id","mouth_id","ear_size_id",
                "eye_black_id","eyewear_id","chain_id","sleeve_id","body_build_id"):
        if key in d:
            out[key]=d.get(key)
    if d.get("team_name") is not None:
        out["team_name"]=d.get("team_name")
    if d.get("team_display_name") is not None:
        out["team_display_name"]=d.get("team_display_name")
    return out
















def assign_team_jersey_number(c,franchise_id,player_id,preferred):
    try:
        preferred=int(preferred)
    except Exception:
        preferred=24
    preferred=max(0,min(99,preferred))
    taken={int(r["jersey_number"]) for r in c.execute(
        "SELECT jersey_number FROM players WHERE franchise_id=? AND active=1 AND status='SIGNED' AND id<>?",
        (franchise_id,player_id)
    ).fetchall() if r["jersey_number"] is not None}
    if preferred not in taken:
        chosen=preferred
    else:
        chosen=next((n for n in range(0,100) if n not in taken),preferred)
    c.execute("UPDATE players SET jersey_number=? WHERE id=?",(chosen,player_id))
    return chosen
















def sim_player_obj(c,pid):
    r=c.execute("SELECT * FROM players WHERE id=?",(pid,)).fetchone()
    if not r:return None
    d=dict(r)
    d["attributes"]=json.loads(d.pop("attributes_json"))
    # RC65 — sponsorships are temporary team modifiers, never permanent player development.
    # Apply them only to the simulation copy of the player's attributes.
    fid=d.get("franchise_id")
    if fid:
        for attr in SPONSORSHIP_ATTRS:
            bonus=team_attribute_bonus(c,fid,attr)
            if bonus:
                d["attributes"][attr]=float(d["attributes"].get(attr,0) or 0)+bonus
    d["season"]=json.loads(d.pop("season_json"))
    d["overall"]=player_overall(d)
    con=c.execute("SELECT * FROM contracts WHERE player_id=?",(pid,)).fetchone()
    d["contract"]=dict(con) if con else None
    # Simulation does not need offers or ledger history on every PA.
    d["offers"]=[]
    d["ledger"]=[]
    return d
















def save_player(c,p,persist_attributes=False):
    """Persist game/career state without leaking temporary simulation modifiers.








    sim_player_obj() applies team sponsorships only to its in-memory attribute copy.
    Normal game saves therefore write XP/stat lines only. The player-development
    endpoint explicitly opts in when a trained attribute really changed.
    """
    if persist_attributes:
        c.execute("UPDATE players SET xp_wallet=?,attributes_json=?,season_json=? WHERE id=?",
                  (p["xp_wallet"],json.dumps(p["attributes"]),json.dumps(p["season"]),p["id"]))
    else:
        c.execute("UPDATE players SET xp_wallet=?,season_json=? WHERE id=?",
                  (p["xp_wallet"],json.dumps(p["season"]),p["id"]))
















def hitter_gps(line):
    raw=line["1B"]*.45+line["2B"]*.75+line["3B"]*1.05+line["HR"]*1.35+line["BB"]*.32+line["RBI"]*.10+line["R"]*.08-line["SO"]*.12
    return 100/(1+math.exp(-(raw-1.05)*1.28))
















def player_overall_from_attrs(attrs, player_type, pos):
    # Development-scale OVR: no artificial 40-point floor and no forced 99 ceiling climb.
    # It summarizes category averages; the simulation itself always uses the raw attributes.
    def avg(keys):
        vals=[float(attrs.get(k,0) or 0) for k in keys]
        return sum(vals)/len(vals) if vals else 0.0








    if player_type=="H":
        batting=avg(["CON","POW","VIS","DISC","TIM"])
        fielding=avg(["FLD","ARM","ACC","REAC"])
        baserunning=avg(["SPD","BRIQ","LEAD"])
        category_weights={
            "C":(.35,.55,.10),
            "1B":(.65,.30,.05),
            "2B":(.45,.40,.15),
            "3B":(.55,.40,.05),
            "SS":(.40,.45,.15),
            "LF":(.60,.25,.15),
            "CF":(.40,.35,.25),
            "RF":(.55,.35,.10),
            "DH":(.90,.05,.05),
            "UTIL":(.45,.35,.20),
        }
        wb,wf,wr=category_weights.get(pos,(.45,.35,.20))
        value=batting*wb+fielding*wf+baserunning*wr
    else:
        pitching=avg(["CTRL","VEL","BRK"])
        craft=avg(["CMD","MOV","DEC","SEQ"])
        fielding=avg(["FLD","ARM","ACC","REAC"])
        sta=float(attrs.get("STA",0) or 0)
        pclt=float(attrs.get("PCLT",0) or 0)
        if pos=="SP":
            value=pitching*.65+sta*.20+fielding*.10+pclt*.05
        elif pos in ("SU","CL"):
            value=pitching*.70+pclt*.15+fielding*.10+sta*.05
        else:
            value=pitching*.68+sta*.10+pclt*.12+fielding*.10
        # Craft ratings add specialization without taking value away from legacy builds.
        value+=craft*.08








    return max(1,int(round(value)))
















def player_overall(player):
    return player_overall_from_attrs(player.get("attributes",{}),player.get("type","H"),player.get("primary_pos","UTIL"))
















def pitcher_gps(line,sp):
    ip=line["OUTS"]/3
    raw=max(-3,ip*.62-line["ER"]*.92)+line["SO"]*.14-line["BB"]*.18-line["H"]*.08
    if sp:raw+=max(0,ip-4)*.18
    return 100/(1+math.exp(-(raw-(.55 if sp else .45))*1.12))
















def contract_for(c,pid):
    r=c.execute("SELECT * FROM contracts WHERE player_id=?",(pid,)).fetchone()
    return dict(r) if r else None
































def previous_team_salary(c,player_id,franchise_id):
    r=c.execute(
        """SELECT salary FROM contract_history
           WHERE player_id=? AND franchise_id=?
           ORDER BY id DESC LIMIT 1""",
        (int(player_id),str(franchise_id))
    ).fetchone()
    return round(float(r["salary"]),2) if r else None








def player_salary_floor(c,player_id):
    """RC72: veteran free-agent floor is based on completed service seasons.








    Rookie/0 completed seasons: .30. Each completed season adds .01, capped
    at a .40 minimum after 10 seasons. Previous oversized contracts do not
    permanently poison the player's market; service time still prevents
    veteran superteams from signing everyone at rookie minimum.
    """
    completed=player_seasons_completed(c,player_id)
    return round(SALARY_MIN + min(completed,10)*0.01,2)








def minimum_offer_salary(c,player_id,franchise_id=None):
    return player_salary_floor(c,player_id)








def renewal_veteran_minimum(c,player_id):
    """Veteran minimum for the season a Day-60 renewal will begin.








    The current regular season becomes one additional completed service season
    before the renewal activates, so the next-season floor is one step ahead of
    the player's live free-agent floor.
    """
    completed=player_seasons_completed(c,player_id)+1
    return round(SALARY_MIN + min(completed,10)*0.01,2)








def next_season_payroll_projection(c,franchise_id,replace_player_id=None,proposed_salary=None):
    """Project signed payroll for next season from continuing deals + renewals.








    This is deliberately a planning view, not a current-season charge. Accepted
    renewals do not pay anything until the next season begins.
    """
    total=0.0
    rows=c.execute("SELECT player_id,salary,years_remaining FROM contracts WHERE franchise_id=?",(franchise_id,)).fetchall()
    for con in rows:
        pid=int(con["player_id"])
        if replace_player_id is not None and pid==int(replace_player_id):
            continue
        if int(con["years_remaining"] or 0)>1:
            total+=(round(float(con["salary"] or SALARY_MIN)+CONTRACT_ESCALATION,2))*REGULAR_SEASON_GAMES
            continue
        renewal=c.execute(
            """SELECT salary FROM offers
               WHERE franchise_id=? AND player_id=? AND offer_type='RENEWAL'
                 AND status IN ('OPEN','HELD','ACCEPTED')
               ORDER BY CASE status WHEN 'ACCEPTED' THEN 0 ELSE 1 END,id DESC LIMIT 1""",
            (franchise_id,pid)
        ).fetchone()
        if renewal:
            total+=float(renewal["salary"] or SALARY_MIN)*REGULAR_SEASON_GAMES
    if proposed_salary is not None:
        total+=float(proposed_salary)*REGULAR_SEASON_GAMES
    return round(total,3)








def projected_next_season_treasury(c,franchise_id):
    fr=c.execute("SELECT * FROM franchises WHERE id=?",(franchise_id,)).fetchone()
    if not fr:return TEAM_BUDGET
    recurring=annual_team_budget(dict(fr))
    safe_rollover=signing_pool_state(c,franchise_id)["available"]
    return round(recurring+safe_rollover,3)








FACILITY_UPGRADE_COSTS=[50,65,80,100,125]
SPONSORSHIP_COST=25.0
SPONSORSHIP_ATTRS={"ARM","ACC","FLD","REAC","SPD"}
DEVELOPMENT_COACH_BASE_COST=30.0
DEVELOPMENT_COACH_MAX=3
DEVELOPMENT_COACH_HIRING_CLOSE_DAY=49
DEVELOPMENT_COACH_INTENSITY={
    1:{"name":"Standard","extra_cost":0.0,"days":[0,49,95]},
    2:{"name":"Focused","extra_cost":5.0,"days":[0,24,49,95]},
    3:{"name":"Elite","extra_cost":10.0,"days":[0,24,49,70,95]},
}
DEVELOPMENT_COACH_TYPES={
    # Hitting specialists
    "CONTACT":{"name":"Contact Coach","attribute":"CON","category":"HITTING","applies_to":"HITTERS"},
    "POWER":{"name":"Power Coach","attribute":"POW","category":"HITTING","applies_to":"HITTERS"},
    "VISION":{"name":"Vision Coach","attribute":"VIS","category":"HITTING","applies_to":"HITTERS"},
    "DISCIPLINE":{"name":"Plate Discipline Coach","attribute":"DISC","category":"HITTING","applies_to":"HITTERS"},
    "TIMING":{"name":"Timing Coach","attribute":"TIM","category":"HITTING","applies_to":"HITTERS"},
    # Baserunning specialists
    "SPEED":{"name":"Speed Coach","attribute":"SPD","category":"BASERUNNING","applies_to":"HITTERS"},
    "BASERUNNING_IQ":{"name":"Baserunning IQ Coach","attribute":"BRIQ","category":"BASERUNNING","applies_to":"HITTERS"},
    "LEAD":{"name":"Lead & Steal Coach","attribute":"LEAD","category":"BASERUNNING","applies_to":"HITTERS"},
    # Defensive specialists. FLD/ARM/ACC/REAC exist for hitters and pitchers.
    "FIELDING":{"name":"Fielding Coach","attribute":"FLD","category":"FIELDING","applies_to":"ALL"},
    "ARM_STRENGTH":{"name":"Arm Strength Coach","attribute":"ARM","category":"FIELDING","applies_to":"ALL"},
    "ACCURACY":{"name":"Accuracy Coach","attribute":"ACC","category":"FIELDING","applies_to":"ALL"},
    "REACTION":{"name":"Reaction Coach","attribute":"REAC","category":"FIELDING","applies_to":"ALL"},
    "CATCHER_CALL":{"name":"Catcher Game-Calling Coach","attribute":"CALL","category":"FIELDING","applies_to":"CATCHERS"},
    # Pitching specialists
    "STAMINA":{"name":"Stamina Coach","attribute":"STA","category":"PITCHING","applies_to":"PITCHERS"},
    "CLUTCH":{"name":"Pitching Clutch Coach","attribute":"PCLT","category":"PITCHING","applies_to":"PITCHERS"},
    "CONTROL":{"name":"Control Coach","attribute":"CTRL","category":"PITCHING","applies_to":"PITCHERS"},
    "COMMAND":{"name":"Command Coach","attribute":"CMD","category":"PITCHING","applies_to":"PITCHERS"},
    "VELOCITY":{"name":"Velocity Coach","attribute":"VEL","category":"PITCHING","applies_to":"PITCHERS"},
    "BREAK":{"name":"Breaking Ball Coach","attribute":"BRK","category":"PITCHING","applies_to":"PITCHERS"},
    "MOVEMENT":{"name":"Movement Coach","attribute":"MOV","category":"PITCHING","applies_to":"PITCHERS"},
    "DECISION":{"name":"Pitching Decision Coach","attribute":"DEC","category":"PITCHING","applies_to":"PITCHERS"},
    "SEQUENCING":{"name":"Pitch Sequencing Coach","attribute":"SEQ","category":"PITCHING","applies_to":"PITCHERS"},
}








def practice_reward_for(c,fid):
    r=c.execute("SELECT training_level FROM franchises WHERE id=?",(fid,)).fetchone()
    level=int(r["training_level"] or 0) if r else 0
    return round(0.25+0.01*level,2)








def active_team_sponsorships(c,fid,season=None):
    if season is None:
        r=c.execute("SELECT v FROM league_state WHERE k='season'").fetchone()
        season=int(r["v"] or 1) if r else 1
    return [dict(x) for x in c.execute(
        """SELECT * FROM team_sponsorships
           WHERE franchise_id=? AND status='ACTIVE' AND start_season<=? AND end_season>=?
           ORDER BY attribute,id""",(fid,int(season),int(season))
    ).fetchall()]








def team_attribute_bonus(c,fid,attribute,season=None):
    return sum(int(x.get("bonus",0) or 0) for x in active_team_sponsorships(c,fid,season)
               if str(x.get("attribute","")).upper()==str(attribute).upper())








def active_team_development_coaches(c,fid,season=None):
    if season is None:
        season=_season_number(c)
    rows=[dict(x) for x in c.execute(
        """SELECT * FROM team_development_coaches
           WHERE franchise_id=? AND season=? ORDER BY coach_slot,id""",
        (str(fid),int(season))
    ).fetchall()]
    for row in rows:
        try: row["checkpoint_days"]=json.loads(row.get("checkpoint_days_json") or "[]")
        except Exception: row["checkpoint_days"]=DEVELOPMENT_COACH_INTENSITY.get(int(row.get("intensity") or 1),DEVELOPMENT_COACH_INTENSITY[1])["days"]
        try: row["applied_days"]=json.loads(row.get("applied_days_json") or "[]")
        except Exception: row["applied_days"]=[]
        tier=DEVELOPMENT_COACH_INTENSITY.get(int(row.get("intensity") or 1),DEVELOPMENT_COACH_INTENSITY[1])
        row["intensity_name"]=tier["name"]
    return rows








def _apply_team_development_point(c,row,stage):
    fid=str(row["franchise_id"]);attribute=str(row["attribute"] or "").upper()
    coach_type=str(row["coach_type"] or "").upper();season=int(row["season"] or 1)
    if not attribute:return 0
    players=c.execute(
        """SELECT id,user_id,name,type,primary_pos,attributes_json FROM players
           WHERE franchise_id=? AND active=1 AND status='SIGNED' ORDER BY id""",
        (fid,)
    ).fetchall()
    changed=0
    for pl in players:
        try:attrs=json.loads(pl["attributes_json"] or "{}")
        except Exception:attrs={}
        if attribute not in attrs:
            continue
        if attribute=="CALL" and str(pl["primary_pos"] or "").upper()!="C":
            continue
        attrs[attribute]=float(attrs.get(attribute,0) or 0)+1.0
        c.execute("UPDATE players SET attributes_json=? WHERE id=?",(json.dumps(attrs),pl["id"]))
        changed+=1
        if pl["user_id"]:
            notify_user(c,pl["user_id"],"DEVELOPMENT",f"Team {DEVELOPMENT_COACH_TYPES.get(coach_type,{}).get('name','Development Coach')}: +1 {attribute}",
                        f"{pl['name']} earned a permanent +1 {attribute} from the club's seasonal development coach ({stage.replace('_',' ').title()}).",str(pl["id"]))
    c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
              ("TEAM_DEVELOPMENT_MILESTONE",None,json.dumps({"franchise_id":fid,"season":season,"coach_type":coach_type,"attribute":attribute,"stage":stage,"players_updated":changed})))
    return changed








def _development_stage(day):
    return "OPENING" if int(day)==0 else f"DAY_{int(day)}"








def _development_row_days(row):
    intensity=int(row["intensity"] or 1) if "intensity" in row.keys() else 1
    try:
        days=[int(x) for x in json.loads(row["checkpoint_days_json"] or "[]")]
    except Exception:
        days=list(DEVELOPMENT_COACH_INTENSITY.get(intensity,DEVELOPMENT_COACH_INTENSITY[1])["days"])
    return sorted(set(days))








def _development_applied_days(row):
    try:return {int(x) for x in json.loads(row["applied_days_json"] or "[]")}
    except Exception:return set()








def _sync_development_legacy_flags(c,row_id,applied):
    c.execute("""UPDATE team_development_coaches
                 SET applied_days_json=?,start_applied=?,midseason_applied=?,endseason_applied=?
                 WHERE id=?""",(
                 json.dumps(sorted(applied)),1 if 0 in applied else 0,
                 1 if any(x in applied for x in (24,49,70)) else 0,
                 1 if REGULAR_SEASON_CALENDAR_DAYS in applied else 0,row_id))








def apply_team_development_coach_milestones(c,season,league_day):
    """Apply each development coach's scheduled permanent +1 checkpoints once."""
    season=int(season);league_day=int(league_day)
    rows=c.execute("SELECT * FROM team_development_coaches WHERE season=? ORDER BY franchise_id,coach_slot,id",(season,)).fetchall()
    applied_events=[]
    for row in rows:
        days=_development_row_days(row);applied=_development_applied_days(row)
        hired_day=int(row["hired_day"] or 0) if "hired_day" in row.keys() else 0
        changed=False
        for checkpoint in days:
            if checkpoint in applied or checkpoint>league_day:
                continue
            # Opening is always the immediate first boost. Other checkpoints that
            # passed before a late hire are intentionally missed rather than back-paid.
            if checkpoint>0 and checkpoint<hired_day:
                applied.add(checkpoint);changed=True
                continue
            n=_apply_team_development_point(c,row,_development_stage(checkpoint))
            applied.add(checkpoint);changed=True
            applied_events.append({"id":row["id"],"stage":_development_stage(checkpoint),"day":checkpoint,"players":n})
        if changed:
            _sync_development_legacy_flags(c,row["id"],applied)
    return applied_events








def effective_stamina(sta):
    """Soft-scale uncapped STA so every point helps without creating infinite endurance."""
    try:
        raw=max(0.0,float(sta or 0))
    except Exception:
        raw=0.0
    return 100.0*(1.0-math.exp(-raw/60.0))
















def reset_pitcher_fatigue(c,reason,season=None,league_day=None,announce=False):
    """Clear carried pitcher workload at official EBL recovery checkpoints."""
    row=c.execute("SELECT COUNT(*) n FROM pitcher_workload").fetchone()
    cleared=int(row["n"] or 0) if row else 0
    c.execute("DELETE FROM pitcher_workload")
    if season is None:
        season=_season_number(c)
    if league_day is None:
        r=c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()
        league_day=int(r["v"] or 0) if r else 0
    c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
              ("PITCHER_FATIGUE_RESET",None,json.dumps({"reason":str(reason),"season":int(season),"league_day":int(league_day),"pitchers_cleared":cleared})))
    if announce:
        post_news(c,"LEAGUE","⭐ All-Star Break: pitching staffs fully recovered",
                  "The first half is complete. Every EBL pitching staff returns to 100% readiness for the second half of the season.",
                  int(league_day),None,None,None,3,season=int(season))
    return cleared
















def pitcher_recovery_state(c,pitcher_id,league_day):
    r=c.execute("SELECT fatigue,last_league_day,last_outs FROM pitcher_workload WHERE pitcher_id=?",(int(pitcher_id),)).fetchone()
    p=c.execute("SELECT attributes_json FROM players WHERE id=?",(int(pitcher_id),)).fetchone()
    attrs=json.loads(p["attributes_json"] or "{}") if p else {}
    sta=float(attrs.get("STA",0) or 0)
    sta_eff=effective_stamina(sta)
    if not r:
        return {"fatigue":0.0,"readiness":100,"days_since":None,"last_outs":0}
    days=max(0,int(league_day)-int(r["last_league_day"] or 0))
    # STA improves recovery too, but with diminishing returns because EBL attributes
    # are uncapped. Recovery Center remains a flat +2 fatigue/day per level.
    fr=c.execute("SELECT recovery_level FROM franchises WHERE id=(SELECT franchise_id FROM players WHERE id=?)",(int(pitcher_id),)).fetchone()
    recovery_level=int(fr["recovery_level"] or 0) if fr else 0
    recovery_per_day=9.5+sta_eff*0.07+(2.0*recovery_level)
    fatigue=max(0.0,float(r["fatigue"] or 0)-days*recovery_per_day)
    readiness=max(35,int(round(100-fatigue)))
    return {"fatigue":round(fatigue,2),"readiness":readiness,"days_since":days,"last_outs":int(r["last_outs"] or 0)}
















def record_pitcher_workload(c,pitcher_id,league_day,outs,is_starter):
    state=pitcher_recovery_state(c,pitcher_id,league_day)
    workload=float(outs)*(3.0 if is_starter else 2.4)
    fatigue=min(65.0,float(state["fatigue"])+workload)
    c.execute("""INSERT INTO pitcher_workload(pitcher_id,fatigue,last_league_day,last_outs,updated_at)
                 VALUES(?,?,?,?,CURRENT_TIMESTAMP)
                 ON CONFLICT(pitcher_id) DO UPDATE SET fatigue=excluded.fatigue,last_league_day=excluded.last_league_day,last_outs=excluded.last_outs,updated_at=CURRENT_TIMESTAMP""",
              (int(pitcher_id),round(fatigue,2),int(league_day),int(outs)))
















def team_strategy_for(c,fid):
    r=c.execute("SELECT * FROM team_strategy WHERE franchise_id=?",(fid,)).fetchone()
    if not r:
        return {"bullpen":{"CL":None,"SU1":None,"SU2":None,"MR":[],"LR":[],"EMERGENCY":[]},
                "defense":{"default_shift":"STANDARD","vs_lhb":"STANDARD","vs_rhb":"STANDARD","corners_in":False,"infield_in":False},
                "bench":{},"substitutions":{}}
    return {"bullpen":json.loads(r["bullpen_json"]),"defense":json.loads(r["defense_json"]),
            "bench":json.loads(r["bench_json"]),"substitutions":json.loads(r["substitutions_json"])}
















def choose_reliever(c,fid,strategy,inning,lead_margin,used,rotation_ids=None,league_day=None):
    bp=strategy["bullpen"]
    rotation_ids={int(x) for x in (rotation_ids or [])}
    if league_day is None:
        try:
            league_day=int(league_cfg(c,"league_day",0) or 0)
        except Exception:
            league_day=0








    def candidate(pid,role,allow_tired=False):
        if not pid or int(pid) in used:return None
        r=c.execute("SELECT id,type,primary_pos,attributes_json FROM players WHERE id=? AND franchise_id=? AND type='P' AND active=1",(int(pid),fid)).fetchone()
        if not r or int(r["id"]) in rotation_ids:return None
        attrs=json.loads(r["attributes_json"] or "{}")
        recovery=pitcher_recovery_state(c,int(r["id"]),int(league_day))
        readiness=int(recovery.get("readiness",100) or 100)
        # A tired arm should be passed over when a rested legal bullpen option exists.
        # We still allow one as a true emergency so the engine never gets stranded.
        if readiness<55 and not allow_tired:return None
        ovr=player_overall_from_attrs(attrs,"P",r["primary_pos"])
        effective=ovr-max(0,80-readiness)*.30
        return (effective,int(r["id"]),role)








    def best(items,role,allow_tired=False):
        choices=[]
        for pid in items:
            x=candidate(pid,role,allow_tired=allow_tired)
            if x:choices.append(x)
        return max(choices) if choices else None








    choices=[]
    if inning>=9 and 0<lead_margin<=3:
        x=candidate(bp.get("CL"),"CL")
        if x:return x[1],x[2]
    if inning>=8 and abs(lead_margin)<=3:
        for k in ("SU1","SU2"):
            x=candidate(bp.get(k),k)
            if x:choices.append(x)
        if choices:
            x=max(choices);return x[1],x[2]
    if inning<=6 or abs(lead_margin)>=4:
        x=best(bp.get("LR",[]),"LR")
        if x:return x[1],x[2]
    x=best(bp.get("MR",[]),"MR")
    if x:return x[1],x[2]
    x=best(bp.get("LR",[]),"LR")
    if x:return x[1],x[2]
    x=best(bp.get("EMERGENCY",[]),"EMERGENCY")
    if x:return x[1],x[2]








    # If the preferred role for this game state is unavailable, use another
    # configured bullpen arm rather than leaving setup/closer pitchers stranded.
    fallback=[]
    for k in ("SU1","SU2","CL"):
        x=candidate(bp.get(k),k)
        if x:fallback.append(x)
    if fallback:
        x=max(fallback);return x[1],x[2]








    # Last-resort fatigue override: only configured bullpen pitchers are legal,
    # but a tired legal arm is better than inventing a pitcher or crashing the game.
    tired=[]
    for k in ("MR","LR","EMERGENCY"):
        for pid in (bp.get(k,[]) or []):
            x=candidate(pid,k,allow_tired=True)
            if x:tired.append(x)
    for k in ("SU1","SU2","CL"):
        x=candidate(bp.get(k),k,allow_tired=True)
        if x:tired.append(x)
    if tired:
        x=max(tired);return x[1],x[2]








    # Hard roster-management rule: an in-game pitching change may only use a
    # pitcher explicitly assigned to the saved bullpen.
    return None,None
















def should_pull_starter(line, inning, sta=0, readiness=100):
    if not line or not line.get("GS"):return False
    outs=int(line.get("OUTS",0) or 0);er=int(line.get("ER",0) or 0);traffic=int(line.get("H",0) or 0)+int(line.get("BB",0) or 0)
    sta=max(0.0,float(sta or 0))
    sta_eff=effective_stamina(sta)
    readiness=max(35.0,min(100.0,float(readiness or 100)))








    # Catastrophic outings end immediately; no starter is left in just to reach an inning target.
    if er>=10:return True
    if er>=7 and outs<18:return True
    if er>=5 and outs<12:return True
    if er>=4 and outs<9:return True
    if traffic>=10 and outs<12:return True
    if inning>=6 and (er>=4 or traffic>=9):return True








    # RC99 workhorse curve: STA is a build-defining capacity stat. Rough rested targets:
    # 0≈3-4 IP, 10≈4-5, 20≈5-6, 30≈6-7, 40≈7-8, 50+≈8-9 with a strong outing.
    # Performance hooks above still pull a high-STA pitcher who is getting hit hard.
    target_outs=11+int(round(sta_eff*.23))
    if readiness<85:target_outs-=1
    if readiness<70:target_outs-=2
    if readiness<55:target_outs-=2
    target_outs=max(9,min(24,target_outs))








    dominant=(er<=1 and traffic<=6)
    very_strong=(er<=2 and traffic<=7)
    if inning>=9 and outs>=24:
        return not (dominant and sta_eff>=60 and readiness>=85)
    if outs>=target_outs:
        extension=min(27,target_outs+3)
        if dominant and outs<extension:return False
        return True
    if inning>=8 and outs>=21 and not very_strong:return True
    return False
















def should_change_reliever(line,inning,role,lead_margin):
    if not line or line.get("GS"):return False
    outs=int(line.get("OUTS",0) or 0);er=int(line.get("ER",0) or 0);traffic=int(line.get("H",0) or 0)+int(line.get("BB",0) or 0)
    role=str(role or "RP").upper()








    # Performance hooks still matter regardless of inning.
    if er>=3 or traffic>=5:return True








    # Long relief is allowed to actually be long relief in non-leverage games.
    if role=="LR" and abs(lead_margin)>=4 and outs<9 and er<=1 and traffic<=5:
        return False








    # Two innings is a normal ceiling for most relievers.
    if outs>=6:return True








    # Protect the closer role for real save situations. A clean setup/middle arm may
    # bridge multiple innings instead of forcing three relievers into every game.
    if inning>=9 and 0<lead_margin<=3 and role!="CL":
        return True
    if inning>=8 and abs(lead_margin)<=3 and role not in ("SU1","SU2","CL") and outs>=3:
        return R.random()<.55
    return False
















# EBL RC55: no position-player bench.
# The Starting Nine remains the position-player unit for the full game.
# Pitching changes remain available through the pitching staff.








def steal_attempt_probability(player,strategy):
    attrs=player["attributes"]
    spd=float(attrs.get("SPD",0) or 0)
    briq=float(attrs.get("BRIQ",attrs.get("BR",0)) or 0)
    lead=float(attrs.get("LEAD",attrs.get("STEAL",0)) or 0)
    # A runner with no speed/instincts should almost never manufacture a steal
    # attempt. SPD creates the physical opportunity; BRIQ and LEAD decide whether
    # that opportunity becomes a controlled attempt.
    base=.012 + spd*.0024 + briq*.0018 + lead*.0022
    mult={"LOW":.55,"NORMAL":1.0,"HIGH":1.65}.get(strategy["substitutions"].get("steal_aggression","NORMAL"),1.0)
    return max(.003,min(.45,base*mult))
















def steal_success_probability(player,catcher=None):
    attrs=player["attributes"]
    spd=float(attrs.get("SPD",0) or 0)
    briq=float(attrs.get("BRIQ",attrs.get("BR",0)) or 0)
    lead=float(attrs.get("LEAD",attrs.get("STEAL",0)) or 0)
    defense=catcher or {}
    # Zero-skill runners no longer inherit an average-looking success rate. A
    # complete catcher can also erase part of the runner's advantage.
    catcher_penalty=(float(defense.get("ARM",0) or 0)*.00135 +
                     float(defense.get("ACC",0) or 0)*.00075 +
                     float(defense.get("REAC",0) or 0)*.00045)
    return max(.25,min(.96,.52+spd*.0040+briq*.0030+lead*.0035-catcher_penalty))
















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
















def fielding_range_skill(attrs,pos):
    """Individual range: getting to the ball is separate from catching/throwing it.








    Outfield range leans hardest on SPD, then REAC. Infield range leans on
    REAC/FLD with a smaller SPD component. ARM never substitutes for range.
    """
    a=attrs or {};pos=str(pos or "").upper()
    spd=max(0.0,float(a.get("SPD",0) or 0))
    reac=max(0.0,float(a.get("REAC",0) or 0))
    fld=max(0.0,float(a.get("FLD",0) or 0))
    if pos in {"LF","CF","RF"}:
        synergy=math.sqrt(spd*reac) if spd>0 and reac>0 else 0.0
        return .38*spd+.34*reac+.18*synergy+.10*fld
    if pos in {"SS","2B","3B","1B","P"}:
        return .20*spd+.47*reac+.33*fld
    return .12*spd+.43*reac+.45*fld
















def fielding_range_miss_probability(attrs,pos,difficulty):
    difficulty=max(0.0,min(1.0,float(difficulty or 0)))
    a=attrs or {};skill=fielding_range_skill(a,pos);pos=str(pos or "").upper()
    spd=max(0.0,float(a.get("SPD",0) or 0));reac=max(0.0,float(a.get("REAC",0) or 0));fld=max(0.0,float(a.get("FLD",0) or 0))
    if pos in {"LF","CF","RF"}:
        # Outfielders with near-zero speed are punished non-linearly: reaction can
        # identify the ball, but it cannot move the defender across the gap.
        core=.20-skill*.007 + .18*math.exp(-spd/5.0) + .05*math.exp(-fld/5.0)
        core=max(.010,min(.50,core))
    else:
        core=.17-skill*.005 + .08*math.exp(-reac/5.0) + .06*math.exp(-fld/5.0)
        core=max(.008,min(.34,core))
    # Routine balls remain catchable even by weak defenders; marginal balls expose
    # poor range sharply. This makes a 0-SPD center fielder a genuine coverage hole
    # without turning every ordinary CPU outfielder into a disaster.
    return max(.001,min(.52,core*(.15+.85*difficulty)))
















def fielding_catch_error_probability(attrs,out_kind):
    """Hands check after the defender has actually reached the ball."""
    a=attrs or {}
    fld=max(0.0,float(a.get("FLD",0) or 0))
    reac=max(0.0,float(a.get("REAC",0) or 0))
    if out_kind=="Lineout":
        p=.028+max(0.0,7.0-fld)*.008+max(0.0,7.0-reac)*.004
    else:
        p=.035+max(0.0,8.0-fld)*.012+max(0.0,5.0-reac)*.004
    if fld>8:
        p-=min(.025,(fld-8.0)*.0009)
    return max(.003,min(.16,p))
























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
    grant_roster_bonus(c,season,"CHAMPIONSHIP_WIN",[franchise_id],CHAMPIONSHIP_WIN_XP,"Won the EBL Championship",league_day)
    post_news(
        c,"CHAMPIONSHIP",
        f"🏆 {team['name']} WIN THE EBL CHAMPIONSHIP!",
        f"{team['name']} are Season {season} EBL Champions. The title is now part of the franchise and player legacy records.",
        league_day,franchise_id,None,None,5
    )
















def post_news(c,category,headline,body,league_day=0,franchise_id=None,player_id=None,game_id=None,importance=1,season=None):
    # News is season-aware so Day 1/Day 94 stories from different seasons never collide.
    if season is None and game_id is not None:
        gr=c.execute("SELECT season FROM games WHERE id=?",(game_id,)).fetchone()
        season=int(gr["season"]) if gr else None
    if season is None:
        season=_season_number(c)
    exists=c.execute("SELECT 1 FROM news WHERE season=? AND league_day=? AND headline=?",(season,league_day,headline)).fetchone()
    if exists:return
    c.execute("""INSERT INTO news(season,league_day,category,headline,body,franchise_id,player_id,game_id,importance)
                 VALUES(?,?,?,?,?,?,?,?,?)""",
              (season,league_day,category,headline,body,franchise_id,player_id,game_id,importance))
































# RC97: Discord bridge ---------------------------------------------------------
# Discord is an output surface, never a source of league truth. The database stays
# authoritative and the bridge only publishes events after they have been committed.
# Each channel is optional; leave an environment variable blank to disable that feed.
DISCORD_WEBHOOK_ENV={
    "NEWS":"EBL_DISCORD_NEWS_WEBHOOK",
    "RESULTS":"EBL_DISCORD_RESULTS_WEBHOOK",
    "TRANSACTIONS":"EBL_DISCORD_TRANSACTIONS_WEBHOOK",
    "AWARDS":"EBL_DISCORD_AWARDS_WEBHOOK",
}
















def _discord_url(feed):
    return str(os.environ.get(DISCORD_WEBHOOK_ENV.get(str(feed).upper(),""),"") or "").strip()
















def _discord_trim(value,limit):
    value=str(value or "").strip()
    if len(value)<=limit:return value
    return value[:max(0,limit-1)].rstrip()+"…"
















def discord_send(feed,title,description="",fields=None,color=0x173F35,footer="Elite Baseball League"):
    """Send one Discord webhook embed. Fail closed without exposing the webhook URL."""
    url=_discord_url(feed)
    if not url:
        return None  # disabled feed: caller may still advance its cursor
    embed={
        "title":_discord_trim(title,256),
        "description":_discord_trim(description,4000),
        "color":int(color),
        "footer":{"text":_discord_trim(footer,2048)},
        "timestamp":datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    clean_fields=[]
    for f in (fields or []):
        name=_discord_trim(f.get("name",""),256)
        value=_discord_trim(f.get("value",""),1024)
        if name and value:
            clean_fields.append({"name":name,"value":value,"inline":bool(f.get("inline",False))})
        if len(clean_fields)>=25:break
    if clean_fields:
        embed["fields"]=clean_fields
    payload={
        "username":"EBL Network",
        "allowed_mentions":{"parse":[]},
        "embeds":[embed],
    }
    try:
        req=Request(
            url,
            data=json.dumps(payload,separators=(",",":")).encode("utf-8"),
            headers={"Content-Type":"application/json","User-Agent":"EBL-Discord-Bridge/1.0"},
            method="POST",
        )
        with urlopen(req,timeout=12) as response:
            response.read()
            return 200 <= int(getattr(response,"status",204) or 204) < 300
    except HTTPError as e:
        try:e.read()
        except Exception:pass
        print(f"DISCORD WEBHOOK ERROR feed={feed}: HTTP {e.code}")
    except URLError as e:
        print(f"DISCORD WEBHOOK NETWORK ERROR feed={feed}: {type(e.reason).__name__}")
    except Exception as e:
        print(f"DISCORD WEBHOOK ERROR feed={feed}: {type(e).__name__}: {str(e)[:160]}")
    return False
















def _discord_state_get(c,key,default=None):
    r=c.execute("SELECT v FROM league_state WHERE k=?",(str(key),)).fetchone()
    return r["v"] if r else default
















def _discord_state_set(c,key,value):
    c.execute("INSERT OR REPLACE INTO league_state(k,v) VALUES(?,?)",(str(key),str(value)))
















def _discord_player_name(c,pid,fallback="Player"):
    try:
        r=c.execute("SELECT name FROM players WHERE id=?",(int(pid),)).fetchone()
        return r["name"] if r else fallback
    except Exception:
        return fallback
















def _discord_team_name(c,fid,fallback="Team"):
    if not fid:return fallback
    r=c.execute("""SELECT COALESCE(NULLIF(TRIM(fb.display_name),''),f.name) name
                   FROM franchises f LEFT JOIN franchise_branding fb ON fb.franchise_id=f.id
                   WHERE f.id=?""",(str(fid),)).fetchone()
    return r["name"] if r else str(fid)
















def _discord_transaction_card(c,row):
    try:payload=json.loads(row["payload_json"] or "{}")
    except Exception:payload={}
    event=str(row["event_type"] or "").upper()
    pid=payload.get("player_id")
    fid=payload.get("franchise_id")
    player=payload.get("player_name") or (_discord_player_name(c,pid) if pid else "Player")
    team=_discord_team_name(c,fid) if fid else ""








    if event=="CONTRACT_SIGNED":
        salary=float(payload.get("salary",0) or 0);bonus=float(payload.get("bonus",0) or 0);years=int(payload.get("years",1) or 1)
        role=str(payload.get("assigned_role") or payload.get("preferred_position") or "").upper()
        desc=f"**{player}** has signed with **{team}**."
        fields=[
            {"name":"Contract","value":f"{salary:.2f} XP/game • {years} season{'s' if years!=1 else ''}","inline":True},
            {"name":"Signing Bonus","value":f"{bonus:g} XP","inline":True},
        ]
        if role:fields.append({"name":"Roster Role","value":role,"inline":True})
        return ("📝 EBL Transaction",desc,fields,0xD4AF37)








    if event=="RENEWAL_ACCEPTED":
        salary=float(payload.get("salary",0) or 0);years=int(payload.get("years",1) or 1)
        effective=int(payload.get("effective_season",0) or 0)
        desc=f"**{player}** and **{team}** have agreed to a contract extension."
        fields=[{"name":"Extension","value":f"{salary:.2f} XP/game • {years} season{'s' if years!=1 else ''}","inline":True}]
        if effective:fields.append({"name":"Begins","value":f"Season {effective}","inline":True})
        return ("📝 Contract Extension",desc,fields,0xD4AF37)








    if event=="PLAYER_RETIRED":
        reason=str(payload.get("reason") or "").replace("_"," ").title()
        seasons=payload.get("seasons_played")
        desc=f"**{player}** has retired from the Elite Baseball League."
        fields=[]
        if team:fields.append({"name":"Final Club","value":team,"inline":True})
        if seasons is not None:fields.append({"name":"Career","value":f"{int(seasons)} season{'s' if int(seasons)!=1 else ''}","inline":True})
        if reason:fields.append({"name":"Retirement","value":reason,"inline":True})
        return ("🎓 EBL Retirement",desc,fields,0x6B7280)








    return None
















def _discord_flush_transactions(c):
    last=int(_discord_state_get(c,"discord_last_transaction_id","0") or 0)
    rows=c.execute("SELECT * FROM transactions WHERE id>? ORDER BY id LIMIT 40",(last,)).fetchall()
    for row in rows:
        card=_discord_transaction_card(c,row)
        url=_discord_url("TRANSACTIONS")
        if card and url:
            ok=discord_send("TRANSACTIONS",card[0],card[1],card[2],card[3],"Official EBL Transaction Wire")
            if ok is not True:
                return
        # Disabled/non-public events are intentionally consumed so turning the feed
        # on later does not dump old internal transactions into Discord.
        _discord_state_set(c,"discord_last_transaction_id",row["id"])
        c.commit()
















def _discord_flush_news(c):
    last=int(_discord_state_get(c,"discord_last_news_id","0") or 0)
    rows=c.execute("SELECT * FROM news WHERE id>? ORDER BY id LIMIT 40",(last,)).fetchall()
    for row in rows:
        should_post=int(row["importance"] or 1)>=2
        url=_discord_url("NEWS")
        if should_post and url:
            footer=f"Season {row['season']} • League Day {row['league_day']} • EBL Network"
            ok=discord_send("NEWS",row["headline"],row["body"],color=0x173F35,footer=footer)
            if ok is not True:
                return
        _discord_state_set(c,"discord_last_news_id",row["id"])
        c.commit()
















def _discord_flush_awards(c):
    last=int(_discord_state_get(c,"discord_last_award_id","0") or 0)
    rows=c.execute("""SELECT ah.*,p.name player_name
                      FROM award_history ah JOIN players p ON p.id=ah.player_id
                      WHERE ah.id>? ORDER BY ah.id LIMIT 40""",(last,)).fetchall()
    if not rows:return
    # Awards are normally written together on the final regular-season calendar day. Group them so Discord gets
    # one awards-show post rather than a dozen nearly simultaneous messages.
    groups=[];current=[];key=None
    for row in rows:
        rk=(int(row["season"]),str(row["period"]))
        if key is not None and rk!=key:
            groups.append(current);current=[]
        current.append(row);key=rk
    if current:groups.append(current)
    for group in groups:
        season=int(group[0]["season"]);period=str(group[0]["period"] or "").replace("_"," ").title()
        lines=[]
        for row in group:
            team=_discord_team_name(c,row["franchise_id"]) if row["franchise_id"] else ""
            suffix=f" — {team}" if team else ""
            lines.append(f"🏆 **{row['award_name']}** — {row['player_name']}{suffix}")
        url=_discord_url("AWARDS")
        if url:
            ok=discord_send("AWARDS",f"🏆 Season {season} EBL Awards","\n".join(lines),color=0xD4AF37,footer=f"{period} • Elite Baseball League")
            if ok is not True:
                return
        _discord_state_set(c,"discord_last_award_id",max(int(x["id"]) for x in group))
        c.commit()
















def _discord_next_result_day(c,last_season,last_day):
    return c.execute("""SELECT season,league_day
                        FROM games
                        WHERE status='FINAL' AND (season>? OR (season=? AND league_day>?))
                        GROUP BY season,league_day
                        ORDER BY season,league_day LIMIT 1""",
                     (last_season,last_season,last_day)).fetchone()
















def _discord_flush_results(c):
    last_season=int(_discord_state_get(c,"discord_results_season",str(_season_number(c))) or _season_number(c))
    last_day=int(_discord_state_get(c,"discord_results_day","0") or 0)
    nxt=_discord_next_result_day(c,last_season,last_day)
    if not nxt:return
    season=int(nxt["season"]);day=int(nxt["league_day"])
    rows=c.execute("""SELECT g.*,
                             COALESCE(NULLIF(TRIM(afb.display_name),''),af.name) away_name,
                             COALESCE(NULLIF(TRIM(hfb.display_name),''),hf.name) home_name
                      FROM games g
                      JOIN franchises af ON af.id=g.away_id
                      JOIN franchises hf ON hf.id=g.home_id
                      LEFT JOIN franchise_branding afb ON afb.franchise_id=af.id
                      LEFT JOIN franchise_branding hfb ON hfb.franchise_id=hf.id
                      WHERE g.season=? AND g.league_day=? AND g.status='FINAL'
                      ORDER BY g.id""",(season,day)).fetchall()
    lines=[]
    for g in rows:
        ar=int(g["away_runs"] or 0);hr=int(g["home_runs"] or 0)
        away=f"**{g['away_name']}**" if ar>hr else str(g["away_name"])
        home=f"**{g['home_name']}**" if hr>ar else str(g["home_name"])
        lines.append(f"{away} **{ar}** — {home} **{hr}**")
    url=_discord_url("RESULTS")
    if url and lines:
        # Split huge future slates safely while keeping a single day's games together
        # whenever possible.
        chunks=[];buf=[];size=0
        for line in lines:
            if buf and size+len(line)+1>3800:
                chunks.append(buf);buf=[];size=0
            buf.append(line);size+=len(line)+1
        if buf:chunks.append(buf)
        for i,chunk in enumerate(chunks,1):
            suffix=f" ({i}/{len(chunks)})" if len(chunks)>1 else ""
            ok=discord_send("RESULTS",f"⚾ EBL Scoreboard — Season {season}, Day {day}{suffix}","\n".join(chunk),color=0x1D4ED8,footer="Final Scores • Elite Baseball League")
            if ok is not True:
                return
    _discord_state_set(c,"discord_results_season",season)
    _discord_state_set(c,"discord_results_day",day)
    c.commit()
















def discord_bridge_bootstrap():
    """Initialize persistent cursors at the current database edge; never flood history."""
    c=conn()
    try:
        if _discord_state_get(c,"discord_bridge_initialized")!="1":
            tx=c.execute("SELECT COALESCE(MAX(id),0) n FROM transactions").fetchone()["n"]
            news=c.execute("SELECT COALESCE(MAX(id),0) n FROM news").fetchone()["n"]
            awards=c.execute("SELECT COALESCE(MAX(id),0) n FROM award_history").fetchone()["n"]
            season=_season_number(c)
            dayrow=c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()
            day=int(dayrow["v"] or 0) if dayrow else 0
            _discord_state_set(c,"discord_last_transaction_id",tx)
            _discord_state_set(c,"discord_last_news_id",news)
            _discord_state_set(c,"discord_last_award_id",awards)
            _discord_state_set(c,"discord_results_season",season)
            _discord_state_set(c,"discord_results_day",day)
            _discord_state_set(c,"discord_bridge_initialized","1")
            c.commit()
    finally:
        c.close()
















def discord_bridge_worker():
    """Publish committed EBL events to Discord without ever blocking gameplay."""
    while True:
        try:
            c=conn()
            try:
                _discord_flush_transactions(c)
                _discord_flush_news(c)
                _discord_flush_awards(c)
                _discord_flush_results(c)
            finally:
                c.close()
        except Exception as e:
            print(f"DISCORD BRIDGE ERROR: {type(e).__name__}: {str(e)[:200]}")
        time.sleep(10)
















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
















    # Individual performances deserve their own headlines when they clear a
    # genuinely dominant threshold. Keep these selective so the Newsroom feels
    # like a league newspaper instead of a box-score dump.
    for pid_s,line in (box.get("hitters") or {}).items():
        pid=int(pid_s)
        hits=int(line.get("H",0) or 0); hr=int(line.get("HR",0) or 0); rbi=int(line.get("RBI",0) or 0)
        if hr>=2 or hits>=4 or rbi>=5:
            pl=c.execute("SELECT name,franchise_id FROM players WHERE id=?",(pid,)).fetchone()
            if pl:
                feats=[]
                if hits:feats.append(f"{hits} hits")
                if hr:feats.append(f"{hr} HR")
                if rbi:feats.append(f"{rbi} RBI")
                post_news(c,"PLAYER",f"🔥 {pl['name']} delivers a dominant performance",
                          f"{pl['name']} powered the lineup with {', '.join(feats)} on League Day {day}.",
                          day,pl["franchise_id"],pid,g["id"],3,season=g["season"])








    for tfid,rows in (box.get("pitchers") or {}).items():
        for line in rows or []:
            pid=int(line.get("player_id",0) or 0); outs=int(line.get("OUTS",0) or 0)
            er=int(line.get("ER",0) or 0); so=int(line.get("SO",0) or 0)
            is_start=int(line.get("GS",0) or 0)==1
            dominant=(is_start and ((outs>=21 and er<=1 and so>=7) or (so>=10 and er<=2))) or ((not is_start) and outs>=6 and er==0 and so>=3)
            if dominant and pid:
                pl=c.execute("SELECT name,franchise_id FROM players WHERE id=?",(pid,)).fetchone()
                if pl:
                    ip=f"{outs//3}.{outs%3}"
                    post_news(c,"PLAYER",f"🔥 {pl['name']} dominates on the mound",
                              f"{pl['name']} worked {ip} innings with {so} strikeouts and {er} earned run{'s' if er!=1 else ''} on League Day {day}.",
                              day,pl["franchise_id"],pid,g["id"],3,season=g["season"])








    sev=box.get("strategy_events",[])
    if len(sev)>=8:
        post_news(c,"MANAGER",f"{names[winner]} lean on the dugout in tactical win",
                  f"The game featured {len(sev)} recorded strategy decisions, giving the EBL community plenty to debate after the final out.",
                  day,winner,None,g["id"],1)
















def generate_daily_news(c,day,season=None):
    season=int(season or _season_number(c))
    games=c.execute("SELECT * FROM games WHERE season=? AND league_day=? AND status='FINAL'",(season,day)).fetchall()
    if not games:return
    # Best run differential of the day.
    best=max(games,key=lambda x:abs(x["away_runs"]-x["home_runs"]))
    winner=best["away_id"] if best["away_runs"]>best["home_runs"] else best["home_id"]
    wn=c.execute("SELECT name FROM franchises WHERE id=?",(winner,)).fetchone()["name"]
    post_news(c,"AROUND_EBL",f"Around the EBL: {wn} make the loudest statement",
              f"Season {season}, League Day {day} is in the books. {len(games)} games reshaped the standings and added new player and team storylines.",
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
























def _record_player(c,key,label,value,pid,g,detail):
    """Update a player record only when the new value is strictly better."""
    old=c.execute("SELECT record_value FROM league_records WHERE record_key=?",(key,)).fetchone()
    if old and float(value)<=float(old["record_value"]):
        return False
    pl=c.execute("SELECT name,franchise_id FROM players WHERE id=?",(pid,)).fetchone()
    if not pl:return False
    c.execute("""INSERT OR REPLACE INTO league_records
        (record_key,record_label,record_value,holder_type,holder_id,game_id,league_day,detail)
        VALUES(?,?,?,?,?,?,?,?)""",
        (key,label,float(value),"PLAYER",str(pid),g["id"],int(g["league_day"]),detail))
    post_news(c,"RECORD",f"🏆 New EBL record: {pl['name']}",
              detail,int(g["league_day"]),pl["franchise_id"],pid,g["id"],3,season=g["season"])
    return True
















def update_player_game_records(c,g,box):
    """Permanent EBL single-game player records from the completed box score."""
    for pid_s,line in (box.get("hitters") or {}).items():
        pid=int(pid_s)
        pl=c.execute("SELECT name FROM players WHERE id=?",(pid,)).fetchone()
        if not pl:continue
        name=pl["name"]
        for key,label,stat in (
            ("PLAYER_H_GAME","Most Hits — Player, Game","H"),
            ("PLAYER_HR_GAME","Most Home Runs — Player, Game","HR"),
            ("PLAYER_RBI_GAME","Most RBI — Player, Game","RBI"),
            ("PLAYER_SB_GAME","Most Stolen Bases — Player, Game","SB"),
        ):
            value=int(line.get(stat,0) or 0)
            if value>0:
                _record_player(c,key,label,value,pid,g,f"{name} recorded {value} {stat} in one game.")








    for _fid,rows in (box.get("pitchers") or {}).items():
        for line in rows or []:
            pid=int(line.get("player_id",0) or 0)
            if not pid:continue
            pl=c.execute("SELECT name FROM players WHERE id=?",(pid,)).fetchone()
            if not pl:continue
            name=pl["name"]
            so=int(line.get("SO",0) or 0)
            outs=int(line.get("OUTS",0) or 0)
            if so>0:
                _record_player(c,"PLAYER_SO_GAME","Most Strikeouts — Pitcher, Game",so,pid,g,
                               f"{name} struck out {so} batters in one game.")
            if outs>=27 and int(line.get("H",0) or 0)==0:
                _record_player(c,"PLAYER_NOHITTER_OUTS","Longest No-Hit Start — Pitcher",outs,pid,g,
                               f"{name} completed {outs//3}.{outs%3} innings without allowing a hit.")
















def update_player_season_records(c,g):
    """Season records use the persisted season lines after this game is saved."""
    season=int(g["season"])
    for pl in c.execute("SELECT id,name,type,season_json FROM players WHERE active=1").fetchall():
        try:st=json.loads(pl["season_json"] or "{}")
        except Exception:continue
        pid=int(pl["id"]); name=pl["name"]
        if pl["type"]=="H":
            checks=(
                ("SEASON_H","Most Hits — Player, Season","H"),
                ("SEASON_HR","Most Home Runs — Player, Season","HR"),
                ("SEASON_RBI","Most RBI — Player, Season","RBI"),
                ("SEASON_SB","Most Stolen Bases — Player, Season","SB"),
            )
        else:
            checks=(
                ("SEASON_W","Most Wins — Pitcher, Season","W"),
                ("SEASON_SO","Most Strikeouts — Pitcher, Season","SO"),
                ("SEASON_SV","Most Saves — Pitcher, Season","SV"),
            )
        for key,label,stat in checks:
            value=int(st.get(stat,0) or 0)
            if value>0:
                _record_player(c,key,label,value,pid,g,
                               f"{name} reached {value} {stat} in Season {season}.")
















def update_player_milestones(c,g):
    """Post once-per-threshold milestone stories; news uniqueness prevents repeats."""
    season=int(g["season"]); day=int(g["league_day"])
    for pl in c.execute("SELECT id,name,franchise_id,type,season_json FROM players WHERE active=1").fetchall():
        try:st=json.loads(pl["season_json"] or "{}")
        except Exception:continue
        pid=int(pl["id"]); name=pl["name"]
        checks=(("H",25),("H",50),("H",75),("H",100),("HR",10),("HR",20),("HR",30),("SB",10),("SB",20)) if pl["type"]=="H" else (("SO",25),("SO",50),("SO",75),("SO",100),("W",5),("W",10),("SV",5),("SV",10))
        for stat,target in checks:
            if int(st.get(stat,0) or 0)>=target:
                headline=f"⭐ {name} reaches {target} {stat}"
                exists=c.execute("SELECT 1 FROM news WHERE season=? AND category='MILESTONE' AND player_id=? AND headline=?",
                                 (season,pid,headline)).fetchone()
                if not exists:
                    post_news(c,"MILESTONE",headline,
                              f"{name} reached the {target} {stat} milestone in Season {season}.",
                              day,pl["franchise_id"],pid,g["id"],2,season=season)








def weekly_recap(c,day,season=None):
    if day<=0 or day%7:return
    season=int(season or _season_number(c))
    games=c.execute("SELECT COUNT(*) n FROM games WHERE season=? AND league_day>? AND league_day<=? AND status='FINAL'",(season,day-7,day)).fetchone()["n"]
    if not games:return
    leader=c.execute("SELECT id,name,wins,losses FROM franchises ORDER BY wins DESC,losses ASC LIMIT 1").fetchone()
    post_news(c,"WEEKLY",f"EBL Week {day//7}: {leader['name']} set the pace",
              f"Seven more league days are complete in Season {season}. {leader['name']} lead at {leader['wins']}-{leader['losses']} as the pennant race, records, and breakout stories develop.",
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








        # RC56 — EBL has no position-player bench.
        # A club may carry only the nine active hitters used by the Starting Nine.
        # Do not rotate extra hitters into/out of the lineup at simulation time.
        # If legacy data somehow contains more than nine active hitters, preserve
        # the coach's saved Starting Nine and only use missing humans to fill holes.
        if len(human_ids)>9:
            saved_humans=[pid for pid in clean if pid in human_ids]
            missing_humans=[pid for pid in human_ids if pid not in saved_humans]
            human_ids=(saved_humans+missing_humans)[:9]
















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
        # Unmanaged clubs get a true baseball-style order every game instead of
        # inheriting defensive-position order (C, 1B, 2B, ...). Human coaches keep
        # complete control of any batting order they save.
        fr=c.execute("SELECT owner_user_id FROM franchises WHERE id=?",(fid,)).fetchone()
        if fr and fr["owner_user_id"] is None and len(lineups[fid])==9:
            lineups[fid]=auto_batting_order(c,lineups[fid])
    rotations={fid:json.loads(lrows[fid]["rotation_json"]) for fid in [away,home]}
    auto_bullpens={}
    # Unmanaged clubs rebuild their staff from the active roster every game.
    # Rotation order and bullpen hierarchy are determined by pitcher OVR, so a
    # newly signed human reliever cannot be trapped outside stale strategy JSON.
    for rf in [away,home]:
        fr=c.execute("SELECT owner_user_id FROM franchises WHERE id=?",(rf,)).fetchone()
        if fr and fr["owner_user_id"] is None:
            auto_rot,auto_bp=auto_pitching_plan(c,rf)
            if auto_rot:
                rotations[rf]=auto_rot
            auto_bullpens[rf]=auto_bp
    # Guard against an old/incomplete rotation. A playable club needs 3-5 pitchers;
    # old CPU saves remain valid with their existing four-man default.
    for rf in [away,home]:
        rotations[rf]=[int(x) for x in rotations[rf] if x is not None]
        if len(rotations[rf])<3:
            fallback=[int(x["id"]) for x in c.execute("SELECT id FROM players WHERE franchise_id=? AND type='P' AND active=1 ORDER BY id",(rf,)).fetchall()]
            for pid in fallback:
                if pid not in rotations[rf]:rotations[rf].append(pid)
                if len(rotations[rf])>=3:break
        rotations[rf]=rotations[rf][:5]








    def scheduled_starter_id(fid):
        rot=rotations[fid]
        game_day=int(g["league_day"]);season_no=int(g["season"])
        if game_day>REGULAR_SEASON_CALENDAR_DAYS:
            games_before=_team_postseason_games_before(c,season_no,fid,game_day)
        else:
            games_before=_team_regular_games_before(c,season_no,fid,game_day)
        return int(rot[games_before%len(rot)])








    starter_ids={fid:scheduled_starter_id(fid) for fid in [away,home]}
    pregame_fatigue={fid:{} for fid in [away,home]}
    for fid in [away,home]:
        for pid in rotations[fid]:
            pregame_fatigue[fid][int(pid)]=pitcher_recovery_state(c,int(pid),int(g["league_day"]))["fatigue"]








    strategies={fid:team_strategy_for(c,fid) for fid in [away,home]}
    for fid,bp in auto_bullpens.items():
        strategies[fid]["bullpen"]=bp








    # Team defense is a real simulation input. Better FLD/REAC turn more marginal
    # balls into outs; ARM/ACC reduce extra-base damage. This is intentionally
    # a moderate modifier so defense matters without overwhelming batted-ball quality.
    defense_rating={}
    for dfid in [away,home]:
        dvals=[]
        for dr in c.execute("SELECT attributes_json FROM players WHERE franchise_id=? AND type='H' AND active=1 AND status='SIGNED'",(dfid,)).fetchall():
            da=json.loads(dr["attributes_json"] or "{}")
            dvals.append(
                (float(da.get("FLD",0) or 0)+team_attribute_bonus(c,dfid,"FLD"))*.30+
                (float(da.get("REAC",0) or 0)+team_attribute_bonus(c,dfid,"REAC"))*.25+
                (float(da.get("SPD",0) or 0)+team_attribute_bonus(c,dfid,"SPD"))*.20+
                (float(da.get("ARM",0) or 0)+team_attribute_bonus(c,dfid,"ARM"))*.125+
                (float(da.get("ACC",0) or 0)+team_attribute_bonus(c,dfid,"ACC"))*.125
            )
        defense_rating[dfid]=sum(dvals)/len(dvals) if dvals else 0.0








    score={away:0,home:0};events=[];box={"hitters":{},"pitchers":{},"fielding":{},"xp":[],"strategy_events":[]}
    defense_players={}
    for dfid in [away,home]:
        defense_players[dfid]={}
        # Prefer the coach's saved field alignment when it still matches the
        # nine active batters. This makes defensive position a true game-day
        # assignment rather than a permanent roster-slot restriction.
        saved_field={}
        try:
            saved_field=json.loads(lrows[dfid]["field_positions_json"] or "{}") if lrows[dfid] else {}
        except Exception:
            saved_field={}
        normalized={}
        for pos,pid in (saved_field or {}).items():
            try:normalized[str(pos).upper()]=int(pid)
            except Exception:pass
        required={"C","1B","2B","3B","SS","LF","CF","RF","DH"}
        if set(normalized.keys())==required and set(normalized.values())==set(int(x) for x in lineups[dfid]):
            defense_players[dfid]={pos:pid for pos,pid in normalized.items() if pos!="DH"}
        else:
            # Backward-compatible fallback for CPU/legacy lineups that have not
            # saved a field alignment yet.
            lineup_ids=set(int(x) for x in lineups[dfid])
            for rr in c.execute("""SELECT position_group,player_id FROM roster_slots WHERE franchise_id=? AND player_id IS NOT NULL""",(dfid,)).fetchall():
                pos=str(rr["position_group"] or "").upper()
                pid=int(rr["player_id"]) if rr["player_id"] is not None else None
                if pid in lineup_ids and pos in {"C","1B","2B","3B","SS","LF","CF","RF"} and pos not in defense_players[dfid]:
                    defense_players[dfid][pos]=pid








    catcher_skill={}
    for dfid in [away,home]:
        cid=defense_players.get(dfid,{}).get("C")
        cp=sim_player_obj(c,cid) if cid else None
        ca=(cp or {}).get("attributes",{})
        catcher_skill[dfid]={
            "player_id":cid,
            "CALL":float(ca.get("CALL",0) or 0),
            "ARM":float(ca.get("ARM",0) or 0),
            "ACC":float(ca.get("ACC",0) or 0),
            "REAC":float(ca.get("REAC",0) or 0),
        }








    def fielding_line(pid):
        key=str(pid)
        if key not in box["fielding"]:
            box["fielding"][key]={"FG":1,"PO":0,"A":0,"E":0,"DP":0,"OAA":0.0,"CH":0,"OFA":0,"POS":""}
        return box["fielding"][key]








    # Every defender who takes the field receives a fielding-game appearance even
    # if no ball is hit directly to him. Actual chances are recorded below.
    for dfid in [away,home]:
        for dpos,dpid in defense_players.get(dfid,{}).items():
            dl=fielding_line(dpid)
            dl["POS"]=dpos








    def choose_fielder(dfid,spray,launch):
        if launch>=18:
            pos="LF" if spray<-13 else "RF" if spray>13 else "CF"
        elif launch<=5:
            pos="3B" if spray<-18 else "SS" if spray<0 else "2B" if spray<18 else "1B"
        else:
            pos="SS" if spray<0 else "2B"
        pid=defense_players.get(dfid,{}).get(pos)
        if not pid:
            opts=list(defense_players.get(dfid,{}).values())
            pid=R.choice(opts) if opts else None
        return pos,sim_player_obj(c,pid) if pid else None








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
            starter_id=starter_ids[fid]
            pitcher_live[fid][pid]={
                "G":1,"GS":1 if pid==starter_id else 0,"OUTS":0,
                "H":0,"ER":0,"BB":0,"SO":0,"W":0,"L":0,"SV":0
            }
            pfl=fielding_line(pid)
            pfl["POS"]="P"
        return pitcher_live[fid][pid]
















    used_pitchers={away:set(),home:set()}
    base_runner={away:None,home:None}
    unearned_runners={away:set(),home:set()}
    current_pitcher={}
    current_pitcher_role={away:"SP",home:"SP"}
    for fid,opp in [(away,home),(home,away)]:
        current_pitcher[fid]=starter_ids[fid]
        used_pitchers[fid].add(current_pitcher[fid])
















    events.append({"type":"GAME_START","away":away,"home":home,"away_name":team_names[away],"home_name":team_names[home],"score":[0,0]})
















    for inning in range(1,10):
        for half,fid,opp in [("TOP",away,home),("BOT",home,away)]:
            outs=0;idx=((inning-1)*4)%9
            # Between-inning pitching management. Starters are evaluated by actual
            # workload/performance; relievers are not automatically replaced just
            # because the calendar reached the 8th or 9th.
            opp_diff=score[opp]-score[fid]
            live_line=pitcher_line(opp,current_pitcher[opp])
            change_reason=None
            if live_line.get("GS"):
                starter_obj=sim_player_obj(c,current_pitcher[opp])
                sta=float((starter_obj or {}).get("attributes",{}).get("STA",0) or 0)
                readiness=max(35,100-float(pregame_fatigue.get(opp,{}).get(int(current_pitcher[opp]),0.0) or 0.0))
                if should_pull_starter(live_line,inning,sta,readiness):
                    change_reason="STARTER_HOOK"
            elif should_change_reliever(live_line,inning,current_pitcher_role.get(opp),opp_diff):
                change_reason="BULLPEN_ROLE"








            if change_reason:
                rp,role=choose_reliever(c,opp,strategies[opp],inning,opp_diff,used_pitchers[opp],rotations[opp],g["league_day"])
                if rp and rp!=current_pitcher[opp]:
                    current_pitcher[opp]=rp;current_pitcher_role[opp]=role or "RP";used_pitchers[opp].add(rp)
                    ev={"type":"PITCHING_CHANGE","team":opp,"pitcher_id":rp,"role":role,"inning":inning,"half":half,"reason":change_reason}
                    events.append(ev);box["strategy_events"].append(ev)
            while outs<3:
                live_line=pitcher_line(opp,current_pitcher[opp])
                if live_line.get("GS"):
                    starter_obj=sim_player_obj(c,current_pitcher[opp])
                    sta=float((starter_obj or {}).get("attributes",{}).get("STA",0) or 0)
                    readiness=max(35,100-float(pregame_fatigue.get(opp,{}).get(int(current_pitcher[opp]),0.0) or 0.0))
                    if should_pull_starter(live_line,inning,sta,readiness):
                        rp,role=choose_reliever(c,opp,strategies[opp],inning,score[opp]-score[fid],used_pitchers[opp],rotations[opp],g["league_day"])
                        if rp and rp!=current_pitcher[opp]:
                            current_pitcher[opp]=rp;current_pitcher_role[opp]=role or "RP";used_pitchers[opp].add(rp)
                            ev={"type":"PITCHING_CHANGE","team":opp,"pitcher_id":rp,"role":role,"inning":inning,"half":half,"reason":"STARTER_HOOK"}
                            events.append(ev);box["strategy_events"].append(ev)
                else:
                    # Mid-inning reliever hooks are reserved for genuine trouble, not
                    # routine role cycling. This keeps clean relievers in the game.
                    traffic=int(live_line.get("H",0) or 0)+int(live_line.get("BB",0) or 0)
                    if int(live_line.get("ER",0) or 0)>=3 or traffic>=5:
                        rp,role=choose_reliever(c,opp,strategies[opp],inning,score[opp]-score[fid],used_pitchers[opp],rotations[opp],g["league_day"])
                        if rp and rp!=current_pitcher[opp]:
                            current_pitcher[opp]=rp;current_pitcher_role[opp]=role or "RP";used_pitchers[opp].add(rp)
                            ev={"type":"PITCHING_CHANGE","team":opp,"pitcher_id":rp,"role":role,"inning":inning,"half":half,"reason":"RELIEVER_TROUBLE"}
                            events.append(ev);box["strategy_events"].append(ev)
                starter_batter_id=lineups[fid][idx%9];idx+=1
                # RC55 — no position-player bench: the scheduled Starting Nine bats.
                batter=sim_player_obj(c,starter_batter_id)
                batline=hitter_line(batter["id"])
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
                balls=strikes=0;pitch_no=0;prev_pitch_type=None
                while True:
                    pitch_no+=1
                    bat_attrs=batter.get("attributes",{})
                    pit_attrs=pitcher.get("attributes",{})








                    con=float(bat_attrs.get("CON",0) or 0)
                    powr=float(bat_attrs.get("POW",0) or 0)
                    vis=float(bat_attrs.get("VIS",0) or 0)
                    disc=float(bat_attrs.get("DISC",0) or 0)
                    tim=float(bat_attrs.get("TIM",0) or 0)








                    ctrl_raw=float(pit_attrs.get("CTRL",0) or 0)
                    cmd_raw=float(pit_attrs.get("CMD",0) or 0)
                    vel_raw=float(pit_attrs.get("VEL",0) or 0)
                    brk_raw=float(pit_attrs.get("BRK",0) or 0)
                    mov_raw=float(pit_attrs.get("MOV",0) or 0)
                    dec_raw=float(pit_attrs.get("DEC",0) or 0)
                    seq_raw=float(pit_attrs.get("SEQ",0) or 0)
                    sta=float(pit_attrs.get("STA",0) or 0)
                    pclt=float(pit_attrs.get("PCLT",0) or 0)
                    sta_eff=effective_stamina(sta)








                    # STA does not award outs directly; it delays skill loss as workload grows.
                    fatigue_start=(14.0+sta_eff*.15) if pitchline.get("GS") else (3.0+sta_eff*.04)
                    fatigue=max(0.0,float(pitchline.get("OUTS",0))-fatigue_start)
                    carry_fatigue=float(pregame_fatigue.get(opp,{}).get(int(pitcher["id"]),0.0) or 0.0)
                    fatigue_penalty=fatigue*.55 + carry_fatigue*.18








                    # PCLT helps a pitcher retain command/movement in genuinely high-leverage
                    # late innings. It is a modifier on physical skills, not a result roll.
                    leverage=inning>=7 and abs(score[fid]-score[opp])<=2
                    clutch_bonus=(pclt*.10) if leverage else 0.0
                    # Catcher CALL is deliberately subtle: elite game-calling improves
                    # command and pitch-shape execution a little over many plate appearances.
                    call_rating=float(catcher_skill.get(opp,{}).get("CALL",0) or 0)
                    call_ctrl=call_rating*.040
                    call_brk=call_rating*.025








                    ctrl=max(0.0,ctrl_raw-fatigue_penalty+clutch_bonus+call_ctrl)
                    cmd=max(0.0,cmd_raw-fatigue_penalty*.55+clutch_bonus*.55)
                    vel_attr=max(0.0,vel_raw-fatigue_penalty*.60+clutch_bonus*.35)
                    brk=max(0.0,brk_raw-fatigue_penalty*.75+clutch_bonus*.65+call_brk)
                    mov=max(0.0,mov_raw-fatigue_penalty*.45+clutch_bonus*.35)
                    dec=max(0.0,dec_raw-fatigue_penalty*.20+clutch_bonus*.20)
                    seq=max(0.0,seq_raw-fatigue_penalty*.15+clutch_bonus*.30)








                    # Physical pitch properties come from actual skills. Sequencing makes
                    # advanced pitchers less likely to repeat the same look back-to-back.
                    pitch_types=["Four-Seam","Slider","Changeup","Sinker","Curve"]
                    ptype=R.choice(pitch_types)
                    if pitch_no>1 and prev_pitch_type and ptype==prev_pitch_type and R.random()<min(.82,seq*.008):
                        ptype=R.choice([x for x in pitch_types if x!=prev_pitch_type])
                    pitch_speed_base={
                        "Four-Seam":90.0,
                        "Sinker":88.5,
                        "Slider":84.5,
                        "Changeup":82.5,
                        "Curve":79.5,
                    }[ptype]
                    vel=round(max(72.0,min(103.0,R.gauss(pitch_speed_base+vel_attr*.18,1.35))),1)








                    # RC57 ATTRIBUTE SPECIALIZATION GATES
                    # CTRL/CMD determine whether the pitcher can actually reach useful locations.
                    # DEC/SEQ can improve choices, but they cannot substitute for raw command.
                    # The lower baseline intentionally makes very low-control pitchers pay a
                    # visible walk penalty while still keeping a playable floor for new builds.
                    zone_p=max(.41,min(.69,.448+ctrl*.0028+cmd*.0010))
                    in_zone=R.random()<zone_p
                    edge=max(0.0,min(1.0,R.random()+ctrl*.0025+cmd*.0030-.12))
                    if in_zone:
                        loc_sd=max(.065,.16-.0007*min(ctrl,80)-.00045*min(cmd,80))
                        px=round(max(.05,min(.95,R.gauss(.5,loc_sd))),3)
                        pz=round(max(.05,min(.95,R.gauss(.5,loc_sd))),3)
                        swing_p=max(.60,min(.84,.69+vis*.0012+(.025 if strikes==2 else 0)-(.01 if balls==3 else 0)))
                    else:
                        px=round(R.choice([R.uniform(.02,.18),R.uniform(.82,.98)]),3)
                        pz=round(R.choice([R.uniform(.02,.18),R.uniform(.82,.98)]),3)
                        # BRK/MOV create the actual chase quality. DEC/SEQ only help when the
                        # pitcher's physical execution gives those choices something to work with.
                        physical_chase=brk*.0020+mov*.0010
                        craft_gate=max(.25,min(1.0,(brk+mov+cmd+vel_attr)/70.0))
                        craft_chase=(dec*.00045+seq*(.00075 if strikes==2 else .00015))*craft_gate
                        swing_p=max(.045,min(.44,.255+physical_chase+craft_chase-disc*.0032-vis*.0013+(.030 if strikes==2 else 0)-(.050 if balls==3 else 0)))








                    if R.random()>=swing_p:
                        if in_zone:
                            strikes+=1;call="Called Strike"
                        else:
                            balls+=1;call="Ball"
                    else:
                        # Bat-to-ball is now its own gate. CON/TIM do the physical hitting;
                        # VIS helps only a little once the swing has already been chosen.
                        # Likewise, DEC/SEQ amplify executed stuff instead of replacing it.
                        physical_pitch=.46*vel_attr+.50*brk+.16*mov+.10*ctrl*edge+.20*cmd*edge
                        craft_gate=max(.20,min(1.0,(vel_attr+brk+mov+cmd)/65.0))
                        sequencing=(seq*(.10 if prev_pitch_type and ptype!=prev_pitch_type else .025)+dec*.07)*craft_gate
                        pitch_skill=physical_pitch+sequencing
                        hitter_skill=.66*con+.30*tim+.04*vis
                        whiff=max(.06,min(.72,.325+(pitch_skill-hitter_skill)*.0046+(.105 if not in_zone else 0)))
                        if R.random()<whiff:
                            strikes+=1;call="Swinging Strike"
                        else:
                            foul_p=max(.13,min(.36,.29-tim*.0010+brk*.0006))
                            if R.random()<foul_p:
                                if strikes<2:strikes+=1
                                call="Foul"
                            else:
                                call="In Play"
















                    events.append({
                        "type":"PITCH","inning":inning,"half":half,
                        "pitch_no":pitch_no,"pitch_type":ptype,"velocity":vel,
                        "px":px,"pz":pz,"call":call,
                        "balls":min(balls,4),"strikes":min(strikes,3),
                        "batter_id":batter["id"],"pitcher_id":pitcher["id"]
                    })
                    prev_pitch_type=ptype
















                    if call=="In Play":
                        # Contact quality is produced from hitter skill versus pitch quality.
                        # POW/TIM/CON create exit velocity and launch-angle quality; VEL/BRK
                        # suppress it. Team defense then influences whether marginal contact
                        # falls safely, rather than a hidden H9/HR9 roll deciding the result.
                        # Separate bat-to-ball skill from impact power so specialized builds
                        # produce visibly different outcomes instead of converging on one generic
                        # contact-quality score. CON/TIM control how often playable contact
                        # becomes a hit; POW/TIM drive impact and home-run damage.
                        # Once the ball is in play, VIS/DISC no longer create hits. They got the
                        # hitter to the right swing decision; CON/TIM must still produce contact.
                        contact_matchup=(.68*con+.32*tim)-(.08*vel_attr+.08*brk+.05*mov+.04*cmd)
                        impact=.62*powr+.22*tim+.16*con-(.10*vel_attr+.08*brk+.10*mov+.04*cmd+.02*dec)
                        exit_velo=round(max(55.0,min(122.0,R.gauss(88.5+impact*.23,7.1))),1)
                        launch_sd=max(10.0,15.8-tim*.08)
                        launch_angle=round(max(-45.0,min(55.0,R.gauss(11.5+tim*.09+powr*.055-mov*.07,launch_sd))),1)
                        spray=round(R.uniform(-42,42),1)








                        power_matchup=.70*powr+.20*tim+.10*con-(.10*mov+.08*brk+.04*vel_attr)
                        hr_score=(exit_velo-97.0)/4.2-abs(launch_angle-27.0)/10.5+(power_matchup-10.0)*.022
                        power_gate=max(.45,min(1.10,.45+powr*.012))
                        hr_p=max(.001,min(.24,power_gate*.30/(1.0+math.exp(-hr_score))))








                        hit_score=(exit_velo-87.2)/7.2-abs(launch_angle-14.0)/22.0
                        # Low CON/TIM carries an explicit penalty instead of being rescued by VIS.
                        # High CON/TIM earns a much larger ceiling so specialization is visible.
                        low_contact_penalty=max(0.0,10.0-con)*.0055+max(0.0,7.0-tim)*.0030
                        contact_bonus=max(-.14,min(.16,(contact_matchup-8.0)*.0032-low_contact_penalty))
                        defense_adj=(defense_rating.get(opp,0.0)-5.0)*.0025
                        hit_p=max(.08,min(.72,.145+.38/(1.0+math.exp(-hit_score))+contact_bonus-defense_adj+shift_adj))








                        roll=R.random()
                        if roll<hr_p:
                            result="HR"
                        elif roll<hit_p:
                            xbh_p=max(.11,min(.44,.20+(exit_velo-90.0)*.0065+max(0.0,launch_angle-10.0)*.0028))
                            triple_p=max(.003,min(.035,.006+float(bat_attrs.get("SPD",0) or 0)*.00035))
                            xb=R.random()
                            if xb<triple_p:
                                result="3B"
                            elif xb<triple_p+xbh_p:
                                result="2B"
                            else:
                                result="1B"
                        else:
                            result="OUT"
                        # Resolve the actual defensive play from the assigned fielder.
                        # Ground balls are multi-player plays: the infielder must field it,
                        # make the throw, and the first baseman must receive it. FLD/REAC
                        # govern range/hands; ARM/ACC govern the throw; batter SPD affects
                        # whether a cleanly fielded grounder becomes an infield hit.
                        out_kind="Flyout" if launch_angle>=18 else "Groundout" if launch_angle<=5 else "Lineout"
                        fpos,fielder=choose_fielder(opp,spray,launch_angle)
                        if launch_angle<=5 and abs(spray)<7 and R.random()<.14:
                            fpos,fielder="P",pitcher
                        elif launch_angle>38 and abs(spray)<9 and R.random()<.18:
                            cpid=defense_players.get(opp,{}).get("C")
                            if cpid: fpos,fielder="C",sim_player_obj(c,cpid)








                        fielder_id=int(fielder["id"]) if fielder else None
                        first_base_id=defense_players.get(opp,{}).get("1B")
                        putout_id=None
                        assist_ids=[]
                        error_fielder_id=None
                        error_type=None
                        defensive_note=None








                        if result!="HR" and fielder:
                            fa=fielder.get("attributes",{})
                            # sim_player_obj already contains the temporary sponsor bonus.
                            # Never add it again here or a +1 sponsor becomes +2 in a play check.
                            fld=float(fa.get("FLD",0) or 0)
                            reac=float(fa.get("REAC",0) or 0)
                            arm=float(fa.get("ARM",0) or 0)
                            acc=float(fa.get("ACC",0) or 0)
                            fl=fielding_line(fielder_id);fl["POS"]=fpos;fl["CH"]+=1
                            batter_spd=float(bat_attrs.get("SPD",0) or 0)








                            first_obj=sim_player_obj(c,first_base_id) if first_base_id else None
                            first_attrs=(first_obj or {}).get("attributes",{})
                            first_fld=float(first_attrs.get("FLD",0) or 0)
                            first_reac=float(first_attrs.get("REAC",0) or 0)








                            if result=="OUT":
                                # The pre-fielding result says the batted ball is normally an out.
                                # Individual range now decides whether the assigned defender can
                                # actually reach it. A miss is a hit, not an error.
                                denominator=max(.001,1.0-hit_p)
                                difficulty=max(0.0,min(1.0,1.0-((roll-hit_p)/denominator)))
                                range_miss_p=fielding_range_miss_probability(fa,fpos,difficulty)
                                if R.random()<range_miss_p:
                                    if fpos in {"LF","CF","RF"} and launch_angle>=18 and (exit_velo>=94 or difficulty>=.72):
                                        result="2B" if R.random()<max(.12,min(.42,.18+(exit_velo-90)*.010+difficulty*.10)) else "1B"
                                    else:
                                        result="1B"
                                    defensive_note="OUTFIELD_RANGE_MISS" if fpos in {"LF","CF","RF"} else "RANGE_MISS"
                                    fl["OAA"]-=round(.25+.55*difficulty,2)
                                    events.append({"type":"RANGE_MISS","inning":inning,"half":half,"team":opp,"fielder_id":fielder_id,"position":fpos,"batter_id":batter["id"],"difficulty":round(difficulty,3),"range_skill":round(fielding_range_skill(fa,fpos),2)})
                                elif out_kind=="Groundout":
                                    # Unassisted first-base grounder.
                                    if fpos=="1B" or not first_obj:
                                        field_err_p=max(.004,min(.070,.036-fld*.00065-reac*.00045))
                                        if R.random()<field_err_p:
                                            result="ROE";fl["E"]+=1;fl["OAA"]-=.35
                                            error_fielder_id=fielder_id;error_type="field"
                                        else:
                                            fl["PO"]+=1;putout_id=fielder_id
                                            if R.random()<max(0.0,min(.10,(fld+reac-24)*.0025)):fl["OAA"]+=.20
                                    else:
                                        # 6-3 / 5-3 / 4-3 / 1-3 style play. The throw and
                                        # first baseman's receiving ability are separate checks.
                                        field_err_p=max(.004,min(.070,.036-fld*.00065-reac*.00045))
                                        throw_err_p=max(.003,min(.045,.020-arm*.00025-acc*.00045-first_fld*.00010))
                                        receive_err_p=max(.002,min(.035,.014-first_fld*.00025-first_reac*.00012))
                                        beat_throw_p=max(.004,min(.090,.012+batter_spd*.00070-reac*.00015-fld*.00012-arm*.00010-acc*.00018))
                                        if R.random()<field_err_p:
                                            result="ROE";fl["E"]+=1;fl["OAA"]-=.35
                                            error_fielder_id=fielder_id;error_type="field"
                                        elif R.random()<throw_err_p:
                                            result="ROE";fl["E"]+=1;fl["OAA"]-=.30
                                            error_fielder_id=fielder_id;error_type="throw"
                                        else:
                                            first_line=fielding_line(first_base_id);first_line["POS"]="1B";first_line["CH"]+=1
                                            if R.random()<receive_err_p:
                                                result="ROE";first_line["E"]+=1;first_line["OAA"]-=.30
                                                fl["A"]+=1;assist_ids=[fielder_id]
                                                error_fielder_id=int(first_base_id);error_type="receive"
                                            elif R.random()<beat_throw_p:
                                                result="1B"
                                                defensive_note="INFIELD_HIT"
                                                if fld+reac<18:fl["OAA"]-=.05
                                            else:
                                                fl["A"]+=1;first_line["PO"]+=1
                                                assist_ids=[fielder_id];putout_id=int(first_base_id)
                                                if R.random()<max(0.0,min(.10,(fld+reac+arm+acc-44)*.0013)):fl["OAA"]+=.20
                                else:
                                    # Once the defender reaches the ball, FLD is the hands/catch
                                    # skill. REAC helps, but speed and arm cannot rescue bad hands.
                                    catch_err_p=fielding_catch_error_probability(fa,out_kind)
                                    collision=False
                                    if fpos in {"LF","CF","RF"}:
                                        coll_p=max(.0005,min(.015,.010-(fld+reac)*.00028))
                                        collision=R.random()<coll_p
                                    if collision or R.random()<catch_err_p:
                                        result="ROE";fl["E"]+=1;fl["OAA"]-=.35
                                        error_fielder_id=fielder_id;error_type="collision" if collision else "field"
                                        if collision:
                                            events.append({"type":"FIELDING_COLLISION","inning":inning,"half":half,"team":opp,"fielder_id":fielder_id,"position":fpos,"batter_id":batter["id"]})
                                    else:
                                        fl["PO"]+=1;putout_id=fielder_id
                                        difficulty=max(0.0,(exit_velo-91.0)*.018+abs(spray)*.003)
                                        if R.random()<max(0.0,min(.12,(fld*.55+reac*.45-18)*.0030+difficulty*.01)):fl["OAA"]+=.25








                            elif result in {"1B","2B","3B"}:
                                # Exceptional range can turn a marginal hit into an out. This uses
                                # the individual fielder rather than only the club-average defense.
                                if out_kind=="Groundout":
                                    range_skill=fielding_range_skill(fa,fpos)
                                    throw_skill=arm*.45+acc*.55
                                    great_p=max(0.0,min(.15,(range_skill*.74+throw_skill*.26-batter_spd*.18-10)*.0032))
                                else:
                                    range_skill=fielding_range_skill(fa,fpos)
                                    great_p=max(0.0,min(.15,(range_skill-11)*.0048-(max(0,exit_velo-96)*.0015)))
                                if result=="1B" and R.random()<great_p:
                                    result="OUT";fl["OAA"]+=1.0
                                    if out_kind=="Groundout" and fpos!="1B" and first_obj:
                                        first_line=fielding_line(first_base_id);first_line["POS"]="1B";first_line["CH"]+=1
                                        fl["A"]+=1;first_line["PO"]+=1;assist_ids=[fielder_id];putout_id=int(first_base_id)
                                    else:
                                        fl["PO"]+=1;putout_id=fielder_id
                                    events.append({"type":"GREAT_PLAY","inning":inning,"half":half,"team":opp,"fielder_id":fielder_id,"position":fpos,"batter_id":batter["id"],"out_type":out_kind})
                                elif result=="2B" and fpos in {"LF","CF","RF"}:
                                    # Strong/accurate outfield arms can keep borderline doubles to singles.
                                    hold_p=max(0.0,min(.18,(arm*.55+acc*.45-batter_spd*.25-18)*.0025))
                                    if R.random()<hold_p:
                                        result="1B";defensive_note="HELD_TO_SINGLE"
                                        events.append({"type":"OUTFIELD_HOLD","inning":inning,"half":half,"team":opp,"fielder_id":fielder_id,"position":fpos,"batter_id":batter["id"]})
                                elif exit_velo<92 and fld+reac<12:
                                    fl["OAA"]-=.08








                            if error_fielder_id is not None:
                                events.append({"type":"FIELDING_ERROR","inning":inning,"half":half,"team":opp,"fielder_id":error_fielder_id,"position":fpos if error_fielder_id==fielder_id else "1B","error_type":error_type or "field","batter_id":batter["id"],"out_type":out_kind})








                        events.append({
                            "type":"BALL_IN_PLAY","inning":inning,"half":half,
                            "batter_id":batter["id"],"pitcher_id":pitcher["id"],
                            "result":result,"exit_velocity":exit_velo,
                            "launch_angle":launch_angle,"spray_angle":spray,
                            "contact_quality":"Barrel" if exit_velo>103 and 18<=launch_angle<=32 else "Hard" if exit_velo>95 else "Normal",
                            "shift":shift_mode,
                            "out_type":out_kind,"fielder_id":fielder_id,"fielder_position":fpos if fielder else None,
                            "putout_id":putout_id,"assist_ids":assist_ids,"first_base_id":int(first_base_id) if first_base_id else None,
                            "defensive_note":defensive_note
                        })
















                        batline["AB"]+=1
















                        if result=="ROE":
                            base_runner[fid]=batter["id"]
                            unearned_runners[fid].add(batter["id"])
                            events.append({"type":"PA_END","inning":inning,"half":half,"batter_id":batter["id"],"pitcher_id":pitcher["id"],"result":"ROE","outs":outs,"score":[score[away],score[home]]})
                            break
                        if result=="OUT":
                            outs+=1
                            pitchline["OUTS"]+=1
                            events.append({
                                "type":"OUT","inning":inning,"half":half,
                                "batter_id":batter["id"],"pitcher_id":pitcher["id"],
                                "outs":outs,"out_type":out_kind,
                                "fielder_id":fielder_id,"fielder_position":fpos if fielder else None,
                                "putout_id":putout_id,"assist_ids":assist_ids,
                                "first_base_id":int(first_base_id) if first_base_id else None
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
                                earned_runs=runs
                                if base_runner[fid] is not None and base_runner[fid] in unearned_runners[fid]: earned_runs-=1
                                pitchline["ER"]+=max(0,earned_runs)
                                if base_runner[fid] is not None: unearned_runners[fid].discard(base_runner[fid])
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
                                    if runner_id not in unearned_runners[fid]: pitchline["ER"]+=1
                                    unearned_runners[fid].discard(runner_id)
                                    events.append({
                                        "type":"RUN","inning":inning,"half":half,
                                        "team":fid,"runs":1,
                                        "score":[score[away],score[home]],
                                        "runner_id":runner_id,"batter_id":batter["id"]
                                    })
                                    base_runner[fid]=None
















                                # RC55 — no pinch runners; the batter who reached base remains the runner.
                                runner_id=batter["id"]
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
                                    safe=R.random()<steal_success_probability(runner,catcher_skill.get(opp))
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
        # RC55 — no position-player defensive replacements; Starting Nine stays on the field.
















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
















        # ---------------------------------------------
        # TEAM SALARY (REGULAR SEASON ONLY)
        # Every active roster player is paid once for every one of the
        # team's 81 regular-season games, whether or not they appeared.
        # Performance XP remains appearance-based below.
        # ---------------------------------------------
        if int(g["league_day"]) <= REGULAR_SEASON_CALENDAR_DAYS:
            roster_players=c.execute(
                """
                SELECT DISTINCT p.id
                FROM roster_slots rs
                JOIN players p ON p.id=rs.player_id
                WHERE rs.franchise_id=?
                  AND rs.player_id IS NOT NULL
                  AND p.active=1
                """,
                (fid,)
            ).fetchall()








            for rr in roster_players:
                salary_pid=int(rr["id"])
                salary_player=sim_player_obj(c,salary_pid)
                if not salary_player:
                    continue








                con=contract_for(c,salary_pid)
                # RC75: unsigned CPU/fallback roster jobs are budgeted at league minimum
                # by signing_pool_state, so game payroll must use that same minimum.
                # Otherwise every CPU slot silently costs .35 while finance reserves .30.
                salary=round(float(con["salary"]) if con else SALARY_MIN,3)








                c.execute(
                    "UPDATE franchises SET xp_spent=xp_spent+? WHERE id=?",
                    (salary,fid)
                )








                # RC76: the club still pays a CPU filler at league minimum, but CPU
                # players never bank XP or develop. Salary XP belongs only to humans.
                if salary_player.get("user_id") is not None:
                    salary_player["xp_wallet"]=round(
                        float(salary_player.get("xp_wallet",0) or 0)+salary,
                        3
                    )
                    c.execute(
                        """INSERT INTO xp_ledger(player_id,event_type,xp,detail_json)
                           VALUES(?,?,?,?)""",
                        (salary_pid,"SALARY",salary,json.dumps({
                            "game":g["id"],"league_day":int(g["league_day"]),"team":fid
                        }))
                    )
                save_player(c,salary_player)








                box["xp"].append({
                    "player_id":salary_pid,
                    "salary":salary,
                    "performance":0
                })
















        participant_ids=set(lineups[fid])
















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
                rivalry_xp_multiplier(c,away,home) *
                franchise_development_multiplier(c,fid),
                3
            )
















            if p.get("user_id") is not None:
                p["xp_wallet"]=round(p["xp_wallet"]+perf,3)
                c.execute(
                    """INSERT INTO xp_ledger(player_id,event_type,xp,detail_json)
                       VALUES(?,?,?,?)""",
                    (pid,"PERFORMANCE",perf,json.dumps({"game":g["id"],"gps":round(gps,1)}))
                )
            else:
                perf=0.0
















            save_player(c,p)
















            box["xp"].append({
                "player_id":pid,
                "salary":0,
                "performance":perf
            })
















        # ---------------------------------------------
        # FIELDING
        # ---------------------------------------------
        for fpid_s,fline in box.get("fielding",{}).items():
            fpid=int(fpid_s)
            fp=sim_player_obj(c,fpid)
            if not fp or fp.get("franchise_id")!=fid: continue
            for k in ("FG","PO","A","E","DP","CH","OFA"):
                fp["season"][k]=fp["season"].get(k,0)+fline.get(k,0)
            fp["season"]["OAA"]=round(float(fp["season"].get("OAA",0) or 0)+float(fline.get("OAA",0) or 0),2)
            chances=fp["season"].get("PO",0)+fp["season"].get("A",0)+fp["season"].get("E",0)
            fp["season"]["FLD_PCT"]=(f"{((fp['season'].get('PO',0)+fp['season'].get('A',0))/chances):.3f}" if chances else "—")
            save_player(c,fp)








        # ---------------------------------------------
        # PITCHERS
        # ---------------------------------------------
















        for spid in used_pitchers[fid]:
            p=sim_player_obj(c,spid)
















            if not p:
                continue
















            is_starter=(
                spid==starter_ids[fid]
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








            record_pitcher_workload(c,spid,int(g["league_day"]),int(pline.get("OUTS",0)),is_starter)








            gps=pitcher_gps(
                pline,
                is_starter
            )
















            xp_mult=SP_XP_MULTIPLIER if is_starter else RP_XP_MULTIPLIER
            perf=round(
                gps_xp(gps) *
                rivalry_xp_multiplier(c,away,home) *
                franchise_development_multiplier(c,fid) *
                xp_mult,
                3
            )
















            if p.get("user_id") is not None:
                p["xp_wallet"]=round(p["xp_wallet"]+perf,3)
                c.execute(
                    """INSERT INTO xp_ledger(player_id,event_type,xp,detail_json)
                       VALUES(?,?,?,?)""",
                    (spid,"PERFORMANCE",perf,json.dumps({"game":g["id"],"gps":round(gps,1)}))
                )
            else:
                perf=0.0
















            save_player(c,p)
















            box["pitchers"].setdefault(fid,[]).append({
                "player_id":spid,
                **pline
            })
















            box["xp"].append({
                "player_id":spid,
                "salary":0,
                "performance":perf
            })
    
    # -------------------------------------------------
    # FINALIZE GAME
    # -------------------------------------------------
















    postseason=int(g["league_day"])>REGULAR_SEASON_CALENDAR_DAYS
















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
















    update_player_game_records(c,g,box)
    update_player_season_records(c,g)
    update_player_milestones(c,g)








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
    day_row=c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()
    day=int(day_row["v"] if day_row else 0)
    c.execute("INSERT INTO commissioner_audit(league_day,action,detail) VALUES(?,?,?)",(day,action,detail))
















def auto_advance_state(c):
    try:per_day=int(league_cfg(c,"auto_advance_per_day","1") or 1)
    except (TypeError,ValueError):per_day=1
    per_day=max(1,min(24,per_day))
    try:next_at=float(league_cfg(c,"auto_advance_next_at","0") or 0)
    except (TypeError,ValueError):next_at=0.0
    try:last_at=float(league_cfg(c,"auto_advance_last_at","0") or 0)
    except (TypeError,ValueError):last_at=0.0
    state={r["k"]:r["v"] for r in c.execute("SELECT k,v FROM league_state WHERE k IN ('season','league_day','phase')")}
    return {
        "enabled":str(league_cfg(c,"auto_advance","0"))=="1",
        "per_day":per_day,
        "interval_seconds":round(86400/per_day),
        "next_at":next_at,
        "last_at":last_at,
        "season":int(state.get("season",1) or 1),
        "league_day":int(state.get("league_day",0) or 0),
        "phase":state.get("phase","REGULAR") or "REGULAR"
    }
















def auto_advance_worker(port):
    # Persisted commissioner scheduler. It advances regular-season league days at
    # an even cadence and automatically shuts itself off once the playoffs begin.
    time.sleep(10)
    while True:
        try:
            c=conn();state=auto_advance_state(c)
            if not state["enabled"]:
                c.close();time.sleep(15);continue
            if str(state["phase"]).upper()!="REGULAR":
                set_league_cfg(c,"auto_advance",0);set_league_cfg(c,"auto_advance_next_at",0)
                audit(c,"AUTO_ADVANCE_STOPPED",f"phase={state['phase']}")
                c.commit();c.close();time.sleep(15);continue
            now=time.time()
            if state["next_at"]<=0:
                set_league_cfg(c,"auto_advance_next_at",now+state["interval_seconds"])
                c.commit();c.close();time.sleep(15);continue
            due=now>=state["next_at"]
            c.close()
            if not due:
                time.sleep(15);continue








            with AUTO_ADVANCE_LOCK:
                c=conn();state=auto_advance_state(c);now=time.time()
                if not state["enabled"] or str(state["phase"]).upper()!="REGULAR" or now<state["next_at"]:
                    c.close();time.sleep(1);continue
                # Move the deadline forward before the request so one slow simulation
                # cannot launch twice. Missed downtime does not create a catch-up storm.
                set_league_cfg(c,"auto_advance_next_at",now+state["interval_seconds"])
                c.commit();c.close()
                try:
                    req=Request(
                        f"http://127.0.0.1:{int(port)}/api/commish/sim-day",
                        data=b"{}",
                        headers={"Content-Type":"application/json","X-EBL-Auto":AUTO_ADVANCE_TOKEN},
                        method="POST"
                    )
                    with urlopen(req,timeout=300) as response:
                        payload=json.loads(response.read().decode("utf-8") or "{}")
                    c=conn();fresh=auto_advance_state(c)
                    set_league_cfg(c,"auto_advance_last_at",time.time())
                    if str(fresh["phase"]).upper()!="REGULAR" or payload.get("phase")=="PLAYOFFS":
                        set_league_cfg(c,"auto_advance",0);set_league_cfg(c,"auto_advance_next_at",0)
                        audit(c,"AUTO_ADVANCE_STOPPED","Playoffs reached")
                    else:
                        audit(c,"AUTO_ADVANCE_DAY",f"day={payload.get('day',fresh['league_day'])}; per_day={fresh['per_day']}")
                    c.commit();c.close()
                except Exception as e:
                    print("AUTO ADVANCE ERROR:",type(e).__name__,str(e))
                    c=conn();set_league_cfg(c,"auto_advance_next_at",time.time()+300);c.commit();c.close()
        except Exception as e:
            print("AUTO ADVANCE WORKER ERROR:",type(e).__name__,str(e))
        time.sleep(15)
















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
    # Broad market pools reduce exact-position bottlenecks. Catcher is part of
    # INF, but catcher-specialist availability is reported separately because
    # only a C specialist may occupy the C defensive slot.
    slot_rows=c.execute("""SELECT position_group,COUNT(*) total,
              SUM(CASE WHEN occupant_type='HUMAN' THEN 1 ELSE 0 END) human,
              SUM(CASE WHEN occupant_type='CPU' THEN 1 ELSE 0 END) cpu,
              SUM(CASE WHEN player_id IS NULL OR occupant_type='OPEN' THEN 1 ELSE 0 END) open
              FROM roster_slots GROUP BY position_group""").fetchall()
    totals={g:{"total":0,"human":0,"cpu":0,"open":0} for g in POSITION_GROUPS}
    for r in slot_rows:
        slot=str(r["position_group"] or "").upper()
        if slot in {"C","1B","2B","3B","SS"}:grp="INF"
        elif slot in {"LF","CF","RF","DH","UTIL"}:grp="OF"
        elif slot in {"SP","RP"}:grp="PITCHER"
        else:continue
        for k in ("total","human","cpu","open"):
            totals[grp][k]+=int(r[k] or 0)
    out=[]
    for grp in POSITION_GROUPS:
        r=totals[grp];total=r["total"];human=r["human"]
        opportunities=max(0,total-human);share=(human/total) if total else 1.0
        level="FULL" if opportunities<=0 else "HIGH_NEED" if share<.25 else "AVAILABLE" if share<.60 else "CROWDED"
        out.append({"position":grp,"level":level,"total_slots":total,"human":human,"cpu":r["cpu"],"open":r["open"],"opportunities":opportunities})
    catch=c.execute("""SELECT COUNT(*) total,
              SUM(CASE WHEN occupant_type='HUMAN' THEN 1 ELSE 0 END) human,
              SUM(CASE WHEN occupant_type='CPU' THEN 1 ELSE 0 END) cpu,
              SUM(CASE WHEN player_id IS NULL OR occupant_type='OPEN' THEN 1 ELSE 0 END) open
              FROM roster_slots WHERE position_group='C'""").fetchone()
    catcher={k:int(catch[k] or 0) for k in ("total","human","cpu","open")} if catch else {"total":0,"human":0,"cpu":0,"open":0}
    catcher["opportunities"]=max(0,catcher["total"]-catcher["human"])
    return out,catcher
























def token_hash(v): return hashlib.sha256(v.encode()).hexdigest()
















def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)
















def iso_after(minutes):
    return (utc_now:=utcnow() + datetime.timedelta(minutes=minutes)).isoformat()
















def parse_iso(v):
    try:return datetime.datetime.fromisoformat(v)
    except:return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
















def supporter_entitlement(c,user_id):
    """Canonical account entitlement. Stripe subscription state mutates this account tier; gameplay reads it here."""
    row=c.execute(
        """SELECT support_tier,supporter_since,supporter_expires_at,
                  founding_supporter,founding_supporter_since,founding_supporter_ref
           FROM users WHERE id=?""",
        (user_id,)
    ).fetchone()
    tier=str((row["support_tier"] if row else "FREE") or "FREE").upper()
    expires=(row["supporter_expires_at"] if row else None)
    active=tier=="SUPPORTER"
    if active and expires:
        active=parse_iso(expires)>utcnow()








    sub=c.execute(
        """SELECT stripe_subscription_id,plan,status,current_period_end,cancel_at_period_end
           FROM support_subscriptions
           WHERE user_id=?
           ORDER BY CASE WHEN status IN ('active','trialing') THEN 0 ELSE 1 END,updated_at DESC
           LIMIT 1""",(user_id,)
    ).fetchone()
    sub=dict(sub) if sub else {}
    entitled_limit=SUPPORTER_PLAYER_LIMIT if active else FREE_PLAYER_LIMIT
    creation_limit=entitled_limit if SUPPORTER_SLOTS_ENFORCED else ABSOLUTE_PLAYER_LIMIT
    used=int(c.execute("SELECT COUNT(*) n FROM players WHERE user_id=? AND active=1",(user_id,)).fetchone()["n"] or 0)
    return {
        "tier":"SUPPORTER" if active else "FREE",
        "supporter":bool(active),
        "badge":"EBL SUPPORTER" if active else "",
        "supporter_since":row["supporter_since"] if row and active else None,
        "supporter_expires_at":expires if active else None,
        "subscription_id":sub.get("stripe_subscription_id") if active else None,
        "subscription_plan":sub.get("plan") if active else None,
        "subscription_status":sub.get("status") if active else None,
        "subscription_period_end":sub.get("current_period_end") if active else None,
        "cancel_at_period_end":bool(int(sub.get("cancel_at_period_end") or 0)) if active else False,
        "founding_supporter":bool(row and int(row["founding_supporter"] or 0)),
        "founding_supporter_since":row["founding_supporter_since"] if row else None,
        "entitled_player_limit":entitled_limit,
        "creation_player_limit":creation_limit,
        "active_players":used,
        "slots_remaining":max(0,creation_limit-used),
        "policy_enforced":bool(SUPPORTER_SLOTS_ENFORCED),
        "absolute_player_limit":ABSOLUTE_PLAYER_LIMIT
    }








def set_supporter_entitlement(c,user_id,supporter,source="COMMISSIONER",expires_at=None,note="",external_ref=""):
    current=supporter_entitlement(c,user_id)
    new_tier="SUPPORTER" if supporter else "FREE"
    since=utcnow().isoformat() if supporter and not current.get("supporter") else current.get("supporter_since")
    if not supporter:
        expires_at=None
    c.execute(
        "UPDATE users SET support_tier=?,supporter_since=?,supporter_expires_at=?,supporter_source=? WHERE id=?",
        (new_tier,since,expires_at,str(source or "")[:40],user_id)
    )
    c.execute(
        """INSERT INTO supporter_entitlement_history(user_id,event_type,old_tier,new_tier,source,external_ref,note)
           VALUES(?,?,?,?,?,?,?)""",
        (user_id,"GRANT" if supporter else "REVOKE",current.get("tier","FREE"),new_tier,str(source or "")[:40],str(external_ref or "")[:160],str(note or "")[:500])
    )
    source_key=str(source or "").upper()
    # RC107: only a real Stripe purchase during Genesis/Beta can create the permanent
    # Founding Supporter marker. Stripe TEST purchases never grant it.
    if supporter and BETA_MODE and source_key=="STRIPE":
        c.execute(
            """UPDATE users
               SET founding_supporter=1,
                   founding_supporter_since=COALESCE(founding_supporter_since,?),
                   founding_supporter_ref=CASE WHEN COALESCE(founding_supporter_ref,'')='' THEN ? ELSE founding_supporter_ref END
               WHERE id=?""",
            (utcnow().isoformat(),str(external_ref or "")[:160],user_id)
        )
    elif (not supporter) and source_key=="STRIPE_REFUND":
        founding=c.execute("SELECT founding_supporter_ref FROM users WHERE id=?",(user_id,)).fetchone()
        if founding and str(founding["founding_supporter_ref"] or "")==str(external_ref or ""):
            c.execute(
                "UPDATE users SET founding_supporter=0,founding_supporter_since=NULL,founding_supporter_ref='' WHERE id=?",
                (user_id,)
            )
    return supporter_entitlement(c,user_id)
















def stripe_webhook_signature_valid(payload,sig_header):
    """Verify Stripe's v1 webhook HMAC against the unmodified request body."""
    mode=str(os.environ.get("EBL_STRIPE_MODE","test") or "test").strip().lower()
    secret_key="EBL_STRIPE_LIVE_WEBHOOK_SECRET" if mode=="live" else "EBL_STRIPE_WEBHOOK_SECRET"
    secret=str(os.environ.get(secret_key,"") or "").strip()
    if not secret or not sig_header:
        return False
    timestamp=None
    signatures=[]
    for item in str(sig_header).split(","):
        key,sep,value=item.strip().partition("=")
        if not sep:continue
        if key=="t":
            try:timestamp=int(value)
            except Exception:return False
        elif key=="v1" and value:
            signatures.append(value)
    if timestamp is None or not signatures:
        return False
    tolerance=max(30,int(os.environ.get("EBL_STRIPE_WEBHOOK_TOLERANCE","300") or 300))
    if abs(int(time.time())-timestamp)>tolerance:
        return False
    signed=str(timestamp).encode("utf-8")+b"."+payload
    expected=hmac.new(secret.encode("utf-8"),signed,hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected,sig) for sig in signatures)
















def stripe_expected_checkout(plan=None):
    plans=stripe_support_plans()
    if plan:
        key=str(plan or "").strip().lower()
        return plans.get(key)
    return plans








def _stripe_unix_iso(value):
    try:
        ts=int(value or 0)
        return datetime.datetime.fromtimestamp(ts,datetime.timezone.utc).isoformat() if ts>0 else None
    except Exception:
        return None








def _subscription_period_end(obj):
    direct=_stripe_unix_iso(obj.get("current_period_end"))
    if direct:return direct
    items=((obj.get("items") or {}).get("data") or [])
    if items and isinstance(items[0],dict):
        v=_stripe_unix_iso(items[0].get("current_period_end"))
        if v:return v
    return _stripe_unix_iso(obj.get("cancel_at"))








def _invoice_subscription_id(obj):
    direct=str(obj.get("subscription") or "")
    if direct:return direct
    parent=obj.get("parent") or {}
    details=(parent.get("subscription_details") or {}) if isinstance(parent,dict) else {}
    return str(details.get("subscription") or "")








def _invoice_period_end(obj):
    lines=((obj.get("lines") or {}).get("data") or [])
    ends=[]
    for line in lines:
        if isinstance(line,dict):
            period=line.get("period") or {}
            try:
                if int(period.get("end") or 0)>0:
                    ends.append(int(period["end"]))
            except Exception:
                pass
    return _stripe_unix_iso(max(ends)) if ends else None








def _stripe_subscription_plan_from_object(obj):
    meta=obj.get("metadata") or {}
    key=str(meta.get("plan") or "").strip().lower()
    plans=stripe_support_plans()
    items=((obj.get("items") or {}).get("data") or [])
    price_id=""
    if items and isinstance(items[0],dict):
        price=items[0].get("price") or {}
        price_id=str(price.get("id") or "") if isinstance(price,dict) else str(price or "")
    if key in ("monthly","yearly"):
        expected=plans.get(key) or {}
        if expected.get("price_id") and price_id and not hmac.compare_digest(str(expected["price_id"]),price_id):
            return None,price_id
        return key,price_id
    for candidate in ("monthly","yearly"):
        expected=str((plans.get(candidate) or {}).get("price_id") or "")
        if expected and price_id and hmac.compare_digest(expected,price_id):
            return candidate,price_id
    return None,price_id








def _upsert_support_subscription(c,subscription_id,user_id,plan,status,customer_id="",price_id="",period_end=None,cancel_at_period_end=False):
    c.execute(
        """INSERT INTO support_subscriptions(
             stripe_subscription_id,user_id,stripe_customer_id,plan,stripe_price_id,status,
             current_period_end,cancel_at_period_end,updated_at)
           VALUES(?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
           ON CONFLICT(stripe_subscription_id) DO UPDATE SET
             user_id=excluded.user_id,
             stripe_customer_id=CASE WHEN excluded.stripe_customer_id<>'' THEN excluded.stripe_customer_id ELSE support_subscriptions.stripe_customer_id END,
             plan=CASE WHEN excluded.plan<>'' THEN excluded.plan ELSE support_subscriptions.plan END,
             stripe_price_id=CASE WHEN excluded.stripe_price_id<>'' THEN excluded.stripe_price_id ELSE support_subscriptions.stripe_price_id END,
             status=excluded.status,
             current_period_end=COALESCE(excluded.current_period_end,support_subscriptions.current_period_end),
             cancel_at_period_end=excluded.cancel_at_period_end,
             updated_at=CURRENT_TIMESTAMP""",
        (subscription_id,int(user_id),str(customer_id or ""),str(plan or ""),str(price_id or ""),str(status or ""),
         period_end,1 if cancel_at_period_end else 0)
    )








def _sync_supporter_from_subscriptions(c,user_id,source,external_ref="",note=""):
    active_rows=c.execute(
        """SELECT stripe_subscription_id,plan,status,current_period_end,cancel_at_period_end
           FROM support_subscriptions
           WHERE user_id=? AND status IN ('active','trialing')
           ORDER BY updated_at DESC""",(user_id,)
    ).fetchall()
    if active_rows:
        row=active_rows[0]
        return set_supporter_entitlement(
            c,user_id,True,source=source,
            expires_at=row["current_period_end"] or None,
            note=note or "Active Stripe Supporter subscription",
            external_ref=external_ref or row["stripe_subscription_id"]
        )
    return set_supporter_entitlement(
        c,user_id,False,source=source,
        note=note or "No active Stripe Supporter subscription",
        external_ref=external_ref
    )
















def new_session(c,user_id,handler=None,remember=False):
    raw=secrets.token_urlsafe(32)
    expires=(utcnow()+(datetime.timedelta(days=30) if remember else datetime.timedelta(hours=12))).isoformat()
    ua=handler.headers.get("User-Agent","")[:500] if handler else ""
    ip=get_client_ip(handler) if handler else ""
    c.execute("DELETE FROM persistent_sessions WHERE user_id=? AND expires_at<?",(user_id,utcnow().isoformat()))
    c.execute("""INSERT INTO persistent_sessions(token_hash,user_id,expires_at,user_agent,ip)
                 VALUES(?,?,?,?,?)""",(token_hash(raw),user_id,expires,ua,ip))
    return raw,expires
















def session_user(*args):
    """Resolve the logged-in user without turning every authenticated request into a DB write.








    SQLite allows many readers but only one writer. Updating last_seen_at on every GET
    caused routine page refreshes to compete with contract/player transactions and could
    lock users out of the app. Session validation is intentionally read-only here.
    """
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
        r=c.execute("""SELECT u.id,u.username,u.role,u.beta_member,u.support_tier,u.supporter_expires_at
                       FROM persistent_sessions s JOIN users u ON u.id=s.user_id
                       WHERE s.token_hash=? AND s.expires_at>?""",
                    (token_hash(raw),utcnow().isoformat())).fetchone()
        return dict(r) if r else None
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
    """Process-local rate limiting so auth does not need a SQLite write lock.








    The existing call signature is preserved. A Railway restart clears these counters,
    which is acceptable for the current single-instance alpha and prevents a busy game
    transaction from making login/register fail with DATABASE_LOCKED.
    """
    now=int(time.time())
    with RATE_LOCK:
        r=RATE_STATE.get(key)
        if not r or now-int(r["window_start"])>=int(window_seconds):
            RATE_STATE[key]={"window_start":now,"count":1}
            return True
        if int(r["count"])>=int(limit):
            return False
        r["count"]+=1
        return True
















def secure_cookie_suffix():
    base=os.environ.get("PUBLIC_BASE_URL","").strip().lower()
    return "; Secure" if base.startswith("https://") else ""
















def session_cookie(raw,max_age=2592000):
    parts=[f"sid={raw}","HttpOnly","SameSite=Lax","Path=/"]
    if max_age is not None:
        parts.append(f"Max-Age={int(max_age)}")
    return "; ".join(parts)+secure_cookie_suffix()
















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
























def compact_events_for_storage(events, summary_only=False):
    """Shrink GameCast payloads while preserving a readable historical record."""
    if not isinstance(events,list):
        return []
    if summary_only:
        start=next((e for e in events if e.get("type")=="GAME_START"),{})
        end=next((e for e in reversed(events) if e.get("type")=="GAME_END"),{})
        score=end.get("final_score") or start.get("score") or [0,0]
        away=start.get("away_name") or start.get("away") or "Away"
        home=start.get("home_name") or start.get("home") or "Home"
        return [{"type":"GAME_SUMMARY","text":f"{away} {score[0]} - {home} {score[1]}","final_score":score}]
    keep={"GAME_START","RUN","PITCHING_CHANGE","FIELDING_ERROR","FIELDING_COLLISION","GREAT_PLAY","OUTFIELD_ASSIST","GAME_END"}
    out=[e for e in events if e.get("type") in keep]
    return out[-160:]








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
    c=conn(); cutoff=max(0,int(current_day)-int(keep_full_days))
    rows=c.execute("""SELECT id,season,league_day,away_id,home_id,away_runs,home_runs,events_json FROM games
                      WHERE status='FINAL' AND (season<? OR (season=? AND league_day<=?)) AND length(events_json)>2""",
                   (int(current_season),int(current_season),cutoff)).fetchall()
    changed=0
    for r in rows:
        try: events=json.loads(r["events_json"] or "[]")
        except: events=[]
        if int(r["season"])<int(current_season):
            compact=[{"type":"GAME_SUMMARY","text":f"{r['away_id']} {r['away_runs']} - {r['home_id']} {r['home_runs']}","final_score":[r['away_runs'],r['home_runs']]}]
        else:
            compact=compact_events_for_storage(events,False)
        new_json=json.dumps(compact,separators=(",",":"))
        if new_json!=(r["events_json"] or ""):
            c.execute("UPDATE games SET events_json=? WHERE id=?",(new_json,r["id"])); changed+=1
    c.commit();c.close();return changed








def run_storage_maintenance(current_season=None,current_day=None,aggressive=False):
    removed_backups=trim_backup_files(keep=0 if aggressive else 1)
    compacted=0; pruned_chat=0; pruned_news=0
    if current_season is not None and current_day is not None:
        compacted=compact_historical_games(current_season,current_day,0 if aggressive else STORAGE_KEEP_FULL_GAME_DAYS)
    c=conn()
    try:
        cur=c.execute("DELETE FROM chat_messages WHERE created_at < datetime('now', ?)",(f"-{CHAT_RETENTION_HOURS} hours",)); pruned_chat=cur.rowcount
        if current_season is not None:
            # Keep the full current season newsroom intact. Low-importance stories
            # are only pruned once they are more than two seasons old; awards,
            # championships, records and other major history remain permanently.
            cutoff=max(1,int(current_season)-2)
            cur=c.execute("DELETE FROM news WHERE season < ? AND importance < 4",(cutoff,)); pruned_news=cur.rowcount
        c.commit()
        try:c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except:pass
    finally:c.close()
    return {"removed_backups":removed_backups,"compacted_games":compacted,"pruned_chat":pruned_chat,"pruned_news":pruned_news,"checkpoint":"ok","vacuumed":False,"storage":storage_report()}
















def owned_active_player(c,user_id,requested_id=None):
    """Return an active player owned by user.








    Browser-selected player ids can become stale after season rollover, logout/login,
    retirement, or account switching. Never let a stale requested id make an account
    with valid active players look empty: try the requested id first, then fall back
    to the user's newest active player.
    """
    try:
        pid=int(requested_id or 0)
    except Exception:
        pid=0
    if pid>0:
        row=c.execute(
            "SELECT * FROM players WHERE id=? AND user_id=? AND active=1",
            (pid,user_id)
        ).fetchone()
        if row:
            return row
    return c.execute(
        "SELECT * FROM players WHERE user_id=? AND active=1 ORDER BY id DESC LIMIT 1",
        (user_id,)
    ).fetchone()








def practice_day_key():
    """Calendar-day key for EBL daily practice, using league HQ Eastern time."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return datetime.datetime.utcnow().date().isoformat()








def request_player_id(handler,body=None):
    if isinstance(body,dict) and body.get("player_id") not in (None,""):
        return body.get("player_id")
    try:
        from urllib.parse import parse_qs
        q=parse_qs(urlparse(handler.path).query)
        return (q.get("player_id") or [None])[0]
    except Exception:
        return None








def valid_same_origin(handler):
    origin=(handler.headers.get("Origin") or "").strip().rstrip("/")
    if not origin:
        return True
    public=os.environ.get("PUBLIC_BASE_URL","").strip().rstrip("/")
    if public and hmac.compare_digest(origin.lower(),public.lower()):
        return True
    host=(handler.headers.get("Host") or "").strip()
    if host and origin.lower() in ("https://"+host.lower(),"http://"+host.lower()):
        return True
    return False
















class H(BaseHTTPRequestHandler):
    def log_message(self,format,*args):
        # BaseHTTPRequestHandler writes normal access logs to stderr, which
        # Railway classifies as error severity. Send routine access logs to
        # stdout so real application errors remain easy to spot.
        print(f"{self.client_address[0]} - - [{self.log_date_time_string()}] {format % args}")








    def end_headers(self):
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Referrer-Policy","same-origin")
        self.send_header("Permissions-Policy","camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https://cdn.jsdelivr.net; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        super().end_headers()
    def out(self,obj,status=200,headers=None):
        b=json.dumps(obj).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",len(b))
        if headers:
            for k,v in headers.items():self.send_header(k,v)
        self.end_headers();self.wfile.write(b)
    def body(self):
        try:n=int(self.headers.get("Content-Length",0) or 0)
        except:n=0
        if n<0 or n>MAX_REQUEST_BYTES:
            raise ValueError("REQUEST_TOO_LARGE")
        if not n:return {}
        try:
            obj=json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            raise ValueError("INVALID_JSON")
        if not isinstance(obj,dict):
            raise ValueError("INVALID_JSON")
        return obj
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
        
    def _raw_response(self, body, content_type="text/plain; charset=utf-8", status=200, head_only=False, headers=None):
        if isinstance(body,str):
            body=body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(body)))
        if headers:
            for k,v in headers.items():
                self.send_header(k,v)
        self.end_headers()
        if not head_only:
            self.wfile.write(body)








    def _public_static_target(self, path):
        p=path
        if p in ("/", "/create-account", "/verify-email", "/reset-password"):
            p="/index.html"
        elif p.startswith("/profile/"):
            username=p[len("/profile/"):].strip("/")
            p="/index.html" if username else "/index.html"
        elif p in ("/favicon.ico","/favicon.png"):
            p="/assets/ebl_logo.png"
        return p








    def _robots_body(self):
        public=os.environ.get("PUBLIC_BASE_URL","https://elite-baseball.com").strip().rstrip("/") or "https://elite-baseball.com"
        indexable=str(os.environ.get("EBL_PUBLIC_INDEXING","0")).strip().lower() in ("1","true","yes","on")
        if indexable:
            return f"User-agent: *\nAllow: /\nSitemap: {public}/sitemap.xml\n"
        return "User-agent: *\nDisallow: /\n"








    def _sitemap_body(self):
        public=os.environ.get("PUBLIC_BASE_URL","https://elite-baseball.com").strip().rstrip("/") or "https://elite-baseball.com"
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{public}/</loc></url>
</urlset>
"""








    def do_GET(self):
        p=urlparse(self.path).path








        if p=="/robots.txt":
            return self._raw_response(self._robots_body(),"text/plain; charset=utf-8")
        if p=="/sitemap.xml":
            return self._raw_response(self._sitemap_body(),"application/xml; charset=utf-8")
        if p=="/health" or p.startswith("/api/"):
            return self.api_get(p)








        p=self._public_static_target(p)
        fp=os.path.normpath(os.path.join(STATIC,p.lstrip("/")))
        if not fp.startswith(STATIC) or not os.path.isfile(fp):
            self.send_error(404)
            return
        b=open(fp,"rb").read()
        return self._raw_response(b,mimetypes.guess_type(fp)[0] or "application/octet-stream")








    def do_HEAD(self):
        p=urlparse(self.path).path
        if p=="/robots.txt":
            return self._raw_response(self._robots_body(),"text/plain; charset=utf-8",head_only=True)
        if p=="/sitemap.xml":
            return self._raw_response(self._sitemap_body(),"application/xml; charset=utf-8",head_only=True)
        if p in ("/health","/api/health"):
            body=json.dumps({"ok":True,"service":"EBL","version":"1.3.0-beta"}).encode("utf-8")
            return self._raw_response(body,"application/json",head_only=True)
        if p=="/api/support":
            body=json.dumps(support_public_config()).encode("utf-8")
            return self._raw_response(body,"application/json",head_only=True)
        if p.startswith("/api/"):
            self.send_response(405)
            self.send_header("Allow","GET")
            self.send_header("Content-Length","0")
            self.end_headers()
            return
        p=self._public_static_target(p)
        fp=os.path.normpath(os.path.join(STATIC,p.lstrip("/")))
        if not fp.startswith(STATIC) or not os.path.isfile(fp):
            self.send_error(404)
            return
        size=os.path.getsize(fp)
        self.send_response(200)
        self.send_header("Content-Type",mimetypes.guess_type(fp)[0] or "application/octet-stream")
        self.send_header("Content-Length",str(size))
        self.end_headers()








    def do_POST(self):
        p=urlparse(self.path).path
        if p=="/api/stripe/webhook":
            return self.stripe_webhook()
        if not valid_same_origin(self):
            return self.out({"error":"INVALID_ORIGIN"},403)
        try:
            result=self.api_post(p)
            if result is None:
                return self.out({"error":"NOT_FOUND"},404)
            return result
        except ValueError as e:
            code=str(e)
            return self.out({"error":code if code in ("REQUEST_TOO_LARGE","INVALID_JSON") else "BAD_REQUEST"},413 if code=="REQUEST_TOO_LARGE" else 400)
        except Exception as e:
            print("POST ERROR:",type(e).__name__,str(e))
            return self.out({"error":"SERVER_ERROR"},500)








    def stripe_webhook(self):
        try:
            n=int(self.headers.get("Content-Length",0) or 0)
        except Exception:
            n=0
        if n<=0 or n>MAX_REQUEST_BYTES:
            return self.out({"error":"INVALID_WEBHOOK_BODY"},400)
        payload=self.rfile.read(n)
        if not stripe_webhook_signature_valid(payload,self.headers.get("Stripe-Signature","")):
            return self.out({"error":"INVALID_STRIPE_SIGNATURE"},400)
        try:
            event=json.loads(payload.decode("utf-8"))
        except Exception:
            return self.out({"error":"INVALID_WEBHOOK_JSON"},400)
        if not isinstance(event,dict) or not event.get("id") or not event.get("type"):
            return self.out({"error":"INVALID_WEBHOOK_EVENT"},400)








        event_id=str(event.get("id"))
        event_type=str(event.get("type"))
        obj=((event.get("data") or {}).get("object") or {})
        if not isinstance(obj,dict):obj={}
        object_id=str(obj.get("id") or "")
        expected=stripe_expected_checkout()
        c=conn()
        try:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT 1 FROM stripe_webhook_events WHERE event_id=?",(event_id,)).fetchone():
                c.commit();c.close()
                return self.out({"received":True,"duplicate":True})








            result="IGNORED"
            if event_type in ("checkout.session.completed","checkout.session.async_payment_succeeded"):
                payment_link=str(obj.get("payment_link") or "")
                ref=str(obj.get("client_reference_id") or "")
                payment_status=str(obj.get("payment_status") or "").lower()
                amount_total=int(obj.get("amount_total") or 0)
                currency=str(obj.get("currency") or "").lower()
                session_id=str(obj.get("id") or "")
                subscription_id=str(obj.get("subscription") or "")
                customer_id=str(obj.get("customer") or "")
                checkout_mode=str(obj.get("mode") or "").lower()
                plans=stripe_support_plans()
                plan_key=None
                plan_cfg=None
                for candidate in ("monthly","yearly"):
                    cfg=plans[candidate]
                    if cfg.get("payment_link_id") and payment_link and hmac.compare_digest(str(cfg["payment_link_id"]),payment_link):
                        plan_key=candidate
                        plan_cfg=cfg
                        break
                money_ok=bool(plan_cfg) and amount_total==int(plan_cfg["amount"]) and currency==plan_cfg["currency"]
                mode_ok=checkout_mode in ("","subscription")








                if plan_cfg and money_ok and mode_ok and payment_status=="paid" and ref and subscription_id:
                    row=c.execute(
                        "SELECT token,user_id,status,plan FROM support_checkout_refs WHERE token=?",
                        (ref,)
                    ).fetchone()
                    if row:
                        uid=int(row["user_id"])
                        if str(row["plan"] or "") and str(row["plan"]).lower()!=plan_key:
                            result="PLAN_REFERENCE_MISMATCH"
                        else:
                            approx_days=32 if plan_key=="monthly" else 370
                            approx_end=(utcnow()+datetime.timedelta(days=approx_days)).isoformat()
                            _upsert_support_subscription(
                                c,subscription_id,uid,plan_key,"active",
                                customer_id=customer_id,price_id=str(plan_cfg.get("price_id") or ""),
                                period_end=approx_end,cancel_at_period_end=False
                            )
                            prior=supporter_entitlement(c,uid)
                            _sync_supporter_from_subscriptions(
                                c,uid,
                                source="STRIPE_TEST" if plans["mode"]=="test" else "STRIPE",
                                external_ref=subscription_id,
                                note=f"Verified Stripe {plan_key} Supporter subscription"
                            )
                            c.execute(
                                """UPDATE support_checkout_refs
                                   SET status='COMPLETED',plan=?,stripe_session_id=?,stripe_subscription_id=?,
                                       stripe_customer_id=?,stripe_price_id=?,payment_status=?,amount_total=?,
                                       currency=?,completed_at=CURRENT_TIMESTAMP
                                   WHERE token=?""",
                                (plan_key,session_id,subscription_id,customer_id,str(plan_cfg.get("price_id") or ""),
                                 payment_status,amount_total,currency,ref)
                            )
                            notify_user(
                                c,uid,"SUPPORTER",
                                "EBL Supporter activated",
                                f"Your verified {plan_key} subscription is active. Supporter features are now unlocked.",
                                subscription_id
                            )
                            result="SUPPORTER_GRANTED" if not prior.get("supporter") else "SUPPORTER_CONFIRMED"
                    else:
                        result="UNMATCHED_REFERENCE"
                elif plan_cfg and payment_status!="paid":
                    result="PAYMENT_NOT_YET_PAID"
                elif not plan_cfg:
                    result="WRONG_PAYMENT_LINK"
                elif not subscription_id:
                    result="MISSING_SUBSCRIPTION"
                else:
                    result="PAYMENT_MISMATCH"








            elif event_type in ("customer.subscription.created","customer.subscription.updated","customer.subscription.deleted"):
                subscription_id=str(obj.get("id") or "")
                status=str(obj.get("status") or "").lower()
                if event_type=="customer.subscription.deleted":
                    status="canceled"
                plan_key,price_id=_stripe_subscription_plan_from_object(obj)
                row=c.execute(
                    "SELECT user_id,plan FROM support_subscriptions WHERE stripe_subscription_id=?",
                    (subscription_id,)
                ).fetchone()
                if row and plan_key:
                    uid=int(row["user_id"])
                    period_end=_subscription_period_end(obj)
                    cancel_at_period_end=bool(obj.get("cancel_at_period_end") or obj.get("cancel_at"))
                    _upsert_support_subscription(
                        c,subscription_id,uid,plan_key,status,
                        customer_id=str(obj.get("customer") or ""),
                        price_id=price_id,
                        period_end=period_end,
                        cancel_at_period_end=cancel_at_period_end
                    )
                    _sync_supporter_from_subscriptions(
                        c,uid,
                        source="STRIPE_TEST" if stripe_support_plans()["mode"]=="test" else "STRIPE_SUBSCRIPTION",
                        external_ref=subscription_id,
                        note=f"Stripe subscription status: {status}"
                    )
                    if status not in ("active","trialing"):
                        notify_user(
                            c,uid,"SUPPORTER",
                            "EBL Supporter subscription inactive",
                            "Your Stripe subscription is no longer active. Supporter-only features are paused; your saved profile customization remains stored.",
                            subscription_id
                        )
                    result=f"SUBSCRIPTION_{status.upper() or 'UPDATED'}"
                elif row and not plan_key:
                    result="UNRECOGNIZED_SUPPORTER_PRICE"
                else:
                    result="UNMATCHED_SUBSCRIPTION"








            elif event_type in ("invoice.paid","invoice.payment_failed"):
                subscription_id=_invoice_subscription_id(obj)
                row=c.execute(
                    "SELECT user_id,plan,status,stripe_customer_id,stripe_price_id,cancel_at_period_end FROM support_subscriptions WHERE stripe_subscription_id=?",
                    (subscription_id,)
                ).fetchone() if subscription_id else None
                if row:
                    uid=int(row["user_id"])
                    paid=event_type=="invoice.paid"
                    period_end=_invoice_period_end(obj)
                    new_status="active" if paid else "past_due"
                    _upsert_support_subscription(
                        c,subscription_id,uid,row["plan"],new_status,
                        customer_id=row["stripe_customer_id"],price_id=row["stripe_price_id"],
                        period_end=period_end,cancel_at_period_end=bool(row["cancel_at_period_end"])
                    )
                    _sync_supporter_from_subscriptions(
                        c,uid,
                        source="STRIPE_TEST" if stripe_support_plans()["mode"]=="test" else "STRIPE_SUBSCRIPTION",
                        external_ref=subscription_id,
                        note="Stripe subscription invoice paid" if paid else "Stripe subscription payment failed"
                    )
                    if not paid:
                        notify_user(
                            c,uid,"SUPPORTER",
                            "Supporter payment needs attention",
                            "Stripe could not collect the latest Supporter renewal. Supporter-only features are paused until the subscription returns to active status.",
                            subscription_id
                        )
                    result="SUBSCRIPTION_RENEWED" if paid else "SUBSCRIPTION_PAYMENT_FAILED"
                else:
                    result="UNMATCHED_INVOICE"








            elif event_type=="charge.refunded":
                payment_intent=str(obj.get("payment_intent") or "")
                amount=int(obj.get("amount") or 0)
                amount_refunded=int(obj.get("amount_refunded") or 0)
                if payment_intent and amount>0 and amount_refunded>=amount:
                    row=c.execute(
                        """SELECT token,user_id,status,stripe_session_id,stripe_subscription_id
                           FROM support_checkout_refs
                           WHERE stripe_payment_intent=? AND status='COMPLETED'
                           ORDER BY completed_at DESC LIMIT 1""",
                        (payment_intent,)
                    ).fetchone()
                    if row and not str(row["stripe_subscription_id"] or ""):
                        uid=int(row["user_id"])
                        set_supporter_entitlement(
                            c,uid,False,
                            source="STRIPE_TEST_REFUND" if stripe_support_plans()["mode"]=="test" else "STRIPE_REFUND",
                            note="Legacy one-time Supporter payment fully refunded",
                            external_ref=str(row["stripe_session_id"] or payment_intent)
                        )
                        c.execute(
                            """UPDATE support_checkout_refs
                               SET status='REFUNDED',payment_status='refunded',refunded_at=CURRENT_TIMESTAMP
                               WHERE token=?""",(row["token"],)
                        )
                        result="LEGACY_SUPPORTER_REVOKED_REFUND"
                    elif row:
                        result="SUBSCRIPTION_CHARGE_REFUNDED"
                    else:
                        result="UNMATCHED_REFUND"
                else:
                    result="PARTIAL_REFUND_OR_UNMATCHED"








            c.execute(
                "INSERT INTO stripe_webhook_events(event_id,event_type,object_id,result) VALUES(?,?,?,?)",
                (event_id,event_type,object_id,result)
            )
            c.commit();c.close()
            return self.out({"received":True})
        except Exception as e:
            try:c.rollback();c.close()
            except Exception:pass
            print("STRIPE WEBHOOK ERROR:",type(e).__name__,str(e))
            return self.out({"error":"WEBHOOK_PROCESSING_FAILED"},500)








    def api_get(self,p):
        u=session_user(self.headers)
        if p in ("/health","/api/health"):
            return self.out({"ok":True,"service":"EBL","version":"1.3.0-beta"})
        if p=="/api/me":
            if not u:return self.out({"user":None})
            c=conn();ent=supporter_entitlement(c,u["id"]);c.close()
            user=dict(u);user["supporter"]=ent["supporter"];user["support_tier"]=ent["tier"]
            user["founding_supporter"]=ent.get("founding_supporter",False)
            user["founding_supporter_since"]=ent.get("founding_supporter_since")
            return self.out({"user":user,"entitlements":ent})
        if p=="/api/account/entitlements":
            au=self.auth()
            if not au:return
            c=conn();ent=supporter_entitlement(c,au["id"]);c.close()
            return self.out({"entitlements":ent})
        if p=="/api/support":return self.out(support_public_config())
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
                          b.display_name,b.city,b.team_name,b.logo_style,b.primary_logo,b.secondary_logo,b.jersey_wordmark,
                          b.primary_color,b.secondary_color,b.accent_color
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
            identity_history=[dict(x) for x in c.execute(
                "SELECT season,city,team_name,display_name,primary_color,secondary_color,accent_color,primary_logo,secondary_logo,jersey_wordmark,started_at FROM franchise_identity_history WHERE franchise_id=? ORDER BY season,id",
                (fid,)
            )]
            roster=[]
            for row in c.execute(
                """SELECT p.id,p.user_id,p.name,p.franchise_id,p.type,p.primary_pos,p.bats,p.throws,p.xp_wallet,
                          p.season_json,p.attributes_json,p.status,p.active,p.face_id,p.skin_color_id,p.hair_id,p.hair_color_id,
                          p.facial_hair_id,p.eye_color_id,p.nose_id,p.eye_shape_id,p.mouth_id,p.ear_size_id,p.eye_black_id,p.eyewear_id,p.chain_id,p.sleeve_id,p.body_build_id,p.jersey_number,u.username
                   FROM players p LEFT JOIN users u ON u.id=p.user_id
                   WHERE p.franchise_id=? AND p.active=1
                   ORDER BY CASE p.type WHEN 'H' THEN 0 ELSE 1 END,p.primary_pos,p.name""",
                (fid,)
            ):
                pl=dict(row)
                try:pl["stats"]=json.loads(pl.pop("season_json") or "{}")
                except Exception:pl["stats"]={}
                try:attrs=json.loads(pl.pop("attributes_json") or "{}")
                except Exception:attrs={}
                pl["overall"]=player_overall_from_attrs(attrs,pl.get("type","H"),pl.get("primary_pos","UTIL"))
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
                "branding":dict(brand) if brand else None,"identity_history":identity_history,
                "division":season_division(c,current_season,fid),
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
                """SELECT id,username,role,created_at,display_name,profile_bio,profile_motto,profile_photo,
                          profile_accent,profile_theme,profile_banner,profile_card_frame,profile_featured_accolade,
                          featured_player_id,beta_member,support_tier,supporter_since,supporter_expires_at,
                          founding_supporter,founding_supporter_since
                   FROM users WHERE lower(username)=lower(?)""",
                (username,)
            ).fetchone()
            if not profile:
                c.close()
                return self.out({"error":"USER_NOT_FOUND"},404)
            uid=profile["id"]
            public_entitlement=supporter_entitlement(c,uid)
            profile=dict(profile)
            profile["support_tier"]=public_entitlement["tier"]
            profile["supporter"]=public_entitlement["supporter"]
            profile["player_slots"]=public_entitlement["entitled_player_limit"]
            profile["customization_active"]=bool(public_entitlement["supporter"])
            profile["founding_supporter"]=bool(public_entitlement.get("founding_supporter",profile.get("founding_supporter",0)))
            profile["founding_supporter_since"]=public_entitlement.get("founding_supporter_since") or profile.get("founding_supporter_since")
            # RC106/RC107: Supporter customization stays stored if support lapses, but a
            # Free account presents the standard EBL identity. Founding status is historical.
            if not public_entitlement["supporter"]:
                profile["display_name"]=""
                profile["profile_bio"]=""
                profile["profile_motto"]=""
                profile["profile_photo"]=""
                profile["profile_accent"]="#d4af37"
                profile["profile_theme"]="CLASSIC"
                profile["profile_banner"]="CLASSIC"
                profile["profile_card_frame"]="CLASSIC"
                profile["profile_featured_accolade"]=""
                profile["featured_player_id"]=None
            players=[]
            for row in c.execute(
                """SELECT p.*,f.name team_name
                   FROM players p LEFT JOIN franchises f ON f.id=p.franchise_id
                   WHERE p.user_id=? ORDER BY p.active DESC,p.id DESC""",
                (uid,)
            ):
                pl=dict(row)
                try:pl["stats"]=json.loads(pl.pop("season_json") or "{}")
                except Exception:pl["stats"]={}
                try:attrs=json.loads(pl.pop("attributes_json") or "{}")
                except Exception:attrs={}
                pl["overall"]=player_overall_from_attrs(attrs,pl.get("type","H"),pl.get("primary_pos","UTIL"))
                con=c.execute("SELECT franchise_id,salary,bonus,years_remaining AS years,'ACTIVE' AS status,signed_at AS created_at FROM contracts WHERE player_id=?",(pl["id"],)).fetchone()
                pl["contract"]=dict(con) if con else None
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
                "profile":profile,
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
                if r.get("holder_type")=="PLAYER":
                    x=c.execute("""SELECT p.name,u.username FROM players p
                                   LEFT JOIN users u ON u.id=p.user_id WHERE p.id=?""",(r["holder_id"],)).fetchone()
                    r["holder_name"]=x["name"] if x else r["holder_id"]
                    r["username"]=x["username"] if x else None
                else:
                    x=c.execute("SELECT name FROM franchises WHERE id=?",(r["holder_id"],)).fetchone()
                    r["holder_name"]=x["name"] if x else r["holder_id"]
            c.close();return self.out({"records":rows})
        if p=="/api/dm/contacts":
            u=self.auth()
            if not u:return
            c=conn()
            rows=[dict(x) for x in c.execute("""SELECT u.id,u.username,u.role,
                (SELECT name FROM players p WHERE p.user_id=u.id AND p.active=1 ORDER BY p.id DESC LIMIT 1) player_name,
                (SELECT f.name FROM players p JOIN franchises f ON f.id=p.franchise_id WHERE p.user_id=u.id AND p.active=1 ORDER BY p.id DESC LIMIT 1) team_name,
                (SELECT COUNT(*) FROM direct_messages dm
                  WHERE dm.sender_user_id=u.id
                    AND dm.recipient_user_id=?
                    AND dm.read_at IS NULL) unread
                FROM users u WHERE u.id<>? ORDER BY unread DESC,u.username""",(u["id"],u["id"]))]
            unread=sum(int(r.get("unread") or 0) for r in rows)
            c.close();return self.out({"contacts":rows,"unread":unread})
        if p=="/api/dm/unread":
            u=self.auth()
            if not u:return
            c=conn()
            row=c.execute("SELECT COUNT(*) n FROM direct_messages WHERE recipient_user_id=? AND read_at IS NULL",(u["id"],)).fetchone()
            unread=int(row["n"] if row else 0)
            c.close();return self.out({"unread":unread})
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
        if p=="/api/commish/auto-advance":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn();state=auto_advance_state(c);c.close()
            if state["next_at"]>0:
                state["next_at_iso"]=datetime.datetime.fromtimestamp(state["next_at"],datetime.timezone.utc).isoformat()
            else:
                state["next_at_iso"]=None
            if state["last_at"]>0:
                state["last_at_iso"]=datetime.datetime.fromtimestamp(state["last_at"],datetime.timezone.utc).isoformat()
            else:
                state["last_at_iso"]=None
            return self.out(state)
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
            regular_games=c.execute("SELECT COUNT(*) n FROM games WHERE season=? AND league_day BETWEEN 1 AND ?",(season,REGULAR_SEASON_CALENDAR_DAYS)).fetchone()["n"]
            final_games=c.execute("SELECT COUNT(*) n FROM games WHERE season=? AND status='FINAL'",(season,)).fetchone()["n"]
            scheduled_games=c.execute("SELECT COUNT(*) n FROM games WHERE season=? AND status='SCHEDULED'",(season,)).fetchone()["n"]
            next_day_games=c.execute("SELECT COUNT(*) n FROM games WHERE season=? AND league_day=? AND status='SCHEDULED'",(season,day+1)).fetchone()["n"] if day<REGULAR_SEASON_CALENDAR_DAYS else 0
















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
                if len(batting)!=9 or not (3<=len(rotation)<=5):
                    lineup_issues.append({
                        "franchise_id":row["franchise_id"],
                        "batting_order":len(batting),
                        "rotation":len(rotation)
                    })
















            issues=[]
            expected_slots=team_count*18
            expected_games=team_count*REGULAR_SEASON_GAMES//2
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
            if lineup_issues:issues.append(f"{len(lineup_issues)} teams have an incomplete batting order or rotation (3-5 starters required)")
            if phase=="REGULAR" and day<REGULAR_SEASON_CALENDAR_DAYS and next_day_games>expected_daily:
                issues.append(f"Too many scheduled games on Day {day+1}: expected at most {expected_daily}, found {next_day_games}")
















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








        if p=="/api/coach/application":
            u=self.auth()
            if not u:return
            c=conn()
            try:
                app=c.execute("SELECT * FROM coach_applications WHERE user_id=? ORDER BY id DESC LIMIT 1",(u["id"],)).fetchone()
                team=c.execute("SELECT id,name FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
                approved=(u["role"] in ("COACH","COMMISSIONER")) or bool(app and app["status"]=="APPROVED")
                available=[dict(x) for x in c.execute("SELECT id,name FROM franchises WHERE owner_user_id IS NULL ORDER BY name")] if approved and not team else []
                return self.out({"application":dict(app) if app else None,"approved":approved,"assigned_team":dict(team) if team else None,"available_teams":available,"applications_open":COACH_APPLICATIONS_OPEN})
            finally:
                c.close()








        if p=="/api/commish/beta-feedback":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn()
            try:
                rows=[dict(x) for x in c.execute("""SELECT bf.*,u.username
                    FROM beta_feedback bf LEFT JOIN users u ON u.id=bf.user_id
                    ORDER BY CASE bf.status WHEN 'OPEN' THEN 0 ELSE 1 END,bf.id DESC LIMIT 250""").fetchall()]
                return self.out({"feedback":rows})
            finally:
                c.close()








        if p=="/api/commish/coach-applications":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn()
            try:
                rows=[dict(x) for x in c.execute("""SELECT a.*,u.username,u.role,f.name preferred_franchise_name,owned.id assigned_franchise_id,owned.name assigned_franchise_name
                    FROM coach_applications a JOIN users u ON u.id=a.user_id
                    LEFT JOIN franchises f ON f.id=a.preferred_franchise_id
                    LEFT JOIN franchises owned ON owned.owner_user_id=a.user_id
                    ORDER BY CASE a.status WHEN 'PENDING' THEN 0 WHEN 'APPROVED' THEN 1 ELSE 2 END,a.id DESC""")]
                return self.out({"applications":rows})
            finally:
                c.close()








        if p=="/api/commish/coach-assignments":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn()
            try:
                coaches=[dict(x) for x in c.execute(
                    """SELECT u.id,u.username,u.role,f.id franchise_id,f.name franchise_name
                       FROM users u
                       LEFT JOIN franchises f ON f.owner_user_id=u.id
                       WHERE u.role='COACH'
                       ORDER BY u.username,f.name"""
                ).fetchall()]
                teams=[dict(x) for x in c.execute(
                    """SELECT f.id,f.name,f.owner_user_id,u.username coach_username
                       FROM franchises f
                       LEFT JOIN users u ON u.id=f.owner_user_id
                       ORDER BY f.name"""
                ).fetchall()]
                return self.out({"coaches":coaches,"teams":teams})
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
            c=conn();rows,catcher=position_demand(c);c.close()
            return self.out({"positions":rows,"catcher_specialty":catcher,"advisory_only":True})
        if p=="/api/commish/audit":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            c=conn();rows=[dict(x) for x in c.execute("SELECT * FROM commissioner_audit ORDER BY id DESC LIMIT 250")]
            c.close();return self.out({"audit":rows})
        if p=="/api/news":
            c=conn();season=_season_number(c)
            rows=[dict(x) for x in c.execute("""SELECT n.*,f.name franchise_name,p.name player_name
                FROM news n LEFT JOIN franchises f ON f.id=n.franchise_id
                LEFT JOIN players p ON p.id=n.player_id
                WHERE n.season=?
                ORDER BY n.league_day DESC,n.importance DESC,n.id DESC LIMIT 60""",(season,))]
            c.close();return self.out({"season":season,"news":rows})
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
                    SELECT id,name,franchise_id,face_id,skin_color_id,hair_id,hair_color_id,facial_hair_id,eye_color_id,nose_id,eye_shape_id,mouth_id,ear_size_id,eye_black_id,eyewear_id,chain_id,sleeve_id,body_build_id,jersey_number,primary_pos,bats,throws
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
                    "face_id":player["face_id"],"skin_color_id":player["skin_color_id"],"hair_id":player["hair_id"],"hair_color_id":player["hair_color_id"],
                    "facial_hair_id":player["facial_hair_id"],"eye_color_id":player["eye_color_id"],
                    "nose_id":player["nose_id"],"eye_shape_id":player["eye_shape_id"],
                    "mouth_id":player["mouth_id"],"ear_size_id":player["ear_size_id"],
                    "eye_black_id":player["eye_black_id"],"eyewear_id":player["eyewear_id"],
                    "chain_id":player["chain_id"],"sleeve_id":player["sleeve_id"],"body_build_id":player["body_build_id"],
                    "jersey_number":player["jersey_number"],"primary_pos":player["primary_pos"],
                    "bats":player["bats"],"throws":player["throws"],
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
                        SELECT name,face_id,skin_color_id,hair_id,hair_color_id,facial_hair_id,eye_color_id,nose_id,eye_shape_id,mouth_id,ear_size_id,eye_black_id,eyewear_id,chain_id,sleeve_id,body_build_id,jersey_number,primary_pos,bats,throws
                        FROM players
                        WHERE id=?
                        """,
                        (pid,)
                    ).fetchone()
















                    pitcher_rows.append({
                        "player_id":pid,
                        "name":player["name"] if player else f"Player {pid}",
                        "team_id":team_id,
                        "face_id":player["face_id"] if player else 1,
                        "skin_color_id":player["skin_color_id"] if player else 1,
                        "hair_id":player["hair_id"] if player else 1,
                        "facial_hair_id":player["facial_hair_id"] if player else 1,
                        "eye_color_id":player["eye_color_id"] if player else 6,
                        "nose_id":player["nose_id"] if player else 1,
                        "eye_shape_id":player["eye_shape_id"] if player else 1,
                        "mouth_id":player["mouth_id"] if player else 1,
                        "ear_size_id":player["ear_size_id"] if player else 2,
                        "hair_color_id":player["hair_color_id"] if player else 3,
                        "eye_black_id":player["eye_black_id"] if player else 1,
                        "eyewear_id":player["eyewear_id"] if player else 1,
                        "chain_id":player["chain_id"] if player else 1,
                        "sleeve_id":player["sleeve_id"] if player else 1,
                        "body_build_id":player["body_build_id"] if player else 1,
                        "jersey_number":player["jersey_number"] if player else 24,
                        "primary_pos":player["primary_pos"] if player else "P",
                        "bats":player["bats"] if player else "R",
                        "throws":player["throws"] if player else "R",
                        **line
                    })
















            # ---------------------------------------------
            # BUILD GAMECAST-FRIENDLY FIELDING ROWS
            # ---------------------------------------------








            fielding_rows=[]
            for pid,line in raw_box.get("fielding",{}).items():
                player=c.execute(
                    """SELECT id,name,franchise_id,jersey_number,primary_pos
                       FROM players WHERE id=?""",
                    (int(pid),)
                ).fetchone()
                if not player:
                    continue
                po=int(line.get("PO",0) or 0);assists=int(line.get("A",0) or 0);errors=int(line.get("E",0) or 0)
                chances=po+assists+errors
                fielding_rows.append({
                    "player_id":int(pid),"name":player["name"],"team_id":player["franchise_id"],
                    "jersey_number":player["jersey_number"],
                    "position":line.get("POS") or player["primary_pos"],
                    **line,
                    "FLD_PCT":f"{((po+assists)/chances if chances else 1.0):.3f}"
                })








            # ---------------------------------------------
            # COMPLETE BOX SCORE
            # ---------------------------------------------
















            game["box"]={
                **raw_box,
                "hitter_rows":hitter_rows,
                "pitcher_rows":pitcher_rows,
                "fielding_rows":fielding_rows
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
                    "E":sum(int(x.get("E",0) or 0) for x in fielding_rows if x.get("team_id")==game["away_id"])
                },
                "home":{
                    "R":game["home_runs"] or 0,
                    "H":sum(
                        int(x.get("H",0) or 0)
                        for x in hitter_rows
                        if x["team_id"]==game["home_id"]
                    ),
                    "E":sum(int(x.get("E",0) or 0) for x in fielding_rows if x.get("team_id")==game["home_id"])
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
            requested=request_player_id(self)
            active_row=owned_active_player(c,u["id"],requested)
            pl=player_obj(c,active_row["id"]) if active_row else None
            if pl and pl.get("franchise_id"):
                f=c.execute(
                    """SELECT f.id,f.name,f.wins,f.losses,f.runs_for,f.runs_against,
                              b.primary_color,b.secondary_color,b.accent_color,b.primary_logo,b.secondary_logo,b.jersey_wordmark
                       FROM franchises f
                       LEFT JOIN franchise_branding b ON b.franchise_id=f.id
                       WHERE f.id=?""",
                    (pl["franchise_id"],)
                ).fetchone()
                if f:
                    pl["team"]=dict(f);pl["team"]["division"]=season_division(c,_season_number(c),pl["franchise_id"])
                pl["recent_game"]=recent_game_for_player(c,pl)
            former=[]
            for row in c.execute(
                "SELECT id FROM players WHERE user_id=? AND active=0 ORDER BY id DESC",
                (u["id"],)
            ).fetchall():
                fp=player_obj(c,row["id"])
                if fp: former.append(fp)
            active_players=[]
            for row in c.execute("SELECT id,name,type,primary_pos,franchise_id,status,xp_wallet FROM players WHERE user_id=? AND active=1 ORDER BY id",(u["id"],)).fetchall():
                active_players.append(dict(row))
            ent=supporter_entitlement(c,u["id"])
            c.close()
            return self.out({"player":pl,"players":active_players,"player_limit":ent["creation_player_limit"],
                             "entitled_player_limit":ent["entitled_player_limit"],"entitlements":ent,"careers":former})
        if p=="/api/my-team":
            u=self.auth()
            if not u:return
            c=conn()
            pl=owned_active_player(c,u["id"],request_player_id(self))
            if not pl:
                c.close();return self.out({"team":None,"reason":"NO_ACTIVE_PLAYER"})
            fid=pl["franchise_id"]
            if not fid:
                c.close();return self.out({"team":None,"player_id":pl["id"],"reason":"FREE_AGENT"})
            team=c.execute("SELECT id,name,wins,losses,runs_for,runs_against FROM franchises WHERE id=?",(fid,)).fetchone()
            if not team:
                c.close();return self.out({"team":None,"player_id":pl["id"],"reason":"TEAM_NOT_FOUND"})
            brand=c.execute("SELECT * FROM franchise_branding WHERE franchise_id=?",(fid,)).fetchone()
            roster=[]
            for row in c.execute(
                """SELECT p.id,p.user_id,p.name,p.hometown,p.franchise_id,p.type,p.primary_pos,p.bats,p.throws,p.jersey_number,p.status,p.xp_wallet,
                          p.face_id,p.skin_color_id,p.hair_id,p.hair_color_id,p.facial_hair_id,p.eye_color_id,p.nose_id,p.eye_shape_id,p.mouth_id,p.ear_size_id,
                          p.eye_black_id,p.eyewear_id,p.chain_id,p.sleeve_id,p.body_build_id,p.attributes_json,p.season_json,u.username
                   FROM players p LEFT JOIN users u ON u.id=p.user_id
                   WHERE p.franchise_id=? AND p.active=1
                   ORDER BY CASE p.type WHEN 'H' THEN 0 ELSE 1 END,p.primary_pos,p.name""",(fid,)):
                x=dict(row)
                try:attrs=json.loads(x.pop("attributes_json") or "{}")
                except Exception:attrs={}
                try:x["stats"]=json.loads(x.pop("season_json") or "{}")
                except Exception:x["stats"]={}
                x["overall"]=player_overall_from_attrs(attrs,x.get("type","H"),x.get("primary_pos","UTIL"))
                roster.append(x)
            l=c.execute("SELECT batting_order_json,rotation_json,field_positions_json FROM lineups WHERE franchise_id=?",(fid,)).fetchone()
            strat=c.execute("SELECT bullpen_json FROM team_strategy WHERE franchise_id=?",(fid,)).fetchone()
            try:lineup=json.loads(l["batting_order_json"] or "[]") if l else []
            except Exception:lineup=[]
            try:rotation=json.loads(l["rotation_json"] or "[]") if l else []
            except Exception:rotation=[]
            try:field_positions=json.loads(l["field_positions_json"] or "{}") if l else {}
            except Exception:field_positions={}
            try:bullpen=json.loads(strat["bullpen_json"] or "{}") if strat else {}
            except Exception:bullpen={}
            state={r["k"]:r["v"] for r in c.execute("SELECT k,v FROM league_state WHERE k IN ('season','league_day','phase')")}
            season=int(state.get("season",1));day=int(state.get("league_day",0));today=practice_day_key()
            attendance=[dict(r) for r in c.execute(
                """SELECT tp.player_id,tp.joined_at,p.name,p.primary_pos,u.username
                   FROM team_practice tp JOIN players p ON p.id=tp.player_id
                   LEFT JOIN users u ON u.id=p.user_id
                   WHERE tp.franchise_id=? AND tp.practice_date=?
                   ORDER BY tp.joined_at""",(fid,today))]
            human_total=c.execute("SELECT COUNT(*) n FROM players WHERE franchise_id=? AND active=1 AND user_id IS NOT NULL",(fid,)).fetchone()["n"]
            practiced=any(int(a["player_id"])==int(pl["id"]) for a in attendance)
            next_game=c.execute(
                """SELECT id,league_day,away_id,home_id,status FROM games
                   WHERE season=? AND league_day>=? AND status='SCHEDULED' AND (away_id=? OR home_id=?)
                   ORDER BY league_day,id LIMIT 1""",(season,max(1,day),fid,fid)).fetchone()
            recent_games=[dict(r) for r in c.execute(
                """SELECT id,league_day,away_id,home_id,away_runs AS away_score,home_runs AS home_score,status FROM games
                   WHERE season=? AND status='FINAL' AND (away_id=? OR home_id=?)
                   ORDER BY league_day DESC,id DESC LIMIT 5""",(season,fid,fid))]
            out={"team":dict(team),"branding":dict(brand) if brand else None,"division":season_division(c,season,fid),
                 "player_id":pl["id"],"roster":roster,"lineup":lineup,"field_positions":field_positions,
                 "rotation":rotation,"bullpen":bullpen,"practice":{"date":today,"reward":practice_reward_for(c,fid),
                 "completed":practiced,"attendance":attendance,"human_total":human_total},
                 "season":season,"league_day":day,"phase":state.get("phase","REGULAR"),
                 "next_game":dict(next_game) if next_game else None,"recent_games":recent_games}
            c.close();return self.out(out)








        if p=="/api/coach/free-agents":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            c=conn();f=c.execute("SELECT * FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            rows=[player_obj(c,x["id"]) for x in c.execute("SELECT id FROM players WHERE status='FREE_AGENT' AND active=1 ORDER BY id DESC LIMIT 100")]
            if f:
                for row in rows:
                    previous=previous_team_salary(c,row["id"],f["id"])
                    service_seasons=player_seasons_completed(c,row["id"])
                    row["previous_team_salary"]=previous
                    row["minimum_offer_salary"]=minimum_offer_salary(c,row["id"],f["id"])
                    row["returning_player"]=previous is not None
                    row["service_seasons"]=service_seasons
                    row["is_rookie_contract"]=service_seasons==0
                    row["offer_roles"]=available_roster_roles(c,f["id"],row)
            c.close();return self.out({"players":rows})
        if p=="/api/coach/team":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            c=conn();f=c.execute("SELECT * FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"team":None})
            roster=[dict(x) for x in c.execute(
                """SELECT p.id,p.user_id,p.name,p.franchise_id,p.type,p.primary_pos,p.bats,p.throws,p.jersey_number,p.xp_wallet,p.status,
                          p.face_id,p.skin_color_id,p.hair_id,p.hair_color_id,p.facial_hair_id,p.eye_color_id,p.nose_id,p.eye_shape_id,p.mouth_id,p.ear_size_id,
                          p.eye_black_id,p.eyewear_id,p.chain_id,p.sleeve_id,p.body_build_id,u.username,
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
                          p.name,p.primary_pos,p.type,p.user_id,u.username
                   FROM contracts co JOIN players p ON p.id=co.player_id
                   LEFT JOIN users u ON u.id=p.user_id
                   WHERE co.franchise_id=? AND p.active=1
                   ORDER BY p.type,p.primary_pos,p.name""",(f["id"],))]
            state={x["k"]:x["v"] for x in c.execute("SELECT k,v FROM league_state WHERE k IN ('season','league_day','phase')")}
            season=int(state.get("season",1));day=int(state.get("league_day",0));phase=str(state.get("phase","REGULAR")).upper()
            renewal_window_open=bool(phase=="REGULAR" and day>=RENEWAL_OPEN_DAY and day<=REGULAR_SEASON_CALENDAR_DAYS)
            for con in contracts:
                con["renewal_eligible"]=bool(renewal_window_open and con.get("user_id") is not None and int(con.get("years_remaining") or 0)==1)
                con["renewal_same_rate"]=round(float(con.get("salary") or SALARY_MIN),2)
                con["renewal_veteran_minimum"]=renewal_veteran_minimum(c,con["player_id"])
                renewal=c.execute(
                    """SELECT id,status,salary,years,message,salary_basis,effective_season,created_at
                       FROM offers WHERE franchise_id=? AND player_id=? AND offer_type='RENEWAL'
                         AND effective_season=? AND status IN ('OPEN','HELD','ACCEPTED')
                       ORDER BY CASE status WHEN 'ACCEPTED' THEN 0 ELSE 1 END,id DESC LIMIT 1""",
                    (f["id"],con["player_id"],season+1)
                ).fetchone()
                con["renewal"]=dict(renewal) if renewal else None
            next_game=c.execute(
                """SELECT id,season,league_day,away_id,home_id,status
                   FROM games WHERE season=? AND league_day>? AND status='SCHEDULED'
                     AND (away_id=? OR home_id=?)
                   ORDER BY league_day,id LIMIT 1""",(season,day,f["id"],f["id"])).fetchone()
            salary_rate=sum(float(x.get("salary") or 0) for x in contracts)
            finance=team_finance_snapshot(c,f["id"])
            for player in roster:
                if player.get("type")=="P":
                    player["recovery"]=pitcher_recovery_state(c,player["id"],day)
            team=dict(f)
            # RC78: show the full current-season cost of every signed human contract
            # immediately. Players are still paid XP game-by-game; this is the
            # season commitment view so coaches can see what the roster has already
            # consumed before making another move.
            team["xp_available"]=finance["available"]
            team["reserved_offers"]=finance["reserved"]
            team["signed_payroll_commitment"]=finance["signed_payroll"]
            team["open_roster_minimum_reserve"]=finance["open_job_minimum_reserve"]
            team["protected_player_commitment"]=finance["protected_payroll"]
            team["salary_paid_to_date"]=round(float(team.get("xp_spent") or 0),3)
            team["xp_after_signed_players"]=round(max(0.0,float(team.get("xp_budget") or 0)-finance["signed_payroll"]),3)
            team["salary_rate"]=round(salary_rate,3)
            team["spend_pct"]=round((finance["signed_payroll"]/max(1.0,float(team.get("xp_budget") or 0)))*100,1)
            team["next_season_committed_payroll"]=next_season_payroll_projection(c,f["id"])
            team["next_season_base_budget"]=round(annual_team_budget(team),3)
            team["next_season_projected_treasury"]=projected_next_season_treasury(c,f["id"])
            team["base_funding"]=TEAM_BUDGET
            team["permanent_pool_growth"]=round(float(team.get("funding_growth") or 0),3)
            team["revenue_upgrades_total"]=revenue_upgrade_levels(team)
            team["revenue_upgrade_bonus"]=revenue_upgrade_bonus(team)
            team["revenue_branch_max"]=REVENUE_BRANCH_MAX
            team["revenue_upgrade_costs"]=REVENUE_UPGRADE_COSTS
            team["revenue_upgrade_bonuses"]=REVENUE_UPGRADE_BONUSES[1:]
            team["practice_reward"]=practice_reward_for(c,f["id"])
            team["recovery_bonus_per_day"]=2*int(team.get("recovery_level") or 0)
            team["development_bonus_active"]=season>1
            team["development_bonus_effective"]=float(team.get("development_bonus") or 0) if season>1 else 0.0
            sponsorships=active_team_sponsorships(c,f["id"],season)
            development_coaches=active_team_development_coaches(c,f["id"],season)
            branding=dict(brand) if brand else None
            if branding is not None:
                used_season=branding.get("inseason_edit_season")
                branding["inseason_edit_used"]=bool(used_season is not None and int(used_season)==season)
                branding["inseason_edit_available"]=not branding["inseason_edit_used"]
            c.close()
            return self.out({"team":team,"branding":branding,"roster":roster,
                             "lineup":json.loads(l["batting_order_json"]) if l else [],
                             "field_positions":json.loads(l["field_positions_json"] or "{}") if l else {},
                             "rotation":json.loads(l["rotation_json"]) if l else [],
                             "strategy":{"bullpen":json.loads(strat["bullpen_json"]) if strat else {},
                                         "defense":json.loads(strat["defense_json"]) if strat else {},
                                         "bench":json.loads(strat["bench_json"]) if strat else {},
                                         "substitutions":json.loads(strat["substitutions_json"]) if strat else {}},
                             "offers":offers,"contracts":contracts,"sponsorships":sponsorships,
                             "development_coaches":development_coaches,
                             "development_coach_options":[{"coach_type":k,**v} for k,v in DEVELOPMENT_COACH_TYPES.items()],
                             "development_coach_rules":{"first_free":True,"maximum":DEVELOPMENT_COACH_MAX,"base_cost":DEVELOPMENT_COACH_BASE_COST,
                                                        "hiring_close_day":DEVELOPMENT_COACH_HIRING_CLOSE_DAY,
                                                        "intensity":[{"level":k,**v,"cost":DEVELOPMENT_COACH_BASE_COST+float(v["extra_cost"])} for k,v in DEVELOPMENT_COACH_INTENSITY.items()]},
                             "next_game":dict(next_game) if next_game else None,
                             "renewal_window_open":renewal_window_open,"renewal_open_day":RENEWAL_OPEN_DAY,
                             "season":season,"league_day":day,"phase":state.get("phase","REGULAR")})
        if p=="/api/friends":
            u=self.auth()
            if not u:return
            c=conn()
            # RC78: friendship is account/profile-level, never player-level. A user
            # with three active players must still appear exactly once in the friends list.
            accepted=[dict(x) for x in c.execute(
                """SELECT f.id,
                          CASE WHEN f.requester_user_id=? THEN f.addressee_user_id ELSE f.requester_user_id END user_id,
                          u.username,u.role
                   FROM friendships f
                   JOIN users u ON u.id=CASE WHEN f.requester_user_id=? THEN f.addressee_user_id ELSE f.requester_user_id END
                   WHERE f.status='ACCEPTED' AND (f.requester_user_id=? OR f.addressee_user_id=?)
                   ORDER BY LOWER(u.username)""",(u["id"],u["id"],u["id"],u["id"]))]
            incoming=[dict(x) for x in c.execute(
                """SELECT f.id,f.requester_user_id user_id,u.username,u.role,f.created_at
                   FROM friendships f JOIN users u ON u.id=f.requester_user_id
                   WHERE f.addressee_user_id=? AND f.status='PENDING' ORDER BY f.id DESC""",(u["id"],))]
            outgoing=[dict(x) for x in c.execute(
                """SELECT f.id,f.addressee_user_id user_id,u.username,u.role,f.created_at
                   FROM friendships f JOIN users u ON u.id=f.addressee_user_id
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
            for r in c.execute("""SELECT p.id,p.name,p.franchise_id,p.primary_pos,p.season_json,p.jersey_number,p.bats,p.throws,
                                         p.face_id,p.skin_color_id,p.hair_id,p.hair_color_id,p.facial_hair_id,p.eye_color_id,
                                         p.nose_id,p.eye_shape_id,p.mouth_id,p.ear_size_id,
                                         p.eye_black_id,p.eyewear_id,p.chain_id,p.sleeve_id,p.body_build_id,u.username,
                                         f.name AS team_name,COALESCE(NULLIF(b.display_name,''),f.name) AS team_display_name
                                  FROM players p
                                  LEFT JOIN users u ON u.id=p.user_id
                                  LEFT JOIN franchises f ON f.id=p.franchise_id
                                  LEFT JOIN franchise_branding b ON b.franchise_id=p.franchise_id
                                  WHERE p.active=1"""):
                st=json.loads(r["season_json"])
                if "PA" in st:
                    ab=st.get("AB",0);h=st.get("H",0);bb=st.get("BB",0);pa=st.get("PA",0)
                    tb=st.get("1B",0)+2*st.get("2B",0)+3*st.get("3B",0)+4*st.get("HR",0)
                    avg=h/ab if ab else 0;obp=(h+bb)/pa if pa else 0;slg=tb/ab if ab else 0
                    # MVP proxy deliberately broad: offense + speed/base value; defense is derived from actual fielding events.
                    fm=fielding_award_metrics(st)
                    oaa=fm["oaa"];ferr=fm["e"]
                    defense_value=oaa*2.0-ferr*.65
                    mvp=(obp+slg)*100 + st.get("HR",0)*1.1 + st.get("SB",0)*.35 + st.get("RBI",0)*.12 + defense_value
                    identity=player_identity_payload(r)
                    identity.update({"avg":avg,"obp":obp,"slg":slg,"ops":obp+slg,"hr":st.get("HR",0),"rbi":st.get("RBI",0),
                                     "sb":st.get("SB",0),"pa":pa,"mvp":mvp,"oaa":oaa,"e":ferr,
                                     "fg":fm["fg"],"po":fm["po"],"a":fm["a"],"dp":fm["dp"],"ch":fm["ch"],
                                     "fld_pct_num":fm["fld_pct"],"fld_pct":(f"{fm['fld_pct']:.3f}" if fm["fld_pct"] is not None else "—"),
                                     "fielding_score":fm["fielding_score"]})
                    hitters.append(identity)
                else:
                    outs=st.get("OUTS",0);er=st.get("ER",0);bb=st.get("BB",0);h=st.get("H",0);so=st.get("SO",0)
                    era=er*27/outs if outs else 99.0;whip=(bb+h)/(outs/3) if outs else 99.0
                    score=(so*1.2)-(er*2.2)-(bb*.7)+(outs/3)*.3
                    identity=player_identity_payload(r)
                    identity.update({"era":era,"whip":whip,"so":so,"sv":st.get("SV",0),"outs":outs,"score":score})
                    pitchers.append(identity)
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
            # Positional Fielding Title races use the same performance formula as the season award.
            league_day=int(c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()["v"] or 0)
            field_min_games=fielding_award_min_games(league_day)
            fielding={}
            fielding_meta={"min_games":field_min_games,"league_day":league_day}
            for pos in ["C","1B","2B","3B","SS","LF","CF","RF"]:
                all_pos=[x for x in hitters if x["pos"]==pos and x.get("fg",0)>0]
                pool=[x for x in all_pos if x.get("fg",0)>=field_min_games]
                ranked=sorted(pool or all_pos,key=fielding_award_sort_key,reverse=True)[:5]
                for x in ranked:
                    x["fielding_qualified"]=x.get("fg",0)>=field_min_games
                fielding[pos]=ranked
            history=[dict(x) for x in c.execute("""SELECT ah.*,p.name player_name,u.username,f.name team_name FROM award_history ah
                LEFT JOIN players p ON p.id=ah.player_id LEFT JOIN users u ON u.id=p.user_id LEFT JOIN franchises f ON f.id=ah.franchise_id
                ORDER BY ah.season DESC,ah.id DESC LIMIT 100""")]
            all_star_row=c.execute("SELECT * FROM all_star_games ORDER BY season DESC LIMIT 1").fetchone()
            all_star=dict(all_star_row) if all_star_row else None
            if all_star:
                for key in ("gold_roster_json","red_roster_json","box_json"):
                    try:all_star[key.replace("_json","")]=json.loads(all_star.pop(key) or ("{}" if key=="box_json" else "[]"))
                    except Exception:all_star[key.replace("_json","")]={} if key=="box_json" else []
            c.close();return self.out({
                "mvp":mvp,
                "batting":batting,
                "home_runs":hr,
                "stolen_bases":sb,
                "pitching":pitching,
                "starting_pitching":starting_pitching,
                "relief_pitching":relief_pitching,
                "fielding":fielding,
                "fielding_meta":fielding_meta,
                "xp_values":{
                    "MVP":15,
                    "BATTING_TITLE":10,
                    "PITCHER_OF_SEASON":15,
                    "RELIEVER_OF_SEASON":10,
                    "SB_TITLE":10,
                    "FIELDING":10,
                    "QUARTER_BATTER":5,
                    "QUARTER_PITCHER":5,
                    "ALL_STAR_SELECTION":ALL_STAR_SELECTION_XP,
                    "PLAYOFF_BERTH":PLAYOFF_ROSTER_XP,
                    "FINAL_FOUR":FINAL_FOUR_XP,
                    "CHAMPIONSHIP_BERTH":CHAMPIONSHIP_BERTH_XP,
                    "CHAMPIONSHIP_WIN":CHAMPIONSHIP_WIN_XP
                },
                "all_star":all_star,
                "history":history
            })
        if p.startswith("/api/chat/"):
            u=self.auth()
            if not u:return
            channel=p.split("/")[-1].upper()
            if channel not in ("EBL","TEAM"):return self.out({"error":"INVALID_CHANNEL"},400)
            c=conn();team_id=None
            # Public/team chat is temporary, but GET must remain read-only.
            # Expired rows are hidden below and physically pruned by storage maintenance.
            if channel=="TEAM":
                pr=owned_active_player(c,u["id"],request_player_id(self))
                team_id=pr["franchise_id"] if pr else None
                if not team_id:c.close();return self.out({"messages":[]})
            rows=[dict(x) for x in c.execute("""SELECT m.id,m.user_id,m.player_id,m.channel,m.team_id,m.message,m.created_at,u.username
                    FROM chat_messages m JOIN users u ON u.id=m.user_id
                    WHERE m.channel=? AND (? IS NULL OR m.team_id=?)
                      AND m.created_at >= datetime('now', ?)
                    ORDER BY m.id DESC LIMIT 50""",(channel,team_id,team_id,f"-{CHAT_RETENTION_HOURS} hours"))]
            rows.reverse()
            for msg in rows:
                pid=msg.get("player_id")
                player=None
                if pid:
                    player=c.execute("""SELECT id,name,franchise_id,face_id,skin_color_id,hair_id,hair_color_id,
                                      facial_hair_id,eye_color_id,nose_id,eye_shape_id,mouth_id,ear_size_id,eye_black_id,eyewear_id,chain_id,sleeve_id,body_build_id,
                                      jersey_number,primary_pos,bats,throws
                                      FROM players WHERE id=?""",(pid,)).fetchone()
                if not player and msg.get("team_id"):
                    player=c.execute("""SELECT id,name,franchise_id,face_id,skin_color_id,hair_id,hair_color_id,
                                      facial_hair_id,eye_color_id,nose_id,eye_shape_id,mouth_id,ear_size_id,eye_black_id,eyewear_id,chain_id,sleeve_id,body_build_id,
                                      jersey_number,primary_pos,bats,throws
                                      FROM players WHERE user_id=? AND active=1 AND franchise_id=?
                                      ORDER BY id DESC LIMIT 1""",(msg["user_id"],msg["team_id"])).fetchone()
                if not player:
                    player=c.execute("""SELECT id,name,franchise_id,face_id,skin_color_id,hair_id,hair_color_id,
                                      facial_hair_id,eye_color_id,nose_id,eye_shape_id,mouth_id,ear_size_id,eye_black_id,eyewear_id,chain_id,sleeve_id,body_build_id,
                                      jersey_number,primary_pos,bats,throws
                                      FROM players WHERE user_id=? AND active=1
                                      ORDER BY id DESC LIMIT 1""",(msg["user_id"],)).fetchone()
                msg["player"]=dict(player) if player else None
                msg.pop("user_id",None)
            c.close();return self.out({"messages":rows})
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
            for r in c.execute("""SELECT p.id,p.name,p.primary_pos,p.xp_wallet,p.attributes_json,p.season_json,p.franchise_id,
                                         p.jersey_number,p.bats,p.throws,p.face_id,p.skin_color_id,p.hair_id,p.hair_color_id,
                                         p.facial_hair_id,p.eye_color_id,p.nose_id,p.eye_shape_id,p.mouth_id,p.ear_size_id,p.eye_black_id,p.eyewear_id,p.chain_id,p.sleeve_id,p.body_build_id,u.username,
                                         f.name AS team_name,COALESCE(NULLIF(b.display_name,''),f.name) AS team_display_name
                                  FROM players p
                                  LEFT JOIN users u ON u.id=p.user_id
                                  LEFT JOIN franchises f ON f.id=p.franchise_id
                                  LEFT JOIN franchise_branding b ON b.franchise_id=p.franchise_id
                                  WHERE p.active=1"""):
                d=dict(r); st=json.loads(d["season_json"]); at=json.loads(d["attributes_json"])
                if "PA" in st:
                    ab=st.get("AB",0);h=st.get("H",0);bb=st.get("BB",0)
                    avg=h/ab if ab else 0
                    obp=(h+bb)/(st.get("PA",0)) if st.get("PA",0) else 0
                    tb=st.get("1B",0)+2*st.get("2B",0)+3*st.get("3B",0)+4*st.get("HR",0)
                    slg=tb/ab if ab else 0
                    identity=player_identity_payload(d)
                    identity.update({"xp":d["xp_wallet"],"avg":avg,"obp":obp,"slg":slg,"ops":obp+slg,"hr":st.get("HR",0),"so":st.get("SO",0),"bb":bb,"pa":st.get("PA",0),"attr_total":sum(at.values())})
                    hitters.append(identity)
                else:
                    outs=st.get("OUTS",0); er=st.get("ER",0); bb=st.get("BB",0); h=st.get("H",0)
                    era=er*27/outs if outs else 0
                    whip=(bb+h)/(outs/3) if outs else 0
                    identity=player_identity_payload(d)
                    identity.update({"xp":d["xp_wallet"],"era":era,"whip":whip,"so":st.get("SO",0),"bb":bb,"outs":outs,"attr_total":sum(at.values())})
                    pitchers.append(identity)
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
        if p=="/api/support/checkout":
            u=self.auth()
            if not u:return
            d=self.body()
            plan=str(d.get("plan","monthly") or "monthly").strip().lower()
            if plan not in ("monthly","yearly"):
                return self.out({"error":"INVALID_SUPPORTER_PLAN"},400)
            plans=stripe_support_plans()
            cfg=plans.get(plan) or {}
            base=str(cfg.get("url") or "")
            if not base.startswith(("https://","http://")) or not cfg.get("payment_link_id"):
                return self.out({"error":"SUPPORT_CHECKOUT_NOT_CONFIGURED","plan":plan},503)
            c=conn()
            try:
                c.execute("BEGIN IMMEDIATE")
                if not rate_limit(c,f"support-checkout:{u['id']}",10,3600):
                    c.rollback();c.close()
                    return self.out({"error":"RATE_LIMITED"},429)
                ent=supporter_entitlement(c,u["id"])
                if ent.get("supporter"):
                    c.commit();c.close()
                    return self.out({"already_supporter":True,"entitlements":ent})
                token=secrets.token_urlsafe(24)
                c.execute(
                    "INSERT INTO support_checkout_refs(token,user_id,status,plan) VALUES(?,?,'PENDING',?)",
                    (token,u["id"],plan)
                )
                c.commit();c.close()
                sep="&" if "?" in base else "?"
                url=base+sep+"client_reference_id="+token
                return self.out({
                    "url":url,
                    "provider":"Stripe",
                    "mode":plans["mode"],
                    "plan":plan,
                    "amount":cfg["amount"],
                    "currency":cfg["currency"].upper()
                })
            except Exception:
                try:c.rollback();c.close()
                except Exception:pass
                raise








        if p=="/api/register":
            d=self.body();username=str(d.get("username","")).strip();password=str(d.get("password",""));email=str(d.get("email","")).strip().lower()
            if not registration_age_eligible(d.get("birth_date")):return self.out({"error":"AGE_REQUIREMENT_NOT_MET","minimum_age":AGE_REQUIREMENT},400)
            if d.get("accepted_terms") is not True:return self.out({"error":"TERMS_NOT_ACCEPTED"},400)
            if BETA_MODE and d.get("accepted_beta_reset") is not True:return self.out({"error":"BETA_RESET_NOT_ACCEPTED"},400)
            if len(username)<3 or len(username)>24 or not all(ch.isalnum() or ch in "_-" for ch in username):return self.out({"error":"INVALID_USERNAME"},400)
            if len(password)<8 or len(password)>128:return self.out({"error":"INVALID_PASSWORD"},400)
            if "@" not in email or "." not in email.split("@")[-1]:return self.out({"error":"INVALID_EMAIL"},400)
            c=conn();ip=get_client_ip(self)
            if not rate_limit(c,f"register:{ip}",5,3600):c.commit();c.close();return self.out({"error":"RATE_LIMITED"},429)
            if c.execute("SELECT 1 FROM users WHERE username=? COLLATE NOCASE",(username,)).fetchone():c.close();return self.out({"error":"USERNAME_TAKEN"},409)
            if c.execute("SELECT 1 FROM user_security WHERE email=?",(email,)).fetchone():c.close();return self.out({"error":"EMAIL_IN_USE"},409)
            c.execute("INSERT INTO users(username,password_hash,role,beta_member) VALUES(?,?,'PLAYER',?)",(username,pwhash(password),1 if BETA_MODE else 0))
            uid=c.execute("SELECT id FROM users WHERE username=?",(username,)).fetchone()["id"]
            raw_verify=secrets.token_urlsafe(24)
            c.execute("""INSERT INTO user_security(user_id,email,email_verified,email_token_hash,email_token_expires)
                         VALUES(?,?,0,?,?)""",(uid,email,token_hash(raw_verify),iso_after(60)))
            sid,_=new_session(c,uid,self,remember=False)
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
            return self.out({"user":{"id":uid,"username":username,"role":"PLAYER","beta_member":1 if BETA_MODE else 0},"verification_email_sent":sent},200,{"Set-Cookie":session_cookie(sid,None)})
        if p=="/api/login":
            d=self.body();username=str(d.get("username","")).strip();password=str(d.get("password",""));remember=bool(d.get("remember_me",False))
            c=conn();ip=get_client_ip(self)
            if not rate_limit(c,f"login:{ip}",20,900):c.commit();c.close();return self.out({"error":"RATE_LIMITED"},429)
            r=c.execute("SELECT id,username,role,password_hash FROM users WHERE username=? COLLATE NOCASE",(username,)).fetchone()
            if not r or not pwcheck(password,r["password_hash"]):c.commit();c.close();return self.out({"error":"INVALID_LOGIN"},401)
            sec=user_restricted(c,r["id"])
            if sec["suspended"]:c.close();return self.out({"error":"ACCOUNT_SUSPENDED"},403)
            sid,_=new_session(c,r["id"],self,remember=remember)
            beta_row=c.execute("SELECT beta_member FROM users WHERE id=?",(r["id"],)).fetchone()
            beta_member=int(beta_row["beta_member"] or 0) if beta_row else 0
            c.commit();c.close()
            return self.out({"user":{"id":r["id"],"username":r["username"],"role":r["role"],"beta_member":beta_member},"remember_me":remember},200,{"Set-Cookie":session_cookie(sid,2592000 if remember else None)})
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
        if p=="/api/profile/update":
            u=self.auth()
            if not u:return
            c=conn()
            ent=supporter_entitlement(c,u["id"])
            if not ent["supporter"]:
                c.close();return self.out({"error":"SUPPORTER_REQUIRED","feature":"PROFILE_CUSTOMIZATION"},403)
            c.close()
            d=self.body()
            display_name=" ".join(str(d.get("display_name","") or "").split()).strip()
            profile_bio=str(d.get("profile_bio","") or "").strip()
            profile_motto=str(d.get("profile_motto","") or "").strip()
            profile_theme=str(d.get("profile_theme","CLASSIC") or "CLASSIC").strip().upper()
            profile_banner=str(d.get("profile_banner","CLASSIC") or "CLASSIC").strip().upper()
            profile_card_frame=str(d.get("profile_card_frame","CLASSIC") or "CLASSIC").strip().upper()
            profile_featured_accolade=" ".join(str(d.get("profile_featured_accolade","") or "").split()).strip()
            profile_accent=str(d.get("profile_accent","#d4af37") or "#d4af37").strip()
            if len(display_name)>48:
                return self.out({"error":"DISPLAY_NAME_TOO_LONG"},400)
            if len(profile_bio)>320:
                return self.out({"error":"PROFILE_BIO_TOO_LONG"},400)
            if len(profile_motto)>120:
                return self.out({"error":"PROFILE_MOTTO_TOO_LONG"},400)
            if profile_theme not in {"CLASSIC","DUGOUT","NIGHT","GOLD"}:
                return self.out({"error":"INVALID_PROFILE_THEME"},400)
            if profile_banner not in {"CLASSIC","STADIUM","DUGOUT","SCOREBOARD","VINTAGE"}:
                return self.out({"error":"INVALID_PROFILE_BANNER"},400)
            if profile_card_frame not in {"CLASSIC","GOLD","NIGHT","RETRO","CHAMPIONSHIP"}:
                return self.out({"error":"INVALID_PROFILE_CARD_FRAME"},400)
            if len(profile_featured_accolade)>120:
                return self.out({"error":"INVALID_FEATURED_ACCOLADE"},400)
            if not valid_hex_color(profile_accent):
                return self.out({"error":"INVALID_PROFILE_ACCENT"},400)
            c=conn()
            current=c.execute("SELECT profile_photo FROM users WHERE id=?",(u["id"],)).fetchone()
            photo=(current["profile_photo"] if current else "") or ""
            if "profile_photo" in d:
                photo=str(d.get("profile_photo","") or "").strip()
                if photo and (not photo.startswith(("data:image/png;base64,","data:image/webp;base64,","data:image/jpeg;base64,")) or len(photo)>MAX_PROFILE_PHOTO_DATA_URL_CHARS):
                    c.close();return self.out({"error":"INVALID_PROFILE_PHOTO"},400)
            featured=d.get("featured_player_id",None)
            if featured in (None,""):
                featured=None
            else:
                try:featured=int(featured)
                except Exception:
                    c.close();return self.out({"error":"INVALID_FEATURED_PLAYER"},400)
                if not c.execute("SELECT 1 FROM players WHERE id=? AND user_id=?",(featured,u["id"])).fetchone():
                    c.close();return self.out({"error":"INVALID_FEATURED_PLAYER"},400)
            c.execute("""UPDATE users SET display_name=?,profile_bio=?,profile_motto=?,profile_photo=?,
                         profile_accent=?,profile_theme=?,profile_banner=?,profile_card_frame=?,
                         profile_featured_accolade=?,featured_player_id=? WHERE id=?""",
                      (display_name,profile_bio,profile_motto,photo,profile_accent,profile_theme,
                       profile_banner,profile_card_frame,profile_featured_accolade,featured,u["id"]))
            c.commit()
            updated=c.execute("""SELECT id,username,role,created_at,display_name,profile_bio,profile_motto,profile_photo,
                                        profile_accent,profile_theme,profile_banner,profile_card_frame,
                                        profile_featured_accolade,featured_player_id FROM users WHERE id=?""",(u["id"],)).fetchone()
            c.close();return self.out({"ok":True,"profile":dict(updated)})








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
            sid,_=new_session(c,uid,self,remember=False)
            c.commit();c.close()
            return self.out({"ok":True,"next":"/#player"},200,{"Set-Cookie":session_cookie(sid,None)})
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
            d=self.body()
            first_name=" ".join(str(d.get("first_name","") or "").split()).strip()
            last_name=" ".join(str(d.get("last_name","") or "").split()).strip()
            hometown_city=" ".join(str(d.get("hometown_city","") or "").split()).strip()
            hometown_region=" ".join(str(d.get("hometown_region","") or "").split()).strip()
            # Compatibility fallback for an older client during rolling deploys.
            legacy_name=" ".join(str(d.get("name","") or "").split()).strip()
            if (not first_name or not last_name) and legacy_name:
                parts=legacy_name.split()
                if len(parts)>=2:
                    first_name=first_name or parts[0]
                    last_name=last_name or " ".join(parts[1:])
            legacy_hometown=" ".join(str(d.get("hometown","") or "").split()).strip()
            if (not hometown_city or not hometown_region) and "," in legacy_hometown:
                a,b=legacy_hometown.split(",",1)
                hometown_city=hometown_city or a.strip()
                hometown_region=hometown_region or b.strip()
            name=(first_name+" "+last_name).strip()
            hometown=(hometown_city+", "+hometown_region).strip(", ")
            pos=str(d.get("position","")).upper();group=str(d.get("position_group") or position_group_for_pos(pos)).upper();bats=d.get("bats");throws=d.get("throws");attrs=d.get("attributes",{})
            c=conn()
            try:
                c.execute("BEGIN IMMEDIATE")
                if u["role"]=="PLAYER":
                    sec=c.execute("SELECT email_verified FROM user_security WHERE user_id=?",(u["id"],)).fetchone()
                    if not sec or not sec["email_verified"]:
                        c.rollback();return self.out({"error":"EMAIL_NOT_VERIFIED"},403)
                if not rate_limit(c,f"player-create:{u['id']}",6,3600):
                    c.rollback();return self.out({"error":"RATE_LIMITED"},429)
                ent=supporter_entitlement(c,u["id"])
                active_count=int(ent["active_players"] or 0)
                if active_count>=int(ent["creation_player_limit"]):
                    c.rollback();return self.out({"error":"ACTIVE_PLAYER_LIMIT_REACHED",
                                                  "limit":ent["creation_player_limit"],
                                                  "entitled_limit":ent["entitled_player_limit"],
                                                  "supporter":ent["supporter"],
                                                  "upgrade_available":not ent["supporter"]},400)
                ptype="P" if group=="PITCHER" else "H";valid=PITCHER_ATTRS if ptype=="P" else HITTER_ATTRS
                valid_pos={"INF":{"C","1B","2B","3B","SS"},"OF":{"LF","CF","RF"},"PITCHER":{"SP","RP"}}
                def _valid_identity_name(part):
                    return bool(part) and all(ch.isalpha() or ch in "'’.- " for ch in part)
                if (not first_name or not last_name or len(first_name)>24 or len(last_name)>24 or len(name)>49
                    or not _valid_identity_name(first_name) or not _valid_identity_name(last_name)):
                    c.rollback();return self.out({"error":"FIRST_AND_LAST_NAME_REQUIRED"},400)
                if not hometown_city or not hometown_region or len(hometown_city)>50 or len(hometown_region)>60 or len(hometown)>80:
                    c.rollback();return self.out({"error":"CITY_AND_STATE_COUNTRY_REQUIRED"},400)
                if group not in POSITION_GROUPS or pos not in valid_pos.get(group,set()) or bats not in ["R","L","S"] or throws not in ["R","L"] or set(attrs)!=set(valid) or sum(attrs.values())!=50 or any(type(v) is not int or v<0 or v>50 for v in attrs.values()) or (pos!="C" and float(attrs.get("CALL",0) or 0)!=0):
                    c.rollback();return self.out({"error":"INVALID_50_XP_BUILD"},400)
                season={k:0 for k in (["G","GS","OUTS","H","ER","BB","SO","W","L","SV"] if ptype=="P" else ["G","PA","AB","H","1B","2B","3B","HR","BB","SO","R","RBI","SB","CS"])}
                face_id=int(d.get("face_id",1));skin_color_id=int(d.get("skin_color_id",1));hair_id=int(d.get("hair_id",1))
                facial_hair_id=int(d.get("facial_hair_id",1));eye_color_id=int(d.get("eye_color_id",6))
                nose_id=int(d.get("nose_id",1));eye_shape_id=int(d.get("eye_shape_id",1))
                mouth_id=int(d.get("mouth_id",1));ear_size_id=int(d.get("ear_size_id",2))
                hair_color_id=int(d.get("hair_color_id",3));eye_black_id=int(d.get("eye_black_id",1))
                eyewear_id=int(d.get("eyewear_id",1));chain_id=int(d.get("chain_id",1));sleeve_id=int(d.get("sleeve_id",1));body_build_id=int(d.get("body_build_id",1))
                jersey_number=int(d.get("jersey_number",24))
                if (face_id not in range(1,21) or skin_color_id not in range(1,9) or hair_id not in range(1,29) or facial_hair_id not in range(1,15)
                    or eye_color_id not in range(1,7) or nose_id not in range(1,5) or eye_shape_id not in range(1,5)
                    or mouth_id not in range(1,5) or ear_size_id not in range(1,4) or hair_color_id not in range(1,10)
                    or eye_black_id not in range(1,6) or eyewear_id not in range(1,6)
                    or chain_id not in range(1,8) or sleeve_id not in range(1,5) or body_build_id not in range(1,4)
                    or jersey_number not in range(0,100)):
                    c.rollback();return self.out({"error":"INVALID_APPEARANCE"},400)
                cur=c.execute("""INSERT INTO players(user_id,name,first_name,last_name,hometown,hometown_city,hometown_region,type,primary_pos,position_group,bats,throws,xp_wallet,attributes_json,season_json,status,active,face_id,skin_color_id,hair_id,facial_hair_id,eye_color_id,nose_id,eye_shape_id,mouth_id,ear_size_id,hair_color_id,eye_black_id,eyewear_id,chain_id,sleeve_id,body_build_id,jersey_number)
                                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,?, ?,'FREE_AGENT',1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(u["id"],name,first_name,last_name,hometown,hometown_city,hometown_region,ptype,pos,group,bats,throws,json.dumps(attrs),json.dumps(season),face_id,skin_color_id,hair_id,facial_hair_id,eye_color_id,nose_id,eye_shape_id,mouth_id,ear_size_id,hair_color_id,eye_black_id,eyewear_id,chain_id,sleeve_id,body_build_id,jersey_number))
                c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",("PLAYER_CREATED",u["id"],json.dumps({"player_id":cur.lastrowid})))
                c.commit()
                return self.out({"player":player_obj(c,cur.lastrowid)})
            except sqlite3.OperationalError as e:
                c.rollback()
                if "locked" in str(e).lower():
                    return self.out({"error":"DATABASE_BUSY"},503)
                raise
            except Exception:
                c.rollback()
                raise
            finally:
                c.close()
        if p=="/api/player/change-position":
            u=self.auth(["PLAYER","COMMISSIONER"])
            if not u:return
            d=self.body();c=conn();c.execute("BEGIN IMMEDIATE")
            pl=owned_active_player(c,u["id"],request_player_id(self,d))
            if not pl:c.close();return self.out({"error":"PLAYER_NOT_FOUND"},404)
            state={r["k"]:r["v"] for r in c.execute("SELECT k,v FROM league_state WHERE k IN ('phase','league_day')")}
            phase=str(state.get("phase","REGULAR")).upper();day=int(state.get("league_day","0") or 0)
            new_group=str(d.get("position_group") or "").upper();new_pos=str(d.get("position") or "").upper()
            old_group=str(pl["position_group"] or position_group_for_pos(pl["primary_pos"])).upper()
            valid_pos={"INF":{"C","1B","2B","3B","SS"},"OF":{"LF","CF","RF"},"PITCHER":{"SP","RP"}}
            if new_group not in POSITION_GROUPS or new_pos not in valid_pos.get(new_group,set()):
                c.rollback();c.close();return self.out({"error":"INVALID_POSITION_CHANGE"},400)
            if (old_group=="PITCHER") != (new_group=="PITCHER"):
                c.rollback();c.close();return self.out({"error":"CANNOT_SWITCH_HITTER_PITCHER_BUILD"},400)
            changing_group=new_group!=old_group
            if changing_group:
                if pl["status"]!="FREE_AGENT":
                    c.rollback();c.close();return self.out({"error":"ROSTER_GROUP_CHANGE_REQUIRES_FREE_AGENT"},400)
                if phase!="OFFSEASON" and day>0:
                    c.rollback();c.close();return self.out({"error":"POSITION_CHANGE_WINDOW_CLOSED","phase":phase,"league_day":day},400)
            old_pos=str(pl["primary_pos"] or "").upper()
            c.execute("UPDATE players SET position_group=?,primary_pos=? WHERE id=?",(new_group,new_pos,pl["id"]))
            # Free-agent market offers are tied to a proposed roster role. Cancel them only
            # when the player changes roster family; a signed player's preference change
            # does not alter the club's actual roster-slot assignment.
            if changing_group:
                c.execute("UPDATE offers SET status='CANCELLED_POSITION_CHANGE' WHERE player_id=? AND offer_type!='RENEWAL' AND status IN ('OPEN','HELD')",(pl["id"],))
            c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",("POSITION_CHANGED",u["id"],json.dumps({"player_id":pl["id"],"from_group":old_group,"to_group":new_group,"from_position":old_pos,"position":new_pos,"team_role_unchanged":pl["status"]=="SIGNED"})))
            c.commit();out=player_obj(c,pl["id"]);c.close();return self.out({"ok":True,"player":out})








        if p=="/api/player/veteran-extension":
            u=self.auth(["PLAYER","COMMISSIONER"])
            if not u:return
            d=self.body();c=conn()
            try:
                c.execute("BEGIN IMMEDIATE")
                phase_row=c.execute("SELECT v FROM league_state WHERE k='phase'").fetchone()
                phase=str(phase_row["v"] if phase_row else "REGULAR").upper()
                if phase!="OFFSEASON":
                    c.rollback();return self.out({"error":"VETERAN_EXTENSION_WINDOW_CLOSED","phase":phase},400)
                pl=owned_active_player(c,u["id"],request_player_id(self,d))
                if not pl:
                    c.rollback();return self.out({"error":"PLAYER_NOT_FOUND"},404)
                completed=extension_completed_seasons(c,pl["id"])
                if completed<12:
                    c.rollback();return self.out({"error":"VETERAN_EXTENSION_NOT_ELIGIBLE","seasons_completed":completed,"required":12},400)
                target=completed+1
                through=int(pl["career_extension_through"] or 12)
                cost=veteran_extension_cost(completed)
                if through>=target:
                    c.rollback();return self.out({"ok":True,"already_paid":True,"player_id":pl["id"],"covered_through":through,"next_career_season":target,"cost":cost,"xp_wallet":float(pl["xp_wallet"] or 0)})
                wallet=float(pl["xp_wallet"] or 0)
                if wallet+1e-9<cost:
                    c.rollback();return self.out({"error":"INSUFFICIENT_XP","cost":cost,"xp_wallet":round(wallet,3),"next_career_season":target},400)
                new_wallet=round(wallet-cost,3)
                c.execute("UPDATE players SET xp_wallet=?,career_extension_through=? WHERE id=?",(new_wallet,target,pl["id"]))
                detail={"completed_seasons":completed,"next_career_season":target,"cost":cost}
                c.execute("INSERT INTO xp_ledger(player_id,event_type,xp,detail_json) VALUES(?,?,?,?)",(pl["id"],"VETERAN_EXTENSION",-cost,json.dumps(detail)))
                c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",("VETERAN_EXTENSION",u["id"],json.dumps({"player_id":pl["id"],**detail})))
                notify_user(c,u["id"],"CAREER","Veteran career extended",f"{pl['name']} is cleared to return for career Season {target} after spending {cost:g} XP.",str(pl["id"]))
                c.commit()
                return self.out({"ok":True,"player_id":pl["id"],"player_name":pl["name"],"cost":cost,"xp_wallet":new_wallet,"covered_through":target,"next_career_season":target})
            finally:
                c.close()








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
                pl=owned_active_player(c,u["id"],request_player_id(self,d))
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
                c.execute("UPDATE offers SET status='CANCELLED_RETIRED' WHERE player_id=? AND status IN ('OPEN','HELD','ACCEPTED')",(pid,))
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
            d=self.body();attr=d.get("attribute");c=conn();c.execute("BEGIN IMMEDIATE");r=owned_active_player(c,u["id"],request_player_id(self,d))
            if not r:c.close();return self.out({"error":"PLAYER_NOT_FOUND"},404)
            # Attribute development is intentionally click-heavy. Keep abuse protection
            # without rate-limiting a normal player who spends a large XP bank quickly.
            if not rate_limit(c,f"xp-spend:{u['id']}",300,60):c.commit();c.close();return self.out({"error":"RATE_LIMITED"},429)
            pl=player_obj(c,r["id"])
            if attr not in pl["attributes"]:c.rollback();c.close();return self.out({"error":"INVALID_ATTRIBUTE"},400)
            if attr=="CALL" and pl.get("primary_pos")!="C":c.rollback();c.close();return self.out({"error":"CALL_RATING_CATCHER_ONLY"},400)
            # EBL attributes are intentionally uncapped. Late-career specialists and
            # club development can push ratings beyond 100; escalating XP cost is the limiter.
            seasons_completed=player_seasons_completed(c,pl["id"])
            surcharge=career_xp_surcharge(seasons_completed)
            cc=development_cost(pl["attributes"][attr],seasons_completed)
            if pl["xp_wallet"]<cc:c.rollback();c.close();return self.out({"error":"INSUFFICIENT_XP","cost":cc,"seasons_completed":seasons_completed,"career_surcharge":surcharge},400)
            old=pl["attributes"][attr];pl["attributes"][attr]+=1;pl["xp_wallet"]=round(pl["xp_wallet"]-cc,3);save_player(c,pl,persist_attributes=True)
            c.execute("INSERT INTO xp_ledger(player_id,event_type,xp,detail_json) VALUES(?,?,?,?)",(pl["id"],"ATTRIBUTE_UPGRADE",-cc,json.dumps({"attribute":attr,"from":old,"to":old+1,"seasons_completed":seasons_completed,"career_surcharge":surcharge,"cost":cc})));c.commit();c.close();return self.out({"ok":True})
        if p=="/api/player/request-cpu-market":
            u=self.auth(["PLAYER","COMMISSIONER"])
            if not u:return
            d=self.body();c=conn();pr=owned_active_player(c,u["id"],request_player_id(self,d))
            if not pr or pr["status"]!="FREE_AGENT":c.close();return self.out({"error":"PLAYER_NOT_FREE_AGENT"},400)
            # CPU franchises fill the player's market up to three active offers.
            # A former-team return offer does not block the player from shopping around.
            existing_rows=c.execute("SELECT franchise_id,status FROM offers WHERE player_id=? AND status IN ('OPEN','HELD')",(pr["id"],)).fetchall()
            existing_teams={x["franchise_id"] for x in existing_rows}
            open_count=sum(1 for x in existing_rows if x["status"]=="OPEN")
            held_count=sum(1 for x in existing_rows if x["status"]=="HELD")
            # HOLD means "keep this offer while I keep shopping." Only OPEN offers
            # occupy the three live-market slots; held offers stay preserved.
            slots=max(0,3-open_count)
            if slots<=0:c.close();return self.out({"error":"OPEN_OFFERS_FULL","open_offers":open_count,"held_offers":held_count},400)
            attrs=json.loads(pr["attributes_json"]);overall=sum(attrs.values())/max(1,len(attrs))
            season=_season_number(c)
            active_ids=active_franchise_ids(c,season)
            q=",".join("?" for _ in active_ids)
            # CPU market is a league-population tool as well as a contract market.
            # Human-controlled clubs recruit for themselves; CPU clubs deliberately
            # concentrate human players into the fullest compatible club first.
            teams=[dict(x) for x in c.execute(f"SELECT * FROM franchises WHERE id IN ({q}) AND owner_user_id IS NULL ORDER BY id",active_ids)]
            last_end=c.execute("SELECT MAX(ended_at) ended_at FROM contract_history WHERE player_id=?",(pr["id"],)).fetchone()["ended_at"]
            if last_end:
                rejected={x["franchise_id"] for x in c.execute("SELECT franchise_id FROM offers WHERE player_id=? AND offer_type!='RENEWAL' AND status='REJECTED' AND created_at>?",(pr["id"],last_end)).fetchall()}
            else:
                rejected={x["franchise_id"] for x in c.execute("SELECT franchise_id FROM offers WHERE player_id=? AND offer_type!='RENEWAL' AND status='REJECTED'",(pr["id"],)).fetchall()}
            attempted_teams=existing_teams|rejected
            candidates=[]
            for f in teams:
                if f["id"] in attempted_teams:
                    continue
                cap=roster_capacity_state(c,f["id"])
                if cap["total_slots"]!=ACTIVE_ROSTER_SIZE or cap["hitter_slots"]!=9 or cap["pitcher_slots"]!=7:
                    enforce_active_rosters(c,season)
                    cap=roster_capacity_state(c,f["id"])
                if pr["type"]=="H" and cap["open_or_cpu_hitters"]<=0:
                    continue
                if pr["type"]=="P" and cap["open_or_cpu_pitchers"]<=0:
                    continue
                role_slot=roster_offer_slot(c,f["id"],dict(pr))
                if not role_slot:
                    continue
                humans=human_roster_count(c,f["id"])
                preferred_fit=1 if str(role_slot["position_group"]).upper()==str(pr["primary_pos"] or "").upper() else 0
                candidates.append({"team":f,"human_count":humans,"preferred_fit":preferred_fit,"role":str(role_slot["position_group"]).upper()})
            # Highest human population wins first. Stable franchise order breaks an empty-league
            # tie, which creates the first human clubhouse instead of scattering rookies.
            candidates.sort(key=lambda x:(-x["human_count"],-x["preferred_fit"],x["team"]["id"]))
            made=[]
            # One CPU offer per market request. Players can Hold and request another, preserving
            # agency, but the default path keeps feeding the most-human compatible club.
            slots=min(1,max(0,3-open_count))
            for rank,candidate in enumerate(candidates):
                if len(made)>=slots:break
                f=candidate["team"];proposed_role=candidate["role"]
                floor=minimum_offer_salary(c,pr["id"],f["id"])
                service_seasons=player_seasons_completed(c,pr["id"])
                market_salary=round(0.30+(overall/100.0)*0.10+R.uniform(-0.015,0.015),2)
                pool=signing_pool_state(c,f["id"])
                if service_seasons==0:
                    # RC113: every CPU rookie gets the same three-year entry offer.
                    # At the baseline 480 XP club budget, minimum payroll reserves
                    # 388.8 XP (16 * .30 * 81), leaving 91.2 XP. Dividing that
                    # evenly across 16 roster jobs produces a 5.7 XP bonus for every
                    # rookie, so signing order no longer determines who gets paid.
                    salary=SALARY_MIN
                    years=CPU_ROOKIE_CONTRACT_YEARS
                    bonus=CPU_ROOKIE_SIGNING_BONUS
                else:
                    salary=round(max(floor,market_salary),2)
                    years=R.choice([1,2,2,3])
                    bonus=round(min(BONUS_CAP,6+overall*.45+R.uniform(0,7)-rank),1)
                premium=max(0.0,salary-SALARY_MIN)*REGULAR_SEASON_GAMES
                max_bonus=max(0.0,pool["available"]-premium)
                # A CPU rookie offer is all-or-nothing at the league-standard bonus.
                # Never shrink a later rookie's bonus merely because earlier players
                # signed first. Veteran CPU offers may still flex to the club's room.
                if service_seasons==0:
                    if bonus>max_bonus+1e-9:
                        continue
                else:
                    bonus=round(min(bonus,max_bonus),1)
                offer_cost=round(bonus+premium,3)
                if offer_cost>pool["available"]+1e-9:
                    continue
                cur=c.execute("INSERT INTO offers(franchise_id,player_id,bonus,salary,years,status,proposed_role) VALUES(?,?,?,?,?,'OPEN',?)",(f["id"],pr["id"],bonus,salary,years,proposed_role))
                made.append({"offer_id":cur.lastrowid,"team":f["name"],"franchise_id":f["id"],"bonus":bonus,"salary":salary,"years":years,"proposed_role":proposed_role,"team_humans":candidate["human_count"]})
            c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",("CPU_MARKET_OFFERS",u["id"],json.dumps({"player_id":pr["id"],"offers":made})))
            for off in made:
                notify_user(c,u["id"],"CONTRACT",f"Contract offer from {off['team']}",f"Proposed role: {off.get('proposed_role') or pr['primary_pos']} • {off['bonus']:g} XP bonus • {off['salary']:g} XP/game • {off['years']} year(s)",str(off["offer_id"]))
            c.commit();c.close();return self.out({"ok":True,"offers":made})
        if p=="/api/coach/apply":
            u=self.auth()
            if not u:return
            if not COACH_APPLICATIONS_OPEN and u["role"]!="COMMISSIONER":
                return self.out({"error":"COACH_APPLICATIONS_CLOSED_BETA","detail":"Human coaching is paused during the player-only accelerated beta."},403)
            d=self.body();preferred=str(d.get("preferred_franchise_id") or "").strip() or None
            experience=str(d.get("experience") or "").strip()[:2000]
            reason=str(d.get("reason") or "").strip()[:3000]
            philosophy=str(d.get("philosophy") or "").strip()[:3000]
            rules_ack=1 if d.get("rules_ack") else 0
            if not reason or not philosophy or not rules_ack:return self.out({"error":"COACH_APPLICATION_INCOMPLETE"},400)
            c=conn()
            try:
                if u["role"] in ("COACH","COMMISSIONER"):return self.out({"error":"ALREADY_COACH_APPROVED"},409)
                if preferred and not c.execute("SELECT 1 FROM franchises WHERE id=?",(preferred,)).fetchone():return self.out({"error":"INVALID_FRANCHISE"},400)
                pending=c.execute("SELECT id FROM coach_applications WHERE user_id=? AND status='PENDING' ORDER BY id DESC LIMIT 1",(u["id"],)).fetchone()
                if pending:return self.out({"error":"APPLICATION_ALREADY_PENDING","application_id":pending["id"]},409)
                cur=c.execute("INSERT INTO coach_applications(user_id,preferred_franchise_id,experience,reason,philosophy,rules_ack,status) VALUES(?,?,?,?,?,?,'PENDING')",(u["id"],preferred,experience,reason,philosophy,rules_ack))
                c.commit();return self.out({"ok":True,"application_id":cur.lastrowid,"status":"PENDING"})
            finally:
                c.close()








        if p in ("/api/commish/coach-application/approve","/api/commish/coach-application/deny"):
            u=self.auth(["COMMISSIONER"])
            if not u:return
            d=self.body();aid=int(d.get("application_id",0) or 0);note=str(d.get("review_note") or "").strip()[:2000]
            status="APPROVED" if p.endswith("/approve") else "DENIED"
            c=conn()
            try:
                app=c.execute("SELECT * FROM coach_applications WHERE id=?",(aid,)).fetchone()
                if not app:return self.out({"error":"APPLICATION_NOT_FOUND"},404)
                if app["status"]!="PENDING":return self.out({"error":"APPLICATION_ALREADY_REVIEWED","status":app["status"]},409)
                c.execute("UPDATE coach_applications SET status=?,review_note=?,reviewed_at=CURRENT_TIMESTAMP,reviewed_by=? WHERE id=?",(status,note,u["id"],aid))
                if status=="APPROVED":
                    target=c.execute("SELECT role,username FROM users WHERE id=?",(app["user_id"],)).fetchone()
                    if not target:return self.out({"error":"APPLICANT_NOT_FOUND"},404)
                    if target["role"]=="PLAYER":c.execute("UPDATE users SET role='COACH' WHERE id=?",(app["user_id"],))
                    notify_user(c,app["user_id"],"COACH","Coach application approved","You are approved to coach in the EBL. A franchise can now be assigned to you.",str(aid))
                else:
                    notify_user(c,app["user_id"],"COACH","Coach application reviewed",note or "Your coach application was not approved at this time.",str(aid))
                day=int(league_cfg(c,"league_day","0") or 0)
                c.execute("INSERT INTO commissioner_audit(league_day,action,detail) VALUES(?,?,?)",(day,"COACH_APPLICATION_"+status,f"application {aid} user {app['user_id']}"))
                c.commit();return self.out({"ok":True,"application_id":aid,"status":status})
            finally:
                c.close()








        if p=="/api/commish/assign-coach":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            d=self.body();coach_id=int(d.get("coach_user_id",0) or 0);fid=str(d.get("franchise_id") or "").strip()
            c=conn()
            try:
                if not fid:
                    return self.out({"error":"FRANCHISE_REQUIRED"},400)
                fr=c.execute("SELECT id,name,owner_user_id FROM franchises WHERE id=?",(fid,)).fetchone()
                if not fr:
                    return self.out({"error":"FRANCHISE_NOT_FOUND"},404)
                if coach_id:
                    coach=c.execute("SELECT id,username,role FROM users WHERE id=?",(coach_id,)).fetchone()
                    if not coach or coach["role"]!="COACH":
                        return self.out({"error":"INVALID_COACH"},400)
                    # One team per coach. Moving a coach automatically releases the old club.
                    c.execute("UPDATE franchises SET owner_user_id=NULL WHERE owner_user_id=? AND id<>?",(coach_id,fid))
                    # One coach per team. Reassignment replaces the previous coach.
                    c.execute("UPDATE franchises SET owner_user_id=? WHERE id=?",(coach_id,fid))
                    action="COACH_ASSIGNED"
                    detail=f"{coach['username']} -> {fr['name']}"
                    result={"ok":True,"coach_user_id":coach_id,"coach_username":coach["username"],"franchise_id":fid,"franchise_name":fr["name"]}
                else:
                    old=None
                    if fr["owner_user_id"]:
                        old=c.execute("SELECT username FROM users WHERE id=?",(fr["owner_user_id"],)).fetchone()
                    c.execute("UPDATE franchises SET owner_user_id=NULL WHERE id=?",(fid,))
                    action="COACH_UNASSIGNED"
                    detail=f"{(old['username'] if old else 'coach')} <- {fr['name']}"
                    result={"ok":True,"coach_user_id":None,"franchise_id":fid,"franchise_name":fr["name"]}
                day=int(league_cfg(c,"league_day","0") or 0)
                c.execute("INSERT INTO commissioner_audit(league_day,action,detail) VALUES(?,?,?)",(day,action,detail))
                c.commit()
                return self.out(result)
            finally:
                c.close()








        if p=="/api/coach/renewal-offer":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            d=self.body()
            try:
                pid=int(d.get("player_id",0));years=int(d.get("years",0))
            except (TypeError,ValueError):
                return self.out({"error":"INVALID_RENEWAL"},400)
            mode=str(d.get("salary_mode") or "").upper().strip()
            message=" ".join(str(d.get("message") or "").split()).strip()
            if years not in (1,2,3) or mode not in ("CURRENT","VETERAN_MIN"):
                return self.out({"error":"INVALID_RENEWAL"},400)
            if len(message)<10 or len(message)>600:
                return self.out({"error":"RENEWAL_MESSAGE_REQUIRED","minimum_chars":10,"maximum_chars":600},400)
            c=conn()
            try:
                f=c.execute("SELECT * FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
                if not f:return self.out({"error":"NO_FRANCHISE"},404)
                state={r["k"]:r["v"] for r in c.execute("SELECT k,v FROM league_state WHERE k IN ('season','league_day','phase')")}
                season=int(state.get("season",1));day=int(state.get("league_day",0));phase=str(state.get("phase","REGULAR")).upper()
                if phase!="REGULAR" or day<RENEWAL_OPEN_DAY or day>REGULAR_SEASON_CALENDAR_DAYS:
                    return self.out({"error":"RENEWAL_WINDOW_CLOSED","opens_day":RENEWAL_OPEN_DAY,"league_day":day,"phase":phase},400)
                pl=c.execute("SELECT id,user_id,name,franchise_id,active FROM players WHERE id=?",(pid,)).fetchone()
                con=c.execute("SELECT * FROM contracts WHERE player_id=?",(pid,)).fetchone()
                if not pl or not con or not pl["active"] or pl["franchise_id"]!=f["id"] or con["franchise_id"]!=f["id"]:
                    return self.out({"error":"PLAYER_NOT_ON_TEAM"},400)
                if pl["user_id"] is None:
                    return self.out({"error":"HUMAN_PLAYER_REQUIRED"},400)
                if pl["user_id"]==u["id"]:
                    return self.out({"error":"CANNOT_SIGN_OWN_PLAYER"},403)
                if int(con["years_remaining"] or 0)!=1:
                    return self.out({"error":"CONTRACT_NOT_EXPIRING"},400)
                accepted=c.execute("SELECT id FROM offers WHERE franchise_id=? AND player_id=? AND offer_type='RENEWAL' AND effective_season=? AND status='ACCEPTED' LIMIT 1",(f["id"],pid,season+1)).fetchone()
                if accepted:
                    return self.out({"error":"RENEWAL_ALREADY_ACCEPTED"},409)
                current_rate=round(float(con["salary"] or SALARY_MIN),2)
                veteran_min=renewal_veteran_minimum(c,pid)
                salary=current_rate if mode=="CURRENT" else veteran_min
                projected=next_season_payroll_projection(c,f["id"],replace_player_id=pid,proposed_salary=salary)
                base_budget=round(annual_team_budget(dict(f)),3)
                projected_treasury=projected_next_season_treasury(c,f["id"])
                if projected>projected_treasury+1e-9:
                    return self.out({"error":"NEXT_SEASON_PAYROLL_EXCEEDED","projected_payroll":projected,"base_budget":base_budget,"projected_treasury":projected_treasury},400)
                c.execute("UPDATE offers SET status='SUPERSEDED' WHERE franchise_id=? AND player_id=? AND offer_type='RENEWAL' AND effective_season=? AND status IN ('OPEN','HELD')",(f["id"],pid,season+1))
                cur=c.execute(
                    """INSERT INTO offers(franchise_id,player_id,bonus,salary,years,status,offer_type,message,effective_season,salary_basis)
                       VALUES(?,?,?,?,?,'OPEN','RENEWAL',?,?,?)""",
                    (f["id"],pid,0.0,salary,years,message,season+1,mode)
                )
                notify_user(c,pl["user_id"],"CONTRACT",f"Renewal offer from {f['name']}",f"{salary:.2f} XP/game • {years} season(s) • {message}",str(cur.lastrowid))
                c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                          ("RENEWAL_OFFERED",u["id"],json.dumps({"player_id":pid,"franchise_id":f["id"],"salary":salary,"years":years,"salary_mode":mode,"effective_season":season+1,"message":message})))
                c.commit()
                return self.out({"ok":True,"offer_id":cur.lastrowid,"salary":salary,"years":years,"salary_mode":mode,"effective_season":season+1,"projected_payroll":projected,"base_budget":base_budget,"projected_treasury":projected_treasury})
            finally:
                c.close()








        if p=="/api/coach/offer":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            d=self.body();pid=int(d.get("player_id",0));bonus=float(d.get("bonus",0));salary=float(d.get("salary",0));years=int(d.get("years",0));requested_role=str(d.get("proposed_role") or "").upper()
            salary=round(salary,2)
            if bonus<0 or bonus>BONUS_CAP or years not in [1,2,3]:return self.out({"error":"INVALID_OFFER"},400)
            c=conn();f=c.execute("SELECT * FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            previous_salary=previous_team_salary(c,pid,f["id"])
            minimum_salary=minimum_offer_salary(c,pid,f["id"])
            # RC91: rookie/veteran status is service-time based, not tied to whether
            # this coach has previously employed the player or whether a contract-history
            # row happens to exist. A free agent with completed EBL seasons is a veteran.
            service_seasons=player_seasons_completed(c,pid)
            is_rookie_contract=service_seasons==0
            if salary<minimum_salary:
                c.close();return self.out({"error":"SALARY_FLOOR_REQUIRED","minimum_salary":minimum_salary,"previous_team_salary":previous_salary},400)
            # RC78: rookie contracts are fixed at league minimum. This prevents a
            # coach from front-loading the economy before a player has EBL service time.
            # Veteran contracts keep the normal service-time floor with no hard ceiling.
            if is_rookie_contract and abs(salary-SALARY_MIN)>1e-9:
                c.close();return self.out({"error":"ROOKIE_SALARY_FIXED","required_salary":SALARY_MIN},400)
            pl=c.execute("SELECT * FROM players WHERE id=?",(pid,)).fetchone()
            if not pl or pl["status"]!="FREE_AGENT":c.close();return self.out({"error":"PLAYER_NOT_FREE_AGENT"},400)
            if pl["user_id"]==u["id"]:c.close();return self.out({"error":"CANNOT_SIGN_OWN_PLAYER"},403)








            # RC58 — don't create or reserve XP for an offer the roster cannot accept.
            cap=roster_capacity_state(c,f["id"])
            if cap["total_slots"]!=ACTIVE_ROSTER_SIZE or cap["hitter_slots"]!=9 or cap["pitcher_slots"]!=7:
                enforce_active_rosters(c)
                cap=roster_capacity_state(c,f["id"])
            if pl["type"]=="H" and cap["open_or_cpu_hitters"]<=0:
                c.close();return self.out({"error":"HITTER_ROSTER_FULL","detail":"All nine position-player jobs are occupied by human players."},400)
            if pl["type"]=="P" and cap["open_or_cpu_pitchers"]<=0:
                c.close();return self.out({"error":"PITCHER_ROSTER_FULL"},400)
            roles=available_roster_roles(c,f["id"],dict(pl))
            if not roles:
                c.close();return self.out({"error":"ROSTER_POSITION_FULL"},400)
            if requested_role and requested_role not in roles:
                c.close();return self.out({"error":"PROPOSED_ROLE_UNAVAILABLE","available_roles":roles},400)
            proposed_role=requested_role or roles[0]








            pool=signing_pool_state(c,f["id"])
            offer_cost=round(bonus + max(0.0,salary-SALARY_MIN)*REGULAR_SEASON_GAMES,3)
            if offer_cost>pool["available"]+1e-9:
                c.close();return self.out({"error":"SIGNING_POOL_EXCEEDED","signing_pool":pool,"offer_cost":offer_cost},400)
            cur=c.execute("INSERT INTO offers(franchise_id,player_id,bonus,salary,years,status,proposed_role) VALUES(?,?,?,?,?,'OPEN',?)",(f["id"],pid,bonus,salary,years,proposed_role))
            owner=c.execute("SELECT user_id,name FROM players WHERE id=?",(pid,)).fetchone()
            if owner and owner["user_id"]:
                notify_user(c,owner["user_id"],"CONTRACT",f"Contract offer from {f['name']}",f"Proposed role: {proposed_role} • {bonus:g} XP bonus • {salary:g} XP/game • {years} year(s)",str(cur.lastrowid))
            c.commit();oid=cur.lastrowid;c.close();return self.out({"ok":True,"offer_id":oid,"proposed_role":proposed_role})
        if p=="/api/player/respond-offer":
            u=self.auth()
            if not u:return
            d=self.body();oid=int(d.get("offer_id",0));action=d.get("action")
            if action not in ["ACCEPT","HOLD","REJECT"]:
                return self.out({"error":"INVALID_ACTION"},400)








            c=conn()
            try:
                # Serialize offer responses. This keeps two players on the same account (or
                # two different users) from partially mutating roster/contract state at once.
                c.execute("BEGIN IMMEDIATE")
                pl=owned_active_player(c,u["id"],request_player_id(self,d))
                if not pl:
                    c.rollback();return self.out({"error":"PLAYER_NOT_FOUND"},404)








                off=c.execute("SELECT * FROM offers WHERE id=? AND player_id=?",(oid,pl["id"])).fetchone()
                if not off or off["status"] not in ["OPEN","HELD"]:
                    c.rollback();return self.out({"error":"OFFER_NOT_AVAILABLE"},400)








                if str(off["offer_type"] or "FREE_AGENT").upper()=="RENEWAL":
                    con=c.execute("SELECT * FROM contracts WHERE player_id=?",(pl["id"],)).fetchone()
                    state={r["k"]:r["v"] for r in c.execute("SELECT k,v FROM league_state WHERE k IN ('season','league_day','phase')")}
                    season=int(state.get("season",1));day=int(state.get("league_day",0));phase=str(state.get("phase","REGULAR")).upper()
                    if not con or con["franchise_id"]!=off["franchise_id"] or int(con["years_remaining"] or 0)!=1:
                        c.rollback();return self.out({"error":"RENEWAL_NO_LONGER_VALID"},400)
                    if phase!="REGULAR" or day<RENEWAL_OPEN_DAY or int(off["effective_season"] or 0)!=season+1:
                        c.rollback();return self.out({"error":"RENEWAL_WINDOW_CLOSED"},400)
                    owner=c.execute("SELECT owner_user_id,name FROM franchises WHERE id=?",(off["franchise_id"],)).fetchone()
                    if action=="HOLD":
                        c.execute("UPDATE offers SET status='HELD' WHERE id=?",(oid,))
                        c.commit();return self.out({"ok":True,"status":"HELD","player_id":pl["id"],"renewal":True})
                    if action=="REJECT":
                        c.execute("UPDATE offers SET status='REJECTED' WHERE id=?",(oid,))
                        if owner and owner["owner_user_id"]:
                            notify_user(c,owner["owner_user_id"],"COACH_CONTRACT","Renewal declined",f"{pl['name']} declined the renewal offer. You can revise the plan while the Day {RENEWAL_OPEN_DAY}–{REGULAR_SEASON_CALENDAR_DAYS} window remains open.",str(pl["id"]))
                        c.commit();return self.out({"ok":True,"status":"REJECTED","player_id":pl["id"],"renewal":True})
                    projected=next_season_payroll_projection(c,off["franchise_id"],replace_player_id=pl["id"],proposed_salary=float(off["salary"] or SALARY_MIN))
                    fr=c.execute("SELECT * FROM franchises WHERE id=?",(off["franchise_id"],)).fetchone()
                    base_budget=round(annual_team_budget(dict(fr)),3) if fr else TEAM_BUDGET
                    projected_treasury=projected_next_season_treasury(c,off["franchise_id"])
                    if projected>projected_treasury+1e-9:
                        c.rollback();return self.out({"error":"NEXT_SEASON_PAYROLL_EXCEEDED","projected_payroll":projected,"base_budget":base_budget,"projected_treasury":projected_treasury},400)
                    c.execute("UPDATE offers SET status='ACCEPTED' WHERE id=?",(oid,))
                    c.execute("UPDATE offers SET status='CANCELLED_PLAYER_RENEWED' WHERE player_id=? AND offer_type='RENEWAL' AND id<>? AND status IN ('OPEN','HELD')",(pl["id"],oid))
                    c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                              ("RENEWAL_ACCEPTED",u["id"],json.dumps({"player_id":pl["id"],"offer_id":oid,"franchise_id":off["franchise_id"],"salary":off["salary"],"years":off["years"],"effective_season":off["effective_season"]})))
                    if owner and owner["owner_user_id"]:
                        notify_user(c,owner["owner_user_id"],"COACH_CONTRACT","Renewal accepted",f"{pl['name']} accepted {float(off['salary']):.2f} XP/game for {int(off['years'])} season(s), beginning next season.",str(pl["id"]))
                    c.commit();return self.out({"ok":True,"status":"ACCEPTED","player_id":pl["id"],"renewal":True,"effective_season":off["effective_season"]})








                if action=="HOLD":
                    c.execute("UPDATE offers SET status='HELD' WHERE id=?",(oid,))
                    c.commit()
                    return self.out({"ok":True,"status":"HELD","player_id":pl["id"]})








                if action=="REJECT":
                    c.execute("UPDATE offers SET status='REJECTED' WHERE id=?",(oid,))
                    c.commit()
                    return self.out({"ok":True,"status":"REJECTED","player_id":pl["id"]})








                # ACCEPT: every lookup and write below is scoped to the selected player_id.
                # A user can therefore own multiple players and sign each independently.
                if c.execute("SELECT 1 FROM contracts WHERE player_id=?",(pl["id"],)).fetchone():
                    c.rollback();return self.out({"error":"PLAYER_ALREADY_SIGNED"},409)








                f=c.execute("SELECT * FROM franchises WHERE id=?",(off["franchise_id"],)).fetchone()
                if not f:
                    c.rollback();return self.out({"error":"FRANCHISE_NOT_FOUND"},404)








                # RC68: revalidate salary rules at acceptance because OPEN/HELD
                # offers can outlive the state used when the offer was created.
                minimum_salary=minimum_offer_salary(c,pl["id"],f["id"])
                if float(off["salary"] or 0)+1e-9 < minimum_salary:
                    c.rollback();return self.out({
                        "error":"SALARY_FLOOR_REQUIRED",
                        "minimum_salary":minimum_salary,
                        "offered_salary":round(float(off["salary"] or 0),2)
                    },400)
                service_seasons=player_seasons_completed(c,pl["id"])
                is_rookie_contract=service_seasons==0
                if is_rookie_contract and abs(float(off["salary"] or 0)-SALARY_MIN)>1e-9:
                    c.rollback();return self.out({"error":"ROOKIE_SALARY_FIXED","required_salary":SALARY_MIN},400)
                if float(off["bonus"] or 0)<0 or float(off["bonus"] or 0)>BONUS_CAP or int(off["years"] or 0) not in (1,2,3):
                    c.rollback();return self.out({"error":"INVALID_OFFER"},400)








                pool=signing_pool_state(c,f["id"],exclude_offer_id=oid)
                accept_cost=round(float(off["bonus"] or 0)+max(0.0,float(off["salary"] or 0)-SALARY_MIN)*REGULAR_SEASON_GAMES,3)
                if accept_cost>pool["available"]+1e-9:
                    c.rollback();return self.out({"error":"SIGNING_POOL_EXCEEDED","signing_pool":pool,"offer_cost":accept_cost},400)








                # RC57: nine hitter jobs + seven pitcher jobs. No hitter bench.
                cap=roster_capacity_state(c,off["franchise_id"])
                if cap["total_slots"]!=ACTIVE_ROSTER_SIZE or cap["hitter_slots"]!=9 or cap["pitcher_slots"]!=7:
                    enforce_active_rosters(c)
                    cap=roster_capacity_state(c,off["franchise_id"])
                if pl["type"]=="H" and cap["open_or_cpu_hitters"]<=0:
                    c.rollback();return self.out({"error":"HITTER_ROSTER_FULL","detail":"EBL clubs carry exactly nine position players and no position-player bench."},400)
                if pl["type"]=="P" and cap["open_or_cpu_pitchers"]<=0:
                    c.rollback();return self.out({"error":"PITCHER_ROSTER_FULL"},400)
                # The contract carries a proposed role. Honor it when possible; if another
                # signing took that job first, fall through to the next compatible CPU/open
                # role rather than breaking the signing flow.
                slot=roster_offer_slot(c,off["franchise_id"],dict(pl),off["proposed_role"] if "proposed_role" in off.keys() else None)
                if not slot:
                    c.rollback();return self.out({"error":"ROSTER_POSITION_FULL"},400)
                assigned_role=str(slot["position_group"] or "").upper()








                displaced_id=slot["player_id"]
                if displaced_id:
                    displaced=c.execute("SELECT user_id FROM players WHERE id=?",(displaced_id,)).fetchone()
                    if displaced and displaced["user_id"] is not None:
                        c.rollback();return self.out({"error":"HUMAN_ROSTER_SLOT_PROTECTED"},409)
                    c.execute("DELETE FROM contracts WHERE player_id=?",(displaced_id,))
                    c.execute("""UPDATE players
                                 SET franchise_id=NULL,status='RETIRED',active=0
                                 WHERE id=?""",(displaced_id,))








                c.execute("""UPDATE roster_slots
                             SET player_id=?,occupant_type='HUMAN'
                             WHERE franchise_id=? AND slot_no=?""",
                          (pl["id"],off["franchise_id"],slot["slot_no"]))








                lr=c.execute("SELECT batting_order_json,rotation_json FROM lineups WHERE franchise_id=?",
                             (off["franchise_id"],)).fetchone()
                if lr and displaced_id:
                    if pl["type"]=="H":
                        order=json.loads(lr["batting_order_json"])
                        if displaced_id in order:
                            order=[pl["id"] if pid==displaced_id else pid for pid in order]
                        c.execute("UPDATE lineups SET batting_order_json=? WHERE franchise_id=?",
                                  (json.dumps(order),off["franchise_id"]))
                    elif pl["type"]=="P" and str(slot["position_group"]).upper()=="SP":
                        rotation=json.loads(lr["rotation_json"])
                        if displaced_id in rotation:
                            rotation=[pl["id"] if pid==displaced_id else pid for pid in rotation]
                        c.execute("UPDATE lineups SET rotation_json=? WHERE franchise_id=?",
                                  (json.dumps(rotation),off["franchise_id"]))








                c.execute("UPDATE offers SET status='ACCEPTED',proposed_role=? WHERE id=?",(assigned_role,oid))
                c.execute("""UPDATE offers
                             SET status='CANCELLED_PLAYER_SIGNED'
                             WHERE player_id=? AND id<>?
                               AND status IN ('OPEN','HELD')""",(pl["id"],oid))








                c.execute("""INSERT INTO contracts(player_id,franchise_id,bonus,salary,years_remaining,years_total,starting_salary)
                             VALUES(?,?,?,?,?,?,?)""",
                          (pl["id"],off["franchise_id"],off["bonus"],off["salary"],off["years"],off["years"],off["salary"]))








                assigned_number=assign_team_jersey_number(c,off["franchise_id"],pl["id"],pl["jersey_number"] if pl["jersey_number"] is not None else 24)
                c.execute("""UPDATE players
                             SET franchise_id=?,status='SIGNED',xp_wallet=xp_wallet+?,jersey_number=?
                             WHERE id=?""",
                          (off["franchise_id"],off["bonus"],assigned_number,pl["id"]))








                # RC72: signing bonuses are immediate treasury purchases, like
                # facilities/sponsorships. Reduce the season's spendable budget once.
                # Do not add the bonus to xp_spent: xp_spent tracks payroll paid during
                # games, while signing_pool_state already protects full-season payroll.
                c.execute("UPDATE franchises SET xp_budget=xp_budget-? WHERE id=?",
                          (off["bonus"],off["franchise_id"]))
                c.execute("""INSERT INTO xp_ledger(player_id,event_type,xp,detail_json)
                             VALUES(?,?,?,?)""",
                          (pl["id"],"SIGNING_BONUS",off["bonus"],json.dumps({"offer_id":oid,"franchise_id":off["franchise_id"]})))
                c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                          ("CONTRACT_SIGNED",u["id"],json.dumps({"player_id":pl["id"],"offer_id":oid,"franchise_id":off["franchise_id"],"bonus":off["bonus"],"salary":off["salary"],"years":off["years"],"assigned_role":assigned_role,"preferred_position":pl["primary_pos"]})))








                brand=c.execute("SELECT display_name FROM franchise_branding WHERE franchise_id=?",(off["franchise_id"],)).fetchone()
                team_display_name=(brand["display_name"] if brand and brand["display_name"] else f["name"])
                c.commit()
                return self.out({"ok":True,"status":"ACCEPTED","player_id":pl["id"],"franchise_id":off["franchise_id"],
                                 "team_name":f["name"],"team_display_name":team_display_name,"assigned_role":assigned_role})








            except sqlite3.IntegrityError as e:
                c.rollback()
                return self.out({"error":"CONTRACT_SIGNING_FAILED","detail":str(e)},409)
            except sqlite3.OperationalError as e:
                c.rollback()
                if "locked" in str(e).lower():
                    return self.out({"error":"DATABASE_BUSY"},503)
                raise
            except Exception:
                c.rollback()
                raise
            finally:
                c.close()








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
            if kind not in REVENUE_BRANCH_COLUMNS:
                return self.out({"error":"INVALID_UPGRADE","allowed":list(REVENUE_BRANCH_COLUMNS)},400)
            c=conn();fr=c.execute("SELECT * FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not fr:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            col=REVENUE_BRANCH_COLUMNS[kind]
            level=int(fr[col] or 0)
            if level>=REVENUE_BRANCH_MAX:c.close();return self.out({"error":"MAX_LEVEL","maximum":REVENUE_BRANCH_MAX},400)
            next_level=level+1
            cost=REVENUE_UPGRADE_COSTS[level]
            current_branch_bonus=REVENUE_UPGRADE_BONUSES[level]
            next_branch_bonus=REVENUE_UPGRADE_BONUSES[next_level]
            annual_gain=round(next_branch_bonus-current_branch_bonus,3)
            # RC92: five-level revenue branches with escalating cost and long-term return.
            finance=signing_pool_state(c,fr["id"])
            if float(finance["available"] or 0)<cost:
                c.close();return self.out({"error":"INSUFFICIENT_RESERVE","cost":cost,"available":finance["available"]},400)
            c.execute(f"UPDATE franchises SET {col}={col}+1,xp_budget=xp_budget-? WHERE id=?",(cost,fr["id"]))
            fr2=dict(c.execute("SELECT * FROM franchises WHERE id=?",(fr["id"],)).fetchone())
            c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                      ("FRANCHISE_UPGRADE",u["id"],json.dumps({"franchise_id":fr["id"],"kind":kind,"level":next_level,"cost":cost,"annual_gain":annual_gain,"branch_annual_bonus":next_branch_bonus})))
            c.commit();c.close()
            return self.out({"ok":True,"kind":kind,"level":next_level,"cost":cost,
                             "annual_gain":annual_gain,"branch_annual_bonus":next_branch_bonus,
                             "revenue_upgrades_total":revenue_upgrade_levels(fr2),
                             "revenue_upgrade_bonus":revenue_upgrade_bonus(fr2),
                             "future_annual_funding":annual_team_budget(fr2)})








        if p=="/api/coach/facility-upgrade":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            kind=str(self.body().get("kind","")).lower()
            cols={"training":"training_level","recovery":"recovery_level"}
            if kind not in cols:return self.out({"error":"INVALID_FACILITY","allowed":list(cols)},400)
            c=conn();fr=c.execute("SELECT * FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not fr:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            col=cols[kind];level=int(fr[col] or 0)
            if level>=5:c.close();return self.out({"error":"MAX_LEVEL"},400)
            cost=FACILITY_UPGRADE_COSTS[level];finance=signing_pool_state(c,fr["id"])
            if float(finance["available"] or 0)<cost:
                c.close();return self.out({"error":"INSUFFICIENT_RESERVE","cost":cost,"available":finance["available"]},400)
            c.execute(f"UPDATE franchises SET {col}={col}+1,xp_budget=xp_budget-? WHERE id=?",(cost,fr["id"]))
            c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                      ("FACILITY_UPGRADE",u["id"],json.dumps({"franchise_id":fr["id"],"kind":kind,"level":level+1,"cost":cost})))
            c.commit();c.close();return self.out({"ok":True,"kind":kind,"level":level+1,"cost":cost})








        if p=="/api/coach/sponsor":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            d=self.body();attribute=str(d.get("attribute","ARM")).upper()
            if attribute not in SPONSORSHIP_ATTRS:return self.out({"error":"INVALID_SPONSOR_ATTRIBUTE","allowed":sorted(SPONSORSHIP_ATTRS)},400)
            c=conn();fr=c.execute("SELECT * FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not fr:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            season_row=c.execute("SELECT v FROM league_state WHERE k='season'").fetchone();season=int(season_row["v"] or 1) if season_row else 1
            existing=c.execute("""SELECT id FROM team_sponsorships WHERE franchise_id=? AND attribute=? AND status='ACTIVE' AND end_season>=?""",
                               (fr["id"],attribute,season)).fetchone()
            if existing:c.close();return self.out({"error":"SPONSOR_ALREADY_ACTIVE","attribute":attribute},400)
            finance=signing_pool_state(c,fr["id"])
            if float(finance["available"] or 0)<SPONSORSHIP_COST:
                c.close();return self.out({"error":"INSUFFICIENT_RESERVE","cost":SPONSORSHIP_COST,"available":finance["available"]},400)
            end_season=season+1
            c.execute("UPDATE franchises SET xp_budget=xp_budget-? WHERE id=?",(SPONSORSHIP_COST,fr["id"]))
            c.execute("""INSERT INTO team_sponsorships(franchise_id,attribute,bonus,start_season,end_season,cost)
                         VALUES(?,?,1,?,?,?)""",(fr["id"],attribute,season,end_season,SPONSORSHIP_COST))
            c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                      ("TEAM_SPONSORSHIP",u["id"],json.dumps({"franchise_id":fr["id"],"attribute":attribute,"bonus":1,"start_season":season,"end_season":end_season,"cost":SPONSORSHIP_COST})))
            c.commit();c.close();return self.out({"ok":True,"attribute":attribute,"bonus":1,"start_season":season,"end_season":end_season,"cost":SPONSORSHIP_COST})








        if p=="/api/coach/development-coach":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            d=self.body();coach_type=str(d.get("coach_type","SPEED")).upper()
            try:intensity=int(d.get("intensity",1) or 1)
            except (TypeError,ValueError):intensity=1
            if coach_type not in DEVELOPMENT_COACH_TYPES:
                return self.out({"error":"INVALID_DEVELOPMENT_COACH","allowed":sorted(DEVELOPMENT_COACH_TYPES)},400)
            if intensity not in DEVELOPMENT_COACH_INTENSITY:
                return self.out({"error":"INVALID_COACH_INTENSITY","allowed":sorted(DEVELOPMENT_COACH_INTENSITY)},400)
            c=conn();fr=c.execute("SELECT * FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not fr:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            state={r["k"]:r["v"] for r in c.execute("SELECT k,v FROM league_state WHERE k IN ('season','league_day','phase')")}
            season=int(state.get("season",1));day=int(state.get("league_day",0));phase=str(state.get("phase","REGULAR")).upper()
            if phase!="REGULAR" or day>=DEVELOPMENT_COACH_HIRING_CLOSE_DAY:
                c.close();return self.out({"error":"DEVELOPMENT_COACH_HIRING_CLOSED","detail":f"Seasonal development coaches must be hired before League Day {DEVELOPMENT_COACH_HIRING_CLOSE_DAY}.","season":season,"league_day":day,"phase":phase},400)
            existing=[dict(x) for x in c.execute("SELECT * FROM team_development_coaches WHERE franchise_id=? AND season=? ORDER BY coach_slot,id",(fr["id"],season)).fetchall()]
            if len(existing)>=DEVELOPMENT_COACH_MAX:
                c.close();return self.out({"error":"DEVELOPMENT_COACH_LIMIT","maximum":DEVELOPMENT_COACH_MAX},400)
            if any(str(x.get("coach_type") or "").upper()==coach_type for x in existing):
                c.close();return self.out({"error":"DEVELOPMENT_COACH_DUPLICATE_SPECIALTY","coach_type":coach_type},400)
            is_free=len(existing)==0
            if is_free:
                intensity=1
            tier=DEVELOPMENT_COACH_INTENSITY[intensity]
            cost=0.0 if is_free else DEVELOPMENT_COACH_BASE_COST+float(tier["extra_cost"])
            finance=signing_pool_state(c,fr["id"])
            if float(finance["available"] or 0)<cost:
                c.close();return self.out({"error":"INSUFFICIENT_RESERVE","cost":cost,"available":finance["available"]},400)
            spec=DEVELOPMENT_COACH_TYPES[coach_type]
            slot=len(existing)+1
            if cost>0:
                c.execute("UPDATE franchises SET xp_budget=xp_budget-? WHERE id=?",(cost,fr["id"]))
            cur=c.execute("""INSERT INTO team_development_coaches(
                             franchise_id,season,coach_slot,coach_type,attribute,cost,is_free,intensity,
                             checkpoint_days_json,applied_days_json,hired_day)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(
                             fr["id"],season,slot,coach_type,spec["attribute"],cost,1 if is_free else 0,intensity,
                             json.dumps(tier["days"]),json.dumps([]),day))
            coach_row=c.execute("SELECT * FROM team_development_coaches WHERE id=?",(cur.lastrowid,)).fetchone()
            # Apply the opening/hire boost now. If a paid coach is hired after one of
            # its optional early checkpoints, that missed checkpoint is not back-paid.
            applied=set()
            opening_players=_apply_team_development_point(c,coach_row,"OPENING")
            applied.add(0)
            for checkpoint in tier["days"]:
                if checkpoint>0 and checkpoint<day:
                    applied.add(int(checkpoint))
            _sync_development_legacy_flags(c,cur.lastrowid,applied)
            c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                      ("DEVELOPMENT_COACH_HIRED",u["id"],json.dumps({"franchise_id":fr["id"],"season":season,"coach_slot":slot,"coach_type":coach_type,"attribute":spec["attribute"],"cost":cost,"free":is_free,"intensity":intensity,"checkpoints":tier["days"],"opening_players":opening_players})))
            schedule_text=", ".join("Opening" if x==0 else f"Day {x}" for x in tier["days"])
            post_news(c,"TEAM",f"{team_name(c,fr['id'])} hire a {spec['name']}",
                      f"The club added a {tier['name'].lower()} development plan for {spec['attribute']} ({schedule_text}). {'The first seasonal coach is free.' if is_free else f'The club committed {cost:g} team XP.'}",
                      day,fr["id"],None,None,1,season=season)
            c.commit();row=dict(c.execute("SELECT * FROM team_development_coaches WHERE id=?",(cur.lastrowid,)).fetchone());c.close()
            return self.out({"ok":True,"coach":row,"name":spec["name"],"attribute":spec["attribute"],"opening_players":opening_players,"cost":cost,"free":is_free,"intensity":intensity,"intensity_name":tier["name"],"checkpoints":tier["days"],"maximum":DEVELOPMENT_COACH_MAX})








        if p=="/api/coach/set-strategy":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            d=self.body();c=conn();f=c.execute("SELECT id FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            fid=f["id"]
            existing=team_strategy_for(c,fid)
            bullpen_supplied="bullpen" in d
            defense_supplied="defense" in d
            subs_supplied="substitutions" in d








            bullpen=(d.get("bullpen") or {}) if bullpen_supplied else (existing.get("bullpen") or {})
            base_defense={"default_shift":"STANDARD","vs_lhb":"STANDARD","vs_rhb":"STANDARD","corners_in":False,"infield_in":False}
            defense={**base_defense,**(existing.get("defense") or {})}
            if defense_supplied:
                defense.update(d.get("defense") or {})








            existing_subs=existing.get("substitutions") or {}
            incoming_subs=(d.get("substitutions") or {}) if subs_supplied else {}
            subs={**existing_subs,**incoming_subs}








            roster={x["id"]:dict(x) for x in c.execute("SELECT id,type,primary_pos FROM players WHERE franchise_id=? AND active=1",(fid,))}
            lr=c.execute("SELECT rotation_json FROM lineups WHERE franchise_id=?",(fid,)).fetchone()
            try:rotation_ids={int(x) for x in json.loads(lr["rotation_json"] or "[]")} if lr else set()
            except Exception:rotation_ids=set()








            # Bullpen validation runs only when the coach is actually editing bullpen roles.
            # CL / SU1 / SU2 are exclusive primary jobs. MR / LR / EMERGENCY are usage
            # pools and may intentionally overlap (the game engine already supports that).
            if bullpen_supplied:
                try:
                    def bp_one(v):
                        return int(v) if v not in (None,"") else None
                    def bp_many(v):
                        out=[]
                        for x in (v or []):
                            pid=int(x)
                            if pid not in out:out.append(pid)
                        return out
                    bullpen={
                        "CL":bp_one(bullpen.get("CL")),
                        "SU1":bp_one(bullpen.get("SU1")),
                        "SU2":bp_one(bullpen.get("SU2")),
                        "MR":bp_many(bullpen.get("MR")),
                        "LR":bp_many(bullpen.get("LR")),
                        "EMERGENCY":bp_many(bullpen.get("EMERGENCY"))
                    }
                except Exception:
                    c.close();return self.out({"error":"INVALID_BULLPEN","detail":"Choose pitchers from the active pitching staff."},400)








                primary=[bullpen[k] for k in ("CL","SU1","SU2") if bullpen.get(k) is not None]
                if len(primary)!=len(set(primary)):
                    c.close();return self.out({"error":"INVALID_BULLPEN","detail":"Closer, Setup 1, and Setup 2 must be different pitchers. MR, LR, and Emergency may overlap."},400)








                ids=list(primary)
                for k in ("MR","LR","EMERGENCY"):ids.extend(bullpen[k])
                if any(i not in roster or roster[i]["type"]!="P" for i in ids):
                    c.close();return self.out({"error":"INVALID_BULLPEN","detail":"Every bullpen assignment must be an active pitcher on this roster."},400)
                if any(i in rotation_ids for i in ids):
                    c.close();return self.out({"error":"PITCHER_ASSIGNED_TO_ROTATION_AND_BULLPEN","detail":"Move the pitcher out of the starting rotation before assigning a bullpen role."},400)








            # RC55 — EBL has no position-player bench. Only steal/bunt aggression remain.
            bench={}
            subs={
                "steal_aggression":subs.get("steal_aggression","NORMAL"),
                "bunt_aggression":subs.get("bunt_aggression","NORMAL")
            }
            allowed={"STANDARD","PULL","OPPO","NO_DOUBLES","BUNT_DEFENSE","INFIELD_IN"}
            for k in ["default_shift","vs_lhb","vs_rhb"]:
                if defense.get(k,"STANDARD") not in allowed:
                    c.close();return self.out({"error":"INVALID_DEFENSE"},400)
            if subs.get("steal_aggression","NORMAL") not in {"LOW","NORMAL","HIGH"}:
                c.close();return self.out({"error":"INVALID_STEAL_AGGRESSION"},400)
            if subs.get("bunt_aggression","NORMAL") not in {"LOW","NORMAL","HIGH"}:
                c.close();return self.out({"error":"INVALID_BUNT_AGGRESSION"},400)








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
            d=self.body();c=conn();f=c.execute("SELECT id,name FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            state={r["k"]:r["v"] for r in c.execute("SELECT k,v FROM league_state WHERE k IN ('season','phase','league_day')")}
            season=int(state.get("season",1));phase=str(state.get("phase","REGULAR")).upper();day=int(state.get("league_day","0") or 0)
            existing=c.execute("SELECT * FROM franchise_branding WHERE franchise_id=?",(f["id"],)).fetchone()
            inseason=phase!="OFFSEASON" and day>0
            if inseason and existing and existing["inseason_edit_season"] is not None and int(existing["inseason_edit_season"])==season:
                c.close();return self.out({"error":"TEAM_IDENTITY_EDIT_USED","phase":phase,"league_day":day,"season":season},400)








            city=" ".join(str(d.get("city","")).split()).strip()
            team_nickname=" ".join(str(d.get("team_name","")).split()).strip()
            # Backward compatibility with the original single display-name field.
            legacy=" ".join(str(d.get("display_name","")).split()).strip()
            if not city and not team_nickname and legacy:
                parts=legacy.rsplit(" ",1);city=parts[0] if len(parts)>1 else "";team_nickname=parts[-1]
            if not (2<=len(city)<=40):c.close();return self.out({"error":"INVALID_TEAM_CITY"},400)
            if not (2<=len(team_nickname)<=40):c.close();return self.out({"error":"INVALID_TEAM_NAME"},400)
            display_name=f"{city} {team_nickname}".strip()
            if len(display_name)>70:c.close();return self.out({"error":"TEAM_IDENTITY_TOO_LONG"},400)








            logo_style=int(d.get("logo_style",1) or 1)
            if logo_style not in range(1,11):c.close();return self.out({"error":"INVALID_LOGO_STYLE"},400)
            pc,sc,ac=d.get("primary_color"),d.get("secondary_color"),d.get("accent_color")
            if not all(valid_hex_color(x) for x in [pc,sc,ac]):c.close();return self.out({"error":"INVALID_COLORS"},400)
            home=str(d.get("uniform_home","WHITE")).upper();away=str(d.get("uniform_away","NAVY")).upper()
            allowed={"WHITE","NAVY","RED","GRAY","BLACK","CREAM"}
            if home not in allowed or away not in allowed:c.close();return self.out({"error":"INVALID_UNIFORM"},400)








            primary_logo=str(d.get("primary_logo",existing["primary_logo"] if existing and "primary_logo" in existing.keys() else "") or "")
            secondary_logo=str(d.get("secondary_logo",existing["secondary_logo"] if existing and "secondary_logo" in existing.keys() else "") or "")
            jersey_wordmark=str(d.get("jersey_wordmark",existing["jersey_wordmark"] if existing and "jersey_wordmark" in existing.keys() else "") or "")
            for artwork in (primary_logo,secondary_logo,jersey_wordmark):
                if artwork and (not artwork.startswith(("data:image/png;base64,","data:image/webp;base64,","data:image/jpeg;base64,","data:image/svg+xml;base64,")) or len(artwork)>MAX_TEAM_LOGO_DATA_URL_CHARS):
                    c.close();return self.out({"error":"INVALID_TEAM_ARTWORK","detail":"Use PNG, JPG or WebP. Each branding image must be 5 MB or smaller."},400)








            prior_edit_season=existing["inseason_edit_season"] if existing and "inseason_edit_season" in existing.keys() else None
            edit_season=season if inseason else prior_edit_season
            c.execute("""INSERT INTO franchise_branding(
                           franchise_id,display_name,city,team_name,logo_style,primary_logo,secondary_logo,jersey_wordmark,
                           primary_color,secondary_color,accent_color,uniform_home,uniform_away,inseason_edit_season,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                         ON CONFLICT(franchise_id) DO UPDATE SET
                           display_name=excluded.display_name,city=excluded.city,team_name=excluded.team_name,logo_style=excluded.logo_style,
                           primary_logo=excluded.primary_logo,secondary_logo=excluded.secondary_logo,jersey_wordmark=excluded.jersey_wordmark,
                           primary_color=excluded.primary_color,secondary_color=excluded.secondary_color,accent_color=excluded.accent_color,
                           uniform_home=excluded.uniform_home,uniform_away=excluded.uniform_away,inseason_edit_season=excluded.inseason_edit_season,
                           updated_at=CURRENT_TIMESTAMP""",
                      (f["id"],display_name,city,team_nickname,logo_style,primary_logo,secondary_logo,jersey_wordmark,pc,sc,ac,home,away,edit_season))
            c.execute("UPDATE franchises SET name=? WHERE id=?",(display_name,f["id"]))
            # Keep the franchise lineage useful: record each distinct saved identity.
            prev_hist=c.execute("""SELECT display_name,primary_color,secondary_color,accent_color,primary_logo,secondary_logo,jersey_wordmark
                                      FROM franchise_identity_history WHERE franchise_id=? ORDER BY id DESC LIMIT 1""",(f["id"],)).fetchone()
            signature=(display_name,pc,sc,ac,primary_logo,secondary_logo,jersey_wordmark)
            prev_signature=tuple(prev_hist[k] for k in ("display_name","primary_color","secondary_color","accent_color","primary_logo","secondary_logo","jersey_wordmark")) if prev_hist else None
            if signature!=prev_signature:
                hist_season=season+1 if phase=="OFFSEASON" else season
                c.execute("""INSERT INTO franchise_identity_history(franchise_id,season,city,team_name,display_name,primary_color,secondary_color,accent_color,primary_logo,secondary_logo,jersey_wordmark)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                          (f["id"],hist_season,city,team_nickname,display_name,pc,sc,ac,primary_logo,secondary_logo,jersey_wordmark))
            c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                      ("FRANCHISE_REBRANDED",u["id"],json.dumps({"franchise_id":f["id"],"display_name":display_name,"city":city,"team_name":team_nickname,"season":season,"inseason_edit":inseason})))
            c.commit();c.close();return self.out({"ok":True,"display_name":display_name,"city":city,"team_name":team_nickname,"inseason_edit_used":inseason,"season":season})
        if p=="/api/coach/set-lineup":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            d=self.body();ids=[int(x) for x in d.get("batting_order",[])]
            if len(ids)!=9 or len(set(ids))!=9:return self.out({"error":"INVALID_LINEUP"},400)
            field=d.get("field_positions") or {}
            required_positions={"C","1B","2B","3B","SS","LF","CF","RF","DH"}
            if set(field.keys())!=required_positions:return self.out({"error":"INVALID_DEFENSIVE_ALIGNMENT"},400)
            try:field={str(pos).upper():int(pid) for pos,pid in field.items()}
            except Exception:return self.out({"error":"INVALID_DEFENSIVE_ALIGNMENT"},400)
            if set(field.values())!=set(ids) or len(set(field.values()))!=9:
                return self.out({"error":"INVALID_DEFENSIVE_ALIGNMENT","detail":"Assign each lineup player to exactly one field position."},400)
            c=conn();f=c.execute("SELECT id FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            valid={x["id"] for x in c.execute("SELECT id FROM players WHERE franchise_id=? AND type='H' AND active=1",(f["id"],))}
            if any(i not in valid for i in ids):c.close();return self.out({"error":"PLAYER_NOT_ON_ROSTER"},400)
            # Any position player can catch. Catcher specialization only controls
            # CALL development and therefore the game-calling bonus.
            c.execute("UPDATE lineups SET batting_order_json=?,field_positions_json=? WHERE franchise_id=?",
                      (json.dumps(ids),json.dumps(field),f["id"]))
            c.commit();c.close();return self.out({"ok":True,"field_positions":field})
        if p=="/api/coach/set-rotation":
            u=self.auth(["COACH","COMMISSIONER"])
            if not u:return
            d=self.body()
            ids=[int(x) for x in d.get("rotation",[]) if x not in (None,"")]
            if not (3<=len(ids)<=5) or len(set(ids))!=len(ids):
                return self.out({"error":"INVALID_ROTATION","detail":"Choose 3 to 5 unique starting pitchers."},400)








            c=conn();f=c.execute("SELECT id FROM franchises WHERE owner_user_id=?",(u["id"],)).fetchone()
            if not f:c.close();return self.out({"error":"NO_FRANCHISE"},404)
            valid={x["id"] for x in c.execute("SELECT id FROM players WHERE franchise_id=? AND type='P' AND active=1",(f["id"],))}
            if any(i not in valid for i in ids):
                c.close();return self.out({"error":"STARTER_NOT_ON_ROSTER"},400)








            starter_set=set(ids)
            bullpen_supplied="bullpen" in d
            saved_bullpen=None








            if bullpen_supplied:
                raw=d.get("bullpen") or {}
                try:
                    def bp_one(v):
                        return int(v) if v not in (None,"") else None
                    def bp_many(v):
                        out=[]
                        for x in (v or []):
                            pid=int(x)
                            if pid not in out:out.append(pid)
                        return out
                    bp={
                        "CL":bp_one(raw.get("CL")),
                        "SU1":bp_one(raw.get("SU1")),
                        "SU2":bp_one(raw.get("SU2")),
                        "MR":bp_many(raw.get("MR")),
                        "LR":bp_many(raw.get("LR")),
                        "EMERGENCY":bp_many(raw.get("EMERGENCY"))
                    }
                except Exception:
                    c.close();return self.out({"error":"INVALID_BULLPEN","detail":"Choose pitchers from the active pitching staff."},400)








                primary=[bp[k] for k in ("CL","SU1","SU2") if bp.get(k) is not None]
                if len(primary)!=len(set(primary)):
                    c.close();return self.out({"error":"INVALID_BULLPEN","detail":"Closer, Setup 1, and Setup 2 must be different pitchers. MR, LR, and Emergency may overlap."},400)








                all_bp=list(primary)
                for k in ("MR","LR","EMERGENCY"):all_bp.extend(bp[k])
                if any(pid not in valid for pid in all_bp):
                    c.close();return self.out({"error":"INVALID_BULLPEN","detail":"Every bullpen assignment must be an active pitcher on this roster."},400)








                # Rotation wins if a stale browser selection somehow contains the same arm.
                # This keeps one-tap staff edits from failing while preserving the no-dual-role rule.
                for k in ("CL","SU1","SU2"):
                    if bp.get(k) in starter_set:bp[k]=None
                for k in ("MR","LR","EMERGENCY"):
                    bp[k]=[pid for pid in bp[k] if pid not in starter_set]








                c.execute("UPDATE team_strategy SET bullpen_json=?,updated_at=CURRENT_TIMESTAMP WHERE franchise_id=?",
                          (json.dumps(bp),f["id"]))
                saved_bullpen=bp
            else:
                # Backward compatibility for older clients: keep the saved bullpen, but
                # automatically remove anyone promoted into the new rotation.
                strat=c.execute("SELECT bullpen_json FROM team_strategy WHERE franchise_id=?",(f["id"],)).fetchone()
                if strat:
                    try:bp=json.loads(strat["bullpen_json"] or "{}")
                    except Exception:bp={}
                    for k in ["CL","SU1","SU2"]:
                        if bp.get(k) is not None and int(bp[k]) in starter_set:bp[k]=None
                    for k in ["MR","LR","EMERGENCY"]:
                        bp[k]=[int(x) for x in bp.get(k,[]) if int(x) not in starter_set]
                    c.execute("UPDATE team_strategy SET bullpen_json=?,updated_at=CURRENT_TIMESTAMP WHERE franchise_id=?",
                              (json.dumps(bp),f["id"]))
                    saved_bullpen=bp








            c.execute("UPDATE lineups SET rotation_json=? WHERE franchise_id=?",(json.dumps(ids),f["id"]))
            c.commit();c.close()
            return self.out({"ok":True,"rotation_size":len(ids),"bullpen":saved_bullpen})
        if p=="/api/team/practice":
            u=self.auth()
            if not u:return
            d=self.body();c=conn()
            pl=owned_active_player(c,u["id"],request_player_id(self,d))
            if not pl:
                c.close();return self.out({"error":"NO_ACTIVE_PLAYER"},404)
            fid=pl["franchise_id"]
            if not fid or str(pl["status"] or "").upper()!="SIGNED":
                c.close();return self.out({"error":"NO_TEAM"},400)
            state={r["k"]:r["v"] for r in c.execute("SELECT k,v FROM league_state WHERE k IN ('season','league_day')")}
            season=int(state.get("season",1));day=int(state.get("league_day",0));today=practice_day_key();reward=practice_reward_for(c,fid)
            existing=c.execute("SELECT xp FROM team_practice WHERE player_id=? AND practice_date=?",(pl["id"],today)).fetchone()
            if existing:
                c.close();return self.out({"ok":True,"already_completed":True,"xp":float(existing["xp"]),"practice_date":today})
            c.execute("""INSERT INTO team_practice(player_id,practice_date,season,league_day,franchise_id,xp)
                         VALUES(?,?,?,?,?,?)""",(pl["id"],today,season,day,fid,reward))
            c.execute("UPDATE players SET xp_wallet=xp_wallet+? WHERE id=?",(reward,pl["id"]))
            c.execute("INSERT INTO xp_ledger(player_id,event_type,xp,detail_json) VALUES(?,?,?,?)",
                      (pl["id"],"TEAM_PRACTICE",reward,json.dumps({"franchise_id":fid,"practice_date":today,"season":season,"league_day":day})))
            c.commit();new_wallet=c.execute("SELECT xp_wallet FROM players WHERE id=?",(pl["id"],)).fetchone()["xp_wallet"];c.close()
            return self.out({"ok":True,"already_completed":False,"xp":reward,"xp_wallet":new_wallet,"practice_date":today})








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
            pr=owned_active_player(c,u["id"],request_player_id(self,d))
            player_id=pr["id"] if pr else None
            if channel=="TEAM":
                team_id=pr["franchise_id"] if pr else None
                if not team_id:c.close();return self.out({"error":"NO_TEAM"},400)
            # simple anti-spam: max 1 message per second/account
            recent=c.execute("SELECT created_at FROM chat_messages WHERE user_id=? ORDER BY id DESC LIMIT 1",(u["id"],)).fetchone()
            c.execute("INSERT INTO chat_messages(user_id,player_id,channel,team_id,message) VALUES(?,?,?,?,?)",(u["id"],player_id,channel,team_id,msg))
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
        if p=="/api/beta/feedback":
            u=self.auth()
            if not u:return
            d=self.body();category=str(d.get("category","FEEDBACK") or "FEEDBACK").upper().strip()
            if category not in ("BUG","FEEDBACK","IDEA"):category="FEEDBACK"
            detail=str(d.get("detail","") or "").strip();page=str(d.get("page","") or "").strip()[:240]
            if len(detail)<3:return self.out({"error":"FEEDBACK_TOO_SHORT"},400)
            if len(detail)>4000:return self.out({"error":"FEEDBACK_TOO_LONG"},400)
            c=conn()
            try:
                if not rate_limit(c,f"beta_feedback:{u['id']}",20,3600):
                    return self.out({"error":"RATE_LIMITED"},429)
                ua=str(self.headers.get("User-Agent","") or "")[:500]
                cur=c.execute("INSERT INTO beta_feedback(user_id,category,page,detail,user_agent) VALUES(?,?,?,?,?)",
                              (u["id"],category,page,detail,ua))
                c.commit();return self.out({"ok":True,"feedback_id":cur.lastrowid})
            finally:
                c.close()








        if p=="/api/commish/resolve-beta-feedback":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            d=self.body()
            try:fid=int(d.get("feedback_id",0) or 0)
            except Exception:return self.out({"error":"INVALID_FEEDBACK"},400)
            c=conn()
            try:
                c.execute("UPDATE beta_feedback SET status='REVIEWED',reviewed_at=CURRENT_TIMESTAMP,reviewed_by=? WHERE id=?",(u["id"],fid))
                c.commit();return self.out({"ok":True})
            finally:
                c.close()








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
                  AND league_day>?
                ORDER BY league_day,id
                """,
                (season,REGULAR_SEASON_CALENDAR_DAYS)
            )]
















            c.close()
















            return self.out({
                "ok":True,
                "state":state,
                "games":games
            })
        if p=="/api/commish/auto-advance":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            d=self.body();enabled=bool(d.get("enabled",False))
            try:per_day=int(d.get("per_day",1) or 1)
            except (TypeError,ValueError):return self.out({"error":"INVALID_ADVANCES_PER_DAY"},400)
            if per_day<1 or per_day>24:
                return self.out({"error":"INVALID_ADVANCES_PER_DAY","minimum":1,"maximum":24},400)
            c=conn();state=auto_advance_state(c)
            if enabled and str(state["phase"]).upper()!="REGULAR":
                c.close();return self.out({"error":"AUTO_ADVANCE_REGULAR_SEASON_ONLY","phase":state["phase"]},400)
            set_league_cfg(c,"auto_advance_per_day",per_day)
            set_league_cfg(c,"auto_advance",1 if enabled else 0)
            next_at=time.time()+(86400/per_day) if enabled else 0
            set_league_cfg(c,"auto_advance_next_at",next_at)
            audit(c,"AUTO_ADVANCE_ENABLED" if enabled else "AUTO_ADVANCE_DISABLED",f"per_day={per_day}")
            c.commit();state=auto_advance_state(c);c.close()
            if state["next_at"]>0:
                state["next_at_iso"]=datetime.datetime.fromtimestamp(state["next_at"],datetime.timezone.utc).isoformat()
            else:
                state["next_at_iso"]=None
            return self.out({"ok":True,**state})
        if p=="/api/commish/sim-day":
            internal_auto=hmac.compare_digest(str(self.headers.get("X-EBL-Auto") or ""),AUTO_ADVANCE_TOKEN)
            if internal_auto:
                u={"id":0,"username":"AUTO_ADVANCE","role":"COMMISSIONER"}
            else:
                u=self.auth(["COMMISSIONER"])
                if not u:return
            c=conn();day=int(c.execute("SELECT v FROM league_state WHERE k='league_day'").fetchone()["v"])+1
            if day>REGULAR_SEASON_CALENDAR_DAYS:
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
                            c,season,code,1,REGULAR_SEASON_CALENDAR_DAYS+1,
                            high["id"],low["id"]
                        )
















                    grant_roster_bonus(c,season,"PLAYOFF_BERTH",[x["id"] for x in seeds],PLAYOFF_ROSTER_XP,"Made the EBL Playoffs",REGULAR_SEASON_CALENDAR_DAYS)








                    # Postseason starts fresh: regular-season pitching workload does not
                    # carry into the playoff bracket.
                    reset_pitcher_fatigue(c,"PLAYOFFS",season=season,league_day=REGULAR_SEASON_CALENDAR_DAYS,announce=False)








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
                        "day":REGULAR_SEASON_CALENDAR_DAYS,
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
                         AND league_day>?
                          AND status='SCHEDULED'
                        """,
                        (season,REGULAR_SEASON_CALENDAR_DAYS)
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
                            grant_roster_bonus(c,season,"FINAL_FOUR",winners,FINAL_FOUR_XP,"Reached the EBL Final Four",day)
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
                            grant_roster_bonus(c,season,"CHAMPIONSHIP_BERTH",winners,CHAMPIONSHIP_BERTH_XP,"Reached the EBL Championship",day)
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
            try:
                # Notify human players that their club is taking the field.
                for g in games:
                    for fid in (g["away_id"],g["home_id"]):
                        for ur in c.execute("SELECT DISTINCT user_id FROM players WHERE franchise_id=? AND active=1 AND user_id IS NOT NULL",(fid,)).fetchall():
                            notify_user(c,ur["user_id"],"GAME",f"Game Day: {team_name(c,g['away_id'])} @ {team_name(c,g['home_id'])}",f"League Day {day}",g["id"])








                results=[]
                for g in games:
                    results.append(simulate_game(c,g))
                    c.commit()








                generate_daily_news(c,day,season)
                weekly_recap(c,day,season)
                process_quarter_awards(c,season,day)
                apply_team_development_coach_milestones(c,season,day)
                if day==ALL_STAR_BREAK_DAY:
                    process_all_star_game(c,season,day)
                    reset_pitcher_fatigue(c,"ALL_STAR_BREAK",season=season,league_day=day,announce=True)
                if day==RENEWAL_OPEN_DAY:
                    for fr in c.execute("SELECT id,name,owner_user_id FROM franchises WHERE owner_user_id IS NOT NULL").fetchall():
                        count=c.execute(
                            """SELECT COUNT(*) n FROM contracts co JOIN players p ON p.id=co.player_id
                               WHERE co.franchise_id=? AND co.years_remaining=1 AND p.active=1 AND p.user_id IS NOT NULL""",
                            (fr["id"],)
                        ).fetchone()["n"]
                        if count:
                            ref=f"renewal-window:{season}:{fr['id']}"
                            if not c.execute("SELECT 1 FROM notifications WHERE user_id=? AND type='COACH_CONTRACT' AND ref_id=? LIMIT 1",(fr["owner_user_id"],ref)).fetchone():
                                notify_user(c,fr["owner_user_id"],"COACH_CONTRACT","Renewal window is open",f"{count} expiring human contract{'s' if count!=1 else ''} need a decision before the postseason. Open Franchise Operations to review them.",ref)
                if day==REGULAR_SEASON_CALENDAR_DAYS:
                    process_season_awards(c,season)
                c.execute("UPDATE league_state SET v=? WHERE k='league_day'",(str(day),))
                c.commit()
            except Exception as exc:
                try:
                    c.rollback()
                except Exception:
                    pass
                c.close()
                print(f"SIM_DAY_ERROR season={season} day={day}: {type(exc).__name__}: {exc}")
                return self.out({"error":"SIMULATION_FAILED","detail":type(exc).__name__,"day":day},500)
            c.close()
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
            d=self.body()
            requested_team_count=d.get("team_count")
            c=conn()
            try:
                # Optional Commissioner-controlled Genesis league size.
                # Supported sizes are even numbers from 8 through the available franchise pool.
                total_franchises=c.execute("SELECT COUNT(*) n FROM franchises").fetchone()["n"]
                if requested_team_count is None:
                    team_count=len(active_franchise_ids(c,1))
                else:
                    try:
                        team_count=int(requested_team_count)
                    except (TypeError,ValueError):
                        return self.out({"error":"INVALID_TEAM_COUNT"},400)
                if team_count<MIN_ACTIVE_TEAMS:
                    return self.out({"error":"MINIMUM_8_TEAMS","minimum":MIN_ACTIVE_TEAMS},400)
                if team_count%2:
                    return self.out({"error":"EVEN_TEAM_COUNT_REQUIRED"},400)
                if team_count>total_franchises:
                    return self.out({"error":"TEAM_COUNT_EXCEEDS_AVAILABLE_FRANCHISES","available":total_franchises},400)








                # Genesis reset: return the closed-alpha league to Season 1, Day 0.
                # Accounts, player identity/attributes, friendships and contracts stay intact.
                # Earned XP, XP ledger history and temporary public/team chat are reset.
                c.execute("DELETE FROM games")
                c.execute("DELETE FROM season_history")
                c.execute("DELETE FROM season_champions")
                c.execute("DELETE FROM franchise_season_history")
                c.execute("DELETE FROM player_championships")
                c.execute("DELETE FROM award_history")
                c.execute("DELETE FROM player_bonus_history")
                c.execute("DELETE FROM all_star_games")
                c.execute("DELETE FROM rivalries")
                c.execute("DELETE FROM league_records")
                c.execute("DELETE FROM news")
                c.execute("DELETE FROM xp_ledger")
                c.execute("DELETE FROM chat_messages")
                c.execute("DELETE FROM notifications WHERE type IN ('GAME','AWARD')")








                c.execute("UPDATE players SET xp_wallet=0,career_extension_through=12")
                c.execute("UPDATE franchises SET wins=0,losses=0,runs_for=0,runs_against=0,xp_spent=0,xp_reserve=0,finish_reward=0,development_bonus=0,funding_growth=0,last_pool_growth=0")
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








                # Rebuild Season 1 membership from the Commissioner-selected league size,
                # then generate the 81-game / 95-calendar-day schedule for exactly those active clubs.
                c.execute("DELETE FROM franchise_seasons WHERE season=1")
                selected_ids=[r["id"] for r in c.execute(
                    "SELECT id FROM franchises ORDER BY id LIMIT ?",
                    (team_count,)
                ).fetchall()]
                set_season_membership(c,1,selected_ids)
                # Persist the Commissioner's choice so no later initialization or
                # season-membership repair can silently snap the league back to 8.
                c.execute(
                    "INSERT INTO league_config(k,v) VALUES('active_team_count',?) "
                    "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                    (str(team_count),)
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
                actual_active=c.execute(
                    "SELECT COUNT(*) n FROM franchise_seasons WHERE season=1 AND status='ACTIVE'"
                ).fetchone()["n"]
                if actual_active!=team_count:
                    return self.out({"error":"LEAGUE_SIZE_NOT_PERSISTED","requested":team_count,"active":actual_active},500)
                return self.out({
                    "ok":True,
                    "season":1,
                    "day":0,
                    "phase":"REGULAR",
                    "games_created":c.execute("SELECT COUNT(*) n FROM games WHERE season=1").fetchone()["n"],
                    "active_team_count":actual_active,
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
                summary={"contracts_expired":0,"contracts_advanced":0,"renewals_activated":0,"retired":0,"retired_names":[],"free_agents":[],"offers_expired":0,"return_offers":0,"rosters_rebuilt":False}
                return_offer_candidates=[]








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
                    if veteran_retirement_due(c,pid):
                        continue
                    if remaining<=0:
                        pl=c.execute("SELECT user_id,name FROM players WHERE id=?",(pid,)).fetchone()
                        seen=c.execute("""SELECT 1 FROM contract_history WHERE player_id=? AND franchise_id=? AND ABS(salary-?)<0.0001 AND signed_at=? LIMIT 1""",(pid,con["franchise_id"],con["salary"],con["signed_at"])).fetchone()
                        if not seen:
                            c.execute("""INSERT INTO contract_history(player_id,franchise_id,bonus,salary,years,signed_at,ended_at) VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)""",(pid,con["franchise_id"],con["bonus"],con["salary"],max(1,int(con["years_total"] or con["years_remaining"] or 1)),con["signed_at"]))
                        renewal=c.execute(
                            """SELECT * FROM offers WHERE player_id=? AND franchise_id=? AND offer_type='RENEWAL'
                               AND status='ACCEPTED' AND effective_season=? ORDER BY id DESC LIMIT 1""",
                            (pid,con["franchise_id"],next_season)
                        ).fetchone()
                        if renewal:
                            c.execute(
                                """UPDATE contracts SET bonus=0,salary=?,years_remaining=?,years_total=?,starting_salary=?,signed_at=CURRENT_TIMESTAMP
                                   WHERE player_id=?""",
                                (renewal["salary"],renewal["years"],renewal["years"],renewal["salary"],pid)
                            )
                            c.execute("UPDATE offers SET status='ACTIVATED_RENEWAL' WHERE id=?",(renewal["id"],))
                            summary["renewals_activated"]+=1
                            if pl and pl["user_id"]:
                                notify_user(c,pl["user_id"],"CONTRACT","Renewal begins",f"{pl['name']} remains with {team_name(c,con['franchise_id'])} at {float(renewal['salary']):.2f} XP/game for {int(renewal['years'])} season(s).",str(pid))
                            c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                                      ("RENEWAL_ACTIVATED",pl["user_id"] if pl else None,json.dumps({"player_id":pid,"franchise_id":con["franchise_id"],"salary":renewal["salary"],"years":renewal["years"],"season":next_season})))
                        else:
                            c.execute("DELETE FROM contracts WHERE player_id=?",(pid,))
                            c.execute("UPDATE roster_slots SET player_id=NULL,occupant_type='OPEN' WHERE player_id=?",(pid,))
                            c.execute("UPDATE players SET franchise_id=NULL,status='FREE_AGENT' WHERE id=? AND active=1",(pid,))
                            summary["contracts_expired"]+=1
                            if pl:
                                summary["free_agents"].append(pl["name"])
                                if pl["user_id"]:
                                    return_offer_candidates.append({
                                        "player_id":pid,
                                        "user_id":pl["user_id"],
                                        "player_name":pl["name"],
                                        "franchise_id":con["franchise_id"],
                                        "previous_salary":float(con["salary"] or SALARY_MIN)
                                    })
                                    notify_user(c,pl["user_id"],"CONTRACT","Contract expired",f"{pl['name']} is now an EBL free agent. Your former club will send a return offer for the new season.",str(pid))
                    else:
                        next_salary=round(float(con["salary"] or SALARY_MIN)+CONTRACT_ESCALATION,2)
                        c.execute("UPDATE contracts SET years_remaining=?,salary=? WHERE player_id=?",(remaining,next_salary,pid))
                        summary["contracts_advanced"]+=1








                c.execute("UPDATE players SET age=age+1 WHERE active=1")
                c.execute("UPDATE team_sponsorships SET status='EXPIRED' WHERE status='ACTIVE' AND end_season<?",(next_season,))








                cap_rows=c.execute("""SELECT p.id,p.user_id,p.name,p.franchise_id,p.age,p.career_extension_through,COUNT(sh.season) seasons_played
                                      FROM players p JOIN season_history sh ON sh.player_id=p.id
                                      WHERE p.active=1 GROUP BY p.id HAVING COUNT(sh.season)>=12""").fetchall()
                for pl in cap_rows:
                    pid=pl["id"]
                    seasons_played=int(pl["seasons_played"] or 0)
                    if not veteran_retirement_due(c,pid):
                        continue
                    # Preserve the final active contract in permanent history before
                    # retirement removes it from the live roster tables.
                    retiring_contract=c.execute("SELECT * FROM contracts WHERE player_id=?",(pid,)).fetchone()
                    if retiring_contract:
                        seen=c.execute("""SELECT 1 FROM contract_history WHERE player_id=? AND franchise_id=? AND ABS(salary-?)<0.0001 AND signed_at=? LIMIT 1""",
                                       (pid,retiring_contract["franchise_id"],retiring_contract["salary"],retiring_contract["signed_at"])).fetchone()
                        if not seen:
                            c.execute("""INSERT INTO contract_history(player_id,franchise_id,bonus,salary,years,signed_at,ended_at)
                                         VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                                      (pid,retiring_contract["franchise_id"],retiring_contract["bonus"],retiring_contract["salary"],max(1,int(retiring_contract["years_total"] or retiring_contract["years_remaining"] or 1)),retiring_contract["signed_at"]))
                    c.execute("DELETE FROM contracts WHERE player_id=?",(pid,))
                    c.execute("UPDATE offers SET status='CANCELLED_RETIRED' WHERE player_id=? AND status IN ('OPEN','HELD','ACCEPTED')",(pid,))
                    c.execute("UPDATE roster_slots SET player_id=NULL,occupant_type='OPEN' WHERE player_id=?",(pid,))
                    c.execute("UPDATE players SET active=0,status='RETIRED',franchise_id=NULL WHERE id=?",(pid,))
                    summary["retired"]+=1
                    if pl["user_id"]:
                        summary["retired_names"].append(pl["name"])
                    reason="12_SEASON_CPU_CAP" if pl["user_id"] is None else "VETERAN_EXTENSION_NOT_PURCHASED"
                    c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                              ("PLAYER_RETIRED",pl["user_id"],json.dumps({"player_id":pid,"player_name":pl["name"],"franchise_id":pl["franchise_id"],"reason":reason,"seasons_played":seasons_played})))
                    if pl["user_id"]:
                        next_cost=veteran_extension_cost(seasons_played)
                        notify_user(c,pl["user_id"],"CAREER","Veteran career complete",f"{pl['name']} completed {seasons_played} EBL seasons. The {next_cost:g} XP extension for career Season {seasons_played+1} was not purchased before rollover.",str(pid))








                economy_awards=apply_finish_economy(c,current_season,current_active)
                summary["franchise_economy"]=economy_awards
                for frrow in c.execute("SELECT * FROM franchises").fetchall():
                    fr=dict(frrow);budget=float(fr.get("xp_budget",TEAM_BUDGET) or TEAM_BUDGET);spent=float(fr.get("xp_spent",0) or 0)
                    unused=max(0.0,budget-spent)
                    reserve=float(fr.get("xp_reserve",0) or 0)+unused
                    fr["xp_reserve"]=reserve
                    # RC61: reserve is spendable next season, not merely tracked.
                    # annual_team_budget includes the 480 base, permanent standings growth, and revenue upgrades.
                    next_budget=round(annual_team_budget(fr)+reserve,3)
                    c.execute("""UPDATE franchises SET wins=0,losses=0,runs_for=0,runs_against=0,
                               xp_reserve=0,xp_spent=0,xp_budget=? WHERE id=?""",(next_budget,fr["id"]))








                if not c.execute("SELECT 1 FROM franchise_seasons WHERE season=? LIMIT 1",(next_season,)).fetchone():
                    set_season_membership(c,next_season,current_active)








                # Every human player whose deal expires gets a visible return offer from
                # the club they just played for. They can accept it, hold it, reject it,
                # or shop the wider market.
                for cand in return_offer_candidates:
                    if cand["franchise_id"] not in current_active:
                        continue
                    active=c.execute("SELECT active,status FROM players WHERE id=?",(cand["player_id"],)).fetchone()
                    if not active or not active["active"] or active["status"]!="FREE_AGENT":
                        continue
                    if c.execute("SELECT 1 FROM offers WHERE player_id=? AND franchise_id=? AND status IN ('OPEN','HELD')",(cand["player_id"],cand["franchise_id"])).fetchone():
                        continue
                    fr=c.execute("SELECT name,xp_budget,xp_spent FROM franchises WHERE id=?",(cand["franchise_id"],)).fetchone()
                    salary=minimum_offer_salary(c,cand["player_id"],cand["franchise_id"])








                    # RC59/RC60 — return offers spend from the same shared signing pool
                    # and can never undercut the player's career salary floor.
                    # The 16 league-minimum salaries are protected first; bonuses and
                    # salary premiums for signed contracts + OPEN/HELD offers all consume
                    # the remaining discretionary pool.
                    pool=signing_pool_state(c,cand["franchise_id"])
                    salary_premium=max(0.0,salary-SALARY_MIN)*REGULAR_SEASON_GAMES
                    available_bonus=max(0.0,pool["available"]-salary_premium)
                    bonus=round(min(5.0,available_bonus),1)








                    # If the mandatory returning-player raise itself cannot fit, do not
                    # create an impossible offer that could later overspend the club.
                    offer_cost=round(bonus+salary_premium,3)
                    if offer_cost>pool["available"]+1e-9:
                        continue








                    cur=c.execute("INSERT INTO offers(franchise_id,player_id,bonus,salary,years,status) VALUES(?,?,?,?,2,'OPEN')",(cand["franchise_id"],cand["player_id"],bonus,salary))
                    summary["return_offers"]+=1
                    if cand["user_id"]:
                        notify_user(c,cand["user_id"],"CONTRACT",f"Return offer from {fr['name'] if fr else cand['franchise_id']}",f"{bonus:g} XP bonus • {salary:g} XP/game • 2 years",str(cur.lastrowid))








                enforce_active_rosters(c,next_season)
                summary["rosters_rebuilt"]=True








                # Opening Day starts with every pitcher fully recovered.
                reset_pitcher_fatigue(c,"NEW_SEASON",season=next_season,league_day=0,announce=False)








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








                for key,value in (("season",str(next_season)),("league_day","0"),("phase","REGULAR"),("playoff_round",""),("champion",""),("pitcher_workload_season",str(next_season))):
                    c.execute("INSERT INTO league_state(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(key,value))
                c.execute("INSERT INTO league_config(k,v) VALUES('season_number',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(str(next_season),))
                post_news(c,"LEAGUE",f"Season {next_season} is open",f"A new EBL season begins. Rosters, contracts, standings, and statistics have rolled forward for Season {next_season}.",0,None,None,None,4,season=next_season)
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
                "SELECT id,name,franchise_id,primary_pos,position_group,type FROM players WHERE user_id IS NOT NULL AND active=1 AND status='SIGNED' AND franchise_id IS NOT NULL ORDER BY id"
            ).fetchall()
















            for pl in humans:
                current=c.execute(
                    "SELECT slot_no,position_group FROM roster_slots WHERE player_id=? LIMIT 1",
                    (pl["id"],)
                ).fetchone()
















                allowed=eligible_roster_slot_groups(dict(pl))
                if current and str(current["position_group"]).upper() in allowed:
                    skipped.append(pl["name"])
                else:
                    marks=",".join("?" for _ in allowed)
                    target=c.execute(
                        f"SELECT slot_no,player_id,position_group FROM roster_slots WHERE franchise_id=? AND position_group IN ({marks}) AND occupant_type IN ('CPU','OPEN') ORDER BY CASE WHEN position_group=? THEN 0 ELSE 1 END,CASE occupant_type WHEN 'CPU' THEN 0 ELSE 1 END,slot_no LIMIT 1",
                        (pl["franchise_id"],*allowed,pl["primary_pos"])
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
            
        if p=="/api/commish/supporter":
            u=self.auth(["COMMISSIONER"])
            if not u:return
            d=self.body()
            target=str(d.get("target","") or "").strip().lower()
            try:target_id=int(d.get("user_id") or 0)
            except Exception:target_id=0
            supporter=bool(d.get("supporter",True))
            expires_at=d.get("expires_at") or None
            if expires_at:
                try:
                    if parse_iso(str(expires_at))<=utcnow():return self.out({"error":"INVALID_EXPIRATION"},400)
                except Exception:return self.out({"error":"INVALID_EXPIRATION"},400)
            c=conn()
            row=None
            if target_id>0:row=c.execute("SELECT id,username FROM users WHERE id=?",(target_id,)).fetchone()
            elif target:
                row=c.execute("""SELECT u.id,u.username FROM users u LEFT JOIN user_security s ON s.user_id=u.id
                                 WHERE lower(u.username)=? OR lower(s.email)=? LIMIT 1""",(target,target)).fetchone()
            if not row:
                c.close();return self.out({"error":"ACCOUNT_NOT_FOUND"},404)
            ent=set_supporter_entitlement(c,int(row["id"]),supporter,source=str(d.get("source") or "COMMISSIONER"),expires_at=expires_at,note=str(d.get("note") or ""),external_ref=str(d.get("external_ref") or ""))
            c.commit();c.close()
            return self.out({"ok":True,"username":row["username"],"entitlements":ent})








        if p=="/api/commish/reset-test-account":
            u=self.auth(["COMMISSIONER"])
            if not u:return








            d=self.body()
            target=str(d.get("target","")).strip().lower()
            if not target:
                return self.out({"error":"TARGET_REQUIRED"},400)








            c=conn()
            try:
                row=c.execute(
                    "SELECT u.id,u.username,u.role,s.email FROM users u LEFT JOIN user_security s ON s.user_id=u.id WHERE lower(u.username)=? OR lower(s.email)=?",
                    (target,target)
                ).fetchone()
                if not row:
                    return self.out({"error":"ACCOUNT_NOT_FOUND"},404)








                uid=int(row["id"]);original_role=str(row["role"] or "PLAYER").upper()
                players=c.execute("SELECT id,franchise_id FROM players WHERE user_id=?",(uid,)).fetchall()
                player_ids=[int(x["id"]) for x in players]
                removed_players=0;restored_slots=0








                # Clear coach-only test state, but never remove COMMISSIONER authority.
                assigned=c.execute("SELECT COUNT(*) n FROM franchises WHERE owner_user_id=?",(uid,)).fetchone()
                coach_assignments=int(assigned["n"] or 0) if assigned else 0
                apps=c.execute("SELECT COUNT(*) n FROM coach_applications WHERE user_id=?",(uid,)).fetchone()
                coach_applications=int(apps["n"] or 0) if apps else 0
                c.execute("UPDATE franchises SET owner_user_id=NULL WHERE owner_user_id=?",(uid,))
                c.execute("DELETE FROM coach_applications WHERE user_id=?",(uid,))
                role_reset=False
                if original_role=="COACH":
                    c.execute("UPDATE users SET role='PLAYER' WHERE id=?",(uid,));role_reset=True








                for p_row in players:
                    pid=int(p_row["id"])
                    slots=c.execute("SELECT franchise_id,slot_no FROM roster_slots WHERE player_id=?",(pid,)).fetchall()
                    for slot in slots:
                        c.execute("UPDATE roster_slots SET player_id=NULL,occupant_type='OPEN' WHERE franchise_id=? AND slot_no=?",
                                  (slot["franchise_id"],slot["slot_no"]))
                        restored_slots+=1
                    c.execute("DELETE FROM offers WHERE player_id=?",(pid,))
                    c.execute("DELETE FROM contracts WHERE player_id=?",(pid,))
                    c.execute("DELETE FROM team_practice WHERE player_id=?",(pid,))
                    c.execute("DELETE FROM xp_ledger WHERE player_id=?",(pid,))
                    c.execute("DELETE FROM season_history WHERE player_id=?",(pid,))
                    c.execute("DELETE FROM player_championships WHERE player_id=?",(pid,))
                    c.execute("DELETE FROM award_history WHERE player_id=?",(pid,))
                    c.execute("DELETE FROM player_bonus_history WHERE player_id=?",(pid,))
                    c.execute("DELETE FROM league_records WHERE holder_type='PLAYER' AND holder_id=?",(str(pid),))
                    c.execute("UPDATE news SET player_id=NULL WHERE player_id=?",(pid,))
                    c.execute("UPDATE chat_messages SET player_id=NULL WHERE player_id=?",(pid,))
                    c.execute("DELETE FROM players WHERE id=?",(pid,))
                    removed_players+=1








                # Account identity/security/profile/friends/messages remain intact. Career-specific
                # notifications are cleared so the same login feels like a fresh player account.
                c.execute("DELETE FROM notifications WHERE user_id=?",(uid,))
                if player_ids:
                    c.execute("UPDATE users SET featured_player_id=NULL WHERE id=?",(uid,))








                enforce_active_rosters(c)
                resulting=c.execute("SELECT role FROM users WHERE id=?",(uid,)).fetchone()
                resulting_role=str(resulting["role"] if resulting else original_role)
                c.execute("INSERT INTO transactions(event_type,actor_user_id,payload_json) VALUES(?,?,?)",
                          ("TEST_PLAYER_STATE_RESET",u["id"],json.dumps({"target_user_id":uid,"username":row["username"],"removed_players":removed_players,"restored_slots":restored_slots,"original_role":original_role,"resulting_role":resulting_role})))
                c.commit()
                return self.out({
                    "ok":True,"username":row["username"],"email":row["email"],
                    "original_role":original_role,"resulting_role":resulting_role,
                    "removed_players":removed_players,"restored_slots":restored_slots,
                    "coach_state_cleared":{"assignments":coach_assignments,"applications":coach_applications,"role_reset":role_reset},
                    "login_preserved":True,"player_creator_ready":True
                })
            finally:
                c.close()








        # Every unknown mutation route must return a real HTTP response. Falling off
        # BaseHTTPRequestHandler makes reverse proxies report a misleading 502.
        return self.out({"error":"NOT_FOUND"},404)
















if __name__=="__main__":
    init_db()
    port=int(os.environ.get("PORT","8000"))
    print(f"EBL v7.8.1 Supporter Login Hotfix RC101: http://127.0.0.1:{port}")
    print("Privileged bootstrap accounts require explicit environment passwords; player accounts register in the UI.")
    host=os.environ.get("HOST","0.0.0.0")
    httpd=ThreadingHTTPServer((host,port),H)
    try:
        discord_bridge_bootstrap()
    except Exception as e:
        print(f"DISCORD BRIDGE BOOTSTRAP ERROR: {type(e).__name__}: {str(e)[:200]}")
    threading.Thread(target=discord_bridge_worker,daemon=True,name="EBL-DiscordBridge").start()
    threading.Thread(target=auto_advance_worker,args=(port,),daemon=True,name="EBL-AutoAdvance").start()
    httpd.serve_forever()








# EBL member profile identity layer: RC87








# RC89: sustainable franchise economy + veteran career extension








# EBL_STRIPE_VERIFIED_SUPPORTER_TEST_RC105








# EBL_RECURRING_SUPPORTER_RC109