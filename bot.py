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
    "soccer_spain_la_liga": "🇪🇸 Spagna - La Liga",
    "soccer_germany_bundesliga": "🇩🇪 Germania - Bundesliga",
    "soccer_france_ligue_one": "🇫🇷 Francia - Ligue 1",
    "soccer_uefa_champions_league": "🇪🇺 UEFA - Champions League"
}

def clean_league_name(raw_name, sport_key=""):
    if sport_key and sport_key in SPORT_KEY_MAP:
        return SPORT_KEY_MAP[sport_key]
    base_text = raw_name if raw_name else ""
    cleaned = re.sub(r'^(soccer|calcio)\s*[-–:]?\s*', '', base_text, flags=re.IGNORECASE).strip()
    return cleaned.title() if cleaned else "Calcio"

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
        return "hard", "🔴 DIFFICILE"

def analyze_match_comprehensive(home_team, away_team, campionato, target_diff="all"):
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

    ou_probs = {}
    for line in [1.5, 2.5, 3.5]:
        p_over = sum(matrix[i][j] for i in range(max_goals+1) for j in range(max_goals+1) if (i + j) > line)
        ou_probs[line] = (p_over, 1.0 - p_over)

    p_home_zero = sum(matrix[0][j] for j in range(max_goals + 1))
    p_away_zero = sum(matrix[i][0] for i in range(max_goals + 1))
    prob_btts_yes = (1.0 - p_home_zero) * (1.0 - p_away_zero)

    # Raccolta automatica di tutti i mercati principali e secondari
    candidates = [
        {"cat": "🏆 Risultato Finale (1X2)", "instruction": f"1 ({home_team} Vincente)", "pick": f"1 ({home_team} Vincente)", "prob": prob_home_win, "kelly": 4.0},
        {"cat": "🏆 Risultato Finale (1X2)", "instruction": "X (Pareggio)", "pick": "X (Pareggio)", "prob": prob_draw, "kelly": 8.0},
        {"cat": "🏆 Risultato Finale (1X2)", "instruction": f"2 ({away_team} Vincente)", "pick": f"2 ({away_team} Vincente)", "prob": prob_away_win, "kelly": 4.0},
        {"cat": "🛡️ Doppia Chance", "instruction": f"1X ({home_team} o Pareggio)", "pick": f"1X ({home_team} o Pareggio)", "prob": prob_dc_1x, "kelly": 2.0},
        {"cat": "🛡️ Doppia Chance", "instruction": f"X2 (Pareggio o {away_team})", "pick": f"X2 (Pareggio o {away_team})", "prob": prob_dc_x2, "kelly": 2.0},
        {"cat": "⚽ Under/Over 1.5 Goal", "instruction": "Over 1.5 Goal", "pick": "Over 1.5 Goal", "prob": ou_probs[1.5][0], "kelly": 2.0},
        {"cat": "⚽ Under/Over 1.5 Goal", "instruction": "Under 1.5 Goal", "pick": "Under 1.5 Goal", "prob": ou_probs[1.5][1], "kelly": 4.0},
        {"cat": "⚽ Under/Over 2.5 Goal", "instruction": "Over 2.5 Goal", "pick": "Over 2.5 Goal", "prob": ou_probs[2.5][0], "kelly": 2.0},
        {"cat": "⚽ Under/Over 2.5 Goal", "instruction": "Under 2.5 Goal", "pick": "Under 2.5 Goal", "prob": ou_probs[2.5][1], "kelly": 4.0},
        {"cat": "⚽ Under/Over 3.5 Goal", "instruction": "Over 3.5 Goal", "pick": "Over 3.5 Goal", "prob": ou_probs[3.5][0], "kelly": 4.0},
        {"cat": "⚽ Under/Over 3.5 Goal", "instruction": "Under 3.5 Goal", "pick": "Under 3.5 Goal", "prob": ou_probs[3.5][1], "kelly": 2.0},
        {"cat": "🥅 Entrambe a Segno (BTTS)", "instruction": "Gol / BTTS Sì", "pick": "Goal / BTTS Sì", "prob": prob_btts_yes, "kelly": 2.0},
    ]

    valid_match_bets = []
    for cand in candidates:
        prob = max(0.005, min(0.995, cand["prob"]))
        fair_odd = 1.0 / prob
        diff_code, d_label = get_difficulty_from_probability(prob)

        # Filtro per difficoltà (Facile, Media, Difficile, Tutte)
        if target_diff != "all" and diff_code != target_diff:
            continue

        analysis_text = (
            f"• **Expected Goals (xG):** `{total_exp_goals:.2f}` attesi (`{exp_home_goals:.2f}` - `{exp_away_goals:.2f}`).\n"
            f"• **Media Torneo:** `{league_mean}` gol/partita.\n"
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
            "kelly_divisor": cand["kelly"],
            "diff_code": diff_code,
            "diff_label": d_label,
            "analysis": analysis_text
        })

    return valid_match_bets

