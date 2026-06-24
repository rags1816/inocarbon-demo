#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║   i-NoCarbon Freemium v5                             ║
║   Multi-food · Multi-transport · Smart recs          ║
║   Water (business) · Optimise scenario               ║
║   Port: 5002                                         ║
╚══════════════════════════════════════════════════════╝
"""
import sys, os, sqlite3
from flask import session, Flask, render_template, request, jsonify

sys.path.insert(0, r'C:\iNoCarbon-shared')

from shared.emission_factors import get_factor, FACTORS_BY_KEY
from shared.benchmarks       import (UK_MONTHLY_AVERAGE_KG, UK_ANNUAL_AVERAGE_KG,
                                     UK_MONTHLY_BY_CATEGORY, get_comparison_band)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('FREEMIUM_SECRET', 'freemium-dev-key')
port = int(os.environ.get('FREEMIUM_PORT', 5002))   # module-level: needed by /api/admin/stats regardless of launch method (gunicorn, direct run, etc.)

# ══════════════════════════════════════════════════════════════════════════════
# AUTH SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
#
# TWO user types:
#
# 1. ADMIN — logs in at /login with ADMIN_USER + ADMIN_PASS from .env
#            Gets: full calculator + floating admin panel (AI toggle,
#            session stats, lead list). AI toggle affects ALL users globally.
#            Example .env:
#                ADMIN_USER=admin
#                ADMIN_PASS=iNC@2026
#
# 2. REGULAR USER — enters any 4-digit PIN at /pin
#            Gets: full calculator, no admin panel, no AI toggle badge.
#            Set DEMO_PINS in .env to restrict which PINs are accepted.
#            Leave DEMO_PINS unset to accept any 4-digit PIN.
#            Example .env:
#                DEMO_PINS=1111,2222,9999
#
# Data isolation: saves/history are scoped per PIN (or per admin session).
# Different browsers are already isolated by Flask sessions.
# Same browser, different PIN = different isolated data.
#
# ── Credentials ──────────────────────────────────────────────────────────────
DEMO_PINS_RAW = os.environ.get('DEMO_PINS', '').strip()
ALLOWED_PINS  = set(
    p.strip() for p in DEMO_PINS_RAW.split(',')
    if p.strip().isdigit()
) if DEMO_PINS_RAW else None
# None = any 4-digit PIN accepted; set = only listed PINs accepted

def _get_admin_creds():
    """Read admin credentials from env (re-read each call so .env changes take effect)."""
    return (
        os.environ.get('ADMIN_USER', 'admin').strip(),
        os.environ.get('ADMIN_PASS', '').strip(),   # empty = admin login disabled
    )

# ── Session helpers ───────────────────────────────────────────────────────────
def is_admin():
    """True if current session is an authenticated admin."""
    return session.get('role') == 'admin'

def is_user():
    """True if current session has a valid PIN."""
    pin = session.get('demo_pin')
    if not pin: return False
    if ALLOWED_PINS is not None: return pin in ALLOWED_PINS
    return len(pin) == 4 and pin.isdigit()

def is_authenticated():
    """True if admin OR valid PIN user."""
    return is_admin() or is_user()

def get_pin():
    """Return the current session PIN, or 'admin' for admin sessions."""
    if is_admin(): return 'admin'
    return session.get('demo_pin')

def require_auth(f):
    """Decorator: redirect to entry page if not authenticated."""
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if is_admin() or is_user():
            return f(*args, **kwargs)
        from flask import redirect
        return redirect('/entry')
    return wrapper

def require_admin(f):
    """Decorator: return 403 if not admin."""
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_admin():
            return jsonify({'status': 'error', 'message': 'Admin only'}), 403
        return f(*args, **kwargs)
    return wrapper

# ── Shared entry page (choose: admin login or PIN) ────────────────────────────
_ENTRY_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="description" content="Sign in to the i-NoCarbon Freemium platform to calculate and optimize your business and household carbon footprint.">
<title>i-NoCarbon — Sign in</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0;font-family:Roboto,Arial,sans-serif}}
body{{background:#1B5E20;min-height:100vh;display:flex;align-items:center;
  justify-content:center;padding:20px}}
.wrap{{display:flex;flex-direction:column;gap:14px;width:100%;max-width:340px}}
.card{{background:white;border-radius:16px;padding:28px 24px;
  box-shadow:0 8px 32px rgba(0,0,0,.3)}}
.logo{{width:56px;height:56px;border-radius:50%;border:3px solid #2E7D32;
  margin:0 auto 12px;display:block}}
h2{{font-size:17px;font-weight:700;color:#1B5E20;text-align:center;margin-bottom:4px}}
.sub{{font-size:11px;color:#9E9E9E;text-align:center;margin-bottom:18px}}
.field{{margin-bottom:10px}}
label{{font-size:10px;font-weight:700;color:#757575;text-transform:uppercase;
  letter-spacing:.05em;display:block;margin-bottom:4px}}
input[type=text],input[type=password]{{width:100%;padding:10px 12px;
  font-size:14px;border:1.5px solid #E0E0E0;border-radius:8px;outline:none;
  color:#212121;background:#FAFAFA}}
input[type=text]:focus,input[type=password]:focus{{border-color:#2E7D32}}
input.pin-input{{font-size:24px;text-align:center;letter-spacing:.3em;
  font-family:monospace}}
.btn{{width:100%;padding:12px;background:#2E7D32;color:white;border:none;
  border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;margin-top:4px}}
.btn:hover{{background:#1B5E20}}
.err{{background:#FFEBEE;color:#C62828;border-radius:6px;padding:8px 12px;
  font-size:11px;margin-bottom:10px}}
.divider{{display:flex;align-items:center;gap:8px;margin:6px 0}}
.divider::before,.divider::after{{content:"";flex:1;height:1px;background:#E0E0E0}}
.divider span{{font-size:10px;color:#BDBDBD;white-space:nowrap}}
.note{{font-size:9px;color:#BDBDBD;text-align:center;margin-top:10px;line-height:1.6}}
.badge{{display:inline-block;font-size:9px;font-weight:700;padding:2px 7px;
  border-radius:10px;vertical-align:middle;margin-left:4px}}
.badge-admin{{background:#E3F2FD;color:#1565C0}}
.badge-user{{background:#E8F5E9;color:#2E7D32}}
</style>
</head>
<body>
<div class="wrap">
  <h1 style="color:white;font-size:24px;font-weight:700;text-align:center;margin-bottom:8px;font-family:inherit;">i-NoCarbon <span style="font-weight:300;opacity:0.85;">Freemium</span></h1>
  <img class="logo" src="/static/icon-192.png"
       onerror="this.style.display='none'" alt="i-NoCarbon">

  <!-- Admin login -->
  <div class="card">
    <h2>Admin login <span class="badge badge-admin">🔧 Admin</span></h2>
    <div class="sub">Full access + admin panel</div>
    {admin_error}
    <form method="POST" action="/login">
      <div class="field">
        <label>Username</label>
        <input type="text" name="username" autocomplete="off"
               placeholder="admin" value="{username_val}">
      </div>
      <div class="field">
        <label>Password</label>
        <input type="password" name="password" autocomplete="off"
               placeholder="••••••••">
      </div>
      <button class="btn" type="submit">Sign in as Admin →</button>
    </form>
  </div>

  <div class="divider"><span>or enter as a user</span></div>

  <!-- PIN entry -->
  <div class="card">
    <h2>User PIN <span class="badge badge-user">👤 User</span></h2>
    <div class="sub">Calculator access · private session</div>
    {pin_error}
    <form method="POST" action="/pin">
      <div class="field">
        <label>4-digit PIN</label>
        <input class="pin-input" type="text" name="pin"
               inputmode="numeric" pattern="[0-9]{{4}}" maxlength="4"
               placeholder="• • • •" autocomplete="off">
      </div>
      <button class="btn" type="submit">Enter as User →</button>
    </form>
    <div class="note">Each PIN is a private session stored in your browser.<br>
      Saves and calculations will be cleared if you close your session, clear browser cookies/data, or use private mode.</div>
  </div>
</div>
</body>
</html>'''

@app.route('/entry')
def entry():
    """Combined entry page — choose admin login or PIN."""
    if is_authenticated():
        from flask import redirect
        return redirect('/')
    return _ENTRY_HTML.format(
        admin_error='', pin_error='',
        username_val='',
    )

@app.route('/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login handler."""
    from flask import redirect
    if is_admin():
        return redirect('/')
    if request.method == 'GET':
        return redirect('/entry')

    username = (request.form.get('username') or '').strip()
    password = (request.form.get('password') or '').strip()
    admin_user, admin_pass = _get_admin_creds()

    if not admin_pass:
        err = "<div class='err'>Admin login is disabled — set ADMIN_PASS in .env</div>"
        return _ENTRY_HTML.format(
            admin_error=err, pin_error='',
            username_val=username,
        )

    if username == admin_user and password == admin_pass:
        session.clear()
        session['role']        = 'admin'
        session['admin_user']  = username
        session.modified       = True
        return redirect('/')

    err = "<div class='err'>Incorrect username or password.</div>"
    return _ENTRY_HTML.format(
        admin_error=err, pin_error='',
        username_val=username,
    )

@app.route('/pin', methods=['GET', 'POST'])
def pin_entry():
    """PIN entry handler for regular users."""
    from flask import redirect
    if is_authenticated():
        return redirect('/')
    if request.method == 'GET':
        return redirect('/entry')

    if not _user_access_enabled():
        err = "<div class='err'>User calculator access is currently disabled. Please contact info@i-nocarbon.com to request access.</div>"
        return _ENTRY_HTML.format(
            admin_error='', pin_error=err,
            username_val='',
        )

    pin = (request.form.get('pin') or '').strip()
    if len(pin) == 4 and pin.isdigit():
        if ALLOWED_PINS is None or pin in ALLOWED_PINS:
            session.clear()
            session['demo_pin'] = pin
            session['role']     = 'user'
            session.modified    = True
            return redirect('/')
        err = "<div class='err'>PIN not recognised. Check with the demo host.</div>"
    else:
        err = "<div class='err'>Please enter exactly 4 digits.</div>"

    return _ENTRY_HTML.format(
        admin_error='', pin_error=err,
        username_val='',
    )

@app.route('/demo')
def demo_tour_entry():
    """Auto-authenticates a user and starts the interactive demo tour."""
    session.clear()
    session['demo_pin'] = '9999'
    session['role']     = 'user'
    session.modified    = True
    from flask import redirect
    return redirect('/?mode=demo')

@app.route('/logout')
def logout():
    """Clear session and return to entry page."""
    session.clear()
    from flask import redirect
    return redirect('/entry')

# ── End auth system ───────────────────────────────────────────────────────────

import urllib.request as _ur
import urllib.error as _ue

_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

