import sqlite3
import math
import os
import threading
import http.server
import socketserver
from datetime import datetime, timedelta
import pytz
import requests
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
# CONFIGURAZIONE BOT & API
# ==========================================
TOKEN = "8578449373:AAFYwnue4sMXjed_P-Bh6_k4yl8jQp3lgr8"
ODDS_API_KEY = "365f573d84b065a782245b03577d20b5"  # Inserisci qui la tua chiave The Odds API

SPORTS_KEYS = [
    "soccer_italy_serie_a",
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "soccer_uefa_champions_league"
]

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

# ==========================================
# PRELEVAMENTO DATI REALI DA THE ODDS API
# ==========================================
def fetch_real_api_bets(target_date_str, market_category):
    tz_it = pytz.timezone("Europe/Rome")
    now_it = datetime.now(tz_it)
    
    if target_date_str == "Oggi":
        target_date_obj = now_it.date()
    elif target_date_str == "Domani":
        target_date_obj = (now_it + timedelta(days=1)).date()
    else:
        target_date_obj = None

    all_bets = []

    for sport_key in SPORTS_KEYS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "eu",
            "markets": "h2h,totals",
            "oddsFormat": "decimal"
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                continue
            data = response.json()
            if not isinstance(data, list):
                continue

            for event in data:
                commence_time_str = event.get("commence_time")
                if not commence_time_str:
                    continue
                
                # Conversione in orario italiano
                dt_utc = datetime.fromisoformat(commence_time_str.replace("Z", "+00:00"))
                dt_it = dt_utc.astimezone(tz_it)
                event_date_obj = dt_it.date()

                # Filtro data rigoroso (Oggi / Domani)
                if target_date_obj and event_date_obj != target_date_obj:
                    continue

                home_team = event.get("home_team")
                away_team = event.get("away_team")
                sport_title = event.get("sport_title", "Calcio")
                formatted_date_time = dt_it.strftime("%d/%m/%Y alle %H:%M")

                bookmakers = event.get("bookmakers", [])
                if not bookmakers:
                    continue

                h2h_outcomes = {}
                totals_outcomes = {}

                for bm in bookmakers:
                    for market in bm.get("markets", []):
                        m_key = market.get("key")
                        if m_key == "h2h" and not h2h_outcomes:
                            for oc in market.get("outcomes", []):
                                h2h_outcomes[oc.get("name")] = oc.get("price")
                        elif m_key == "totals" and not totals_outcomes:
                            for oc in market.get("outcomes", []):
                                if oc.get("point") == 2.5:
                                    totals_outcomes[oc.get("name")] = oc.get("price")

                # SCOMMESSE PRINCIPALI (1X2 e Doppia Chance)
                if market_category == "principali" and len(h2h_outcomes) >= 3:
                    price_home, price_draw, price_away = None, None, None
                    for name, price in h2h_outcomes.items():
                        if name.lower() == home_team.lower():
                            price_home = price
                        elif name.lower() == away_team.lower():
                            price_away = price
                        elif "draw" in name.lower() or "pareggio" in name.lower():
                            price_draw = price

                    if price_home and price_draw and price_away:
                        inv_h = 1.0 / price_home
                        inv_d = 1.0 / price_draw
                        inv_a = 1.0 / price_away
                        total_inv = inv_h + inv_d + inv_a

                        prob_home = inv_h / total_inv
                        prob_draw = inv_d / total_inv
                        prob_away = inv_a / total_inv

                        prob_1x = prob_home + prob_draw
                        prob_x2 = prob_away + prob_draw

                        # 1X2 Bets
                        for pick_name, p_val, odd_val in [
                            (f"1 ({home_team} Vincente)", prob_home, price_home),
                            ("X (Pareggio)", prob_draw, price_draw),
                            (f"2 ({away_team} Vincente)", prob_away, price_away)
                        ]:
                            all_bets.append({
                                "partita": f"{home_team} vs {away_team}",
                                "campionato": sport_title,
                                "data_ora": formatted_date_time,
                                "categoria": "🏆 Risultato Finale (1X2)",
                                "pick": pick_name,
                                "quota_simulata": odd_val,
                                "probabilita": round(p_val * 100, 1),
                                "diff_label": "🟢 FACILE" if p_val >= 0.6 else ("🟡 MEDIA" if p_val >= 0.38 else "🔴 DIFFICILE"),
                                "diff_code": "principali",
                                "analysis": f"Quota reale da The Odds API. Probabilità implicita: {round(p_val*100,1)}%."
                            })

                        # Doppia Chance Bets
                        odd_1x = max(1.05, round(1.0 / prob_1x * 0.95, 2))
                        odd_x2 = max(1.05, round(1.0 / prob_x2 * 0.95, 2))
                        for pick_name, p_val, odd_val in [
                            (f"1X ({home_team} o Pareggio)", prob_1x, odd_1x),
                            (f"X2 (Pareggio o {away_team})", prob_x2, odd_x2)
                        ]:
                            all_bets.append({
                                "partita": f"{home_team} vs {away_team}",
                                "campionato": sport_title,
                                "data_ora": formatted_date_time,
                                "categoria": "🛡️ Doppia Chance",
                                "pick": pick_name,
                                "quota_simulata": odd_val,
                                "probabilita": round(p_val * 100, 1),
                                "diff_label": "🟢 FACILE" if p_val >= 0.6 else ("🟡 MEDIA" if p_val >= 0.38 else "🔴 DIFFICILE"),
                                "diff_code": "principali",
                                "analysis": f"Calcolato da quote 1X2 reali API."
                            })

                # SCOMMESSE SECONDARIE (Under / Over 2.5)
                elif market_category == "secondarie" and totals_outcomes:
                    p_over = totals_outcomes.get("Over")
                    p_under = totals_outcomes.get("Under")
                    if p_over and p_under:
                        inv_o = 1.0 / p_over
                        inv_u = 1.0 / p_under
                        tot_inv = inv_o + inv_u
                        prob_over = inv_o / tot_inv
                        prob_under = inv_u / tot_inv

                        for pick_name, p_val, odd_val in [
                            ("Over 2.5 Goal", prob_over, p_over),
                            ("Under 2.5 Goal", prob_under, p_under)
                        ]:
                            all_bets.append({
                                "partita": f"{home_team} vs {away_team}",
                                "campionato": sport_title,
                                "data_ora": formatted_date_time,
                                "categoria": "⚽ Under/Over 2.5 Goal",
                                "pick": pick_name,
                                "quota_simulata": odd_val,
                                "probabilita": round(p_val * 100, 1),
                                "diff_label": "🟢 FACILE" if p_val >= 0.6 else ("🟡 MEDIA" if p_val >= 0.38 else "🔴 DIFFICILE"),
                                "diff_code": "secondarie",
                                "analysis": f"Quota reale Over/Under 2.5 da The Odds API."
                            })

        except Exception as e:
            print(f"Errore API per {sport_key}: {e}")
            continue

    # ORDINAMENTO RIGOROSO PER PROBABILITÀ (Dalla più alta alla più bassa)
    all_bets.sort(key=lambda x: x["probabilita"], reverse=True)
    return all_bets[:30]

