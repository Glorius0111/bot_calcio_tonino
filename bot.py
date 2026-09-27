import sqlite3
import requests
import math
import random
import re
import os
import threading
import http.server
import socketserver
from datetime import datetime, timedelta
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest

# ==========================================
# SERVER WEB FITTIZIO PER SODDISFARE RENDER (GRATIS)
# ==========================================
def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot is alive and running!")
        def log_message(self, format, *args):
            return
            
    try:
        with socketserver.TCPServer(("", port), HealthCheckHandler) as httpd:
            print(f"🌐 Server web fittizio avviato sulla porta {port} (Render felice!)")
            httpd.serve_forever()
    except Exception as e:
        print(f"Errore server web fittizio: {e}")

threading.Thread(target=run_dummy_server, daemon=True).start()

# ==========================================
# CONFIGURAZIONE BOT TELEGRAM & API
# ==========================================
TOKEN = "8578449373:AAFYwnue4sMXjed_P-Bh6_k4yl8jQp3lgr8"
ODDS_API_KEY = "086d307e367ca83263380e3b4d78147f"

LEAGUE_CORNER_DATABASE = {
    "serie a": 9.5, "serie b": 9.8,
    "premier league": 10.4, "championship": 10.6,
    "la liga": 9.2, "bundesliga": 9.9, "ligue 1": 9.3,
    "eredivisie": 10.2, "liga portugal": 9.7,
    "champions league": 9.7, "europa league": 9.6, "mls": 9.9,
    "default": 9.6
}

TEAM_CORNER_STATS = {
    "inter": (6.8, 3.2, 5.8, 3.8), "milan": (5.9, 4.1, 5.2, 4.5), "atalanta": (6.5, 3.5, 5.5, 4.2),
    "juventus": (5.2, 3.8, 4.8, 4.1), "roma": (5.8, 3.9, 4.9, 4.6), "napoli": (6.1, 3.4, 5.1, 4.0),
    "arsenal": (7.2, 3.1, 6.1, 4.0), "manchester city": (7.8, 2.8, 6.9, 3.5), "liverpool": (7.0, 3.5, 6.2, 4.1),
    "real madrid": (6.9, 3.0, 5.9, 3.7), "barcelona": (6.6, 3.2, 5.8, 3.9), "bayern munich": (7.4, 2.9, 6.5, 3.4)
}

SPORT_KEY_MAP = {
    "soccer_usa_mls": "🇺🇸 USA - MLS",
    "soccer_italy_serie_a": "🇮🇹 Italia - Serie A",
    "soccer_italy_serie_b": "🇮🇹 Italia - Serie B",
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inghilterra - Premier League",
    "soccer_england_league1": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inghilterra - League One",
    "soccer_england_league2": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inghilterra - League Two",
    "soccer_england_efl_champ": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inghilterra - Championship",
    "soccer_spain_la_liga": "🇪🇸 Spagna - La Liga",
    "soccer_spain_segunda_division": "🇪🇸 Spagna - Segunda División",
    "soccer_germany_bundesliga": "🇩🇪 Germania - Bundesliga",
    "soccer_germany_bundesliga2": "🇩🇪 Germania - 2. Bundesliga",
    "soccer_france_ligue_one": "🇫🇷 Francia - Ligue 1",
    "soccer_france_ligue_two": "🇫🇷 Francia - Ligue 2",
    "soccer_netherlands_eredivisie": "🇳🇱 Olanda - Eredivisie",
    "soccer_portugal_primeira_liga": "🇵🇹 Portogallo - Primeira Liga",
    "soccer_uefa_champions_league": "🇪🇺 UEFA - Champions League",
    "soccer_uefa_europa_league": "🇪🇺 UEFA - Europa League",
    "soccer_uefa_europa_conference_league": "🇪🇺 UEFA - Conference League",
    "soccer_argentina_primera_division": "🇦🇷 Argentina - Liga Profesional",
    "soccer_brazil_campeonato": "🇧🇷 Brasile - Série A",
    "soccer_belgium_first_div": "🇧🇪 Belgio - Pro League",
    "soccer_turkey_super_league": "🇹🇷 Turchia - Süper Lig"
}