def _load_dotenv():
    if not os.path.exists(_ENV_FILE): return
    with open(_ENV_FILE, encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith('#') or '=' not in _line: continue
            _k, _, _v = _line.partition('=')
            _k = _k.strip(); _v = _v.strip()
            if _k and _k not in os.environ: os.environ[_k] = _v

_load_dotenv()

def _get_api_key():
    return os.environ.get('ANTHROPIC_API_KEY', '').strip()

def _get_gemini_key():
    return os.environ.get('GEMINI_API_KEY', '').strip()

def _get_rate_limit_value():
    try:
        return int(os.environ.get('AI_MAX_PER_HOUR', '20').strip())
    except ValueError:
        return 20

def _save_env_var(key, val):
    lines = []
    if os.path.exists(_ENV_FILE):
        with open(_ENV_FILE, encoding='utf-8') as _f:
            for l in _f:
                if not l.startswith(f'{key}='):
                    lines.append(l)
    if val is not None:
        lines.append(f'{key}={val}\n')
        os.environ[key] = str(val)
    else:
        os.environ.pop(key, None)
    with open(_ENV_FILE, 'w', encoding='utf-8') as _f:
        _f.writelines(lines)

def _save_api_keys(anthropic_key=None, gemini_key=None):
    lines = []
    if os.path.exists(_ENV_FILE):
        with open(_ENV_FILE, encoding='utf-8') as _f:
            for l in _f:
                if not l.startswith('ANTHROPIC_API_KEY=') and not l.startswith('GEMINI_API_KEY='):
                    lines.append(l)
    
    a_val = anthropic_key.strip() if anthropic_key is not None else os.environ.get('ANTHROPIC_API_KEY', '').strip()
    g_val = gemini_key.strip() if gemini_key is not None else os.environ.get('GEMINI_API_KEY', '').strip()
    
    if a_val:
        lines.append(f'ANTHROPIC_API_KEY={a_val}\n')
        os.environ['ANTHROPIC_API_KEY'] = a_val
    else:
        os.environ.pop('ANTHROPIC_API_KEY', None)
        
    if g_val:
        lines.append(f'GEMINI_API_KEY={g_val}\n')
        os.environ['GEMINI_API_KEY'] = g_val
    else:
        os.environ.pop('GEMINI_API_KEY', None)
        
    with open(_ENV_FILE, 'w', encoding='utf-8') as _f:
        _f.writelines(lines)




@app.after_request
def no_cache(response):
    """Prevent browser caching during development — ensures fresh JS on every load."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma']        = 'no-cache'
    response.headers['Expires']       = '0'
    response.headers['ngrok-skip-browser-warning'] = 'true'  # suppress ngrok interstitial page
    return response

# ── UK Prices ──────────────────────────────────────────────────────────────
# These are fallback defaults only. The values actually served to the app
# come from get_current_prices() below, which reads admin-updated values
# from .env first (set via the Admin panel "Update pricing & sources"
# button — see request for a declared, refreshable source) and falls back
# to these defaults if nothing has been saved yet. This avoids prices being
# silently baked into source code and going stale (e.g. the previous
# "Ofgem Q2 2026" figures were already out of date by 1 July 2026).
_PRICE_DEFAULTS = {
    "elec_p_kwh":     26.11,   # Ofgem price cap, Jul-Sep 2026
    "gas_p_kwh":       7.33,   # Ofgem price cap, Jul-Sep 2026
    "petrol_p_litre": 155.5,   # DESNZ Weekly Road Fuel Prices, w/c 15 Jun 2026
    "diesel_p_litre": 176.7,   # DESNZ Weekly Road Fuel Prices, w/c 15 Jun 2026
    "water_p_m3":    177.0,
    "hotel_avg_night": 80.0,   # average UK hotel room £/night
}
_PRICE_SOURCE_DEFAULT = "Ofgem Q3 2026 cap · DESNZ Weekly Road Fuel Prices (w/c 15 Jun 2026)"
_PRICE_ENV_KEYS = {
    "elec_p_kwh":      "PRICE_ELEC_P_KWH",
    "gas_p_kwh":       "PRICE_GAS_P_KWH",
    "petrol_p_litre":  "PRICE_PETROL_P_LITRE",
    "diesel_p_litre":  "PRICE_DIESEL_P_LITRE",
    "water_p_m3":      "PRICE_WATER_P_M3",
    "hotel_avg_night": "PRICE_HOTEL_AVG_NIGHT",
}

def get_current_prices():
    """Current pricing dict — admin-saved .env values override the hardcoded
    defaults above. Call this fresh each request so admin updates apply
    immediately, with no restart needed."""
    out = dict(_PRICE_DEFAULTS)
    for key, env_key in _PRICE_ENV_KEYS.items():
        raw = os.environ.get(env_key, '').strip()
        if raw:
            try:
                out[key] = float(raw)
            except ValueError:
                pass
    return out

def get_price_source_label():
    return os.environ.get('PRICE_SOURCE_LABEL', '').strip() or _PRICE_SOURCE_DEFAULT

def get_price_updated_date():
    return os.environ.get('PRICE_UPDATED_DATE', '').strip()

def get_hotel_ef_uk_average():
    raw = os.environ.get('HOTEL_EF_UK_AVERAGE', '').strip()
    if raw:
        try: return float(raw)
        except ValueError: pass
    return HOTEL_EF['uk_average']

def save_source_data(values: dict):
    """Persist admin-edited pricing/source values to .env. Any key not
    supplied is left unchanged. Always stamps PRICE_UPDATED_DATE."""
    from datetime import date
    for key, env_key in _PRICE_ENV_KEYS.items():
        if key in values and values[key] not in (None, ''):
            try:
                _save_env_var(env_key, str(float(values[key])))
            except (TypeError, ValueError):
                pass
    if values.get('hotel_ef_uk_average') not in (None, ''):
        try:
            _save_env_var('HOTEL_EF_UK_AVERAGE', str(float(values['hotel_ef_uk_average'])))
        except (TypeError, ValueError):
            pass
    if values.get('price_source_label'):
        _save_env_var('PRICE_SOURCE_LABEL', str(values['price_source_label']).strip())
    _save_env_var('PRICE_UPDATED_DATE', date.today().isoformat())

# ── Petrol/diesel transport costs — derived from real pump prices ───────────
# Typical UK real-world fuel consumption by vehicle class (L/100km). These
# are editable estimates (AA/WhatCar typical real-world averages, not
# official lab-test figures) — used to turn a pump price into a £/km cost
# instead of a flat guessed rate.
FUEL_CONSUMPTION_L_PER_100KM = {
    "petrol_car_avg":     7.0,
    "diesel_car_avg":     6.0,
    "hybrid_car":         4.5,   # petrol-equivalent, partial electric assist
    "petrol_small":       6.0,
    "petrol_large":       9.5,
    "diesel_van_medium":  9.0,
    "diesel_van_large":  12.0,
    "motorbike":          4.0,
}
FUEL_CONSUMPTION_SOURCE = "Typical UK real-world consumption, AA/WhatCar averages"

def _fuel_cost_per_km(key, prices):
    """£/km for a petrol/diesel/hybrid mode, computed from the current pump
    price and a typical consumption figure. Returns None for any mode not
    in FUEL_CONSUMPTION_L_PER_100KM (EV/public transport/taxi/flights keep
    their static TRANSPORT_MAP estimate instead)."""
    consumption = FUEL_CONSUMPTION_L_PER_100KM.get(key)
    if consumption is None:
        return None
    price_per_litre_p = prices['diesel_p_litre'] if key.startswith('diesel') else prices['petrol_p_litre']
    return round(price_per_litre_p * consumption / 10000.0, 4)   # pence/litre -> £/km


# ── Regional emission factors (from full version) ─────────────────────────────
EF_REGIONAL = {
    'UK':   {'elec': 0.19553, 'gas': 0.18296, 'water': 0.14900, 'oil': 0.24597, 'lpg': 0.21444,
             'source': 'DESNZ 2025 (UK)', 'label': '🇬🇧 UK',
             'links': {
                'DESNZ 2025': 'https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting',
                'Ofgem price cap': 'https://www.ofgem.gov.uk/check-if-energy-price-cap-affects-you'
             }},
    'EU':   {'elec': 0.23300, 'gas': 0.20200, 'water': 0.14900, 'oil': 0.24597, 'lpg': 0.21444,
             'source': 'EEA 2024 (EU)', 'label': '🇪🇺 European Union',
             'links': {
                'EEA 2024': 'https://www.eea.europa.eu/data-and-maps/data/co2-intensity-of-electricity-generation'
             }},
    'US':   {'elec': 0.37100, 'gas': 0.18100, 'water': 0.14900, 'oil': 0.24597, 'lpg': 0.21444,
             'source': 'EPA 2024 (US)', 'label': '🇺🇸 United States',
             'links': {
                'EPA 2024': 'https://www.epa.gov/climateleadership/ghg-emission-factors-hub'
             }},
    'INTL': {'elec': 0.48500, 'gas': 0.20100, 'water': 0.14900, 'oil': 0.24597, 'lpg': 0.21444,
             'source': 'IEA 2024 (International)', 'label': '🌍 International / Global',
             'links': {
                'IEA 2024': 'https://www.iea.org/data-and-statistics',
                'IPCC Tier 1': 'https://www.ipcc.ch/report/2006-ipcc-guidelines-for-national-greenhouse-gas-inventories/'
             }},
}

def get_regional_ef(region, key):
    """Get emission factor for a key, adjusted for region."""
    r = EF_REGIONAL.get(region, EF_REGIONAL['UK'])
    return r.get(key, EF_REGIONAL['UK'].get(key, 0))

# ── Food definitions ──────────────────────────────────────────────────────────
# Each item: key, display name, emoji, unit, ef (kg CO2e/unit),
#            typical_monthly_kg (for cost estimate), cost_per_kg (£)
#
# SOURCE NOTE: DEFRA/DESNZ's official "Government Conversion Factors for Company
# Reporting" does NOT publish per-kg food-production emission factors (it covers
# fuels, electricity, transport, waste, water and business travel only). These
# food figures are the widely-used global average values from Poore & Nemecek
# (2018, Science) — the largest peer-reviewed meta-analysis of food carbon
# footprints to date — as popularised via Our World in Data. This is a credible,
# industry-standard reference, just not a DEFRA dataset, so it must be cited
# correctly wherever these numbers are shown.
FOOD_SOURCE_LABEL = "Poore & Nemecek (2018), via Our World in Data"
FOOD_SOURCE_URL    = "https://ourworldindata.org/environmental-impacts-of-food"
FOOD_ITEMS = [
    # key            name              emoji  unit      ef       typ_kg  £/kg
    ("food_beef",    "Beef",           "🥩",  "kg",    27.000,   1.0,   12.0),
    ("food_lamb",    "Lamb",           "🐑",  "kg",    39.200,   0.5,   14.0),
    ("food_pork",    "Pork",           "🥓",  "kg",     7.600,   1.0,    8.0),
    ("food_chicken", "Chicken",        "🍗",  "kg",     5.400,   1.5,    6.0),
    ("food_fish",    "Fish",           "🐟",  "kg",     5.400,   1.0,   10.0),
    ("food_milk",    "Dairy milk",     "🥛",  "litre",  2.790,   8.0,    1.1),
    ("food_cheese",  "Cheese",         "🧀",  "kg",     9.800,   0.5,   10.0),
    ("food_eggs",    "Eggs",           "🥚",  "kg",     3.900,   0.5,    3.5),
    ("food_bread",   "Bread and grains", "🍞",  "kg",     1.190,   2.0,    2.0),
    ("food_rice",    "Rice and pasta",   "🍚",  "kg",     1.570,   1.0,    1.5),
    ("food_veg",     "Vegetables",     "🥦",  "kg",     0.580,   3.0,    2.5),
    ("food_fruit",   "Fruit",          "🍎",  "kg",     0.670,   2.0,    2.5),
    ("food_tofu",    "Tofu and legumes", "🌱",  "kg",     2.000,   0.5,    3.0),
]
FOOD_MAP = {f[0]: f for f in FOOD_ITEMS}

# Frequency → monthly kg multiplier (rough portions per week × 4.33)
FREQ_KG = {
    "never":       0.0,
    "rarely":      0.25,   # once or twice a month
    "weekly":      0.5,    # once a week × 4.33 ÷ some portion
    "several":     1.2,    # several times a week
    "daily":       2.5,    # daily
}

# Food tooltip descriptions shown on hover
FOOD_TOOLTIPS = {
    "food_beef":    "Highest carbon food — cattle produce methane. Even small reductions make a big difference.",
    "food_lamb":    "Highest carbon food of all — even higher than beef per kg.",
    "food_pork":    "Medium impact — about 5× lower than beef.",
    "food_chicken": "Lower impact — includes fried chicken, roast chicken, chicken curry, nuggets.",
    "food_fish":    "Similar to chicken. Includes all seafood.",
    "food_milk":    "Measured per litre. Includes milk in tea, coffee, cereal.",
    "food_cheese":  "Higher impact than milk — takes ~10 litres of milk to make 1 kg of cheese.",
    "food_eggs":    "Moderate impact. Per dozen eggs ≈ 1.8 kg CO₂e.",
    "food_bread":   "Low impact. Includes cereals, oats, flour.",
    "food_rice":    "Low-medium impact. Includes pasta, noodles.",
    "food_veg":     "Very low impact. All fresh, frozen and tinned vegetables.",
    "food_fruit":   "Very low impact. All fresh, frozen and tinned fruit.",
    "food_tofu":    "Low impact. Includes beans, lentils, chickpeas, tofu.",
}

# ── Transport definitions ─────────────────────────────────────────────────────
TRANSPORT_MODES = [
    # key                    label                            emoji  ef_key                  £/km
    ("petrol_car_avg",      "Petrol car (average)",          "🚗",  "petrol_car_avg",       0.14),
    ("diesel_car_avg",      "Diesel car (average)",          "🚕",  "diesel_car_avg",       0.14),
    ("electric_car",        "Electric car",                  "⚡",  "electric_car",         0.05),
    ("hybrid_car",          "Hybrid car",                    "🔋",  "hybrid_car",           0.10),
    ("phev_charged",        "Plug-in hybrid (PHEV)",         "🔌",  "phev_charged",         0.08),
    ("petrol_small",        "Petrol car (small)",            "🚙",  "petrol_small",         0.12),
    ("petrol_large",        "Petrol/SUV (large)",            "🛻",  "petrol_large",         0.18),
    ("diesel_van_medium",   "Diesel van (medium)",           "🚐",  "diesel_van_medium",    0.18),
    ("diesel_van_large",    "Diesel van (large)",            "🚛",  "diesel_van_large",     0.22),
    ("electric_van",        "Electric van",                  "🔋",  "electric_van",         0.06),
    ("national_rail",       "Train",                         "🚆",  "national_rail",        0.16),
    ("bus_local",           "Bus",                           "🚌",  "bus_local",            0.12),
    ("tube",                "London Underground",            "🚇",  "tube",                 0.13),
    ("motorbike",           "Motorbike",                     "🏍️",  "motorbike",            0.10),
    ("bicycle",             "Bicycle / e-bike",              "🚲",  "bicycle",              0.0),
    ("walking",             "Walking",                       "🚶",  "walking",              0.0),
    ("taxi",                "Taxi / Uber",                   "🚖",  "taxi",                 0.20),
    ("flight_short_economy","Short-haul flight (economy)",  "✈️",  "flight_short_economy", 0.35),
    ("flight_long_economy", "Long-haul flight (economy)",   "🛫",  "flight_long_economy",  0.40),
    ("flight_short_business","Short-haul flight (business)","💺",  "flight_short_business",0.55),
    ("flight_long_business", "Long-haul flight (business)", "🛩️",  "flight_long_business", 0.65),
]
TRANSPORT_MAP  = {t[0]: t for t in TRANSPORT_MODES}
ZERO_EMISSION  = {"bicycle", "walking"}
LOW_EMISSION   = {"electric_car", "phev_charged", "national_rail", "tube", "bus_local"}

# ── Transport → GHG scope classification ──────────────────────────────────────
# Matches the GHG Protocol convention this app's own Scope 1/2/3 drawer
# describes: "Scope 1: Direct — gas boiler, petrol/diesel fuel burned",
# "Scope 2: Indirect — electricity purchased from grid",
# "Scope 3: Value chain — food production, public transport, supply chain".
#
# Previously the backend applied a flat 85%/15% split to ALL transport_kg
# regardless of mode, which silently put 85% of train/bus/flight emissions
# into Scope 1 — contradicting the label shown right next to the number.
# This now classifies per mode instead:
#   Scope 1 — fuel burned directly in a vehicle the user owns/drives
#   Scope 2 — electricity charged into a user-owned EV/PHEV
#   Scope 3 — third-party-operated transport (rail/bus/tube/taxi), flights,
#             and zero-emission active travel (bicycle/walking — 0 kg anyway)
TRANSPORT_SCOPE_1 = {
    "petrol_car_avg", "diesel_car_avg", "hybrid_car",
    "petrol_small", "petrol_large",
    "diesel_van_medium", "diesel_van_large", "motorbike",
}
TRANSPORT_SCOPE_2 = {
    "electric_car", "electric_van", "phev_charged",
}
# Anything not listed above (national_rail, bus_local, tube, taxi, bicycle,
# walking, and all flight_* keys) defaults to Scope 3.

def transport_scope(key: str) -> int:
    """Return the GHG scope (1, 2 or 3) for a transport mode key."""
    if key in TRANSPORT_SCOPE_1: return 1
    if key in TRANSPORT_SCOPE_2: return 2
    return 3

# ── Water ─────────────────────────────────────────────────────────────────────
WATER_EF    = get_factor("water_supply")  # 0.344 kgCO2e/m3
LPG_EF      = 0.21419   # kgCO2e/kWh (DESNZ 2025)
OIL_EF      = 0.24700   # kgCO2e/kWh
COAL_EF     = 0.31900   # kgCO2e/kWh
WASTE_EF    = 0.58700   # kgCO2e/kg  (landfill)
RECYCLE_EF  = 0.02100   # kgCO2e/kg  (recycled)
HOTEL_EF    = {
    # DEFRA/DESNZ DOES publish a "Hotel stay" Scope 3 factor — it is compiled
    # from the Cornell Hotel Sustainability Benchmarking Index (via the
    # International Tourism Partnership / Greenview Hotel Footprinting Tool),
    # not measured by DEFRA directly, but it IS part of the official workbook.
    # The most recent figure verifiable at the time of writing (2022 dataset,
    # cross-checked via Circular Ecology's published analysis of the DEFRA
    # Hotel Footprinting Tool data) was 10.4 kgCO2e per UK room-night — the
    # previous 21.0 value here was roughly double that with no clear source.
    # NOTE: confirm against the current-year DEFRA "Hotel stay" tab via the
    # admin "Update source data" panel before relying on this for reporting.
    "uk_average": 10.4,   # kgCO2e per room-night (DEFRA/DESNZ, Cornell HSBI data)
    "eco":         4.0,
    "luxury":      19.0,
    "international":30.0,
}
HOTEL_EF_SOURCE = "DEFRA/DESNZ via Cornell Hotel Sustainability Benchmarking Index"

# ── Smart Recommendation Engine ───────────────────────────────────────────────
def build_smart_recommendations(inputs, emissions):
    """
    Generate personalised recommendations based on ACTUAL inputs chosen.
    Suppresses irrelevant recommendations, promotes specific ones.
    Returns list of recommendation dicts, ranked by potential impact.
    """
    recs = []
    transport_modes = inputs.get("transport_modes", [])
    food_items      = inputs.get("food_items", {})
    elec_kwh        = inputs.get("elec_kwh", 0)
    gas_kwh         = inputs.get("gas_kwh", 0)
    water_m3        = inputs.get("water_m3", 0)
    org_type        = inputs.get("org_type", "household")

    transport_keys  = [m["key"] for m in transport_modes]
    all_zero_em     = all(k in ZERO_EMISSION for k in transport_keys) if transport_keys else False
    has_ev          = any(k in {"electric_car","phev_charged"} for k in transport_keys)
    has_petrol_diesel = any(k in {"petrol_car_avg","diesel_car_avg","petrol_small",
                                   "petrol_large","diesel_van_medium","petrol_van_small",
                                   "hybrid_car","motorbike","taxi"} for k in transport_keys)
    has_pub_trans   = any(k in {"national_rail","tube","bus_local"} for k in transport_keys)

    beef_kg    = food_items.get("food_beef",  0) + food_items.get("food_lamb", 0)
    chicken_kg = food_items.get("food_chicken",0) + food_items.get("food_fish", 0)
    dairy_kg   = food_items.get("food_milk",  0) + food_items.get("food_cheese", 0)
    plant_kg   = (food_items.get("food_veg",  0) + food_items.get("food_fruit", 0) +
                  food_items.get("food_tofu", 0))
    # total_food_em not needed - food_kg calculated below

    em = emissions  # shorthand

    # ── ENERGY recs ──────────────────────────────────────────────────────────
    if elec_kwh > 0 and em.get("scope_2_kg", 0) > 20:
        recs.append({
            "category":   "Energy",
            "icon":       "⚡",
            "title":      "Switch to a 100% renewable electricity tariff",
            "body":       f"Your electricity currently produces {em.get('scope_2_kg',0):.0f} kg CO₂e/month. A green tariff drops this to zero — no change in how you use power, just a different supplier. Takes 15 minutes online.",
            "saving_kg":  round(em.get("scope_2_kg", 0), 1),
            "saving_label": f"Save {em.get('scope_2_kg',0):.0f} kg CO₂e/month",
            "difficulty": "Easy",
            "linked_to":  "Your electricity input",
        })

    if gas_kwh > 500:
        gas_kg_em = round(gas_kwh * get_factor("natural_gas"), 1)
        save_kg   = round(gas_kg_em * 0.15, 1)
        recs.append({
            "category":   "Energy",
            "icon":       "🔥",
            "title":      "Turn your thermostat down by 1–2°C and lag your hot water tank",
            "body":       f"You use {gas_kwh:.0f} kWh of gas/month. Reducing by 15% through draught-proofing and a lower thermostat setting saves approximately {save_kg:.0f} kg CO₂e/month — and cuts your gas bill by £{round(gas_kwh*0.15*get_current_prices()['gas_p_kwh']/100):.0f}/month.",
            "saving_kg":  save_kg,
            "saving_label": f"Save ~{save_kg:.0f} kg CO₂e/month",
            "difficulty": "Easy",
            "linked_to":  f"Your gas input: {gas_kwh:.0f} kWh/month",
        })

    if gas_kwh > 1000:
        recs.append({
            "category":   "Energy",
            "icon":       "🏠",
            "title":      "Consider cavity wall or loft insulation",
            "body":       f"At {gas_kwh:.0f} kWh/month, your gas usage is high. Proper insulation typically reduces heating demand by 20–30%, saving {round(gas_kwh*0.25*get_factor('natural_gas'),0):.0f} kg CO₂e/month and significantly reducing bills.",
            "saving_kg":  round(gas_kwh * 0.25 * get_factor("natural_gas"), 1),
            "saving_label": f"Save ~{round(gas_kwh*0.25*get_factor('natural_gas'),0):.0f} kg CO₂e/month",
            "difficulty": "Medium",
            "linked_to":  f"Your gas input: {gas_kwh:.0f} kWh/month",
        })

    # ── TRANSPORT recs ───────────────────────────────────────────────────────
    if all_zero_em and transport_keys:
        recs.append({
            "category":   "Transport",
            "icon":       "🌟",
            "title":      "Your transport is already zero-carbon — outstanding",
            "body":       "Walking and cycling produce no CO₂ at all. You're already leading by example on transport. Share your approach — it's the single most impactful transport choice anyone can make.",
            "saving_kg":  0,
            "saving_label": "Already at zero",
            "difficulty": "Already done",
            "linked_to":  "Your transport: walking/cycling",
        })
    elif has_ev and not has_petrol_diesel:
        recs.append({
            "category":   "Transport",
            "icon":       "⚡",
            "title":      "Your vehicle is already low-carbon — well done",
            "body":       "Your EV or PHEV produces significantly less CO₂ than petrol or diesel. Pair it with a renewable electricity tariff and your transport footprint becomes near-zero.",
            "saving_kg":  round(em.get("transport_kg", 0) * 0.05, 1),
            "saving_label": "Switch to green tariff to go even lower",
            "difficulty": "Easy",
            "linked_to":  "Your EV/PHEV selection",
        })
    elif has_petrol_diesel:
        trans_kg = em.get("transport_kg", 0)
        for m in transport_modes:
            if m["key"] in {"petrol_car_avg","diesel_car_avg","petrol_small","petrol_large","hybrid_car"}:
                km = m.get("km", 0)
                save = round(km * (get_factor(m["key"]) - get_factor("electric_car")), 1)
                if save > 5:
                    recs.append({
                        "category":   "Transport",
                        "icon":       "🔋",
                        "title":      f"Switch your {TRANSPORT_MAP[m['key']][1].lower()} to an EV for your next vehicle",
                        "body":       f"Your {TRANSPORT_MAP[m['key']][1].lower()} produces {get_factor(m['key']):.3f} kgCO₂e/km. An equivalent EV produces {get_factor('electric_car'):.3f} kgCO₂e/km — 69% lower. At {km:.0f} km/month that's a saving of {save:.0f} kg CO₂e/month.",
                        "saving_kg":  save,
                        "saving_label": f"Save {save:.0f} kg CO₂e/month",
                        "difficulty": "Hard",
                        "linked_to":  f"Your {TRANSPORT_MAP[m['key']][1]} at {km:.0f} km/month",
                    })

        if not has_pub_trans and trans_kg > 50:
            recs.append({
                "category":   "Transport",
                "icon":       "🚆",
                "title":      "Replace some car journeys with public transport",
                "body":       f"The bus emits 0.08 kgCO₂e/km vs 0.17 for a petrol car — half the emissions. National Rail is even lower at 0.035 kgCO₂e/km. Even replacing 25% of your car journeys with public transport would save meaningful CO₂.",
                "saving_kg":  round(trans_kg * 0.15, 1),
                "saving_label": f"Save ~{round(trans_kg*0.15,0):.0f} kg CO₂e/month",
                "difficulty": "Medium",
                "linked_to":  "Your current transport mix",
            })

    # ── FOOD recs ────────────────────────────────────────────────────────────
    if beef_kg >= 0.3:  # triggers at 'rarely' (0.25*1.0) or above
        save_kg = round(beef_kg * (get_factor("food_beef") - get_factor("food_chicken")), 1)
        recs.append({
            "category":   "Food",
            "icon":       "🥩",
            "title":      f"Swap some beef/lamb for chicken, fish or plant-based alternatives",
            "body":       f"You consume approximately {beef_kg:.1f} kg of beef/lamb per month. Beef produces 27 kgCO₂e/kg — 5× more than chicken (5.4 kg) and 47× more than vegetables (0.58 kg). Replacing just half your beef with chicken saves {round(beef_kg*0.5*(get_factor('food_beef')-get_factor('food_chicken')),1):.0f} kg CO₂e/month.",
            "saving_kg":  save_kg,
            "saving_label": f"Save up to {save_kg:.0f} kg CO₂e/month",
            "difficulty": "Easy",
            "linked_to":  f"Your beef/lamb consumption: {beef_kg:.1f} kg/month",
        })

    if chicken_kg >= 0.5 and beef_kg < 0.3:  # any regular chicken/fish with low red meat
        recs.append({
            "category":   "Food",
            "icon":       "🍗",
            "title":      "Your protein choices are already relatively low-carbon",
            "body":       f"Chicken and fish produce 5.4 kgCO₂e/kg — much lower than beef (27 kg) or lamb (39 kg). Your food footprint is well below average for a meat-eater. Adding more plant-based meals a few days a week would reduce it further.",
            "saving_kg":  round(chicken_kg * 0.2 * (5.4 - 2.0), 1),
            "saving_label": "Add plant-based days to go lower",
            "difficulty": "Easy",
            "linked_to":  "Your chicken/fish selection",
        })

    if plant_kg >= 3 and beef_kg < 0.3:  # plant-rich diet with low/no red meat
        recs.append({
            "category":   "Food",
            "icon":       "🌱",
            "title":      "Your diet is already very low-carbon — well done",
            "body":       "A plant-rich diet is one of the most powerful individual actions for the climate. Your food footprint is well below the UK average. Consider reducing dairy (especially cheese at 9.8 kgCO₂e/kg) if you want to go further.",
            "saving_kg":  0,
            "saving_label": "Already low-carbon",
            "difficulty": "Already done",
            "linked_to":  "Your plant-based food selections",
        })

    # If no food selected at all, suggest reviewing food footprint
    if not food_items:
        recs.append({
            "category":   "Food",
            "icon":       "🍽️",
            "title":      "Add your food choices to see personalised recommendations",
            "body":       "Food accounts for 20-25% of the average UK carbon footprint. Go back to Step 3 and select what you typically eat to get specific food recommendations.",
            "saving_kg":  0,
            "saving_label": "Complete your food selections",
            "difficulty": "Easy",
            "linked_to":  "No food items selected",
        })

    # ── WATER rec (business only) ────────────────────────────────────────────
    if water_m3 > 20 and org_type in ("business", "restaurant"):
        water_kg = round(water_m3 * WATER_EF, 1)
        recs.append({
            "category":   "Water",
            "icon":       "💧",
            "title":      "Install flow restrictors and fix leaks to reduce water use",
            "body":       f"Your water consumption of {water_m3:.0f} m³/month produces {water_kg:.0f} kg CO₂e and costs approximately £{round(water_m3*get_current_prices()['water_p_m3']/100,0):.0f}/month. Low-cost flow restrictors on taps and fixing dripping fixtures typically reduce commercial water use by 15–20%.",
            "saving_kg":  round(water_kg * 0.15, 1),
            "saving_label": f"Save ~{round(water_kg*0.15,0):.0f} kg CO₂e/month",
            "difficulty": "Easy",
            "linked_to":  f"Your water use: {water_m3:.0f} m³/month",
        })

    # Sort by saving_kg descending, but put "already done" last
    def sort_key(r):
        if r["difficulty"] == "Already done":
            return -999
        return r["saving_kg"]

    recs.sort(key=sort_key, reverse=True)

    # Cap at 5, but always include "already done" items as encouragement
    done  = [r for r in recs if r["difficulty"] == "Already done"]
    other = [r for r in recs if r["difficulty"] != "Already done"]
    return other[:4] + done[:1]


# ── Feasibility bounds for optimiser ──────────────────────────────────────────
FEASIBILITY_BOUNDS = {
    "elec":      {"max_pct":0.30,"disruption":1,"label":"electricity use",
                  "description":"Switch to LED lighting, turn off standby devices, use appliances efficiently"},
    "gas":       {"max_pct":0.25,"disruption":2,"label":"gas consumption",
                  "description":"Turn heating down 1–2°C, improve draught-proofing, lag pipes and hot water tank"},
    "transport": {"max_pct":0.40,"disruption":3,"label":"transport distance",
                  "description":"Combine errands into fewer trips, work from home where possible, cycle or walk for short journeys"},
    "food":      {"max_pct":0.20,"disruption":4,"label":"food carbon footprint",
                  "description":"Shift toward a flexitarian diet — reduce beef and lamb, add more plant-based meals"},
}
OPTIMISE_PRIORITY = ["elec", "gas", "transport", "food"]
OPTIMISE_SCENARIOS = {
    "opt_5":  {"label":"Optimise to save 5% of total costs",  "pct":0.05},
    "opt_10": {"label":"Optimise to save 10% of total costs", "pct":0.10},
    "opt_15": {"label":"Optimise to save 15% of total costs", "pct":0.15},
    "opt_20": {"label":"Optimise to save 20% of total costs", "pct":0.20},
    "opt_30": {"label":"Optimise to save 30% of total costs", "pct":0.30},
}
EMISSION_SCENARIOS = {
    "em_5":  {"label":"Reduce emissions by 5%",  "pct":0.05},
    "em_10": {"label":"Reduce emissions by 10%", "pct":0.10},
    "em_15": {"label":"Reduce emissions by 15%", "pct":0.15},
    "em_20": {"label":"Reduce emissions by 20%", "pct":0.20},
    "em_30": {"label":"Reduce emissions by 30%", "pct":0.30},
    "em_50": {"label":"Reduce emissions by 50%", "pct":0.50},
}
COST_SCENARIOS = {
    "cost_5":  {"label":"Reduce costs by 5%",  "pct":0.05},
    "cost_10": {"label":"Reduce costs by 10%", "pct":0.10},
    "cost_15": {"label":"Reduce costs by 15%", "pct":0.15},
    "cost_20": {"label":"Reduce costs by 20%", "pct":0.20},
    "cost_30": {"label":"Reduce costs by 30%", "pct":0.30},
}

# ── DB ────────────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'freemium.db')
def init_db():
    db = sqlite3.connect(DB_PATH)
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS email_captures (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT    NOT NULL UNIQUE,
            result_kg     REAL,
            org_type      TEXT,
            region        TEXT,
            captured_at   TEXT    NOT NULL DEFAULT (datetime('now')),
            energy_kg     REAL,
            transport_kg  REAL,
            food_kg       REAL,
            other_kg      REAL,
            total_kg      REAL,
            recs_json     TEXT,
            consented     INTEGER NOT NULL DEFAULT 0,
            notified      INTEGER NOT NULL DEFAULT 0
        )""")
        # Safe upgrade: add new columns if upgrading from old schema
        for col_sql in [
            "ALTER TABLE email_captures ADD COLUMN org_type     TEXT",
            "ALTER TABLE email_captures ADD COLUMN region       TEXT",
            "ALTER TABLE email_captures ADD COLUMN energy_kg    REAL",
            "ALTER TABLE email_captures ADD COLUMN transport_kg REAL",
            "ALTER TABLE email_captures ADD COLUMN food_kg      REAL",
            "ALTER TABLE email_captures ADD COLUMN other_kg     REAL",
            "ALTER TABLE email_captures ADD COLUMN total_kg     REAL",
            "ALTER TABLE email_captures ADD COLUMN recs_json    TEXT",
            "ALTER TABLE email_captures ADD COLUMN consented    INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE email_captures ADD COLUMN notified     INTEGER NOT NULL DEFAULT 0",
        ]:
            try: db.execute(col_sql)
            except Exception: pass
        db.commit()
    finally:
        db.close()
