import requests
from datetime import datetime
import pytz

def get_today_soccer_matches():
    tz_it = pytz.timezone("Europe/Rome")
    today_str = datetime.now(tz_it).strftime("%Y%m%d")
    matches = []
    
    # 1. Tentativo con ESPN API
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?dates={today_str}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=8)
        print(f"DEBUG - ESPN API Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            events = data.get("events", [])
            print(f"DEBUG - ESPN eventi trovati: {len(events)}")
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
        else:
            print(f"DEBUG - ESPN errore risposta: {response.text[:200]}")
    except Exception as e:
        print(f"DEBUG - Eccezione ESPN API: {e}")

    # 2. Se ESPN non restituisce nulla, proviamo con The Odds API (endpoint corretto 'upcoming')
    if not matches and ODDS_API_KEY:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/upcoming/events?apiKey={ODDS_API_KEY}"
            response = requests.get(url, timeout=8)
            print(f"DEBUG - Odds API Status: {response.status_code}")
            
            if response.status_code == 200:
                events = response.json()
                print(f"DEBUG - Odds API eventi totali trovati: {len(events)}")
                for ev in events:
                    sport_key = ev.get("sport_key", "")
                    # Filtriamo solo gli eventi di calcio
                    if "soccer" in sport_key.lower():
                        home = ev.get("home_team")
                        away = ev.get("away_team")
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
            else:
                print(f"DEBUG - Odds API errore risposta: {response.text[:200]}")
        except Exception as e:
            print(f"DEBUG - Eccezione Odds API: {e}")

    # 3. Fallback finale se entrambe falliscono o non ci sono match
    if not matches:
        print("DEBUG - Nessun match trovato dalle API. Vengono usati i match di fallback.")
        matches = [
            {"home": "Austin FC", "away": "San Diego FC", "campionato": "🇺🇸 USA - MLS", "data_ora": "Prossimamente"},
            {"home": "Inter", "away": "Milan", "campionato": "🇮🇹 Italia - Serie A", "data_ora": "Prossimamente"},
            {"home": "Arsenal", "away": "Chelsea", "campionato": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inghilterra - Premier League", "data_ora": "Prossimamente"}
        ]

    return matches