# ==========================================
# GESTIONE DATABASE SQLITE
# ==========================================
def init_db():
    conn = sqlite3.connect("value_bets.db", check_same_thread=False)
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
    conn = sqlite3.connect("value_bets.db", check_same_thread=False)
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
    conn = sqlite3.connect("value_bets.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO bankroll (user_id, capitale_iniziale, capitale_attuale)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET capitale_iniziale=?, capitale_attuale=?
    ''', (user_id, nuovo_capitale, nuovo_capitale, nuovo_capitale, nuovo_capitale))
    conn.commit()
    conn.close()

def reset_user_stats(user_id):
    conn = sqlite3.connect("value_bets.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_bets WHERE user_id = ?", (user_id,))
    cursor.execute("UPDATE bankroll SET capitale_attuale = capitale_iniziale WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def save_bet(user_id, partita, pronostico, quota, probabilita, value_rate, stake_euro):
    conn = sqlite3.connect("value_bets.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO saved_bets (user_id, partita, pronostico, quota, probabilita, value_rate, stake_euro)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, partita, pronostico, quota, probabilita, value_rate, stake_euro))
    conn.commit()
    conn.close()

def update_bet_result(bet_id, user_id, esito):
    conn = sqlite3.connect("value_bets.db", check_same_thread=False)
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

def scan_api_fixtures(target_date_str="Oggi", league_type="top", target_diff="all"):
    tz_it = pytz.timezone("Europe/Rome")
    now_it = datetime.now(tz_it)
    
    if target_date_str == "Oggi":
        filter_date = now_it.strftime("%d/%m/%Y")
    elif target_date_str == "Domani":
        filter_date = (now_it + timedelta(days=1)).strftime("%d/%m/%Y")
    else:
        filter_date = "ALL"

    all_found_bets = []

    if ODDS_API_KEY:
        try:
            sports_url = f"https://api.the-odds-api.com/v4/sports?apiKey={ODDS_API_KEY}"
            resp = requests.get(sports_url, timeout=8)
            if resp.status_code != 200:
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
                odds_url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={ODDS_API_KEY}&regions=uk,eu&markets=h2h"
                odds_resp = requests.get(odds_url, timeout=5)
                if odds_resp.status_code != 200:
                    continue

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
                        continue

                    if filter_date != "ALL" and match_date_str != filter_date:
                        continue

                    if home and away:
                        match_candidates = analyze_match_comprehensive(home, away, campionato, target_diff)
                        for mc in match_candidates:
                            mc["data_ora"] = data_ora_str
                            all_found_bets.append(mc)
        except Exception as e:
            print(f"❌ Errore API: {e}")

    # ORDINAMENTO RIGOROSO PER PROBABILITÀ (Dalla più alta alla più bassa)
    all_found_bets.sort(key=lambda x: x["probabilita"], reverse=True)
    return all_found_bets[:40]

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
    _, cap_att = get_user_bankroll(user_id)
    context.user_data["awaiting_bankroll"] = False
    context.user_data["awaiting_real_odd"] = False

    keyboard = [
        [InlineKeyboardButton("🔍 Scansiona Partite (API)", callback_data="select_date")],
        [InlineKeyboardButton("💰 Bankroll & Gestione Capitale", callback_data="manage_bankroll")],
        [InlineKeyboardButton("📊 Le mie Bet Salvate", callback_data="view_bets")]
    ]
    welcome_msg = (
        "🤖 **AI Value Betting Bot (Poisson + Quota Utente)**\n\n"
        f"💵 **Bankroll Attuale:** `{cap_att:.2f}€`\n\n"
        "Seleziona un'opzione per iniziare:"
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
        msg = "📅 **SELEZIONA LA DATA:**"
        keyboard = [
            [InlineKeyboardButton("📅 Solo Oggi", callback_data="date_Oggi")],
            [InlineKeyboardButton("📅 Solo Domani", callback_data="date_Domani")],
            [InlineKeyboardButton("🌍 Tutte le date", callback_data="date_ALL")],
            [InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("date_"):
        chosen_date = query.data.split("_")[1]
        context.user_data["chosen_date"] = chosen_date

        msg = f"🏆 **DATA SELEZIONATA:** `{chosen_date}`\n\nScegli il livello dei campionati:"
        keyboard = [
            [InlineKeyboardButton("🏆 Solo Top Campionati", callback_data="league_top")],
            [InlineKeyboardButton("🌍 Tutti i Campionati della Giornata", callback_data="league_all")],
            [InlineKeyboardButton("🔙 Indietro", callback_data="select_date")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("league_"):
        league_type = query.data.split("_")[1]
        context.user_data["league_type"] = league_type

        msg = "🎚️ **SELEZIONA IL LIVELLO DI PROBABILITÀ:**"
        keyboard = [
            [InlineKeyboardButton("🟢 Facile (Probabilità >= 60%)", callback_data="diff_easy")],
            [InlineKeyboardButton("🟡 Media (Probabilità 38% - 59%)", callback_data="diff_medium")],
            [InlineKeyboardButton("🔴 Difficile (Probabilità < 38%)", callback_data="diff_hard")],
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

        await safe_edit_message(query, f"🔍 **Scansione partite in corso (`{chosen_date}` | `{diff_label}`). Attendere...**")

        value_bets = scan_api_fixtures(chosen_date, league_type, target_diff)
        context.user_data["cached_value_bets"] = value_bets

        if not value_bets:
            keyboard = [[InlineKeyboardButton("🔙 Cambia Filtri", callback_data="select_date")]]
            await safe_edit_message(query, f"❌ Nessuna giocata trovata per i criteri selezionati (`{chosen_date}`).", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        msg = f"🎯 **CLASSIFICATE PER PROBABILITÀ ({len(value_bets)} opzioni):**\nSeleziona una giocata:"
        keyboard = []
        for i, vb in enumerate(value_bets[:12]):
            btn_text = f"{vb['probabilita']}% | {vb['partita']} -> {vb['pick']} (Fair: @{vb['quota_fair']})"
            if len(btn_text) > 60:
                btn_text = f"{vb['probabilita']}% | {vb['pick']}"
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
        context.user_data["awaiting_real_odd"] = True

        msg = (
            f"📊 **ANALISI STATISTICA (POISSON)**\n\n"
            f"🏆 **Campionato:** `{vb['campionato']}`\n"
            f"🏟 **Match:** `{vb['partita']}`\n"
            f"📅 **Data e Ora:** `{vb['data_ora']}`\n\n"
            f"🗂 **Mercato:** `{vb['categoria']}`\n"
            f"🎯 **Pronostico:** `{vb['pick']}`\n"
            f"📈 **Probabilità del Modello:** `{vb['probabilita']}%` (`{vb['diff_label']}`)\n"
            f"⚖️ **Quota Fair Matematica:** `{vb['quota_fair']}`\n\n"
            f"{vb['analysis']}\n\n"
            f"✍️ **INSERISCI LA QUOTA REALE:**\n"
            f"Digita in chat la quota offerta dal tuo bookmaker per questa scommessa (es. `1.85` o `2.10`):"
        )
        keyboard = [[InlineKeyboardButton("🔙 Torna alla Lista", callback_data="diff_" + context.user_data.get("target_diff", "all"))]]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "confirm_save_bet":
        vb = context.user_data.get("pending_bet_to_save")
        if not vb:
            await query.message.reply_text("❌ Nessuna giocata pendente da salvare.")
            return
        user_id = query.from_user.id
        save_bet(
            user_id=user_id,
            partita=vb["partita"],
            pronostico=vb["pick"],
            quota=vb["quota_reale"],
            probabilita=vb["probabilita"],
            value_rate=vb["value_rate"],
            stake_euro=vb["stake_euro"]
        )
        msg = f"✅ **Giocata salvata con successo nel Bankroll!**\n\n📌 {vb['partita']} -> {vb['pick']} (@{vb['quota_reale']})\nStake: `{vb['stake_euro']:.2f}€`"
        keyboard = [[InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "view_bets":
        user_id = query.from_user.id
        conn = sqlite3.connect("value_bets.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT id, partita, pronostico, quota, stake_euro, esito FROM saved_bets WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            msg = "📊 **Non hai ancora salvato nessuna scommessa.**"
            keyboard = [[InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]]
            await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        msg = "📊 **LE TUE ULTIME SCOMMESSE SALVATE:**\nClicca per aggiornarne l'esito:"
        keyboard = []
        for row in rows:
            bid, partita, pronostico, quota, stake, esito = row
            emoji = "⏳" if esito == "PENDING" else ("✅" if esito == "WON" else "❌")
            btn_text = f"{emoji} {partita} | {pronostico} (@{quota})"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"bet_detail_{bid}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")])
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("bet_detail_"):
        bet_id = int(query.data.split("_")[2])
        user_id = query.from_user.id
        conn = sqlite3.connect("value_bets.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT id, partita, pronostico, quota, stake_euro, esito, profitto, data FROM saved_bets WHERE id = ? AND user_id = ?", (bet_id, user_id))
        row = cursor.fetchone()
        conn.close()

        if not row:
            await query.message.reply_text("❌ Scommessa non trovata.")
            return

        bid, partita, pronostico, quota, stake, esito, profitto, data = row
        emoji = "⏳" if esito == "PENDING" else ("✅" if esito == "WON" else "❌")
        msg = (
            f"📋 **DETTAGLIO SCOMMESSA #{bid}**\n\n"
            f"🏟 **Match:** `{partita}`\n"
            f"🎯 **Pronostico:** `{pronostico}`\n"
            f"🟢 **Quota:** `@`**`{quota}`**\n"
            f"💰 **Stake:** `{stake:.2f}€`\n"
            f"📊 **Stato:** `{emoji} {esito}`\n"
            f"💵 **Profitto:** `{profitto:+.2f}€`\n"
            f"📅 **Data:** `{data}`\n\n"
            f"Aggiorna l'esito:"
        )
        keyboard = [
            [
                InlineKeyboardButton("✅ Vinta (WON)", callback_data=f"result_won_{bid}"),
                InlineKeyboardButton("❌ Persa (LOST)", callback_data=f"result_lost_{bid}")
            ],
            [InlineKeyboardButton("🔙 Torna alle Bet Salvate", callback_data="view_bets")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("result_won_") or query.data.startswith("result_lost_"):
        parts = query.data.split("_")
        esito_val = "WON" if parts[1] == "won" else "LOST"
        bet_id = int(parts[2])
        user_id = query.from_user.id

        update_bet_result(bet_id, user_id, esito_val)
        _, cap_att = get_user_bankroll(user_id)

        msg = f"✅ **Esito aggiornato a {esito_val}!**\n\n💵 **Bankroll Aggiornato:** `{cap_att:.2f}€`"
        keyboard = [
            [InlineKeyboardButton("📊 Visualizza Bet Salvate", callback_data="view_bets")],
            [InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "manage_bankroll":
        user_id = query.from_user.id
        cap_init, cap_att = get_user_bankroll(user_id)
        context.user_data["awaiting_bankroll"] = True
        context.user_data["awaiting_real_odd"] = False

        msg = (
            f"💰 **GESTIONE BANKROLL & CAPITALE**\n\n"
            f"• **Capitale Iniziale:** `{cap_init:.2f}€`\n"
            f"• **Capitale Attuale:** `{cap_att:.2f}€`\n\n"
            f"✍️ *Invia il nuovo importo in euro* (es. `150` o `250.50`) come messaggio in chat."
        )
        keyboard = [
            [InlineKeyboardButton("🔄 Reset Statistiche & Bankroll", callback_data="reset_bankroll")],
            [InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "reset_bankroll":
        user_id = query.from_user.id
        reset_user_stats(user_id)
        _, cap_att = get_user_bankroll(user_id)
        msg = f"🔄 **Statistiche e Bankroll resettati!**\n\nCapitale attuale: `{cap_att:.2f}€`"
        keyboard = [[InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_bankroll"):
        text = update.message.text.strip().replace(",", ".")
        try:
            new_cap = float(text)
            if new_cap <= 0:
                raise ValueError()
            user_id = update.effective_user.id
            set_user_bankroll(user_id, new_cap)
            context.user_data["awaiting_bankroll"] = False
            
            keyboard = [[InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]]
            await update.message.reply_text(
                f"✅ **Bankroll aggiornato con successo!**\nNuovo capitale: `{new_cap:.2f}€`",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except ValueError:
            await update.message.reply_text("❌ Importo non valido. Inserisci un numero valido (es. `150` o `200.50`).", parse_mode="Markdown")

    elif context.user_data.get("awaiting_real_odd"):
        text = update.message.text.strip().replace(",", ".")
        try:
            real_odd = float(text)
            if real_odd <= 1.0:
                raise ValueError()
            
            context.user_data["awaiting_real_odd"] = False
            vb = context.user_data.get("selected_vb")
            if not vb:
                await update.message.reply_text("❌ Sessione scaduta. Avvia una nuova scansione.")
                return

            prob_dec = vb["probabilita"] / 100.0
            value_rate = (real_odd * prob_dec) - 1.0
            value_rate_pct = round(value_rate * 100, 1)

            user_id = update.effective_user.id
            _, cap_att = get_user_bankroll(user_id)

            b = real_odd - 1.0
            kelly_raw = ((b * prob_dec - (1 - prob_dec)) / b) / vb["kelly_divisor"] if b > 0 else 0
            stake_pct_calc = max(0.0, min(kelly_raw * 100, 10.0))
            calculated_stake = (cap_att * stake_pct_calc) / 100.0
            stake_euro = max(1.0, calculated_stake) if calculated_stake < 1.0 else calculated_stake
            stake_pct = (stake_euro / cap_att) * 100.0 if cap_att > 0 else 1.0

            vb["quota_reale"] = real_odd
            vb["value_rate"] = value_rate
            vb["stake_euro"] = stake_euro
            context.user_data["pending_bet_to_save"] = vb

            is_value = value_rate > 0
            value_status = f"🟢 **VALUE BET CONFERMATA!** (`+{value_rate_pct}%` di valore)" if is_value else f"🔴 **Nessun Valore** (`{value_rate_pct}%` - Quota troppo bassa rispetto alla probabilità)"

            msg = (
                f"🚀 **RISULTATO ANALISI VALUE BET**\n\n"
                f"🏆 **Campionato:** `{vb['campionato']}`\n"
                f"🏟 **Match:** `{vb['partita']}`\n"
                f"📅 **Data e Ora:** `{vb['data_ora']}`\n\n"
                f"🗂 **Mercato:** `{vb['categoria']}`\n"
                f"🎯 **Pronostico:** `{vb['pick']}`\n\n"
                f"📈 **Probabilità Modello:** `{vb['probabilita']}%`\n"
                f"⚖️ **Quota Fair:** `{vb['quota_fair']}`\n"
                f"🟢 **Quota Reale (Tua):** `@`**`{real_odd}`**\n\n"
                f"{value_status}\n\n"
                f"💡 **BANKROLL & STAKE (KELLY):**\n"
                f"• **Capitale Attuale:** `{cap_att:.2f}€`\n"
                f"• **Stake Consigliato:** `{stake_euro:.2f}€` (`{stake_pct:.1f}%` del bankroll)"
            )

            keyboard = [
                [InlineKeyboardButton("💾 Salva questa Bet nel Bankroll", callback_data="confirm_save_bet")],
                [InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]
            ]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        except ValueError:
            await update.message.reply_text("❌ Quota non valida. Inserisci un numero decimale valido (es. `1.85` o `2.10`).", parse_mode="Markdown")
    else:
        await update.message.reply_text("Usa i pulsanti del menu per interagire con il bot.", parse_mode="Markdown")

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Avvia il bot e menu principale")
    ])

def main():
    init_db()
    application = Application.builder().token(TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot Telegram avviato con successo...")
    application.run_polling()

if __name__ == "__main__":
    main()