init_db()

# ── Routes ────────────────────────────────────────────────────────────────────

# Quiz questions — 6 questions across 3 rounds of 2
QUIZ_QUESTIONS = [
    # Round 1
    {"round":1,"emoji":"🚗",
     "question":"Which transport emits the least CO2 per km?",
     "options":["Petrol car","Diesel car","Electric car","Plane"],
     "answer":"Electric car",
     "fact":"An EV produces 0.053 kgCO2e/km vs 0.170 for a petrol car — 69% lower. (DESNZ 2025)"},
    {"round":1,"emoji":"🥩",
     "question":"Which food has the highest carbon footprint per kg?",
     "options":["Rice","Chicken","Beef","Bread"],
     "answer":"Beef",
     "fact":"Beef produces 27 kgCO2e/kg — 5x more than chicken (5.4 kg) and 47x more than vegetables. (Poore & Nemecek, 2018, via Our World in Data)"},
    # Round 2
    {"round":2,"emoji":"⚡",
     "question":"What is the UK grid electricity carbon factor in 2025?",
     "options":["0.05 kgCO2e/kWh","0.20 kgCO2e/kWh","0.50 kgCO2e/kWh","1.0 kgCO2e/kWh"],
     "answer":"0.20 kgCO2e/kWh",
     "fact":"The exact DESNZ 2025 value is 0.19553 kgCO2e/kWh — down 61% since 2012 thanks to renewables."},
    {"round":2,"emoji":"🚆",
     "question":"Which is lower carbon per km — a car or a train?",
     "options":["Petrol car (0.170)","Diesel car (0.168)","National Rail (0.035)","They are equal"],
     "answer":"National Rail (0.035)",
     "fact":"National Rail produces 0.035 kgCO2e/km — nearly 5x lower than the average petrol car. (DESNZ 2025)"},
    # Round 3
    {"round":3,"emoji":"🐑",
     "question":"Which has a higher carbon footprint — beef or lamb?",
     "options":["Beef (27 kg)","Lamb (39 kg)","They are equal","Depends on the breed"],
     "answer":"Lamb (39 kg)",
     "fact":"Lamb produces 39.2 kgCO2e/kg — even higher than beef at 27 kg. Both are far above chicken at 5.4 kg."},
    {"round":3,"emoji":"🏠",
     "question":"A home uses 900 kWh of gas per month. Roughly how much CO2 is that?",
     "options":["16 kg","65 kg","165 kg","650 kg"],
     "answer":"165 kg",
     "fact":"900 kWh x 0.18296 kgCO2e/kWh = 164.7 kg CO2e per month — roughly the same as driving 970 km by car."},
]