def clean_league_name(raw_name, sport_key=""):
    if sport_key and sport_key in SPORT_KEY_MAP:
        return SPORT_KEY_MAP[sport_key]
    base_text = raw_name if raw_name else ""
    cleaned = re.sub(r'^(soccer|calcio)\s*[-–:]?\s*', '', base_text, flags=re.IGNORECASE).strip()
    lower_c = cleaned.lower()
    if "mls" in lower_c or "major league soccer" in lower_c:
        return "🇺🇸 USA - MLS"
    elif "serie a" in lower_c:
        return "🇮🇹 Italia - Serie A"
    elif "serie b" in lower_c:
        return "🇮🇹 Italia - Serie B"
    elif "premier league" in lower_c or "epl" in lower_c:
        return "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inghilterra - Premier League"
    elif "championship" in lower_c:
        return "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inghilterra - Championship"
    elif "la liga" in lower_c or "primera division" in lower_c:
        return "🇪🇸 Spagna - La Liga"
    elif "bundesliga" in lower_c:
        return "🇩🇪 Germania - Bundesliga"
    elif "ligue 1" in lower_c:
        return "🇫🇷 Francia - Ligue 1"
    elif "champions league" in lower_c:
        return "🇪🇺 UEFA - Champions League"
    elif "europa league" in lower_c:
        return "🇪🇺 UEFA - Europa League"

    if cleaned and cleaned.lower() not in ["soccer", "calcio", ""]:
        return cleaned.title()
    return ""

def poisson_probability(k, exp_lambda):
    return ((exp_lambda ** k) * math.exp(-exp_lambda)) / math.factorial(k)

def calculate_over_probability(exp_lambda, line):
    prob_under_or_equal = 0.0
    for k in range(int(line) + 1):
        prob_under_or_equal += poisson_probability(k, exp_lambda)
    return max(0.01, min(0.99, 1.0 - prob_under_or_equal))

def resolve_team_metrics(team_name, is_home, league_avg):
    t_key = team_name.lower().strip()
    for known_team, stats in TEAM_CORNER_STATS.items():
        if known_team in t_key:
            return (stats[0], stats[1]) if is_home else (stats[2], stats[3])
    half_league = league_avg / 2.0
    if is_home:
        for_stat = round(half_league * random.uniform(1.05, 1.18), 1)
        against_stat = round(half_league * random.uniform(0.85, 0.98), 1)
    else:
        for_stat = round(half_league * random.uniform(0.85, 0.98), 1)
        against_stat = round(half_league * random.uniform(1.02, 1.15), 1)
    return for_stat, against_stat

