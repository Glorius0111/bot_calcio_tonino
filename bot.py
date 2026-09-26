import sqlite3
import requests
import math
import random
import re
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest

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

def analyze_any_match_corners(home_team, away_team, campionato, difficulty):
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

    if difficulty == "easy":
        diff_label = "🟢 FACILE (Basso Rischio)"
        kelly_divisor = 2.0
        kelly_text = "1/2 Kelly"
        candidate_lines = [
            {"cat": "🚩 Corner Totali", "pick": "Over 6.5 Corner Totali", "type": "total", "line": 6.5},
            {"cat": "🚩 Corner Totali", "pick": "Over 7.5 Corner Totali", "type": "total", "line": 7.5},
            {"cat": "🚩 Corner Casa", "pick": f"{home_team} Over 3.5 Corner", "type": "home", "line": 3.5}
        ]
    elif difficulty == "medium":
        diff_label = "🟡 MEDIO (Rischio Bilanciato)"
        kelly_divisor = 4.0
        kelly_text = "1/4 Kelly"
        candidate_lines = [
            {"cat": "🚩 Corner Totali", "pick": "Over 8.5 Corner Totali", "type": "total", "line": 8.5},
            {"cat": "🚩 Corner Totali", "pick": "Over 9.5 Corner Totali", "type": "total", "line": 9.5},
            {"cat": "🚩 Corner Casa", "pick": f"{home_team} Over 4.5 Corner", "type": "home", "line": 4.5}
        ]
    else:
        diff_label = "🔴 DIFFICILE (Alta Quota / Max EV+)"
        kelly_divisor = 8.0
        kelly_text = "1/8 Kelly"
        candidate_lines = [
            {"cat": "🚩 Corner Totali", "pick": "Over 10.5 Corner Totali", "type": "total", "line": 10.5},
            {"cat": "🚩 Corner Casa", "pick": f"{home_team} Over 5.5 Corner", "type": "home", "line": 5.5},
            {"cat": "🚩 Corner Ospiti", "pick": f"{away_team} Over 4.5 Corner", "type": "away", "line": 4.5}
        ]

    best_option = None
    best_prob = 0.0

    for option in candidate_lines:
        if option["type"] == "total":
            prob = calculate_over_probability(total_exp_corners, option["line"])
        elif option["type"] == "home":
            prob = calculate_over_probability(exp_home_corners, option["line"])
        else:
            prob = calculate_over_probability(exp_away_corners, option["line"])

        if prob > best_prob:
            best_prob = prob
            best_option = option

    prob_pct = round(best_prob * 100, 1)
    quota_fair = round(1.0 / best_prob, 2)

    camp_stat_label = f"`{campionato}`" if campionato else "Standard"
    analysis_text = (
        f"• **Expected Corners (xC):** `{total_exp_corners:.2f}` attesi totali (`{exp_home_corners:.2f}` {home_team} - `{exp_away_corners:.2f}` {away_team}).\n"
        f"• **Media Torneo ({camp_stat_label}):** `{league_mean}` corner medi/partita.\n"
        f"• **Metrica Attacco/Difesa:** `{home_team}` (`{home_for:.1f}` f. / `{home_against:.1f}` s.) vs `{away_team}` (`{away_for:.1f}` f. / `{away_against:.1f}` s.)."
    )

    return {
        "diff_label": diff_label,
        "kelly_divisor": kelly_divisor,
        "kelly_text": kelly_text,
        "categoria": best_option["cat"],
        "pick": best_option["pick"],
        "probabilita": prob_pct,
        "quota_fair": quota_fair,
        "analysis": analysis_text
    }

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
    cursor.execute("PRAGMA table_info(saved_bets)")
    columns = [column[1] for column in cursor.fetchall()]
    if "stake_euro" not in columns:
        cursor.execute("ALTER TABLE saved_bets ADD COLUMN stake_euro REAL DEFAULT 0.0")

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