@app.before_request
def add_ngrok_bypass():
    """Auto-redirect ngrok visitors to bypass the interstitial warning page."""
    if 'ngrok-free' in (request.host or '') and 'ngrok-skip-browser-warning' not in request.args:
        from flask import redirect
        separator = '&' if '?' in request.url else '?'
        return redirect(request.url + separator + 'ngrok-skip-browser-warning=true')

@app.route('/')
@require_auth
def index():
    return render_template('index.html',
        food_items         = FOOD_ITEMS,
        food_tooltips      = FOOD_TOOLTIPS,
        transport_modes    = TRANSPORT_MODES,
        optimise_scenarios = OPTIMISE_SCENARIOS,
        emission_scenarios = EMISSION_SCENARIOS,
        cost_scenarios     = COST_SCENARIOS,
        quiz_questions     = QUIZ_QUESTIONS,
        demo_pin           = get_pin(),
        is_admin           = is_admin(),
        current_prices     = get_current_prices(),
        price_source_label = get_price_source_label(),
        price_updated_date = get_price_updated_date(),
        hotel_ef_uk        = get_hotel_ef_uk_average(),
    )


@app.route('/api/calculate', methods=['POST'])
def calculate():
    body     = request.get_json(silent=True) or {}
    if not body:
        return jsonify({"status":"error","message":"No data received. Please complete the calculator steps."}), 400
    prices   = {**get_current_prices(), **(body.get('prices') or {})}
    org_type = body.get('org_type', 'household')
    occupants= max(1, int(body.get('occupants', 1) or 1))

    # ── Energy ────────────────────────────────────────────────────────────────
    elec_kwh    = float(body.get('elec_kwh', 0) or 0)
    gas_kwh     = float(body.get('gas_kwh',  0) or 0)
    lpg_kwh     = float(body.get('lpg_kwh',  0) or 0)
    oil_kwh     = float(body.get('oil_kwh',  0) or 0)
    water_m3    = float(body.get('water_m3', 0) or 0)
    waste_kg    = float(body.get('waste_kg', 0) or 0)
    recycled_kg = float(body.get('recycled_kg', 0) or 0)

    # Hotel (business/restaurant only)
    hotel_nights    = float(body.get('hotel_nights', 0) or 0) if org_type != 'household' else 0
    hotel_type_key  = body.get('hotel_type', 'uk_average')
    hotel_ef_val    = get_hotel_ef_uk_average() if hotel_type_key == 'uk_average' \
                       else HOTEL_EF.get(hotel_type_key, HOTEL_EF['uk_average'])
    hotel_kg        = round(hotel_nights * hotel_ef_val, 4)
    cost_hotel      = round(hotel_nights * prices.get('hotel_avg_night', 80.0), 2)

    # ── Region-aware emission factors ────────────────────────────────────────
    region   = body.get('region', 'UK').upper()
    if region not in EF_REGIONAL:
        region = 'UK'
    reg      = EF_REGIONAL[region]
    ef_elec  = reg['elec']
    ef_gas   = reg['gas']
    ef_water = reg.get('water', WATER_EF)
    ef_lpg   = reg.get('lpg', LPG_EF)
    ef_oil   = reg.get('oil', OIL_EF)
    reg_source = reg['source']
    reg_links  = reg.get('links', {})

    elec_kg  = round(elec_kwh * ef_elec,  4)
    gas_kg   = round(gas_kwh  * ef_gas,   4)
    lpg_kg   = round(lpg_kwh  * ef_lpg,   4)
    oil_kg   = round(oil_kwh  * ef_oil,   4)
    water_kg = round(water_m3 * ef_water,                   4)
    waste_kg_em  = round(waste_kg    * WASTE_EF,            4)
    recycle_kg_em= round(recycled_kg * RECYCLE_EF,          4)
    energy_kg= round(elec_kg + gas_kg + lpg_kg + oil_kg + water_kg + waste_kg_em + recycle_kg_em, 4)

    cost_elec  = round(elec_kwh * prices["elec_p_kwh"]  / 100, 2)
    cost_gas   = round(gas_kwh  * prices["gas_p_kwh"]   / 100, 2)
    cost_lpg   = round(lpg_kwh  * 0.06, 2)   # ~6p/kWh
    cost_oil   = round(oil_kwh  * 0.07, 2)   # ~7p/kWh
    cost_water = round(water_m3 * prices["water_p_m3"]  / 100, 2)
    cost_energy= round(cost_elec + cost_gas + cost_lpg + cost_oil + cost_water, 2)

    # ── Multi-mode transport ──────────────────────────────────────────────────
    transport_modes = body.get('transport_modes', [])   # [{key, km}, ...]
    transport_kg    = 0.0
    cost_transport  = 0.0
    transport_detail= []
    scope1_transport_kg = 0.0
    scope2_transport_kg = 0.0
    scope3_transport_kg = 0.0

    for m in transport_modes:
        key = m.get('key', '')
        km  = float(m.get('km', 0) or 0)
        if not key or km <= 0 or key not in FACTORS_BY_KEY:
            continue
        ef       = get_factor(key)
        m_kg     = round(km * ef, 4)
        transport_kg += m_kg

        # Cost — petrol/diesel/hybrid modes use real pump prices (see
        # FUEL_CONSUMPTION_L_PER_100KM / _fuel_cost_per_km above); everything
        # else (EV, public transport, taxi, flights) uses the static £/km
        # estimate already in TRANSPORT_MAP.
        tm = TRANSPORT_MAP.get(key)
        fuel_cost_per_km = _fuel_cost_per_km(key, prices)
        cost_per_km = fuel_cost_per_km if fuel_cost_per_km is not None else (tm[4] if tm else 0.14)
        m_cost = round(km * cost_per_km, 2)
        cost_transport += m_cost

        # Scope (per mode — see transport_scope() above)
        sc = transport_scope(key)
        if sc == 1:   scope1_transport_kg += m_kg
        elif sc == 2: scope2_transport_kg += m_kg
        else:         scope3_transport_kg += m_kg

        transport_detail.append({
            "key": key, "label": TRANSPORT_MAP[key][1] if key in TRANSPORT_MAP else key,
            "km": km, "kg": m_kg, "cost": m_cost, "scope": sc,
        })

    transport_kg   = round(transport_kg,   4)
    cost_transport = round(cost_transport, 2)

    # ── Multi-item food ───────────────────────────────────────────────────────
    food_items_input = body.get('food_items', {})   # {key: kg_per_month}
    food_kg    = 0.0
    cost_food  = 0.0
    food_detail= []
    high_impact_foods = []

    for key, qty in food_items_input.items():
        qty = float(qty or 0)
        if qty <= 0 or key not in FOOD_MAP:
            continue
        ef   = get_factor(key)
        f_kg = round(qty * ef, 4)
        food_kg  += f_kg

        fi = FOOD_MAP[key]
        f_cost = round(qty * fi[6], 2)
        cost_food += f_cost

        food_detail.append({
            "key": key, "label": fi[1], "qty": qty, "unit": fi[3],
            "kg": f_kg, "cost": f_cost, "ef": ef,
        })
        if ef >= 5.0:
            high_impact_foods.append(fi[1])

    food_kg   = round(food_kg,   4)
    cost_food = round(cost_food, 2)

    # ── Totals ────────────────────────────────────────────────────────────────
    total_kg   = round(energy_kg + transport_kg + food_kg + hotel_kg, 2)
    cost_total = round(cost_energy + cost_transport + cost_food + cost_hotel, 2)
    cost_annual= round(cost_total * 12, 2)
    cost_pp    = round(cost_total / occupants, 2)

    # Scopes — built per transport mode (see transport_scope() above), not a
    # flat ratio. gas/oil/lpg combustion and owned-ICE-vehicle fuel = Scope 1;
    # purchased grid electricity (home + EV/PHEV charging) = Scope 2;
    # food, water, hotel nights, third-party transport and flights = Scope 3.
    scope_1_kg = round(gas_kg + lpg_kg + oil_kg + scope1_transport_kg, 2)
    scope_2_kg = round(elec_kg + scope2_transport_kg, 2)
    scope_3_kg = round(food_kg + water_kg + hotel_kg + waste_kg_em + recycle_kg_em
                        + scope3_transport_kg, 2)

    annual_kg  = round(total_kg * 12, 1)
    trees      = max(0, round(annual_kg / 21.7))

    vs_avg     = round(total_kg - UK_MONTHLY_AVERAGE_KG, 2)
    band       = get_comparison_band(total_kg, monthly=True)

    # ── Smart recommendations ─────────────────────────────────────────────────
    inputs_for_recs = {
        "transport_modes": transport_modes,
        "food_items":      food_items_input,
        "elec_kwh":        elec_kwh,
        "gas_kwh":         gas_kwh,
        "water_m3":        water_m3,
        "org_type":        org_type,
    }
    emissions_for_recs = {
        "scope_2_kg":    scope_2_kg,
        "transport_kg":  transport_kg,
        "food_kg":       food_kg,
    }
    try:
        recs = build_smart_recommendations(inputs_for_recs, emissions_for_recs)
    except Exception as rec_err:
        import traceback; traceback.print_exc()
        recs = []  # gracefully degrade — return results without recommendations

    return jsonify({
        "status": "ok",
        "monthly": {
            "energy_kg":    round(energy_kg,    2),
            "transport_kg": round(transport_kg, 2),
            "food_kg":      round(food_kg,      2),
            "water_kg":     round(water_kg,     2),
            "total_kg":     total_kg,
            "vs_uk_avg_kg": vs_avg,
            "vs_uk_avg_pct":round(vs_avg / UK_MONTHLY_AVERAGE_KG * 100, 1),
            "scope_1_kg":   scope_1_kg,
            "scope_2_kg":   scope_2_kg,
            "scope_3_kg":   scope_3_kg,
        },
        "costs": {
            "elec": cost_elec, "gas": cost_gas, "water": cost_water,
            "energy": cost_energy, "transport": cost_transport, "food": cost_food,
            "total": cost_total, "annual": cost_annual, "per_head": cost_pp,
        },
        "annual":  {"total_kg": annual_kg, "trees": trees, "cost": cost_annual},
        "band":    band,
        "chart": {
            "em_yours":  [round(energy_kg,1), round(transport_kg,1), round(food_kg,1), round(hotel_kg,1)],
            "em_avg":    [UK_MONTHLY_BY_CATEGORY.get("Energy", 250.0),
                          UK_MONTHLY_BY_CATEGORY.get("Transport", 177.0),
                          UK_MONTHLY_BY_CATEGORY.get("Food", 155.0),
                          0.0],
            "cost_yours":[cost_energy, cost_transport, cost_food, cost_hotel],
            "labels":    ["🏠 Energy", "🚗 Transport", "🍽️ Food", "🏨 Hotel"],
        },
        "detail": {
            "transport": transport_detail,
            "food":      sorted(food_detail, key=lambda x: x["kg"], reverse=True),
        },
        "hotel": {"nights": hotel_nights, "type": hotel_type_key, "kg": hotel_kg, "cost": cost_hotel},
        "recommendations": recs,
        "region": {"code": region, "source": reg_source, "links": reg_links, "label": EF_REGIONAL[region]["label"]},
        "inputs": {
            "elec_kwh": elec_kwh, "gas_kwh": gas_kwh, "water_m3": water_m3,
            "transport_modes": transport_modes, "food_items": food_items_input,
            "org_type": org_type,
        },
        "source": f"DESNZ 2025 · {get_price_source_label()}",
    })