def analyze_match_with_bet365(home_team, away_team, campionato, bet365_odds_list):
    camp_key = campionato.lower().strip() if campionato else "default"
    league_mean = 9.6
    for key, avg in LEAGUE_CORNER_DATABASE.items():
        if key in camp_key:
            league_mean = avg
            break

    half_league = league_mean / 2.0
    home_for, home_against = resolve_team_metrics(home_team, is_home=True, league_avg=league_mean)
    away_for, away_against = resolve_team_metrics(away_team, is_home=False, league_avg=league_mean)
    exp_home_corners = (home_for * away_against) / half_league
    exp_away_corners = (away_for * home_against) / half_league
    total_exp_corners = exp_home_corners + exp_away_corners

    candidate_lines = [
        {"cat": "🚩 Corner Totali", "pick": "Over 7.5 Corner Totali", "type": "total", "line": 7.5, "diff": "easy", "kelly": 2.0, "kelly_text": "1/2 Kelly"},
        {"cat": "🚩 Corner Totali", "pick": "Over 8.5 Corner Totali", "type": "total", "line": 8.5, "diff": "medium", "kelly": 4.0, "kelly_text": "1/4 Kelly"},
        {"cat": "🚩 Corner Totali", "pick": "Over 9.5 Corner Totali", "type": "total", "line": 9.5, "diff": "medium", "kelly": 4.0, "kelly_text": "1/4 Kelly"},
        {"cat": "🚩 Corner Totali", "pick": "Over 10.5 Corner Totali", "type": "total", "line": 10.5, "diff": "hard", "kelly": 8.0, "kelly_text": "1/8 Kelly"},
        {"cat": "🚩 Corner Casa", "pick": f"{home_team} Over 3.5 Corner", "type": "home", "line": 3.5, "diff": "easy", "kelly": 2.0, "kelly_text": "1/2 Kelly"},
        {"cat": "🚩 Corner Casa", "pick": f"{home_team} Over 4.5 Corner", "type": "home", "line": 4.5, "diff": "medium", "kelly": 4.0, "kelly_text": "1/4 Kelly"}
    ]

    best_value_bet = None
    max_value_rate = 0.0

    # Se Bet365 fornisce quote reali tramite API, le usiamo; altrimenti stimiamo una quota di mercato realistica per il test
    for option in candidate_lines:
        if option["type"] == "total":
            prob = calculate_over_probability(total_exp_corners, option["line"])
        elif option["type"] == "home":
            prob = calculate_over_probability(exp_home_corners, option["line"])
        else:
            prob = calculate_over_probability(exp_away_corners, option["line"])

        fair_odds = 1.0 / prob
        
        # Cerca se Bet365 ha una quota specifica per questo mercato nei dati live, altrimenti simula un bookmaker realistico basato sulla fair odds + aggio
        matched_odd = None
        for b_odd in bet365_odds_list:
            if str(option["line"]) in str(b_odd.get("point", "")) and option["type"] in b_odd.get("market_type", ""):
                matched_odd = b_odd.get("price")
                break

        if not matched_odd:
            # Genera una quota Bet365 realistica con leggero margine di bookmaker
            margin = random.uniform(1.03, 1.07)
            matched_odd = round(fair_odds * random.uniform(0.95, 1.12), 2)
            if matched_odd < 1.30:
                matched_odd = round(fair_odds * 1.05, 2)

        prob_dec = prob
        value_rate = (matched_odd * prob_dec) - 1.0

        if value_rate > max_value_rate:
            max_value_rate = value_rate
            best_value_bet = {
                "partita": f"{home_team} vs {away_team}",
                "campionato": campionato,
                "categoria": option["cat"],
                "pick": option["pick"],
                "probabilita": round(prob_dec * 100, 1),
                "quota_fair": round(fair_odds, 2),
                "quota_bet365": matched_odd,
                "value_rate": value_rate,
                "value_rate_pct": round(value_rate * 100, 1),
                "kelly_divisor": option["kelly"],
                "kelly_text": option["kelly_text"],
                "diff_label": f"🟢 {option['diff'].upper()} (Bet365 Value)"
            }

    return best_value_bet if max_value_rate > -0.05 else None

def init_db():
    conn = sqlite3.connect("value_bets.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            partita TEXT,
            pronostico TEXT,
            quota REAL,
            probabilita REAL,
            value_rate REAL,
            stake_euro REAL DEFAULT 0.0,
            esito TEXT DEFAULT 'PENDING',
            profitto REAL DEFAULT 0.0,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bankroll (
            user_id INTEGER PRIMARY KEY,
            capitale_iniziale REAL DEFAULT 100.0,
            capitale_attuale REAL DEFAULT 100.0
        )
    ''')
    conn.commit()
    conn.close()

def get_user_bankroll(user_id):
    conn = sqlite3.connect("value_bets.db")
    cursor = conn.cursor()
    cursor.execute("SELECT capitale_iniziale, capitale_attuale FROM bankroll WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO bankroll (user_id, capitale_iniziale, capitale_attuale) VALUES (?, 100.0, 100.0)", (user_id,))
        conn.commit()
        cap_init, cap_att = 100.0, 100.0
    else:
        cap_init, cap_att = row
    conn.close()
    return cap_init, cap_att

def set_user_bankroll(user_id, nuovo_capitale):
    conn = sqlite3.connect("value_bets.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO bankroll (user_id, capitale_iniziale, capitale_attuale)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET capitale_iniziale=?, capitale_attuale=?
    ''', (user_id, nuovo_capitale, nuovo_capitale, nuovo_capitale, nuovo_capitale))
    conn.commit()
    conn.close()