# ==========================================
# GESTIONE INTERFACCIA TELEGRAM
# ==========================================
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
        [InlineKeyboardButton("🔍 Scansiona Value Bets (Da API Reali)", callback_data="select_date")],
        [InlineKeyboardButton("💰 Bankroll & Gestione Capitale", callback_data="manage_bankroll")],
        [InlineKeyboardButton("📊 Le mie Bet Salvate", callback_data="view_bets")]
    ]
    welcome_msg = (
        "🤖 **AI Value Betting Bot (Dati Reali API)**\n\n"
        f"💵 **Bankroll Attuale:** `{cap_att:.2f}€` (Iniziale: `{cap_init:.2f}€`)\n\n"
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
            [InlineKeyboardButton("🔙 Torna al Menu", callback_data="main_menu")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("date_"):
        chosen_date = query.data.split("_")[1]
        context.user_data["chosen_date"] = chosen_date

        msg = f"🏆 **DATA SELEZIONATA:** `{chosen_date}`\n\nScegli il tipo di mercato da scansionare:"
        keyboard = [
            [InlineKeyboardButton("🏆 Scommesse Principali (1X2, DC)", callback_data="market_principali")],
            [InlineKeyboardButton("⚽ Scommesse Secondarie (Under/Over 2.5)", callback_data="market_secondarie")],
            [InlineKeyboardButton("🔙 Indietro", callback_data="select_date")]
        ]
        await safe_edit_message(query, msg, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("market_"):
        market_category = query.data.split("_")[1]
        context.user_data["market_category"] = market_category
        chosen_date = context.user_data.get("chosen_date", "Oggi")

        await safe_edit_message(query, f"🔍 **Connessione a The Odds API in corso per `{chosen_date}`... Attendere prego.**")

        value_bets = fetch_real_api_bets(chosen_date, market_category)
        context.user_data["cached_value_bets"] = value_bets

        if not value_bets:
            keyboard = [[InlineKeyboardButton("🔙 Cambia Data/Filtri", callback_data="select_date")]]
            await safe_edit_message(query, f"❌ Nessuna partita o quota trovata per `{chosen_date}` con i mercati selezionati.", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        msg = f"🎯 **CLASSIFICATE PER PROBABILITÀ ({len(value_bets)} opzioni):**\nSeleziona una partita:"
        keyboard = []
        for i, vb in enumerate(value_bets[:12]):
            btn_text = f"{vb['probabilita']}% | {vb['partita']} -> {vb['pick']} (@{vb['quota_simulata']})"
            if len(btn_text) > 60:
                btn_text = f"{vb['probabilita']}% | {vb['pick']} (@{vb['quota_simulata']})"
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
        context.user_data["pending_bet_to_save"] = vb

        user_id = query.from_user.id
        cap_init, cap_att = get_user_bankroll(user_id)
        
        # Calcolo Stake con Criterio di Kelly conservativo
        b = vb["quota_simulata"] - 1.0
        prob_dec = vb["probabilita"] / 100.0
        kelly_raw = ((b * prob_dec - (1 - prob_dec)) / b) / 4.0 if b > 0 else 0
        calculated_stake = max(1.0, cap_att * max(0.0, min(kelly_raw, 0.05)))
        stake_pct = (calculated_stake / cap_att) * 100.0 if cap_att > 0 else 1.0
        vb["stake_euro"] = calculated_stake

        msg = (
            f"🚀 **DETTAGLIO SCOMMESSA & ANALISI REALE**\n\n"
            f"🏆 **Campionato:** `{vb['campionato']}`\n"
            f"🏟 **Match:** `{vb['partita']}`\n"
            f"📅 **Data e Ora:** `{vb['data_ora']}`\n\n"
            f"🗂 **Mercato:** `{vb['categoria']}`\n"
            f"🎯 **PRONOSTICO:** `{vb['pick']}`\n"
            f"🟢 **Quota Reale (API):** `@`**`{vb['quota_simulata']}`**\n"
            f"📊 **Probabilità Stimata:** `{vb['probabilita']}%` (`{vb['diff_label']}`)\n\n"
            f"💡 **BANKROLL & STAKE CONSIGLIATO:**\n"
            f"• **Capitale Attuale:** `{cap_att:.2f}€`\n"
            f"• **Stake (Kelly):** `{calculated_stake:.2f}€` (`{stake_pct:.1f}%` del bankroll)\n\n"
            f"📈 **INFO API:**\n{vb['analysis']}"
        )

        keyboard = [
            [InlineKeyboardButton("💾 Salva questa Bet nel Bankroll", callback_data="confirm_save_bet")],
            [InlineKeyboardButton("🔙 Torna alla Lista", callback_data="market_" + vb["diff_code"])]
        ]
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
            quota=vb["quota_simulata"],
            probabilita=vb["probabilita"],
            value_rate=0.0,
            stake_euro=vb["stake_euro"]
        )
        msg = f"✅ **Giocata salvata con successo nel tuo Bankroll!**\n\n📌 {vb['partita']} -> {vb['pick']} (@{vb['quota_simulata']})"
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

    print("🤖 Bot Telegram avviato con successo (Dati Reali API)...")
    application.run_polling()

if __name__ == "__main__":
    main()