@app.route('/api/scenario', methods=['POST'])
def scenario():
    body        = request.get_json(silent=True) or {}
    current     = body.get('current', {})
    target_type = body.get('target_type', 'em_10')
    prices      = {**get_current_prices(), **(body.get('prices') or {})}

    total_kg    = float(current.get('total_kg',    500))
    energy_kg   = float(current.get('energy_kg',   200))
    trans_kg    = float(current.get('transport_kg',150))
    food_kg     = float(current.get('food_kg',     150))
    scope_1_kg  = float(current.get('scope_1_kg',  120))
    scope_2_kg  = float(current.get('scope_2_kg',   80))
    cost_total  = float(current.get('cost_total',   300))
    cost_energy = float(current.get('cost_energy',  100))
    cost_trans  = float(current.get('cost_trans',    80))
    cost_food   = float(current.get('cost_food',    120))
    gas_kwh     = float(current.get('gas_kwh',      900))
    actions     = []

    if target_type.startswith('em_'):
        pct      = EMISSION_SCENARIOS.get(target_type, {}).get('pct', 0.10)
        save_need= round(total_kg * pct, 1)
        rem      = save_need
        new_e, new_t, new_f = energy_kg, trans_kg, food_kg
        new_ce, new_ct, new_cf = cost_energy, cost_trans, cost_food

        if rem > 0 and scope_2_kg > 0:
            a = min(scope_2_kg, rem); new_e -= a; rem -= a
            actions.append({"action":"Switch to 100% renewable electricity tariff","em_save":round(a,1),"cost_save":0,"cost_note":"Same or cheaper price — no behaviour change needed","difficulty":"Easy"})
        if rem > 0 and scope_1_kg > 0:
            a = min(scope_1_kg*0.20, rem); cs = round((gas_kwh*0.20*prices["gas_p_kwh"])/100,2)
            new_e -= a; new_ce -= cs; rem -= a
            actions.append({"action":"Improve insulation (reduce gas by 20%)","em_save":round(a,1),"cost_save":cs,"cost_note":f"Save £{cs:.0f}/month on gas bills","difficulty":"Medium"})
        if rem > 0 and food_kg > 0:
            a = min(food_kg*0.30, rem); cs = round(a*0.50,2)
            new_f -= a; new_cf -= cs; rem -= a
            actions.append({"action":"Adopt flexitarian diet (less beef & lamb)","em_save":round(a,1),"cost_save":cs,"cost_note":f"Save ~£{cs:.0f}/month on food","difficulty":"Easy"})
        if rem > 0 and trans_kg > 0:
            a = min(trans_kg*0.60, rem); cs = round(cost_trans*0.30,2)
            new_t -= a; new_ct = max(0,cost_trans-cs); rem -= a
            actions.append({"action":"Switch to EV or reduce driving by 30%","em_save":round(a,1),"cost_save":cs,"cost_note":f"Save ~£{cs:.0f}/month on fuel","difficulty":"Hard"})

        new_total = round(new_e+new_t+new_f, 1)
        new_cost  = round(new_ce+new_ct+new_cf, 2)
        achieved  = round(total_kg-new_total, 1)
        ci        = round(new_cost-cost_total, 2)
        return jsonify({"status":"ok","target_type":target_type,
            "target_label":EMISSION_SCENARIOS[target_type]["label"],
            "target_kg":round(total_kg*(1-pct),1),
            "achieved_save_kg":achieved,"achieved_pct":round(achieved/total_kg*100,1) if total_kg else 0,
            "new_total_kg":new_total,"new_cost_total":new_cost,
            "cost_impact":ci,"cost_direction":"saving" if ci<=0 else "increase",
            "actions":actions})

    elif target_type.startswith('cost_'):
        pct      = COST_SCENARIOS.get(target_type, {}).get('pct', 0.10)
        save_need= round(cost_total*pct, 2)
        rem      = save_need
        new_e, new_t, new_f = energy_kg, trans_kg, food_kg

        if rem > 0:
            a = min(cost_energy*0.15,rem); es = round(a/prices["elec_p_kwh"]*100*0.19553,1)
            new_e -= es; rem -= a
            actions.append({"action":"LED lighting, smart thermostat, appliance efficiency","cost_save":round(a,2),"em_save":es,"cost_note":f"Save £{a:.0f}/month","difficulty":"Easy"})
        if rem > 0:
            a = min(cost_trans*0.25,rem); es = round(trans_kg*0.20,1)
            new_t -= es; rem -= a
            actions.append({"action":"Combine trips, use public transport or cycle","cost_save":round(a,2),"em_save":es,"cost_note":f"Save £{a:.0f}/month on fuel","difficulty":"Easy"})
        if rem > 0:
            a = min(cost_food*0.15,rem); es = round(food_kg*0.15,1)
            new_f -= es
            actions.append({"action":"Reduce food waste, buy seasonal & local","cost_save":round(a,2),"em_save":es,"cost_note":f"Save £{a:.0f}/month on food","difficulty":"Easy"})

        es_total = round(energy_kg+trans_kg+food_kg-new_e-new_t-new_f, 1)
        return jsonify({"status":"ok","target_type":target_type,
            "target_label":COST_SCENARIOS[target_type]["label"],
            "target_cost":round(cost_total*(1-pct),2),
            "achieved_cost_save":round(sum(a["cost_save"] for a in actions),2),
            "new_cost_total":round(cost_total-sum(a["cost_save"] for a in actions),2),
            "em_save_kg":es_total,"new_total_kg":round(new_e+new_t+new_f,1),
            "em_pct_reduction":round(es_total/total_kg*100,1) if total_kg else 0,
            "actions":actions})

    return jsonify({"status":"error","message":"Unknown target type"}), 400