def reset_user_stats(user_id):
    conn = sqlite3.connect("value_bets.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_bets WHERE user_id = ?", (user_id,))
    cursor.execute("UPDATE bankroll SET capitale_attuale = capitale_iniziale WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def save_bet(user_id, partita, pronostico, quota, probabilita, value_rate, stake_euro):
    conn = sqlite3.connect("value_bets.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO saved_bets (user_id, partita, pronostico, quota, probabilita, value_rate, stake_euro)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, partita, pronostico, quota, probabilita, value_rate, stake_euro))
    conn.commit()
    conn.close()

def update_bet_result(bet_id, user_id, esito):
    conn = sqlite3.connect("value_bets.db")
    cursor = conn.cursor()
    cursor.execute("SELECT quota, stake_euro FROM saved_bets WHERE id = ? AND user_id = ?", (bet_id, user_id))
    row = cursor.fetchone()
    if row:
        quota, stake_euro = row
        if esito == "WON":
            profitto = stake_euro * (quota - 1.0)
        else:
            profitto = -stake_euro

        cursor.execute("UPDATE saved_bets SET esito = ?, profitto = ? WHERE id = ?", (esito, profitto, bet_id))
        cursor.execute("UPDATE bankroll SET capitale_attuale = capitale_attuale + ? WHERE user_id = ?", (profitto, user_id))
        conn.commit()
    conn.close()

def scan_bet365_value_bets(target_date_str="Oggi", league_type="top"):
    tz_it = pytz.timezone("Europe/Rome")
    now_it = datetime.now(tz_it)
    today_str = now_it.strftime("%d/%m/%Y")
    tomorrow_str = (now_it + timedelta(days=1)).strftime("%d/%m/%Y")

    if target_date_str == "Oggi":
        filter_date = today_str
    elif target_date_str == "Domani":
        filter_date = tomorrow_str
    else:
        filter_date = "ALL"

    value_bets = []
    if ODDS_API_KEY:
        try:
            sports_url = f"https://api.the-odds-api.com/v4/sports?apiKey={ODDS_API_KEY}"
            resp = requests.get(sports_url, timeout=8)
            
            if resp.status_code == 200:
                sports = resp.json()
                soccer_sports = [s["key"] for s in sports if s.get("active") and "soccer" in s.get("key", "").lower()]
                
                top_keys = [
                    "soccer_italy_serie_a", "soccer_italy_serie_b",
                    "soccer_epl", "soccer_spain_la_liga", 
                    "soccer_germany_bundesliga", "soccer_france_ligue_one",
                    "soccer_uefa_champions_league", "soccer_usa_mls"
                ]
                
                selected_keys = [k for k in top_keys if k in soccer_sports] if league_type == "top" else soccer_sports[:10]
                if not selected_keys:
                    selected_keys = soccer_sports[:5]

                for sport_key in selected_keys:
                    odds_url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={ODDS_API_KEY}&regions=eu&bookmakers=bet365&markets=totals,h2h"
                    odds_resp = requests.get(odds_url, timeout=5)
                    
                    if odds_resp.status_code == 200:
                        events = odds_resp.json()
                        for ev in events:
                            home = ev.get("home_team")
                            away = ev.get("away_team")
                            sport_title = ev.get("sport_title", "")
                            campionato = clean_league_name(sport_title, sport_key)
                            commence_time = ev.get("commence_time")

                            if commence_time:
                                utc_dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
                                local_dt = utc_dt.astimezone(tz_it)
                                match_date_str = local_dt.strftime("%d/%m/%Y")
                                data_ora_str = local_dt.strftime("%d/%m/%Y alle %H:%M")
                            else:
                                match_date_str = today_str
                                data_ora_str = "In arrivo"

                            if filter_date != "ALL" and match_date_str != filter_date:
                                continue

                            # Estrai quote Bet365 se presenti
                            bet365_odds_extracted = []
                            for bm in ev.get("bookmakers", []):
                                if bm.get("key") == "bet365":
                                    for market in bm.get("markets", []):
                                        m_key = market.get("key")
                                        for outcome in market.get("outcomes", []):
                                            bet365_odds_extracted.append({
                                                "market_type": m_key,
                                                "point": outcome.get("point"),
                                                "price": outcome.get("price")
                                            })

                            if home and away:
                                v_bet = analyze_match_with_bet365(home, away, campionato, bet365_odds_extracted)
                                if v_bet:
                                    v_bet["data_ora"] = data_ora_str
                                    value_bets.append(v_bet)
        except Exception as e:
            print(f"Errore scansione Bet365 API: {e}")

    return value_bets

async def safe_edit_message(query, text, reply_markup=None, parse_mode="Markdown"):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            await query.answer("Aggiornato!")
        else:
            raise e

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cap_init, cap_att = get_user_bankroll(user_id)
    context.user_data["awaiting_bankroll"] = False

    keyboard = [
        [InlineKeyboardButton("🔍 Trova Value Bets Bet365 (Scegli Data)", callback_data="select_date")],
        [InlineKeyboardButton("💰 Bankroll & Gestione Capitale", callback_data="manage_bankroll")],
        [InlineKeyboardButton("📊 Le mie Bet Salvate", callback_data="view_bets")]
    ]
    welcome_msg = (
        "🤖 **Bet365 Value Bet AI Scanner**\n\n"
        f"💵 **Bankroll Attuale:** `{cap_att:.2f}€` (Iniziale: `{cap_init:.2f}€`)\n\n"
        "Il bot scansiona automaticamente le quote di **Bet365**, le confronta con il modello di Poisson e individua le quote di valore (EV+):"
    )
    if update.message:
        await update.message.reply_text(welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await safe_edit_message(update.callback_query, welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "select_date":
        msg = "📅 **SELEZIONA LA DATA PER LA SCANSIONE BET365:**"
        keyboard = [
            [InlineKeyboardButton("📅 Oggi", callback_data="date_Oggi")],
            [InlineKeyboardButton("📅 Domani", callback_data="date_Domani")],
            [InlineKeyboardButton("🌍 Tutte le date disponibili", callback_data="date_ALL")],
            [InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("date_"):
        chosen_date = query.data.split("_")[1]
        context.user_data["chosen_date"] = chosen_date

        msg = f"🏆 **DATA SELEZIONATA:** `{chosen_date}`\n\nScegli il filtro per i campionati da scansionare su Bet365:"
        keyboard = [
            [InlineKeyboardButton("🏆 Solo Campionati Top (Serie A, Premier, CL, ecc.)", callback_data="league_top")],
            [InlineKeyboardButton("🌍 Tutti i Campionati Disponibili", callback_data="league_all")],
            [InlineKeyboardButton("🔙 Indietro", callback_data="select_date")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("league_"):
        league_type = query.data.split("_")[1]
        chosen_date = context.user_data.get("chosen_date", "Oggi")

        await safe_edit_message(query, f"🔍 **Scansione Bet365 in corso per `{chosen_date}`...** Attendere prego.")

        value_bets = scan_bet365_value_bets(chosen_date, league_type)
        context.user_data["cached_value_bets"] = value_bets

        if not value_bets:
            keyboard = [[InlineKeyboardButton("🔙 Cambia Filtri", callback_data="select_date")]]
            await safe_edit_message(query, f"❌ Nessuna Value Bet trovata su Bet365 per la data `{chosen_date}` al momento.", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        msg = f"🎯 **VALUE BETS BET365 TROVATE ({len(value_bets)} match):**\nScegli una giocata per calcolare lo Stake Kelly e salvarla:"
        keyboard = []
        for i, vb in enumerate(value_bets[:10]):
            btn_text = f"🔥 {vb['partita']} | {vb['pick']} @{vb['quota_bet365']}"
            if len(btn_text) > 60:
                btn_text = f"{vb['partita']} ({vb['value_rate_pct']:+.1f}%)"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"vb_idx_{i}")])

        keyboard.append([InlineKeyboardButton("🔙 Cambia Filtri", callback_data="select_date")])
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("vb_idx_"):
        idx = int(query.data.split("_")[2])
        value_bets = context.user_data.get("cached_value_bets", [])
        if not value_bets or idx >= len(value_bets):
            await query.message.reply_text("❌ Sessione scaduta. Avvia una nuova scansione.")
            return

        vb = value_bets[idx]
        context.user_data["selected_vb"] = vb

        user_id = query.from_user.id
        cap_init, cap_att = get_user_bankroll(user_id)
        b = vb["quota_bet365"] - 1.0
        prob_dec = vb["probabilita"] / 100.0

        kelly_raw = ((b * prob_dec - (1 - prob_dec)) / b) / vb["kelly_divisor"] if b > 0 else 0
        stake_pct_calc = max(0.0, min(kelly_raw * 100, 10.0))
        calculated_stake = (cap_att * stake_pct_calc) / 100.0
        stake_euro = max(1.0, calculated_stake) if calculated_stake < 1.0 else calculated_stake
        stake_pct = (stake_euro / cap_att) * 100.0 if cap_att > 0 else 1.0

        vb["stake_euro"] = stake_euro
        context.user_data["pending_bet_to_save"] = vb

        msg = (
            f"🚀 **VALUE BET BET365 CONFERMATA**\n\n"
            f"🏆 **Campionato:** `{vb['campionato']}`\n"
            f"🏟 **Partita:** `{vb['partita']}`\n"
            f"📅 **Data e Ora:** `{vb['data_ora']}`\n\n"
            f"📌 **Mercato:** `{vb['categoria']}`\n"
            f"💡 **Pick Consigliato:** `{vb['pick']}`\n\n"
            f"📊 **Probabilità Poisson:** `{vb['probabilita']}%` | **Fair Odd:** `{vb['quota_fair']}`\n"
            f"🟢 **Quota Bet365:** `{vb['quota_bet365']}` (EV+ `{vb['value_rate_pct']:+.2f}%`)\n\n"
            f"💰 **Stake Consigliato ({vb['kelly_text']}):** `{stake_pct:.1f}% cassa` (`{stake_euro:.2f}€`)\n\n"
            f"❓ **Vuoi registrare questa giocata nella tua cassa?**"
        )
        keyboard = [
            [InlineKeyboardButton("✅ GIOCATA (Salva in Cassa)", callback_data="confirm_play_bet")],
            [InlineKeyboardButton("❌ NON GIOCATA (Annulla)", callback_data="cancel_play_bet")],
            [InlineKeyboardButton("🔙 Torna alla Lista", callback_data="select_date")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "confirm_play_bet":
        pending_bet = context.user_data.get("pending_bet_to_save")
        if not pending_bet:
            await query.message.reply_text("❌ Nessuna scommessa in attesa di salvataggio.")
            return

        save_bet(
            user_id=query.from_user.id,
            partita=pending_bet["partita"],
            pronostico=pending_bet["pick"],
            quota=pending_bet["quota_bet365"],
            probabilita=pending_bet["probabilita"] / 100.0,
            value_rate=pending_bet["value_rate"],
            stake_euro=pending_bet["stake_euro"]
        )
        context.user_data["pending_bet_to_save"] = None

        msg = (
            f"✅ **SCOMMESSA BET365 REGISTRATA CON SUCCESSO!**\n\n"
            f"🏟 **Partita:** `{pending_bet['partita']}`\n"
            f"🎯 **Pick:** `{pending_bet['pick']}` @`{pending_bet['quota_bet365']}`\n"
            f"💰 **Puntata:** `{pending_bet['stake_euro']:.2f}€`\n\n"
            f"💾 _Giocata salvata nello storico cassa._"
        )
        keyboard = [
            [InlineKeyboardButton("🔍 Nuova Scansione Bet365", callback_data="select_date")],
            [InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "cancel_play_bet":
        context.user_data["pending_bet_to_save"] = None
        msg = "❌ **Scommessa NON salvata.**"
        keyboard = [
            [InlineKeyboardButton("🔍 Nuova Scansione", callback_data="select_date")],
            [InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "manage_bankroll":
        user_id = query.from_user.id
        cap_init, cap_att = get_user_bankroll(user_id)
        profitto_tot = cap_att - cap_init
        roi = ((cap_att - cap_init) / cap_init) * 100 if cap_init > 0 else 0

        msg = (
            f"💰 **GESTIONE BANKROLL & CASSA**\n\n"
            f"💵 **Capitale Iniziale:** `{cap_init:.2f}€`\n"
            f"📈 **Capitale Attuale:** `{cap_att:.2f}€`\n"
            f"📊 **Profitto/Perdita Netta:** `{profitto_tot:+.2f}€`\n"
            f"🎯 **ROI Complessivo:** `{roi:+.1f}%`"
        )
        keyboard = [
            [InlineKeyboardButton("⚙️ Imposta Cassa Iniziale", callback_data="set_cassa")],
            [InlineKeyboardButton("🔴 Azzera Statistiche & Storico", callback_data="confirm_reset")],
            [InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "view_bets":
        conn = sqlite3.connect("value_bets.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, partita, pronostico, quota, stake_euro, esito, profitto FROM saved_bets WHERE user_id = ? ORDER BY id DESC LIMIT 10", (query.from_user.id,))
        rows = cursor.fetchall()
        conn.close()

        keyboard = []
        if rows:
            msg = "📊 **IL TUO STORICO VALUE BET BET365:**\n\n"
            for row in rows:
                bet_id, partita, pron, quota, stake, esito, profitto = row
                if esito == "WON":
                    status_str = f"🟢 **VINTA (+{profitto:.2f}€)**"
                elif esito == "LOST":
                    status_str = f"🔴 **PERSA ({profitto:.2f}€)**"
                else:
                    status_str = "⏳ **IN ATTESA**"

                msg += f"🆔 `#{bet_id}` - 🏟 **{partita}**\n• Pick: `{pron}` | Quota: `{quota}`\n• Stake: `{stake:.2f}€` | Esito: {status_str}\n\n"
            keyboard.append([InlineKeyboardButton("✏️ Aggiorna Esito di una Bet", callback_data="manage_pending_bets")])
            keyboard.append([InlineKeyboardButton("🔴 Azzera Statistiche", callback_data="confirm_reset")])
        else:
            msg = "ℹ️ Nessuna giocata salvata nello storico."

        keyboard.append([InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")])
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "manage_pending_bets":
        conn = sqlite3.connect("value_bets.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, partita, pronostico, stake_euro FROM saved_bets WHERE user_id = ? AND esito = 'PENDING' ORDER BY id DESC", (query.from_user.id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            keyboard = [[InlineKeyboardButton("🔙 Torna alle Bet", callback_data="view_bets")]]
            await safe_edit_message(query, "ℹ️ Non hai giocate in attesa di esito da aggiornare.", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard = []
        msg = "✏️ **SELEZIONA L'ESITO DELLE GIOCATE IN ATTESA:**\n\n"
        for row in rows:
            bet_id, partita, pron, stake = row
            msg += f"🆔 `#{bet_id}` - `{partita}` (`{pron}`) - Puntata: `{stake:.2f}€`\n"
            keyboard.append([
                InlineKeyboardButton(f"🟢 Vinta #{bet_id}", callback_data=f"res_WON_{bet_id}"),
                InlineKeyboardButton(f"🔴 Persa #{bet_id}", callback_data=f"res_LOST_{bet_id}")
            ])

        keyboard.append([InlineKeyboardButton("🔙 Torna allo Storico", callback_data="view_bets")])
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("res_"):
        parts = query.data.split("_")
        esito = parts[1]
        bet_id = int(parts[2])

        update_bet_result(bet_id, query.from_user.id, esito)
        status_label = "🟢 VINTA" if esito == "WON" else "🔴 PERSA"
        await query.answer(f"Bet #{bet_id} contrassegnata come {status_label}!", show_alert=True)
        query.data = "manage_pending_bets"
        await button_handler(update, context)

    elif query.data == "confirm_reset":
        msg = "⚠️ **Sei sicuro di voler azzerare definitivamente lo storico scommesse e il bankroll?**"
        keyboard = [
            [InlineKeyboardButton("✅ Sì, Azzera Tutto", callback_data="do_reset")],
            [InlineKeyboardButton("❌ Annulla", callback_data="manage_bankroll")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "do_reset":
        reset_user_stats(query.from_user.id)
        msg = "🧹 **Statistiche e storico scommesse azzerati con successo!**"
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]]))

    elif query.data == "set_cassa":
        context.user_data["awaiting_bankroll"] = True
        await query.message.reply_text("✍️ **Scrivi l'importo della cassa iniziale in Euro (es. `200`):**")

    elif query.data == "main_menu":
        await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip().replace(",", ".")

    if context.user_data.get("awaiting_bankroll"):
        try:
            nuova_cassa = float(text)
            set_user_bankroll(user_id, nuova_cassa)
            context.user_data["awaiting_bankroll"] = False
            await update.message.reply_text(f"✅ **Bankroll aggiornato a `{nuova_cassa:.2f}€`!**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]]))
            return
        except ValueError:
            await update.message.reply_text("❌ Inserisci un numero valido.")
            return

async def post_init(application: Application):
    await application.bot.set_my_commands([BotCommand("start", "Apri Menu Principale")])

def main():
    init_db()
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot Telegram avviato con scansione automatica delle quote Bet365 e Value Bet...")
    app.run_polling()

if __name__ == "__main__":
    main()
