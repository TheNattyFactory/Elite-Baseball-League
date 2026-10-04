"""Franchise identity defaults, artwork generation, and static brand asset helpers.

Legacy seed identifiers remain stable so existing databases can distinguish league-generated art
from coach-uploaded custom artwork.
"""
import base64
import math
import mimetypes
import os

from ebl_config import STATIC

# official EBL baseline branding. These are lightweight league defaults
# for CPU/unclaimed franchises. Existing uploaded/custom artwork is never overwritten.
OFFICIAL_BRAND_SEED_KEY="official_franchise_branding_rc122_static_assets_28teams_v1"
LEGACY_FRANCHISE_BRANDS={
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
















# league-wide production logo sets. These SVG data URIs give every
# franchise a coherent PRIMARY / SECONDARY / WORDMARK system while preserving
# any artwork a coach or commissioner has already uploaded.
# final commissioner-approved EBL franchise identities and palettes.
OFFICIAL_FRANCHISE_BRANDS={
    "EBL-F01":{'city': 'Atlanta', 'team': 'Scouts', 'primary': '#173F35', 'secondary': '#D7C7A1', 'accent': '#0A1D2A', 'style': 4, 'home': 'CREAM', 'away': 'NAVY'},
    "EBL-F02":{'city': 'New York', 'team': 'Empires', 'primary': '#111827', 'secondary': '#D4AF37', 'accent': '#F2F0E8', 'style': 8, 'home': 'WHITE', 'away': 'BLACK'},
    "EBL-F03":{'city': 'Los Angeles', 'team': 'Stars', 'primary': '#0B1F4A', 'secondary': '#F5C542', 'accent': '#FFFFFF', 'style': 2, 'home': 'WHITE', 'away': 'NAVY'},
    "EBL-F04":{'city': 'Chicago', 'team': 'Wind', 'primary': '#0B2545', 'secondary': '#69B8E5', 'accent': '#FFFFFF', 'style': 6, 'home': 'WHITE', 'away': 'NAVY'},
    "EBL-F05":{'city': 'Houston', 'team': 'Apollos', 'primary': '#0B1F3A', 'secondary': '#F47C20', 'accent': '#F4F1EA', 'style': 5, 'home': 'WHITE', 'away': 'NAVY'},
    "EBL-F06":{'city': 'New Orleans', 'team': 'Rougarou', 'primary': '#3B185F', 'secondary': '#D4AF37', 'accent': '#0F4C3A', 'style': 8, 'home': 'CREAM', 'away': 'BLACK'},
    "EBL-F07":{'city': 'Philadelphia', 'team': 'Founders', 'primary': '#17324D', 'secondary': '#A61B2B', 'accent': '#E7D9B5', 'style': 7, 'home': 'CREAM', 'away': 'NAVY'},
    "EBL-F08":{'city': 'Jackson', 'team': 'Catfish', 'primary': '#062A47', 'secondary': '#0E7490', 'accent': '#D4AF37', 'style': 6, 'home': 'CREAM', 'away': 'NAVY'},
    "EBL-F09":{'city': 'Birmingham', 'team': 'Hammers', 'primary': '#15191F', 'secondary': '#B7372F', 'accent': '#D9DDE2', 'style': 3, 'home': 'GRAY', 'away': 'BLACK'},
    "EBL-F10":{'city': 'Dallas', 'team': 'Wranglers', 'primary': '#17365D', 'secondary': '#8B5A2B', 'accent': '#F2E6C9', 'style': 1, 'home': 'CREAM', 'away': 'NAVY'},
    "EBL-F11":{'city': 'Jacksonville', 'team': 'Breakers', 'primary': '#062A47', 'secondary': '#00A9C6', 'accent': '#F2F7F7', 'style': 6, 'home': 'WHITE', 'away': 'NAVY'},
    "EBL-F12":{'city': 'Minneapolis', 'team': 'Northmen', 'primary': '#0B2545', 'secondary': '#1E5AA8', 'accent': '#D9B36C', 'style': 6, 'home': 'WHITE', 'away': 'NAVY'},
    "EBL-F13":{'city': 'St. Louis', 'team': 'Archers', 'primary': '#0B2545', 'secondary': '#C1121F', 'accent': '#D4AF37', 'style': 4, 'home': 'CREAM', 'away': 'NAVY'},
    "EBL-F14":{'city': 'San Jose', 'team': 'Circuit', 'primary': '#050505', 'secondary': '#00D1C7', 'accent': '#7CFF35', 'style': 9, 'home': 'WHITE', 'away': 'BLACK'},
    "EBL-F15":{'city': 'Columbus', 'team': 'Aviators', 'primary': '#123B63', 'secondary': '#C1121F', 'accent': '#D9E0E8', 'style': 6, 'home': 'WHITE', 'away': 'NAVY'},
    "EBL-F16":{'city': 'Charlotte', 'team': 'Crowns', 'primary': '#4B2E83', 'secondary': '#D4AF37', 'accent': '#111111', 'style': 5, 'home': 'WHITE', 'away': 'BLACK'},
    "EBL-F17":{'city': 'Indianapolis', 'team': 'Racers', 'primary': '#C1121F', 'secondary': '#111827', 'accent': '#F1FAEE', 'style': 3, 'home': 'WHITE', 'away': 'NAVY'},
    "EBL-F18":{'city': 'Wilmington', 'team': 'Admirals', 'primary': '#0B2545', 'secondary': '#0E7490', 'accent': '#D4AF37', 'style': 6, 'home': 'CREAM', 'away': 'NAVY'},
    "EBL-F19":{'city': 'Seattle', 'team': 'Evergreens', 'primary': '#0B5D3B', 'secondary': '#203A43', 'accent': '#DDE9E4', 'style': 6, 'home': 'WHITE', 'away': 'NAVY'},
    "EBL-F20":{'city': 'Denver', 'team': 'Summit', 'primary': '#0052CC', 'secondary': '#0B1F44', 'accent': '#D4AF37', 'style': 6, 'home': 'WHITE', 'away': 'NAVY'},
    "EBL-F21":{'city': 'Oklahoma City', 'team': 'Twisters', 'primary': '#0B1F44', 'secondary': '#00BCEB', 'accent': '#F7F9FC', 'style': 7, 'home': 'WHITE', 'away': 'NAVY'},
    "EBL-F22":{'city': 'Nashville', 'team': 'Sound', 'primary': '#14213D', 'secondary': '#D4AF37', 'accent': '#F6F1E1', 'style': 7, 'home': 'CREAM', 'away': 'NAVY'},
    "EBL-F23":{'city': 'Washington', 'team': 'Eagles', 'primary': '#0D2B4E', 'secondary': '#8B1538', 'accent': '#D4AF37', 'style': 5, 'home': 'WHITE', 'away': 'NAVY'},
    "EBL-F24":{'city': 'Las Vegas', 'team': 'High Rollers', 'primary': '#000000', 'secondary': '#8B0000', 'accent': '#D4AF37', 'style': 3, 'home': 'BLACK', 'away': 'RED'},
    "EBL-F25":{'city': 'Boston', 'team': 'Minutemen', 'primary': '#0B2545', 'secondary': '#A61B2B', 'accent': '#D8C3A5', 'style': 7, 'home': 'CREAM', 'away': 'NAVY'},
    "EBL-F26":{'city': 'Portland', 'team': 'Pioneers', 'primary': '#285943', 'secondary': '#6B4F2A', 'accent': '#E8E0C8', 'style': 6, 'home': 'CREAM', 'away': 'NAVY'},
    "EBL-F27":{'city': 'Detroit', 'team': 'Motors', 'primary': '#111820', 'secondary': '#D7262E', 'accent': '#BFC5CA', 'style': 4, 'home': 'GRAY', 'away': 'BLACK'},
    "EBL-F28":{'city': 'Louisville', 'team': 'Thoroughbreds', 'primary': '#6B0F1A', 'secondary': '#111111', 'accent': '#D4AF37', 'style': 5, 'home': 'WHITE', 'away': 'BLACK'},
    "EBL-F29":{'city': 'Memphis', 'team': 'Tigers', 'primary': '#071A31', 'secondary': '#0F4CC9', 'accent': '#F0A23A', 'style': 5, 'home': 'WHITE', 'away': 'NAVY'},
    "EBL-F30":{'city': 'Baltimore', 'team': 'Clippers', 'primary': '#111111', 'secondary': '#F05A16', 'accent': '#F1E3C6', 'style': 6, 'home': 'CREAM', 'away': 'NAVY'},
}
FORCE_OFFICIAL_IDENTITY_IDS={"EBL-F08","EBL-F13"}

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








def legacy_brand_art(brand):
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









# Premium franchise identity renderer. The legacy renderer remains above so
# the seed can identify exact league-generated art and safely replace only that.
def _brand_color_tuple(value):
    v=str(value or "#000000").strip().lstrip("#")
    if len(v)==3:
        v="".join(ch*2 for ch in v)
    try:
        return tuple(int(v[i:i+2],16) for i in (0,2,4))
    except Exception:
        return (0,0,0)


def _brand_mix(a,b,t):
    aa=_brand_color_tuple(a); bb=_brand_color_tuple(b)
    t=max(0.0,min(1.0,float(t)))
    vals=[round(aa[i]*(1-t)+bb[i]*t) for i in range(3)]
    return "#"+"".join(f"{max(0,min(255,v)):02X}" for v in vals)


def _premium_brand_motif(team,primary,secondary,accent):
    t=str(team or "").lower()
    if "scout" in t:
        compass=_brand_star_points(256,190,88,26,4)
        return f'<circle cx="256" cy="190" r="104" fill="{_brand_mix(primary,"#000000",.22)}" stroke="{secondary}" stroke-width="10"/><polygon points="{compass}" fill="{accent}" stroke="{secondary}" stroke-width="8"/><path d="M256 88 L270 167 L256 190 L242 167Z" fill="{secondary}"/><path d="M150 287 L190 226 H176 L210 178 L196 178 L229 128 L262 178 L248 178 L282 226 H268 L308 287Z" fill="{primary}" stroke="{accent}" stroke-width="5"/>'
    return _brand_motif(team,primary,secondary,accent)


def _premium_badge(style,primary,secondary,accent):
    dark=_brand_mix(primary,"#000000",.46)
    if style in (3,4):
        outer='M256 22 L448 96 V265 Q448 391 256 486 Q64 391 64 265 V96Z'
        inner='M256 54 L416 116 V258 Q416 365 256 448 Q96 365 96 258 V116Z'
        return f'<path d="{outer}" fill="url(#pbg)" stroke="{accent}" stroke-width="15"/><path d="{inner}" fill="none" stroke="{secondary}" stroke-width="9"/><path d="{inner}" fill="none" stroke="{accent}" stroke-opacity=".25" stroke-width="3" stroke-dasharray="11 9"/>'
    if style in (5,8):
        return f'<circle cx="256" cy="256" r="228" fill="url(#pbg)" stroke="{accent}" stroke-width="15"/><circle cx="256" cy="256" r="198" fill="none" stroke="{secondary}" stroke-width="10"/><circle cx="256" cy="256" r="174" fill="none" stroke="{accent}" stroke-opacity=".25" stroke-width="4"/>'
    if style in (6,9):
        return f'<polygon points="256,24 454,138 454,374 256,488 58,374 58,138" fill="url(#pbg)" stroke="{accent}" stroke-width="15"/><polygon points="256,58 424,155 424,357 256,454 88,357 88,155" fill="none" stroke="{secondary}" stroke-width="9"/><polygon points="256,76 407,164 407,348 256,436 105,348 105,164" fill="none" stroke="{accent}" stroke-opacity=".22" stroke-width="3" stroke-dasharray="10 8"/>'
    return f'<path d="M256 23 L472 256 L256 489 L40 256Z" fill="url(#pbg)" stroke="{accent}" stroke-width="15"/><path d="M256 58 L438 256 L256 454 L74 256Z" fill="none" stroke="{secondary}" stroke-width="9"/><path d="M256 78 L419 256 L256 434 L93 256Z" fill="none" stroke="{accent}" stroke-opacity=".22" stroke-width="3" stroke-dasharray="10 8"/>'


def _premium_title_size(team):
    n=len(str(team or ""))
    return 58 if n<=7 else (51 if n<=10 else (43 if n<=13 else 35))


def _premium_wordmark_size(team):
    n=len(str(team or ""))
    return 124 if n<=7 else (108 if n<=10 else (92 if n<=13 else 76))


def generated_official_brand_art(brand):
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
    dark=_brand_mix(primary,"#000000",.58)
    light=_brand_mix(accent,"#FFFFFF",.18)
    sec_light=_brand_mix(secondary,"#FFFFFF",.14)
    defs=f'<defs><linearGradient id="pbg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{_brand_mix(primary,"#FFFFFF",.10)}"/><stop offset=".56" stop-color="{primary}"/><stop offset="1" stop-color="{dark}"/></linearGradient><linearGradient id="metal" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{light}"/><stop offset=".48" stop-color="{accent}"/><stop offset="1" stop-color="{_brand_mix(accent,"#000000",.28)}"/></linearGradient><linearGradient id="teamG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{sec_light}"/><stop offset="1" stop-color="{secondary}"/></linearGradient><filter id="shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="8" stdDeviation="7" flood-color="#000" flood-opacity=".48"/></filter></defs>'
    badge=_premium_badge(style,primary,secondary,accent)
    motif=_premium_brand_motif(team,primary,secondary,accent)
    title_size=_premium_title_size(team)
    wm_size=_premium_wordmark_size(team)

    primary_svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><!-- EBL-RC116-PREMIUM -->{defs}<g filter="url(#shadow)">{badge}</g><path d="M130 88 Q256 51 382 88" fill="none" stroke="{secondary}" stroke-width="5"/><text x="256" y="105" text-anchor="middle" font-family="Arial Black,Impact,Arial,sans-serif" font-size="21" font-weight="900" letter-spacing="6" fill="{accent}">{city_e}</text><g transform="translate(0 24) scale(1 .94)" filter="url(#shadow)">{motif}</g><path d="M48 344 L112 319 H400 L464 344 L433 413 L256 442 L79 413Z" fill="{dark}" stroke="{accent}" stroke-width="11"/><path d="M79 347 H433 L407 397 Q256 425 105 397Z" fill="url(#teamG)" stroke="{primary}" stroke-width="5"/><text x="256" y="391" text-anchor="middle" font-family="Arial Black,Impact,Arial,sans-serif" font-size="{title_size}" font-weight="900" fill="{accent}" stroke="{dark}" stroke-width="8" paint-order="stroke">{team_e}</text><path d="M157 458 H355" stroke="{secondary}" stroke-width="9" stroke-linecap="round"/><polygon points="{_brand_star_points(256,458,14,6)}" fill="{accent}"/><text x="256" y="488" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="13" font-weight="800" letter-spacing="5" fill="{accent}" opacity=".82">ELITE BASEBALL</text></svg>'

    # Cap/scorebug mark: same club icon, tighter framing, prominent monogram.
    secondary_svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><!-- EBL-RC116-PREMIUM -->{defs}<g filter="url(#shadow)">{_premium_badge(5 if style in (1,3,4,7,8) else style,primary,secondary,accent)}</g><g transform="translate(38 42) scale(.85)" opacity=".98">{motif}</g><path d="M159 326 H353 L335 397 H177Z" fill="{dark}" stroke="{accent}" stroke-width="8"/><text x="256" y="383" text-anchor="middle" font-family="Arial Black,Impact,Arial,sans-serif" font-size="72" font-weight="900" fill="{accent}" stroke="{primary}" stroke-width="7" paint-order="stroke">{monogram}</text><text x="256" y="438" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="18" font-weight="900" letter-spacing="6" fill="{secondary}">{city_code}</text></svg>'

    # Merchandise/header wordmark with a mini crest and full outlined athletic type.
    wordmark_svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="360" viewBox="0 0 1200 360"><!-- EBL-RC116-PREMIUM -->{defs}<g transform="translate(-58 -76) scale(.68)" filter="url(#shadow)">{badge}{motif}</g><text x="758" y="96" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="42" font-weight="900" letter-spacing="13" fill="{secondary}">{city_e}</text><g transform="skewX(-7)"><text x="795" y="220" text-anchor="middle" font-family="Arial Black,Impact,Arial,sans-serif" font-size="{wm_size}" font-weight="900" fill="{primary}" stroke="{accent}" stroke-width="13" paint-order="stroke">{team_e}</text><text x="795" y="220" text-anchor="middle" font-family="Arial Black,Impact,Arial,sans-serif" font-size="{wm_size}" font-weight="900" fill="{primary}" stroke="{dark}" stroke-width="4" paint-order="stroke">{team_e}</text></g><path d="M340 266 H1120" stroke="{secondary}" stroke-width="16" stroke-linecap="round"/><path d="M500 297 H970" stroke="{accent}" stroke-width="6" stroke-linecap="round" opacity=".84"/><polygon points="{_brand_star_points(1050,297,15,6)}" fill="{secondary}"/></svg>'
    return {"primary":_brand_svg_uri(primary_svg),"secondary":_brand_svg_uri(secondary_svg),"wordmark":_brand_svg_uri(wordmark_svg)}

# Final franchise artwork map. Coach-owned F21 stays outside static defaults; files live in static/assets and are seeded
# into SQLite as self-contained data URIs while remaining replaceable by coach uploads.
PRODUCTION_BRAND_FILES={
    "EBL-F02":{'primary': 'assets/ebl-f02_primary.webp', 'secondary': 'assets/ebl-f02_secondary.webp', 'wordmark': 'assets/ebl-f02_wordmark.webp'},
    "EBL-F03":{'primary': 'assets/ebl-f03_primary.webp', 'secondary': 'assets/ebl-f03_secondary.webp', 'wordmark': 'assets/ebl-f03_wordmark.webp'},
    "EBL-F04":{'primary': 'assets/ebl-f04_primary.webp', 'secondary': 'assets/ebl-f04_secondary.webp', 'wordmark': 'assets/ebl-f04_wordmark.webp'},
    "EBL-F05":{'primary': 'assets/ebl-f05_primary.webp', 'secondary': 'assets/ebl-f05_secondary.webp', 'wordmark': 'assets/ebl-f05_wordmark.webp'},
    "EBL-F06":{'primary': 'assets/ebl-f06_primary.webp', 'secondary': 'assets/ebl-f06_secondary.webp', 'wordmark': 'assets/ebl-f06_wordmark.webp'},
    "EBL-F07":{'primary': 'assets/ebl-f07_primary.webp', 'secondary': 'assets/ebl-f07_secondary.webp', 'wordmark': 'assets/ebl-f07_wordmark.webp'},
    "EBL-F08":{'primary': 'assets/ebl-f08_primary.webp', 'secondary': 'assets/ebl-f08_secondary.webp', 'wordmark': 'assets/ebl-f08_wordmark.webp'},
    "EBL-F09":{'primary': 'assets/ebl-f09_primary.webp', 'secondary': 'assets/ebl-f09_secondary.webp', 'wordmark': 'assets/ebl-f09_wordmark.webp'},
    "EBL-F10":{'primary': 'assets/ebl-f10_primary.webp', 'secondary': 'assets/ebl-f10_secondary.webp', 'wordmark': 'assets/ebl-f10_wordmark.webp'},
    "EBL-F11":{'primary': 'assets/ebl-f11_primary.webp', 'secondary': 'assets/ebl-f11_secondary.webp', 'wordmark': 'assets/ebl-f11_wordmark.webp'},
    "EBL-F12":{'primary': 'assets/ebl-f12_primary.webp', 'secondary': 'assets/ebl-f12_secondary.webp', 'wordmark': 'assets/ebl-f12_wordmark.webp'},
    "EBL-F13":{'primary': 'assets/ebl-f13_primary.webp', 'secondary': 'assets/ebl-f13_secondary.webp', 'wordmark': 'assets/ebl-f13_wordmark.webp'},
    "EBL-F14":{'primary': 'assets/ebl-f14_primary.webp', 'secondary': 'assets/ebl-f14_secondary.webp', 'wordmark': 'assets/ebl-f14_wordmark.webp'},
    "EBL-F15":{'primary': 'assets/ebl-f15_primary.webp', 'secondary': 'assets/ebl-f15_secondary.webp', 'wordmark': 'assets/ebl-f15_wordmark.webp'},
    "EBL-F16":{'primary': 'assets/ebl-f16_primary.webp', 'secondary': 'assets/ebl-f16_secondary.webp', 'wordmark': 'assets/ebl-f16_wordmark.webp'},
    "EBL-F17":{'primary': 'assets/ebl-f17_primary.webp', 'secondary': 'assets/ebl-f17_secondary.webp', 'wordmark': 'assets/ebl-f17_wordmark.webp'},
    "EBL-F18":{'primary': 'assets/ebl-f18_primary.webp', 'secondary': 'assets/ebl-f18_secondary.webp', 'wordmark': 'assets/ebl-f18_wordmark.webp'},
    "EBL-F19":{'primary': 'assets/ebl-f19_primary.webp', 'secondary': 'assets/ebl-f19_secondary.webp', 'wordmark': 'assets/ebl-f19_wordmark.webp'},
    "EBL-F20":{'primary': 'assets/ebl-f20_primary.webp', 'secondary': 'assets/ebl-f20_secondary.webp', 'wordmark': 'assets/ebl-f20_wordmark.webp'},
    "EBL-F22":{'primary': 'assets/ebl-f22_primary.webp', 'secondary': 'assets/ebl-f22_secondary.webp', 'wordmark': 'assets/ebl-f22_wordmark.webp'},
    "EBL-F23":{'primary': 'assets/ebl-f23_primary.webp', 'secondary': 'assets/ebl-f23_secondary.webp', 'wordmark': 'assets/ebl-f23_wordmark.webp'},
    "EBL-F24":{'primary': 'assets/ebl-f24_primary.webp', 'secondary': 'assets/ebl-f24_secondary.webp', 'wordmark': 'assets/ebl-f24_wordmark.webp'},
    "EBL-F25":{'primary': 'assets/ebl-f25_primary.webp', 'secondary': 'assets/ebl-f25_secondary.webp', 'wordmark': 'assets/ebl-f25_wordmark.webp'},
    "EBL-F26":{'primary': 'assets/ebl-f26_primary.webp', 'secondary': 'assets/ebl-f26_secondary.webp', 'wordmark': 'assets/ebl-f26_wordmark.webp'},
    "EBL-F27":{'primary': 'assets/ebl-f27_primary.png', 'secondary': 'assets/ebl-f27_secondary.png', 'wordmark': 'assets/ebl-f27_wordmark.png'},
    "EBL-F28":{'primary': 'assets/ebl-f28_primary.webp', 'secondary': 'assets/ebl-f28_secondary.webp', 'wordmark': 'assets/ebl-f28_wordmark.webp'},
    "EBL-F29":{'primary': 'assets/ebl-f29_primary.webp', 'secondary': 'assets/ebl-f29_secondary.webp', 'wordmark': 'assets/ebl-f29_wordmark.webp'},
    "EBL-F30":{'primary': 'assets/ebl-f30_primary.webp', 'secondary': 'assets/ebl-f30_secondary.webp', 'wordmark': 'assets/ebl-f30_wordmark.webp'},
}

def branding_assets_ready(fid):
    """Return True when this franchise's complete 3-piece static brand set exists."""
    try:
        files=PRODUCTION_BRAND_FILES.get(str(fid or "")) or {}
        return set(files)=={"primary","secondary","wordmark"} and all(
            os.path.isfile(os.path.join(STATIC,name)) for name in files.values()
        )
    except Exception:
        return False

def brand_seed_key(fid):
    return f"{OFFICIAL_BRAND_SEED_KEY}:{str(fid or '').lower()}"

def _official_static_art_data_uri(asset_name):
    try:
        path=os.path.join(STATIC,asset_name)
        with open(path,"rb") as f:
            raw=f.read()
        mime=mimetypes.guess_type(path)[0] or "application/octet-stream"
        return f"data:{mime};base64,"+base64.b64encode(raw).decode("ascii")
    except Exception:
        return ""

def official_brand_art(brand,fid=None):
    files=PRODUCTION_BRAND_FILES.get(str(fid or ""))
    if files:
        art={k:_official_static_art_data_uri(v) for k,v in files.items()}
        if all(art.values()):
            return art
    return generated_official_brand_art(brand)