@app.route('/api/scenario/optimise', methods=['POST'])
def scenario_optimise():
    body    = request.get_json(silent=True) or {}
    target  = body.get('target_type', 'opt_10')
    current = body.get('current', {})
    prices  = {**get_current_prices(), **(body.get('prices') or {})}
    pct     = OPTIMISE_SCENARIOS.get(target, {}).get('pct', 0.10)

    total_cost  = float(current.get('cost_total',  400))
    cost_elec   = float(current.get('cost_elec',    80))
    cost_gas    = float(current.get('cost_gas',     60))
    cost_trans  = float(current.get('cost_trans',  130))
    cost_food   = float(current.get('cost_food',   130))
    total_kg    = float(current.get('total_kg',    500))
    elec_only_kg= float(current.get('scope_2_kg',  100))
    gas_kg      = float(current.get('scope_1_kg',  100))
    trans_kg    = float(current.get('transport_kg',150))
    food_kg     = float(current.get('food_kg',     150))

    target_save = round(total_cost * pct, 2)
    available   = {
        "elec":      round(cost_elec  * FEASIBILITY_BOUNDS["elec"]["max_pct"],      2),
        "gas":       round(cost_gas   * FEASIBILITY_BOUNDS["gas"]["max_pct"],        2),
        "transport": round(cost_trans * FEASIBILITY_BOUNDS["transport"]["max_pct"],  2),
        "food":      round(cost_food  * FEASIBILITY_BOUNDS["food"]["max_pct"],       2),
    }
    em_available = {
        "elec":      round(elec_only_kg * FEASIBILITY_BOUNDS["elec"]["max_pct"],      2),
        "gas":       round(gas_kg       * FEASIBILITY_BOUNDS["gas"]["max_pct"],       2),
        "transport": round(trans_kg     * FEASIBILITY_BOUNDS["transport"]["max_pct"], 2),
        "food":      round(food_kg      * FEASIBILITY_BOUNDS["food"]["max_pct"],      2),
    }
    total_available = sum(available.values())
    remaining = target_save
    cat_results = {}

    for cat in OPTIMISE_PRIORITY:
        if remaining <= 0.005:
            cat_results[cat] = {"pct_applied":0.0,"cost_save":0.0,"em_save":0.0,"disruption":FEASIBILITY_BOUNDS[cat]["disruption"]}; continue
        max_save = available[cat]
        if max_save <= 0:
            cat_results[cat] = {"pct_applied":0.0,"cost_save":0.0,"em_save":0.0,"disruption":FEASIBILITY_BOUNDS[cat]["disruption"]}; continue
        actual   = min(max_save, remaining)
        fraction = actual / max_save
        cat_results[cat] = {
            "pct_applied": round(fraction * FEASIBILITY_BOUNDS[cat]["max_pct"], 4),
            "cost_save":   round(actual, 2),
            "em_save":     round(em_available[cat] * fraction, 2),
            "disruption":  FEASIBILITY_BOUNDS[cat]["disruption"],
        }
        remaining = max(0, remaining - actual)

    achieved_save = round(sum(r["cost_save"] for r in cat_results.values()), 2)
    em_save_total = round(sum(r["em_save"]   for r in cat_results.values()), 2)
    new_total_kg  = round(max(0, total_kg - em_save_total), 1)
    achievable    = achieved_save >= target_save * 0.95

    # Narrative
    narrative = []
    narrative.append(
        f"To save <strong>£{achieved_save:.0f}/month</strong> from your "
        f"<strong>£{total_cost:.0f}/month</strong> total, the optimal split across "
        f"your consumption is:"
    )
    for cat in OPTIMISE_PRIORITY:
        r = cat_results[cat]
        if r["pct_applied"] < 0.001: continue
        narrative.append(
            f"• Reduce <strong>{FEASIBILITY_BOUNDS[cat]['label']}</strong> by "
            f"<strong>{r['pct_applied']*100:.0f}%</strong> — saving "
            f"<strong>£{r['cost_save']:.0f}/month</strong>"
        )
    em_pct = round(em_save_total/total_kg*100,1) if total_kg else 0
    narrative.append(
        f"As a result, your carbon footprint falls from "
        f"<strong>{total_kg:.0f} kg</strong> to "
        f"<strong>{new_total_kg:.0f} kg CO₂e/month</strong> — "
        f"a <strong>{em_pct}% reduction</strong>."
    )
    narrative.append(
        "All reductions are within normal operational feasibility — "
        "no major equipment changes or lifestyle disruption required."
        if achievable else
        "Some reductions approach the upper limit without structural changes."
    )

    actions = []
    for cat in OPTIMISE_PRIORITY:
        r = cat_results[cat]
        if r["pct_applied"] < 0.001: continue
        diff = "Easy" if r["disruption"] <= 2 else "Medium"
        actions.append({
            "category":    cat,
            "label":       FEASIBILITY_BOUNDS[cat]["label"].capitalize(),
            "pct":         f"{r['pct_applied']*100:.0f}%",
            "cost_save":   r["cost_save"],
            "em_save":     r["em_save"],
            "cost_str":    f"£{r['cost_save']:.0f}/month",
            "em_str":      f"{r['em_save']:.1f} kg CO₂e/month",
            "description": FEASIBILITY_BOUNDS[cat]["description"],
            "difficulty":  diff,
            "disruption":  r["disruption"],
        })

    shortfall_note = None
    if not achievable:
        max_p = round(total_available/total_cost*100,1)
        shortfall_note = (
            f"Your {pct*100:.0f}% target (£{target_save:.0f}/month) exceeds what's achievable "
            f"within normal operational bounds. The maximum feasible saving without structural "
            f"changes is £{total_available:.0f}/month ({max_p}%). To go further, consider "
            f"switching to a green energy tariff, installing a heat pump, or switching to an EV."
        )

    return jsonify({
        "status":"ok","target_type":target,
        "target_label":OPTIMISE_SCENARIOS[target]["label"],
        "target_pct":pct,"target_save":target_save,
        "achieved_save":achieved_save,"achievable":achievable,
        "new_cost_total":round(total_cost-achieved_save,2),
        "em_save_kg":em_save_total,"new_total_kg":new_total_kg,
        "em_pct":em_pct,
        "cat_results":{k:{"pct_applied":v["pct_applied"],"cost_save":v["cost_save"],"em_save":v["em_save"]} for k,v in cat_results.items()},
        "actions":actions,"narrative":narrative,"shortfall_note":shortfall_note,
        "total_available":total_available,
    })





@app.route('/favicon.png')
def favicon():
    """Serve circular i-NoCarbon logo as favicon."""
    return app.send_static_file('icon-32.png')