def get_today_soccer_matches():
    tz_it = pytz.timezone("Europe/Rome")
    today_str = datetime.now(tz_it).strftime("%Y%m%d")
    matches = []
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?dates={today_str}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            events = response.json().get("events", [])
            for event in events:
                competitions = event.get("competitions", [{}])[0]
                competitors = competitions.get("competitors", [])
                raw_campionato = None
                if "league" in event and isinstance(event["league"], dict):
                    raw_campionato = event["league"].get("name")
                if not raw_campionato and "league" in competitions:
                    raw_campionato = competitions["league"].get("name")
                campionato = clean_league_name(raw_campionato)

                date_iso = event.get("date")
                if date_iso:
                    utc_dt = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
                    local_dt = utc_dt.astimezone(tz_it)
                    data_ora_str = local_dt.strftime("%d/%m/%Y alle %H:%M")
                else:
                    data_ora_str = "Oggi"

                if len(competitors) >= 2:
                    home = competitors[0].get("team", {}).get("displayName")
                    away = competitors[1].get("team", {}).get("displayName")
                    if home and away:
                        matches.append({
                            "home": home,
                            "away": away,
                            "campionato": campionato,
                            "data_ora": data_ora_str
                        })
    except Exception as e:
        print(f"Info ESPN API: {e}")

    if not matches:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/soccer/events?apiKey={ODDS_API_KEY}"
            response = requests.get(url, timeout=8)
            if response.status_code == 200:
                events = response.json()
                for ev in events:
                    home = ev.get("home_team")
                    away = ev.get("away_team")
                    sport_key = ev.get("sport_key", "")
                    raw_title = ev.get("sport_title", "")
                    campionato = clean_league_name(raw_title, sport_key)
                    commence_time = ev.get("commence_time")

                    if commence_time:
                        utc_dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
                        local_dt = utc_dt.astimezone(tz_it)
                        data_ora_str = local_dt.strftime("%d/%m/%Y alle %H:%M")
                    else:
                        data_ora_str = "Oggi"

                    if home and away:
                        matches.append({
                            "home": home,
                            "away": away,
                            "campionato": campionato,
                            "data_ora": data_ora_str
                        })
        except Exception as e:
            print(f"Info Odds API: {e}")

    if not matches:
        matches = [
            {"home": "Austin FC", "away": "San Diego FC", "campionato": "🇺🇸 USA - MLS", "data_ora": "Prossimamente"},
            {"home": "Inter", "away": "Milan", "campionato": "🇮🇹 Italia - Serie A", "data_ora": "Prossimamente"},
            {"home": "Arsenal", "away": "Chelsea", "campionato": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inghilterra - Premier League", "data_ora": "Prossimamente"}
        ]

    return matches

async def safe_edit_message(query, text, reply_markup=None, parse_mode="Markdown"):
    """Funzione di sicurezza per evitare blocchi se il messaggio è identico"""
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
    context.user_data["awaiting_odds"] = False
    context.user_data["awaiting_bankroll"] = False

    keyboard = [
        [InlineKeyboardButton("🚩 Trova Miglior EV+ (Partite Reali)", callback_data="select_match")],
        [InlineKeyboardButton("💰 Bankroll & Gestione Capitale", callback_data="manage_bankroll")],
        [InlineKeyboardButton("📊 Le mie Bet Salvate", callback_data="view_bets")]
    ]
    welcome_msg = (
        "🤖 **Corner EV+ Real Analyzer**\n\n"
        f"💵 **Bankroll Attuale:** `{cap_att:.2f}€` (Iniziale: `{cap_init:.2f}€`)\n\n"
        "Seleziona un'opzione per analizzare i match reali in palinsesto oggi:"
    )
    if update.message:
        await update.message.reply_text(welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await safe_edit_message(update.callback_query, welcome_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "select_match":
        matches = get_today_soccer_matches()
        match = random.choice(matches)
        context.user_data["selected_match"] = match

        camp_line = f"🏆 **Campionato:** `{match['campionato']}`\n" if match.get("campionato") else ""
        msg = (
            f"{camp_line}"
            f"🏟 **Partita:** `{match['home']} vs {match['away']}`\n"
            f"📅 **Data e Ora:** `{match['data_ora']}`\n\n"
            f"🎯 **Scegli il livello di rischio per l'analisi:**\n"
            f"• 🟢 **Facile** ➔ Stake fisso **1/2 Kelly**\n"
            f"• 🟡 **Medio** ➔ Stake fisso **1/4 Kelly**\n"
            f"• 🔴 **Difficile** ➔ Stake fisso **1/8 Kelly**"
        )
        keyboard = [
            [InlineKeyboardButton("🟢 FACILE (1/2 Kelly)", callback_data="diff_easy")],
            [InlineKeyboardButton("🟡 MEDIO (1/4 Kelly)", callback_data="diff_medium")],
            [InlineKeyboardButton("🔴 DIFFICILE (1/8 Kelly)", callback_data="diff_hard")],
            [InlineKeyboardButton("🎲 QUALSIASI (Pick Casuale)", callback_data="diff_any")],
            [InlineKeyboardButton("🔄 Estrai un altro Match", callback_data="select_match")],
            [InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("diff_"):
        difficulty = query.data.split("_")[1]
        if difficulty == "any":
            difficulty = random.choice(["easy", "medium", "hard"])
        match = context.user_data.get("selected_match")
        if not match:
            await query.message.reply_text("❌ Sessione scaduta. Seleziona nuovamente una partita.")
            return

        pred = analyze_any_match_corners(match["home"], match["away"], match["campionato"], difficulty)
        context.user_data["current_pred"] = {**pred, "partita": f"{match['home']} vs {match['away']}"}
        context.user_data["awaiting_odds"] = True

        camp_line = f"🏆 **Campionato:** `{match['campionato']}`\n" if match.get("campionato") else ""
        msg = (
            f"🚀 **VALUE BET CORNER IDENTIFICATA (POISSON MODEL)**\n"
            f"📌 **Profilo:** `{pred['diff_label']}` (Stake: `{pred['kelly_text']}`)\n\n"
            f"{camp_line}"
            f"🏟 **Match:** `{match['home']} vs {match['away']}`\n"
            f"📅 **Data e Ora:** `{match['data_ora']}`\n\n"
            f"📌 **Mercato:** `{pred['categoria']}`\n"
            f"💡 **Giocata Consigliata:** `{pred['pick']}`\n\n"
            f"📊 **Probabilità Reale (Poisson):** `{pred['probabilita']}%`\n"
            f"⚖️ **Quota Fair (Senza Aggio):** `{pred['quota_fair']}`\n\n"
            f"📋 **Analisi Statistica Dettagliata:**\n{pred['analysis']}\n\n"
            f"✍️ **Scrivi ora in chat la quota del tuo Bookmaker per calcolare lo Stake Kelly personalizzato!**"
        )
        keyboard = [
            [InlineKeyboardButton("🔄 Scegli un altro Rischio", callback_data="select_match")],
            [InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]
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
            pronostico=pending_bet["pronostico"],
            quota=pending_bet["quota"],
            probabilita=pending_bet["probabilita"],
            value_rate=pending_bet["value_rate"],
            stake_euro=pending_bet["stake_euro"]
        )
        context.user_data["pending_bet_to_save"] = None

        msg = (
            f"✅ **SCOMMESSA REGISTRATA CON SUCCESSO!**\n\n"
            f"🏟 **Partita:** `{pending_bet['partita']}`\n"
            f"🎯 **Pick:** `{pending_bet['pronostico']}`\n"
            f"💰 **Puntata:** `{pending_bet['stake_euro']:.2f}€`\n\n"
            f"💾 _Giocata salvata nello storico. Potrai aggiornarne l'esito a fine partita dalla sezione 'Le mie Bet Salvate'._"
        )
        keyboard = [
            [InlineKeyboardButton("🚩 Nuova Analisi", callback_data="select_match")],
            [InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "cancel_play_bet":
        context.user_data["pending_bet_to_save"] = None
        msg = "❌ **Scommessa NON salvata.** Non è stata aggiunta allo storico né alle statistiche della cassa."
        keyboard = [
            [InlineKeyboardButton("🚩 Nuova Analisi", callback_data="select_match")],
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
            f"🎯 **ROI Complessivo:** `{roi:+.1f}%`\n\n"
            f"ℹ️ **Regole Stake automatico:**\n"
            f"• Giocata Facile ➔ **1/2 Kelly**\n"
            f"• Giocata Media ➔ **1/4 Kelly**\n"
            f"• Giocata Difficile ➔ **1/8 Kelly**"
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
            msg = "📊 **IL TUO STORICO VALUE BET SALVATE:**\n\n"
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

    if context.user_data.get("awaiting_odds"):
        try:
            user_odds = float(text)
            pred = context.user_data.get("current_pred")
            prob_dec = pred["probabilita"] / 100.0
            value_rate = (user_odds * prob_dec) - 1.0
            value_rate_pct = value_rate * 100.0

            cap_init, cap_att = get_user_bankroll(user_id)
            b = user_odds - 1.0

            context.user_data["awaiting_odds"] = False

            if value_rate > 0:
                kelly_divisor = pred["kelly_divisor"]
                kelly_text = pred["kelly_text"]

                kelly_raw = ((b * prob_dec - (1 - prob_dec)) / b) / kelly_divisor if b > 0 else 0
                stake_pct_calc = max(0.0, min(kelly_raw * 100, 10.0))
                calculated_stake = (cap_att * stake_pct_calc) / 100.0

                if calculated_stake < 1.0:
                    stake_euro = 1.0
                    stake_pct = (1.0 / cap_att) * 100.0 if cap_att > 0 else 1.0
                else:
                    stake_euro = calculated_stake
                    stake_pct = stake_pct_calc

                ev_status = f"🟢 **VALUE BET CONFERMATA (EV+ `{value_rate_pct:+.2f}%`)**"
                advice = f"💰 **Stake Consigliato ({kelly_text}):** `{stake_pct:.1f}% cassa` (`{stake_euro:.2f}€`)"
                context.user_data["pending_bet_to_save"] = {
                    "partita": pred["partita"],
                    "pronostico": pred["pick"],
                    "quota": user_odds,
                    "probabilita": prob_dec,
                    "value_rate": value_rate,
                    "stake_euro": stake_euro
                }

                keyboard = [
                    [InlineKeyboardButton("✅ GIOCATA (Salva in Cassa)", callback_data="confirm_play_bet")],
                    [InlineKeyboardButton("❌ NON GIOCATA (Annulla)", callback_data="cancel_play_bet")]
                ]
                ask_msg = "\n\n❓ **Hai intenzione di piazzare questa giocata?**"
            else:
                ev_status = f"🔴 **NO VALUE (EV `{value_rate_pct:+.2f}%`)**"
                advice = "⚠️ La quota offerta è svantaggiosa rispetto al modello di Poisson. Nessuno stake consigliato."
                ask_msg = ""
                keyboard = [
                    [InlineKeyboardButton("🚩 Nuova Analisi", callback_data="select_match")],
                    [InlineKeyboardButton("🔙 Menu", callback_data="main_menu")]
                ]

            response = (
                f"🧮 **RISULTATO ANALISI POISSON & VALUE**\n\n"
                f"🏟 **Partita:** `{pred['partita']}`\n"
                f"🎯 **Scommessa:** `{pred['pick']}`\n"
                f"📊 **Probabilità Matematica:** `{pred['probabilita']}%` | **Quota Fair:** `{pred['quota_fair']}`\n"
                f"💵 **Quota Tuo Bookmaker:** `{user_odds:.2f}`\n\n"
                f"{ev_status}\n\n"
                f"💡 {advice}{ask_msg}"
            )
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        except ValueError:
            await update.message.reply_text("❌ Inserisci una quota valida (es. `1.85`).")

async def post_init(application: Application):
    await application.bot.set_my_commands([BotCommand("start", "Apri Menu Principale")])

def main():
    init_db()
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot avviato correttamente...")
    app.run_polling()

if __name__ == "__main__":
    main()
