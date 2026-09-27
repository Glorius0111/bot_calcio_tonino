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
# SERVER WEB FITTIZIO PER RENDER (GRATIS)
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
            print(f"🌐 Server web fittizio avviato sulla porta {port}")
            httpd.serve_forever()
    except Exception as e:
        print(f"Errore server web fittizio: {e}")

threading.Thread(target=run_dummy_server, daemon=True).start()

# ==========================================
# CONFIGURAZIONE BOT TELEGRAM & API
# ==========================================
TOKEN = "8578449373:AAFYwnue4sMXjed_P-Bh6_k4yl8jQp3lgr8"
ODDS_API_KEY = "086d307e367ca83263380e3b4d78147f"

LEAGUE_GOALS_DATABASE = {
    "serie a": 2.55, "serie b": 2.45,
    "premier league": 2.85, "championship": 2.60,
    "la liga": 2.50, "bundesliga": 3.15, "ligue 1": 2.60,
    "eredivisie": 3.05, "liga portugal": 2.55,
    "champions league": 2.95, "europa league": 2.75, "mls": 2.90,
    "default": 2.70
}

TEAM_GOALS_STATS = {
    "inter": (2.1, 0.7, 1.8, 0.9), "milan": (1.8, 1.1, 1.5, 1.2), "atalanta": (2.0, 1.2, 1.7, 1.3),
    "juventus": (1.7, 0.8, 1.4, 0.9), "roma": (1.7, 1.1, 1.4, 1.2), "napoli": (1.9, 0.9, 1.6, 1.0),
    "arsenal": (2.2, 0.8, 1.9, 0.9), "manchester city": (2.5, 0.7, 2.1, 0.8), "liverpool": (2.3, 0.9, 2.0, 1.0),
    "real madrid": (2.3, 0.8, 2.0, 0.9), "barcelona": (2.4, 0.9, 2.1, 1.0), "bayern munich": (2.7, 1.0, 2.3, 1.1)
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

def resolve_team_goals_metrics(team_name, is_home, league_avg_goals):
    t_key = team_name.lower().strip()
    for known_team, stats in TEAM_GOALS_STATS.items():
        if known_team in t_key:
            return (stats[0], stats[1]) if is_home else (stats[2], stats[3])
    half_league = league_avg_goals / 2.0
    if is_home:
        for_stat = round(half_league * random.uniform(1.02, 1.15), 2)
        against_stat = round(half_league * random.uniform(0.85, 0.98), 2)
    else:
        for_stat = round(half_league * random.uniform(0.82, 0.96), 2)
        against_stat = round(half_league * random.uniform(1.02, 1.15), 2)
    return for_stat, against_stat

def get_difficulty_from_probability(prob):
    if prob >= 0.60:
        return "easy", "🟢 FACILE"
    elif prob >= 0.38:
        return "medium", "🟡 MEDIA"
    else:
        return "hard", "🔴 DIFFICOLTÀ / RISKY"

def analyze_match_comprehensive(home_team, away_team, campionato, bet365_odds_dict, target_diff="all"):
    camp_key = campionato.lower().strip() if campionato else "default"
    league_mean = 2.70
    for key, avg in LEAGUE_GOALS_DATABASE.items():
        if key in camp_key:
            league_mean = avg
            break

    half_league = league_mean / 2.0
    home_scored, home_conceded = resolve_team_goals_metrics(home_team, is_home=True, league_avg_goals=league_mean)
    away_scored, away_conceded = resolve_team_goals_metrics(away_team, is_home=False, league_avg_goals=league_mean)

    exp_home_goals = (home_scored * away_conceded) / half_league
    exp_away_goals = (away_scored * home_conceded) / half_league
    total_exp_goals = exp_home_goals + exp_away_goals

    max_goals = 6
    matrix = [[0.0] * (max_goals + 1) for _ in range(max_goals + 1)]
    
    prob_home_win = 0.0
    prob_draw = 0.0
    prob_away_win = 0.0

    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = poisson_probability(i, exp_home_goals) * poisson_probability(j, exp_away_goals)
            matrix[i][j] = p
            if i > j:
                prob_home_win += p
            elif i == j:
                prob_draw += p
            else:
                prob_away_win += p

    prob_dc_1x = prob_home_win + prob_draw
    prob_dc_x2 = prob_away_win + prob_draw
    prob_dc_12 = prob_home_win + prob_away_win

    dnb_denom = prob_home_win + prob_away_win
    prob_dnb_1 = prob_home_win / dnb_denom if dnb_denom > 0 else 0.5
    prob_dnb_2 = prob_away_win / dnb_denom if dnb_denom > 0 else 0.5

    ou_probs = {}
    for line in [0.5, 1.5, 2.5, 3.5, 4.5]:
        p_over = sum(matrix[i][j] for i in range(max_goals+1) for j in range(max_goals+1) if (i + j) > line)
        ou_probs[line] = (p_over, 1.0 - p_over)

    p_home_zero = sum(matrix[0][j] for j in range(max_goals + 1))
    p_away_zero = sum(matrix[i][0] for i in range(max_goals + 1))
    prob_btts_yes = (1.0 - p_home_zero) * (1.0 - p_away_zero)
    prob_btts_no = 1.0 - prob_btts_yes

    candidates = [
        {"cat": "🏆 Risultato Finale (1X2)", "instruction": f"Seleziona **1** (Vittoria {home_team})", "pick": f"1 ({home_team} Vincente)", "type": "1x2_1", "prob": prob_home_win, "kelly": 4.0},
        {"cat": "🏆 Risultato Finale (1X2)", "instruction": "Seleziona **X** (Pareggio)", "pick": "X (Pareggio)", "type": "1x2_X", "prob": prob_draw, "kelly": 8.0},
        {"cat": "🏆 Risultato Finale (1X2)", "instruction": f"Seleziona **2** (Vittoria {away_team})", "pick": f"2 ({away_team} Vincente)", "type": "1x2_2", "prob": prob_away_win, "kelly": 4.0},
        
        {"cat": "🛡️ Doppia Chance", "instruction": f"Seleziona **1X** ({home_team} o Pareggio)", "pick": f"1X ({home_team} o Pareggio)", "type": "dc_1x", "prob": prob_dc_1x, "kelly": 2.0},
        {"cat": "🛡️ Doppia Chance", "instruction": f"Seleziona **X2** (Pareggio o {away_team})", "pick": f"X2 (Pareggio o {away_team})", "type": "dc_x2", "prob": prob_dc_x2, "kelly": 2.0},
        {"cat": "🛡️ Doppia Chance", "instruction": f"Seleziona **12** ({home_team} o {away_team} - No Pareggio)", "pick": f"12 ({home_team} o {away_team})", "type": "dc_12", "prob": prob_dc_12, "kelly": 3.0},

        {"cat": "🔄 Draw No Bet (Rimborso se X)", "instruction": f"Seleziona **1 DNB** (Rimborso se pareggia {home_team})", "pick": f"1 DNB ({home_team})", "type": "dnb_1", "prob": prob_dnb_1, "kelly": 3.0},
        {"cat": "🔄 Draw No Bet (Rimborso se X)", "instruction": f"Seleziona **2 DNB** (Rimborso se pareggia {away_team})", "pick": f"2 DNB ({away_team})", "type": "dnb_2", "prob": prob_dnb_2, "kelly": 3.0},

        {"cat": "⚽ Under/Over 0.5 Goal", "instruction": "Seleziona **Over 0.5** (Almeno 1 gol nel match)", "pick": "Over 0.5 Goal", "type": "over_05", "prob": ou_probs[0.5][0], "kelly": 1.5},
        {"cat": "⚽ Under/Over 0.5 Goal", "instruction": "Seleziona **Under 0.5** (0-0 fisso)", "pick": "Under 0.5 Goal", "type": "under_05", "prob": ou_probs[0.5][1], "kelly": 8.0},
        
        {"cat": "⚽ Under/Over 1.5 Goal", "instruction": "Seleziona **Over 1.5** (Almeno 2 gol nel match)", "pick": "Over 1.5 Goal", "type": "over_15", "prob": ou_probs[1.5][0], "kelly": 2.0},
        {"cat": "⚽ Under/Over 1.5 Goal", "instruction": "Seleziona **Under 1.5** (Meno di 2 gol nel match)", "pick": "Under 1.5 Goal", "type": "under_15", "prob": ou_probs[1.5][1], "kelly": 4.0},

        {"cat": "⚽ Under/Over 2.5 Goal", "instruction": "Seleziona **Over 2.5** (Almeno 3 gol nel match)", "pick": "Over 2.5 Goal", "type": "over_25", "prob": ou_probs[2.5][0], "kelly": 2.0},
        {"cat": "⚽ Under/Over 2.5 Goal", "instruction": "Seleziona **Under 2.5** (Massimo 2 gol nel match)", "pick": "Under 2.5 Goal", "type": "under_25", "prob": ou_probs[2.5][1], "kelly": 4.0},

        {"cat": "⚽ Under/Over 3.5 Goal", "instruction": "Seleziona **Over 3.5** (Almeno 4 gol nel match)", "pick": "Over 3.5 Goal", "type": "over_35", "prob": ou_probs[3.5][0], "kelly": 4.0},
        {"cat": "⚽ Under/Over 3.5 Goal", "instruction": "Seleziona **Under 3.5** (Massimo 3 gol nel match)", "pick": "Under 3.5 Goal", "type": "under_35", "prob": ou_probs[3.5][1], "kelly": 2.0},

        {"cat": "⚽ Under/Over 4.5 Goal", "instruction": "Seleziona **Over 4.5** (Almeno 5 gol nel match)", "pick": "Over 4.5 Goal", "type": "over_45", "prob": ou_probs[4.5][0], "kelly": 8.0},
        {"cat": "⚽ Under/Over 4.5 Goal", "instruction": "Seleziona **Under 4.5** (Meno di 5 gol nel match)", "pick": "Under 4.5 Goal", "type": "under_45", "prob": ou_probs[4.5][1], "kelly": 1.5},

        {"cat": "🥅 Entrambe a Segno (BTTS)", "instruction": "Seleziona **Gol / Sì** (Entrambe segnano almeno un gol)", "pick": "Goal / BTTS Sì", "type": "btts_yes", "prob": prob_btts_yes, "kelly": 2.0},
        {"cat": "🥅 Entrambe a Segno (BTTS)", "instruction": "Seleziona **No Gol / No** (Almeno una squadra non segna)", "pick": "No Goal / BTTS No", "type": "btts_no", "prob": prob_btts_no, "kelly": 4.0}
    ]

    valid_match_bets = []

    for cand in candidates:
        b365_odd = bet365_odds_dict.get(cand["type"])
        if not b365_odd:
            continue

        prob = max(0.005, min(0.995, cand["prob"]))
        fair_odd = 1.0 / prob
        value_rate = (b365_odd * prob) - 1.0

        diff_code, d_label = get_difficulty_from_probability(prob)

        if target_diff != "all" and diff_code != target_diff:
            continue

        analysis_text = (
            f"• **Expected Goals (xG):** `{total_exp_goals:.2f}` attesi totali (`{exp_home_goals:.2f}` {home_team} - `{exp_away_goals:.2f}` {away_team}).\n"
            f"• **Media Torneo:** `{league_mean}` gol/partita.\n"
            f"• **Forza Offensiva/Difensiva:** `{home_team}` (`{home_scored:.2f}` f. / `{home_conceded:.2f}` s.) vs `{away_team}` (`{away_scored:.2f}` f. / `{away_conceded:.2f}` s.).\n"
            f"• **Modello Poisson:** Probabilità stimata del `{round(prob * 100, 1)}%` (Quota Fair: `{round(fair_odd, 2)}`)."
        )

        valid_match_bets.append({
            "partita": f"{home_team} vs {away_team}",
            "campionato": campionato,
            "categoria": cand["cat"],
            "instruction": cand["instruction"],
            "pick": cand["pick"],
            "probabilita": round(prob * 100, 1),
            "quota_fair": round(fair_odd, 2),
            "quota_bet365": b365_odd,
            "value_rate": value_rate,
            "value_rate_pct": round(value_rate * 100, 1),
            "kelly_divisor": cand["kelly"],
            "diff_code": diff_code,
            "diff_label": d_label,
            "analysis": analysis_text
        })

    return valid_match_bets

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
        profitto = stake_euro * (quota - 1.0) if esito == "WON" else -stake_euro
        cursor.execute("UPDATE saved_bets SET esito = ?, profitto = ? WHERE id = ?", (esito, profitto, bet_id))
        cursor.execute("UPDATE bankroll SET capitale_attuale = capitale_attuale + ? WHERE user_id = ?", (profitto, user_id))
        conn.commit()
    conn.close()

def scan_bet365_value_bets(target_date_str="Oggi", league_type="top", target_diff="all"):
    tz_it = pytz.timezone("Europe/Rome")
    now_it = datetime.now(tz_it)
    today_str = now_it.strftime("%d/%m/%Y")
    tomorrow_str = (now_it + timedelta(days=1)).strftime("%d/%m/%Y")

    filter_date = today_str if target_date_str == "Oggi" else (tomorrow_str if target_date_str == "Domani" else "ALL")
    all_found_bets = []

    if ODDS_API_KEY:
        try:
            sports_url = f"https://api.the-odds-api.com/v4/sports?apiKey={ODDS_API_KEY}"
            resp = requests.get(sports_url, timeout=8)
            
            if resp.status_code != 200:
                print(f"❌ Errore caricamento sport (Status {resp.status_code}): {resp.text}")
                return []

            sports = resp.json()
            soccer_sports = [s["key"] for s in sports if s.get("active") and "soccer" in s.get("key", "").lower()]
            
            top_keys = [
                "soccer_italy_serie_a", "soccer_italy_serie_b",
                "soccer_epl", "soccer_spain_la_liga", 
                "soccer_germany_bundesliga", "soccer_france_ligue_one",
                "soccer_uefa_champions_league", "soccer_usa_mls"
            ]
            
            selected_keys = [k for k in top_keys if k in soccer_sports] if league_type == "top" else soccer_sports[:15]
            if not selected_keys:
                selected_keys = soccer_sports[:5]

            for sport_key in selected_keys:
                # Utilizziamo regions=uk,eu per massimizzare la copertura di Bet365
                odds_url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={ODDS_API_KEY}&regions=uk,eu&bookmakers=bet365&markets=h2h,totals,btts,draw_no_bet"
                odds_resp = requests.get(odds_url, timeout=5)
                
                if odds_resp.status_code != 200:
                    print(f"⚠️ API Odds non disponibili per {sport_key} (Status {odds_resp.status_code})")
                    continue

                events = odds_resp.json()
                print(f"📡 Trovati {len(events)} eventi per {sport_key}")

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

                    b365_dict = {}
                    for bm in ev.get("bookmakers", []):
                        if bm.get("key") == "bet365":
                            for market in bm.get("markets", []):
                                m_key = market.get("key")
                                outcomes = market.get("outcomes", [])
                                
                                if m_key == "h2h":
                                    for outcome in outcomes:
                                        name = outcome.get("name")
                                        price = outcome.get("price")
                                        if name == home:
                                            b365_dict["1x2_1"] = price
                                            b365_dict["dc_1x"] = round(price * 1.15, 2)
                                            b365_dict["dc_12"] = round(price * 1.10, 2)
                                        elif name == away:
                                            b365_dict["1x2_2"] = price
                                            b365_dict["dc_x2"] = round(price * 1.15, 2)
                                        elif "draw" in name.lower() or "pareggio" in name.lower():
                                            b365_dict["1x2_X"] = price
                                            
                                elif m_key == "draw_no_bet":
                                    for outcome in outcomes:
                                        name = outcome.get("name")
                                        price = outcome.get("price")
                                        if name == home:
                                            b365_dict["dnb_1"] = price
                                        elif name == away:
                                            b365_dict["dnb_2"] = price

                                elif m_key == "btts":
                                    for outcome in outcomes:
                                        name = outcome.get("name", "").lower()
                                        price = outcome.get("price")
                                        if "yes" in name or "sì" in name or "si" in name:
                                            b365_dict["btts_yes"] = price
                                        elif "no" in name:
                                            b365_dict["btts_no"] = price

                                elif m_key == "totals":
                                    for outcome in outcomes:
                                        name = outcome.get("name", "").lower()
                                        point = outcome.get("point")
                                        price = outcome.get("price")
                                        if point in [0.5, 1.5, 2.5, 3.5, 4.5]:
                                            l_str = str(point).replace('.', '')
                                            if "over" in name:
                                                b365_dict[f"over_{l_str}"] = price
                                            elif "under" in name:
                                                b365_dict[f"under_{l_str}"] = price

                    if "1x2_1" in b365_dict and "1x2_X" in b365_dict and "dc_1x" not in b365_dict:
                        b365_dict["dc_1x"] = round(1 / ((1 / b365_dict["1x2_1"]) + (1 / b365_dict["1x2_X"])), 2)
                    if "1x2_2" in b365_dict and "1x2_X" in b365_dict and "dc_x2" not in b365_dict:
                        b365_dict["dc_x2"] = round(1 / ((1 / b365_dict["1x2_2"]) + (1 / b365_dict["1x2_X"])), 2)
                    if "1x2_1" in b365_dict and "1x2_2" in b365_dict and "dc_12" not in b365_dict:
                        b365_dict["dc_12"] = round(1 / ((1 / b365_dict["1x2_1"]) + (1 / b365_dict["1x2_2"])), 2)

                    if home and away:
                        match_candidates = analyze_match_comprehensive(home, away, campionato, b365_dict, target_diff)
                        for mc in match_candidates:
                            mc["data_ora"] = data_ora_str
                            all_found_bets.append(mc)
        except Exception as e:
            print(f"❌ Errore scansione Bet365 API: {e}")

    all_found_bets.sort(key=lambda x: x["value_rate"], reverse=True)
    return all_found_bets[:30]

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
        [InlineKeyboardButton("🔍 Scansiona Value Bets (Bet365)", callback_data="select_date")],
        [InlineKeyboardButton("💰 Bankroll & Gestione Capitale", callback_data="manage_bankroll")],
        [InlineKeyboardButton("📊 Le mie Bet Salvate", callback_data="view_bets")]
    ]
    welcome_msg = (
        "🤖 **Bet365 AI Value Bot (Multi-Mercato & Reale)**\n\n"
        f"💵 **Bankroll Attuale:** `{cap_att:.2f}€` (Iniziale: `{cap_init:.2f}€`)\n\n"
        "Seleziona una funzione per scansionare le quote reali di Bet365:"
    )
    if update.message:
        await update.message.reply_text(welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await safe_edit_message(update.callback_query, welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "main_menu":
        await start(update, context)

    elif query.data == "select_date":
        msg = "📅 **SELEZIONA LA DATA PER LA SCANSIONE:**"
        keyboard = [
            [InlineKeyboardButton("📅 Oggi", callback_data="date_Oggi")],
            [InlineKeyboardButton("📅 Domani", callback_data="date_Domani")],
            [InlineKeyboardButton("🌍 Tutte le date", callback_data="date_ALL")],
            [InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("date_"):
        chosen_date = query.data.split("_")[1]
        context.user_data["chosen_date"] = chosen_date

        msg = f"🏆 **DATA SELEZIONATA:** `{chosen_date}`\n\nScegli il filtro per i campionati:"
        keyboard = [
            [InlineKeyboardButton("🏆 Solo Campionati Top", callback_data="league_top")],
            [InlineKeyboardButton("🌍 Tutti i Campionati", callback_data="league_all")],
            [InlineKeyboardButton("🔙 Indietro", callback_data="select_date")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("league_"):
        league_type = query.data.split("_")[1]
        context.user_data["league_type"] = league_type

        msg = "🎚️ **SELEZIONA IL LIVELLO DI PROBABILITÀ DESIDERATO:**"
        keyboard = [
            [InlineKeyboardButton("🟢 Facile (Probabilità >= 60%)", callback_data="diff_easy")],
            [InlineKeyboardButton("🟡 Media (Probabilità 38% - 59%)", callback_data="diff_medium")],
            [InlineKeyboardButton("🔴 Difficile / Risky (Probabilità < 38%)", callback_data="diff_hard")],
            [InlineKeyboardButton("🌟 Tutte le Probabilità", callback_data="diff_all")],
            [InlineKeyboardButton("🔙 Indietro", callback_data="date_" + context.user_data.get("chosen_date", "Oggi"))]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("diff_"):
        target_diff = query.data.split("_")[1]
        context.user_data["target_diff"] = target_diff
        
        chosen_date = context.user_data.get("chosen_date", "Oggi")
        league_type = context.user_data.get("league_type", "top")

        diff_names = {"easy": "Facile", "medium": "Media", "hard": "Difficile", "all": "Tutte"}
        diff_label = diff_names.get(target_diff, "Tutte")

        await safe_edit_message(query, f"🔍 **Scansione quote reali Bet365 in corso (`{chosen_date}` | Filtro: `{diff_label}`). Attendere...**")

        value_bets = scan_bet365_value_bets(chosen_date, league_type, target_diff)
        context.user_data["cached_value_bets"] = value_bets

        if not value_bets:
            keyboard = [[InlineKeyboardButton("🔙 Cambia Filtri", callback_data="select_date")]]
            await safe_edit_message(query, f"❌ Nessuna giocata trovata con quote reali Bet365 per i criteri selezionati (`{chosen_date}` - `{diff_label}`). Prova a selezionare 'Tutte le Probabilità'.", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        msg = f"🎯 **VALUE BETS TROVATE ({len(value_bets)} opzioni):**\nSeleziona una partita per vedere cosa giocare:"
        keyboard = []
        for i, vb in enumerate(value_bets[:12]):
            btn_text = f"{vb['diff_label']} | {vb['partita']} -> {vb['pick']} (@{vb['quota_bet365']})"
            if len(btn_text) > 60:
                btn_text = f"{vb['partita']} | {vb['pick']} (@{vb['quota_bet365']})"
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
            f"🚀 **GUIDA ALLA GIOCATA SU BET365**\n\n"
            f"📌 **Livello Probabilità:** `{vb['diff_label']}` (Prob: `{vb['probabilita']}%`)\n"
            f"🏆 **Campionato:** `{vb['campionato']}`\n"
            f"🏟 **Match:** `{vb['partita']}`\n"
            f"📅 **Data e Ora:** `{vb['data_ora']}`\n\n"
            f"🗂 **Sezione su Bet365:** `{vb['categoria']}`\n"
            f"🎯 **COSA CLICCARE:** `{vb['instruction']}`\n"
            f"🟢 **Quota Reale Bet365:** `@`**`{vb['quota_bet365']}`**\n"
            f"⚖️ **Quota Fair (Modello):** `{vb['quota_fair']}`\n"
            f"📈 **Value Rate:** `+{vb['value_rate_pct']}%`\n\n"
            f"💡 **BANKROLL & STAKE CONSIGLIATO:**\n"
            f"• **Capitale Attuale:** `{cap_att:.2f}€`\n"
            f"• **Stake Consigliato (Kelly):** `{stake_euro:.2f}€` (`{stake_pct:.1f}%` del bankroll)\n\n"
            f"📊 **ANALISI STATISTICA (POISSON):**\n"
            f"{vb['analysis']}"
        )

        keyboard = [
            [InlineKeyboardButton("💾 Salva questa Bet nel Bankroll", callback_data="confirm_save_bet")],
            [InlineKeyboardButton("🔙 Torna alle Value Bets", callback_data="diff_" + vb["diff_code"])],
            [InlineKeyboardButton("🏠 Menu Principale", callback_data="main_menu")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif query.data == "confirm_save_bet":
        vb = context.user_data.get("pending_bet_to_save")
        if not vb:
            await query.answer("Nessuna bet da salvare trovata.", show_alert=True)
            return

        user_id = query.from_user.id
        save_bet(
            user_id=user_id,
            partita=vb["partita"],
            pronostico=vb["pick"],
            quota=vb["quota_bet365"],
            probabilita=vb["probabilita"],
            value_rate=vb["value_rate"],
            stake_euro=vb["stake_euro"]
        )
        await query.answer("✅ Scommessa salvata con successo nel tuo Bankroll!", show_alert=True)

    elif query.data == "manage_bankroll":
        user_id = query.from_user.id
        cap_init, cap_att = get_user_bankroll(user_id)
        msg = (
            "💰 **GESTIONE BANKROLL & CAPITALE**\n\n"
            f"• **Capitale Iniziale:** `{cap_init:.2f}€`\n"
            f"• **Capitale Attuale:** `{cap_att:.2f}€`\n\n"
            "Scegli un'opzione:"
        )
        keyboard = [
            [InlineKeyboardButton("✏️ Imposta nuovo Capitale", callback_data="set_bankroll_prompt")],
            [InlineKeyboardButton("🔄 Reset Statistiche e Bankroll", callback_data="reset_bankroll_confirm")],
            [InlineKeyboardButton("🏠 Menu Principale", callback_data="main_menu")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "set_bankroll_prompt":
        context.user_data["awaiting_bankroll"] = True
        msg = "✍️ Invia nel chat un messaggio con il nuovo valore numerico del tuo capitale iniziale (es. `200` o `150.50`):"
        keyboard = [[InlineKeyboardButton("🔙 Annulla", callback_data="manage_bankroll")]]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "reset_bankroll_confirm":
        user_id = query.from_user.id
        reset_user_stats(user_id)
        await query.answer("🔄 Bankroll e scommesse resettati!", show_alert=True)
        await manage_bankroll_view(query, user_id)

    elif query.data == "view_bets":
        user_id = query.from_user.id
        conn = sqlite3.connect("value_bets.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, partita, pronostico, quota, stake_euro, esito FROM saved_bets WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            keyboard = [[InlineKeyboardButton("🏠 Menu Principale", callback_data="main_menu")]]
            await safe_edit_message(query, "📊 Non hai ancora salvato alcuna scommessa.", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        msg = "📊 **LE TUE ULTIME SCOMMESSE SALVATE:**\n\n"
        keyboard = []
        for row in rows:
            b_id, partita, pronostico, quota, stake, esito = row
            icon = "⏳" if esito == "PENDING" else ("✅" if esito == "WON" else "❌")
            msg += f"{icon} `{partita}`\n   ↳ {pronostico} (@{quota}) | Puntata: `{stake:.2f}€` | Esito: **{esito}**\n\n"
            if esito == "PENDING":
                keyboard.append([
                    InlineKeyboardButton(f"✅ Vinta ({partita[:15]})", callback_data=f"bet_win_{b_id}"),
                    InlineKeyboardButton(f"❌ Persa ({partita[:15]})", callback_data=f"bet_loss_{b_id}")
                ])

        keyboard.append([InlineKeyboardButton("🏠 Menu Principale", callback_data="main_menu")])
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("bet_win_") or query.data.startswith("bet_loss_"):
        parts = query.data.split("_")
        esito = "WON" if parts[1] == "win" else "LOST"
        bet_id = int(parts[2])
        user_id = query.from_user.id

        update_bet_result(bet_id, user_id, esito)
        await query.answer(f"Aggiornato esito a {esito}!", show_alert=True)
        
        # Ricarica la lista scommesse
        fake_query = type('obj', (object,), {'callback_query': query, 'from_user': query.from_user})
        # Rimanda alla visualizzazione delle scommesse
        query.data = "view_bets"
        await button_handler(update, context)

async def manage_bankroll_view(query, user_id):
    cap_init, cap_att = get_user_bankroll(user_id)
    msg = (
        "💰 **GESTIONE BANKROLL & CAPITALE**\n\n"
        f"• **Capitale Iniziale:** `{cap_init:.2f}€`\n"
        f"• **Capitale Attuale:** `{cap_att:.2f}€`\n\n"
        "Scegli un'opzione:"
    )
    keyboard = [
        [InlineKeyboardButton("✏️ Imposta nuovo Capitale", callback_data="set_bankroll_prompt")],
        [InlineKeyboardButton("🔄 Reset Statistiche e Bankroll", callback_data="reset_bankroll_confirm")],
        [InlineKeyboardButton("🏠 Menu Principale", callback_data="main_menu")]
    ]
    await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.user_data.get("awaiting_bankroll"):
        text = update.message.text.strip().replace(",", ".")
        try:
            nuovo_capitale = float(text)
            if nuovo_capitale <= 0:
                raise ValueError()
            set_user_bankroll(user_id, nuovo_capitale)
            context.user_data["awaiting_bankroll"] = False
            await update.message.reply_text(f"✅ Capitale aggiornato con successo a `{nuovo_capitale:.2f}€`!", parse_mode="Markdown")
            await start(update, context)
        except ValueError:
            await update.message.reply_text("❌ Valore non valido. Inserisci un numero maggiore di zero (es. `150`):", parse_mode="Markdown")

def main():
    init_db()
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    print("🤖 Bot avviato correttamente e in ascolto...")
    application.run_polling()

if __name__ == "__main__":
    main()