@app.route('/manifest.json')
def serve_manifest():
    """PWA manifest — makes freemium installable on mobile home screen."""
    import json as _json
    manifest = {
        "name": "i-NoCarbon Calculator",
        "short_name": "iNoCarbon",
        "description": "Free carbon footprint calculator",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#1B5E20",
        "theme_color": "#2E7D32",
        "icons": [
                  {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
                  {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
              ]
    }
    from flask import Response
    return Response(_json.dumps(manifest), mimetype='application/json')

@app.route('/service-worker.js')
def serve_sw():
    """Minimal service worker for PWA."""
    sw = """self.addEventListener('fetch', e => {});"""
    from flask import Response
    return Response(sw, mimetype='application/javascript')

@app.route('/privacy')
def privacy(): return render_template('privacy.html')


@app.route('/api/saves', methods=['GET', 'POST', 'DELETE'])
def named_saves():
    """Named calculation saves stored in server session, scoped to PIN."""
    from flask import session as flask_session
    # Namespace saves by PIN so different users don't see each other's data
    pin_key = f'saves_{get_pin() or "anon"}'
    if pin_key not in flask_session:
        flask_session[pin_key] = {}
    saves = flask_session[pin_key]

    if request.method == 'GET':
        return jsonify({'status': 'ok', 'saves': saves})

    body = request.get_json(silent=True) or {}

    if request.method == 'POST':
        name   = (body.get('name') or '').strip()[:40]
        result = body.get('result', {})
        if not name:
            return jsonify({'status': 'error', 'message': 'Name required'}), 400
        saves[name] = {'result': result, 'saved_at': __import__('datetime').datetime.now().isoformat()[:16]}
        flask_session.modified = True
        return jsonify({'status': 'ok', 'saves': saves})

    if request.method == 'DELETE':
        name = (body.get('name') or '').strip()
        saves.pop(name, None)
        flask_session.modified = True
        return jsonify({'status': 'ok', 'saves': saves})

@app.route('/upgrade')
def upgrade(): return render_template('upgrade.html')


# ── Email capture ─────────────────────────────────────────────────────────────
import re as _re

_EMAIL_RE = _re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

@app.route('/api/capture-email', methods=['POST', 'OPTIONS'])
def capture_email():
    """Capture a lead email address with footprint data and GDPR consent flag.

    Stores to freemium.db email_captures table.
    Deduplicates by email (INSERT OR IGNORE).
    Sends notification email to info@i-nocarbon.com if SMTP configured.
    Returns JSON {status, message, is_new}.
    """
    if request.method == 'OPTIONS':
        return '', 200

    body         = request.get_json(silent=True) or {}
    raw_email    = (body.get('email') or '').strip().lower()[:254]
    consented    = bool(body.get('consented', False))
    org_type     = (body.get('org_type') or 'household').strip()[:40]
    region       = (body.get('region') or 'UK').strip()[:10].upper()

    # Footprint breakdown
    energy_kg    = body.get('energy_kg')
    transport_kg = body.get('transport_kg')
    food_kg      = body.get('food_kg')
    other_kg     = body.get('other_kg')
    total_kg     = body.get('total_kg') or body.get('result_kg')
    recs_json    = body.get('recs_json') or '[]'

    # Validate
    if not raw_email:
        return jsonify({'status': 'error', 'message': 'Email address is required.'}), 400
    if not _EMAIL_RE.match(raw_email):
        return jsonify({'status': 'error', 'message': 'Please enter a valid email address.'}), 400
    if not consented:
        return jsonify({'status': 'error', 'message': 'Please tick the consent box to continue.'}), 400

    def _safe_float(v):
        try: return float(v) if v is not None else None
        except (TypeError, ValueError): return None

    db = None
    try:
        db = sqlite3.connect(DB_PATH)
        cur = db.execute(
            """INSERT OR IGNORE INTO email_captures
               (email, org_type, region, energy_kg, transport_kg, food_kg, other_kg,
                total_kg, result_kg, recs_json, consented, notified)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,0)""",
            (raw_email, org_type, region,
             _safe_float(energy_kg), _safe_float(transport_kg),
             _safe_float(food_kg),   _safe_float(other_kg),
             _safe_float(total_kg),  _safe_float(total_kg),
             str(recs_json), 1)
        )
        db.commit()
        is_new = cur.rowcount > 0
        lead_id = cur.lastrowid

        # ── Send notification email to i-NoCarbon ────────────────────────────
        notified = False
        smtp_host = os.environ.get('SMTP_HOST', '').strip()
        smtp_user = os.environ.get('SMTP_USER', '').strip()
        smtp_pass = os.environ.get('SMTP_PASS', '').strip()
        smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        notify_to = os.environ.get('NOTIFY_EMAIL', 'info@i-nocarbon.com').strip()

        if is_new and smtp_host and smtp_user and smtp_pass:
            try:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                import json as _json

                recs_list = []
                try: recs_list = _json.loads(recs_json)[:3]
                except Exception: pass

                rec_lines = '\n'.join(
                    f"  {i+1}. {r.get('title','')}: {r.get('saving_label','')}"
                    for i, r in enumerate(recs_list)
                ) or '  (no recommendations recorded)'

                body_text = f"""New i-NoCarbon Freemium Lead
{'='*40}
Email:       {raw_email}
Org type:    {org_type}
Region:      {region}
Total CO2:   {_safe_float(total_kg) or 'n/a'} kg/month
  Energy:    {_safe_float(energy_kg) or 'n/a'} kg
  Transport: {_safe_float(transport_kg) or 'n/a'} kg
  Food:      {_safe_float(food_kg) or 'n/a'} kg
  Other:     {_safe_float(other_kg) or 'n/a'} kg

Top Recommendations:
{rec_lines}

Consented:   Yes (GDPR)
Captured:    {__import__('datetime').datetime.now().strftime('%d %b %Y %H:%M')}
{'='*40}
Action: Reply to {raw_email} with their personalised PDF report.
"""
                msg = MIMEMultipart()
                msg['From']    = smtp_user
                msg['To']      = notify_to
                msg['Subject'] = f'🌿 New i-NoCarbon lead: {raw_email} ({_safe_float(total_kg) or "?"} kg CO2/mo)'
                msg.attach(MIMEText(body_text, 'plain'))

                with smtplib.SMTP(smtp_host, smtp_port) as srv:
                    srv.starttls()
                    srv.login(smtp_user, smtp_pass)
                    srv.sendmail(smtp_user, notify_to, msg.as_string())

                notified = True
                db.execute("UPDATE email_captures SET notified=1 WHERE id=?", (lead_id,))
                db.commit()

            except Exception:
                import traceback; traceback.print_exc()
                # Non-fatal — lead is saved, notification just didn't send

        db.close()
        db = None

        msg = ('Thanks! We\'ll send your personalised report to ' + raw_email + ' shortly.' if is_new
               else 'You\'re already on our list — we\'ll be in touch with your report.')
        return jsonify({'status': 'ok', 'message': msg, 'is_new': is_new, 'notified': notified})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'status': 'error', 'message': 'Could not save your details. Please try again.'}), 500
    finally:
        if db:
            db.close()


# ── Admin: view captured leads (protect this with a secret in production) ─────
@app.route('/admin/leads')
def admin_leads():
    """Simple plain-text lead list. Protect with Basic Auth or restrict by IP in production."""
    secret = request.args.get('key', '')
    admin_key = os.environ.get('ADMIN_KEY', '').strip()
    if admin_key and secret != admin_key:
        return 'Unauthorized', 401
    db = None
    try:
        db   = sqlite3.connect(DB_PATH)
        rows = db.execute(
            "SELECT id, email, result_kg, org_type, region, captured_at "
            "FROM email_captures ORDER BY captured_at DESC"
        ).fetchall()
        db.close()
        db = None
        lines = [f"i-NoCarbon Freemium — Lead List ({len(rows)} total)\n"]
        lines.append("=" * 60)
        for r in rows:
            kg_str = f"{r[2]:.0f}" if r[2] is not None else "—"
            lines.append(
                f"[{r[5]}]  {r[1]:<40}  "
                f"kg={kg_str}  "
                f"org={r[3] or '—'}  region={r[4] or '—'}"
            )
        from flask import Response
        return Response('\n'.join(lines), mimetype='text/plain')
    except Exception as e:
        return f'Error: {e}', 500
    finally:
        if db:
            db.close()


# ── Anthropic API key management ────────────────────────────────────────────
# ── Session timeout (30-min inactivity) ──────────────────────────────────────
from datetime import datetime, timedelta

@app.before_request
def check_session_timeout():
    """Clear session data after 30 minutes of inactivity."""
    if request.endpoint in ('static', 'favicon', 'manifest',
                            'entry', 'admin_login', 'pin_entry', 'logout'):
        return
    last = session.get('last_active')
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if datetime.now() - last_dt > timedelta(minutes=30):
                session['timed_out'] = True
                session['last_active'] = datetime.now().isoformat()
        except Exception:
            session.clear()
    session['last_active'] = datetime.now().isoformat()
    session.permanent = True
    app.permanent_session_lifetime = timedelta(hours=2)

@app.route('/api/session-status')
def session_status():
    """Check if session has timed out."""
    timed_out = session.pop('timed_out', False)
    return jsonify({'timed_out': timed_out})


@app.route('/api/session-ping', methods=['POST'])
def session_ping():
    """Called by client every 5 min to refresh session timestamp."""
    session['last_active'] = datetime.now().isoformat()
    return jsonify({'status': 'ok'})


@app.route('/api/haskey')
def api_haskey():
    return jsonify({'has_key': bool(_get_api_key())})

@app.route('/api/setkey', methods=['POST'])
def api_setkey():
    key = (request.get_json(silent=True) or {}).get('key', '').strip()
    if not key or not key.startswith('sk-'):
        return jsonify({'status': '0', 'message': 'Invalid key'})
    _save_api_key(key)
    return jsonify({'status': 'ok', 'message': 'API key saved'})

_AI_SYSTEM_FREEM = """You are a carbon footprint data parser for i-NoCarbon Freemium.
Extract ALL activities from the user's input and return ONLY a JSON object (no markdown).

Return format:
{
  "transport_modes": [{"key": "petrol_car_avg", "km": 400}],
  "food_items": {"food_beef": 1.0, "food_chicken": 0.5},
  "elec_kwh": 350, "gas_kwh": 900, "water_m3": 5,
  "lpg_kwh": 0, "oil_kwh": 0,
  "hotel_nights": 0, "hotel_type": "uk_average",
  "waste_kg": 0, "recycled_kg": 0,
  "extras": []
}

Transport keys: petrol_car_avg, diesel_car_avg, electric_car, hybrid_car, petrol_small, petrol_large,
diesel_van_medium, diesel_van_large, electric_van, national_rail, bus_local, tube, motorbike,
bicycle, walking, taxi, flight_short_economy, flight_long_economy, flight_short_business, flight_long_business.

Food keys (kg/month): food_beef, food_lamb, food_pork, food_chicken, food_fish, food_milk,
food_cheese, food_eggs, food_bread, food_rice, food_veg, food_fruit, food_tofu.

Conversion rules:
- Miles to km: multiply by 1.60934 (exact UK statute mile conversion)
- The user's message may end with a context tag like "[Working days per month: 22. Commute: return trip (x2).]" —
  ALWAYS use those exact numbers for the calculations below instead of any example figures. If no such tag is
  present, default to 22 working days and a return-trip (x2) commute.
- Daily commute (e.g. "30 miles a day to work"): miles x commute_multiplier x 1.60934 x working_days.
  Worked example at the defaults (22 days, x2): 30 miles/day = 30 x 2 x 1.60934 x 22 = 2,124 km/month
- Weekly driving (e.g. "drive 100 miles a week"): miles x commute_multiplier x 1.60934 x 4.33 (weeks/month).
  Worked example at the defaults (x2): 100 miles/week = 100 x 2 x 1.60934 x 4.33 = 1,394 km/month
- One-off trip (e.g. "drove to London 50 miles"): miles x commute_multiplier x 1.60934.
  Worked example at the defaults (x2): 50 miles = 50 x 2 x 1.60934 = 161 km
- All quantities must be MONTHLY totals

Food frequency values (use EXACT values below — these map to dropdown options):
- "once a month" or "rarely" → frequency = 0.25
- "once a fortnight" or "every two weeks" → frequency = 0.5
- "once a week" → frequency = 1
- "twice a week" → frequency = 2
- "3 times a week" → frequency = 3
- "4 times a week" → frequency = 4
- "5 times a week" or "weekdays" → frequency = 5
- "6 times a week" → frequency = 6
- "every day" or "daily" or "7 times a week" → frequency = 7

For food_items, return the frequency value multiplied by the monthly base:
Monthly base quantities (at once/week = frequency 1):
- food_beef, food_pork, food_fish, food_rice: base = 1.0 kg/month
- food_lamb, food_cheese, food_eggs, food_tofu: base = 0.5 kg/month
- food_chicken: base = 1.5 kg/month
- food_milk: base = 8.0 litre/month
- food_bread, food_fruit: base = 2.0 kg/month
- food_veg: base = 3.0 kg/month

So food_items value = frequency × base. Examples:
- "beef twice a week" → food_beef = 2 × 1.0 = 2.0
- "chicken once a week" → food_chicken = 1 × 1.5 = 1.5
- "eggs daily" → food_eggs = 7 × 0.5 = 3.5
- "milk every day" → food_milk = 7 × 8.0 = 56.0

Zero for anything not mentioned.
Diets rule: If a user specifies a diet generally (e.g. "vegetarian only" or "vegan diet") without listing specific food items, populate the food_items dict with the following standard baseline quantities:
- "vegetarian" / "vegetarian food only" / "vegetarian diet" -> food_milk=24.0, food_cheese=1.5, food_eggs=1.5, food_bread=2.0, food_rice=1.0, food_veg=6.0, food_fruit=4.0, food_tofu=1.0 (all meat and fish keys must be 0)
- "vegan" / "vegan diet" -> food_bread=2.0, food_rice=1.0, food_veg=9.0, food_fruit=6.0, food_tofu=2.0 (all meat, fish, milk, cheese, eggs must be 0)

For activities outside standard categories add to extras: [{"description":"...", "kg_estimate":10.0, "factor_note":"..."}]
Return only the JSON object."""

# ── AI Quick Entry toggle (admin-controlled) ──────────────────────────────────
def _ai_enabled():
    """Check if AI entry is enabled (default: True if key exists)."""
    val = os.environ.get('AI_ENTRY_ENABLED', '1').strip().lower()
    return val not in ('0', 'false', 'off', 'no')

def _set_ai_enabled(enabled: bool):
    lines = []
    if os.path.exists(_ENV_FILE):
        with open(_ENV_FILE, encoding='utf-8') as _f:
            lines = [l for l in _f.readlines() if not l.startswith('AI_ENTRY_ENABLED=')]
    lines.append(f'AI_ENTRY_ENABLED={"1" if enabled else "0"}\n')
    with open(_ENV_FILE, 'w', encoding='utf-8') as _f: _f.writelines(lines)
    os.environ['AI_ENTRY_ENABLED'] = '1' if enabled else '0'

def _user_access_enabled():
    """Check if regular user calculator access is enabled (default: True)."""
    val = os.environ.get('USER_ACCESS_ENABLED', '1').strip().lower()
    return val not in ('0', 'false', 'off', 'no')

def _set_user_access_enabled(enabled: bool):
    _save_env_var('USER_ACCESS_ENABLED', '1' if enabled else '0')

@app.route('/api/ai-toggle', methods=['GET', 'POST'])
def api_ai_toggle():
    """GET: return AI state (all users). POST: admin only — toggle for everyone."""
    if request.method == 'POST':
        if not is_admin():
            return jsonify({'status': 'error', 'message': 'Admin only'}), 403
        body = request.get_json(silent=True) or {}
        enabled = bool(body.get('enabled', True))
        _set_ai_enabled(enabled)
        return jsonify({'status': 'ok', 'ai_enabled': enabled})
    return jsonify({'ai_enabled': _ai_enabled(),
                    'has_key': bool(_get_api_key()),
                    'has_gemini_key': bool(_get_gemini_key()),
                    'active_provider': os.environ.get('ACTIVE_AI_PROVIDER', 'gemini').strip().lower(),
                    'is_admin': is_admin()})

@app.route('/api/admin/user-access-toggle', methods=['POST'])
@require_admin
def api_user_access_toggle():
    """Toggle user calculator access."""
    body = request.get_json(silent=True) or {}
    enabled = bool(body.get('enabled', True))
    _set_user_access_enabled(enabled)
    return jsonify({'status': 'ok', 'user_access_enabled': enabled})

@app.route('/api/admin/debug-toggle', methods=['POST'])
@require_admin
def api_debug_toggle():
    """Toggle Flask debug mode for next restart."""
    body = request.get_json(silent=True) or {}
    enabled = bool(body.get('enabled', True))
    _save_env_var('FLASK_DEBUG', '1' if enabled else '0')
    return jsonify({'status': 'ok', 'flask_debug_enabled': enabled})

# ── Admin panel API ───────────────────────────────────────────────────────────
@app.route('/api/admin/stats')
@require_admin
def admin_stats():
    """Return stats for the admin panel."""
    db = None
    try:
        db   = sqlite3.connect(DB_PATH)
        lead_count = db.execute("SELECT COUNT(*) FROM email_captures").fetchone()[0]
        rows = db.execute(
            "SELECT email, result_kg, org_type, region, captured_at "
            "FROM email_captures ORDER BY captured_at DESC LIMIT 20"
        ).fetchall()
        db.close()
        db = None
        leads = [{'email': r[0], 'kg': r[1], 'org': r[2],
                  'region': r[3], 'at': r[4]} for r in rows]
    except Exception:
        lead_count, leads = 0, []
    finally:
        if db:
            db.close()
    return jsonify({
        'status':      'ok',
        'ai_enabled':  _ai_enabled(),
        'user_access_enabled': _user_access_enabled(),
        'flask_debug_enabled': os.environ.get('FLASK_DEBUG', '1').strip().lower() not in ('0', 'false', 'off', 'no'),
        'has_api_key': bool(_get_api_key()),
        'has_gemini_key': bool(_get_gemini_key()),
        'active_provider': os.environ.get('ACTIVE_AI_PROVIDER', 'gemini').strip().lower(),
        'server_port': port,
        'ai_limit':    _get_rate_limit_value(),
        'lead_count':  lead_count,
        'leads':       leads,
        'admin_user':  session.get('admin_user', 'admin'),
        'prices':              get_current_prices(),
        'hotel_ef_uk_average': get_hotel_ef_uk_average(),
        'price_source_label':  get_price_source_label(),
        'price_updated_date':  get_price_updated_date(),
    })

@app.route('/api/admin/setkeys', methods=['POST'])
@require_admin
def api_admin_setkeys():
    """Save Anthropic and Gemini keys and configuration."""
    body = request.get_json(silent=True) or {}
    anthropic_key = body.get('anthropic_key')
    gemini_key = body.get('gemini_key')
    ai_limit = body.get('ai_limit')
    active_provider = body.get('active_provider')
    
    _save_api_keys(anthropic_key, gemini_key)
    
    if ai_limit is not None:
        try:
            limit_val = int(ai_limit)
            if limit_val > 0:
                _save_env_var('AI_MAX_PER_HOUR', str(limit_val))
        except ValueError:
            pass
            
    if active_provider in ('gemini', 'anthropic'):
        _save_env_var('ACTIVE_AI_PROVIDER', active_provider)
            
    return jsonify({'status': 'ok', 'message': 'API keys and configuration saved successfully'})


@app.route('/api/admin/update-source', methods=['POST'])
@require_admin
def api_admin_update_source():
    """Update the declared pricing & emission-factor source data — covers
    the energy/fuel prices, the UK hotel-stay factor, and a free-text
    source label shown across the app (footer, assumptions panel, region
    description). Lets the admin keep these current without redeploying
    code each time Ofgem or pump prices change."""
    body = request.get_json(silent=True) or {}
    try:
        save_source_data({
            'elec_p_kwh':         body.get('elec_p_kwh'),
            'gas_p_kwh':          body.get('gas_p_kwh'),
            'petrol_p_litre':     body.get('petrol_p_litre'),
            'diesel_p_litre':     body.get('diesel_p_litre'),
            'water_p_m3':         body.get('water_p_m3'),
            'hotel_avg_night':    body.get('hotel_avg_night'),
            'hotel_ef_uk_average':body.get('hotel_ef_uk_average'),
            'price_source_label': body.get('price_source_label'),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    return jsonify({
        'status': 'ok',
        'message': 'Pricing & source data updated',
        'prices': get_current_prices(),
        'hotel_ef_uk_average': get_hotel_ef_uk_average(),
        'price_source_label': get_price_source_label(),
        'price_updated_date': get_price_updated_date(),
    })


# ── AI rate limiting ──────────────────────────────────────────────────────────
_ai_calls = {}  # session_id -> (count, window_start)

def _check_rate_limit():
    """Allow max AI queries per session per hour."""
    import time
    limit = _get_rate_limit_value()
    sid = session.get('session_id')
    if not sid:
        import uuid
        sid = str(uuid.uuid4())
        session['session_id'] = sid
    now = time.time()
    if sid in _ai_calls:
        count, start = _ai_calls[sid]
        if now - start > 3600:  # reset after 1 hour
            _ai_calls[sid] = (1, now)
            return True, limit - 1
        if count >= limit:
            remaining_mins = int((3600 - (now - start)) / 60)
            return False, remaining_mins
        _ai_calls[sid] = (count + 1, start)
        return True, limit - count - 1
    else:
        _ai_calls[sid] = (1, now)
        return True, limit - 1


@app.route('/api/ai-entry', methods=['POST', 'OPTIONS'])
def api_ai_entry():
    if request.method == 'OPTIONS': return '', 200
    body = request.get_json(silent=True, force=True) or {}
    text = body.get('text', '').strip()
    user_gemini_key    = body.get('user_gemini_key', '').strip()
    user_anthropic_key = body.get('user_anthropic_key', '').strip()
    mode = body.get('mode', 'parse').strip()

    # If admin AI is off but user supplied their own key, allow it
    admin_ai_on = _ai_enabled()
    using_user_gemini    = (not admin_ai_on) and bool(user_gemini_key)
    using_user_anthropic = (not admin_ai_on) and bool(user_anthropic_key) and not using_user_gemini
    using_user_key       = using_user_gemini or using_user_anthropic

    if not text:
        return jsonify({'status': '0', 'message': 'No text provided'})
    allowed, remaining = _check_rate_limit()
    if not allowed:
        return jsonify({'status': '0', 'error': 'rate_limit',
                       'message': f'AI limit reached. Try again in {remaining} minutes.'})
    if not admin_ai_on and not using_user_key:
        return jsonify({'status': '0', 'error': 'disabled',
                        'message': 'AI is off. Add your own free Gemini key above to use AI Quick Entry.'})

    # Determine provider: user key overrides admin, Gemini takes priority if both provided
    if using_user_gemini:
        provider = 'gemini'
    elif using_user_anthropic:
        provider = 'anthropic'
    else:
        provider = body.get('provider') or os.environ.get('ACTIVE_AI_PROVIDER', 'gemini').strip().lower()

    import json as _json

    # ── System prompts ────────────────────────────────────────────────────────
    freetext_system = (
        "You are i-NoCarbon, a helpful carbon and energy advisor for UK households and small businesses. "
        "Answer questions clearly and practically in 3-5 sentences. "
        "Stay strictly on topic: carbon footprints, energy, transport, food, waste, sustainability, costs, and UK energy prices. "
        "If asked about unrelated topics, politely redirect to carbon/energy topics. "
        "Do not output JSON. Just answer naturally and helpfully."
    )

    if provider == 'gemini':
        gemini_key = user_gemini_key if using_user_gemini else _get_gemini_key()
        if not gemini_key:
            return jsonify({'status': '0', 'error': 'no_key', 'message': 'No Gemini API key — add to .env or set via Admin panel'})

        gemini_models = ['gemini-3.1-flash-lite', 'gemini-2.5-flash', 'gemini-3.5-flash']
        _RETRY_CODES = (400, 404, 429, 500, 529)
        for g_model in gemini_models:
            try:
                if mode == 'freetext':
                    payload = _json.dumps({
                        'contents': [{'parts': [{'text': text}]}],
                        'systemInstruction': {'parts': [{'text': freetext_system}]},
                        'generationConfig': {'temperature': 0.4}
                    }).encode('utf-8')
                else:
                    payload = _json.dumps({
                        'contents': [{'parts': [{'text': text}]}],
                        'systemInstruction': {'parts': [{'text': _AI_SYSTEM_FREEM}]},
                        'generationConfig': {
                            'responseMimeType': 'application/json',
                            'temperature': 0.1
                        }
                    }).encode('utf-8')
                url = f'https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={gemini_key}'
                req = _ur.Request(url, data=payload, headers={'Content-Type': 'application/json'})
                with _ur.urlopen(req, timeout=20) as resp:
                    result = _json.loads(resp.read().decode('utf-8'))
                candidates = result.get('candidates', [])
                if not candidates: continue
                raw = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                if mode == 'freetext':
                    return jsonify({'status': 'ok', 'answer': raw.strip(), 'model': g_model})
                parsed = _json.loads(raw.strip())
                return jsonify({'status': 'ok', 'parsed': parsed, 'model': g_model})
            except _ue.HTTPError as e:
                if e.code in _RETRY_CODES: continue
                return jsonify({'status': '0', 'message': f'Gemini API error {e.code}'})
            except Exception:
                continue
        return jsonify({'status': '0', 'message': 'All Gemini models failed'})

    else: # anthropic
        api_key = user_anthropic_key if using_user_anthropic else _get_api_key()
        if not api_key:
            return jsonify({'status': '0', 'error': 'no_key', 'message': 'No Anthropic API key — add yours in the key panel above or contact admin'})

        models = ['claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-7']
        _RETRY_CODES = (400, 404, 429, 500, 529)
        for model in models:
            try:
                sys_prompt = freetext_system if mode == 'freetext' else _AI_SYSTEM_FREEM
                payload = _json.dumps({
                    'model': model, 'max_tokens': 800,
                    'system': sys_prompt,
                    'messages': [{'role': 'user', 'content': text}]
                }).encode('utf-8')
                req = _ur.Request(
                    'https://api.anthropic.com/v1/messages',
                    data=payload,
                    headers={'x-api-key': api_key, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'}
                )
                with _ur.urlopen(req, timeout=20) as resp:
                    result = _json.loads(resp.read().decode('utf-8'))
                raw = (result.get('content') or [{}])[0].get('text', '')
                if mode == 'freetext':
                    return jsonify({'status': 'ok', 'answer': raw.strip(), 'model': model})
                clean = raw.strip()
                if '```' in clean:
                    clean = clean.split('```')[1]
                    if clean.startswith('json'): clean = clean[4:]
                parsed = _json.loads(clean.strip())
                return jsonify({'status': 'ok', 'parsed': parsed, 'model': model})
            except _ue.HTTPError as e:
                if e.code in _RETRY_CODES: continue
                return jsonify({'status': '0', 'message': f'API error {e.code}'})
            except Exception:
                continue
        return jsonify({'status': '0', 'message': 'All models failed'})



if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', '1').strip().lower() not in ('0', 'false', 'off', 'no')
    print(f"\n  i-NoCarbon Freemium v5 -> http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
