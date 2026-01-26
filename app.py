import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import json
import agente_ia

st.set_page_config(page_title="Il Nostro Cubo", page_icon="🧊")

# --- FUNZIONI UTILI ---
def connect_db():
    scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/drive']
    json_creds = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
    client = gspread.authorize(creds)
    return client.open("CuboAmoreDB") 

def notifica_telegram(testo):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.get(url, params={"chat_id": chat_id, "text": testo})
    except:
        pass

# --- NUOVA FUNZIONE: STATISTICHE ---
def calcola_statistiche():
    try:
        sh = connect_db()
        ws = sh.worksheet("Log_Mood")
        df = pd.DataFrame(ws.get_all_records())
        
        # Se il foglio è vuoto o ha nomi colonne sbagliati
        if df.empty:
            return "Nessun dato registrato ancora."
            
        # Assumiamo che le colonne siano data, ora, mood (l'ordine conta se non hanno header)
        # Se hai messo gli header nel foglio, usa i nomi. Altrimenti usa indici.
        # Qui assumo che la colonna 3 sia il Mood (index 2)
        mood_col = df.columns[2] 
        
        conteggio = df[mood_col].value_counts().to_dict()
        
        report = "📊 **Statistiche Umore (Totali):**\n"
        for emozione, numero in conteggio.items():
            report += f"- {emozione}: {numero} volte\n"
            
        return report
    except Exception as e:
        return f"Errore stats: {str(e)}"

# --- FUNZIONE: RICEZIONE COMANDI TELEGRAM ---
def check_telegram_updates():
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        # Usiamo un offset per non rileggere messaggi vecchi (in un'app reale servirebbe un DB per l'offset)
        # Qui facciamo un controllo semplice sugli ultimi messaggi
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        resp = requests.get(url).json()
        
        if "result" in resp:
            ultimo_messaggio = resp["result"][-1] # Prendi l'ultimo
            testo = ultimo_messaggio["message"]["text"]
            msg_id = ultimo_messaggio["update_id"]
            
            # Qui servirebbe una logica per non eseguire lo stesso comando 2 volte.
            # Per semplicità in Streamlit, controlliamo solo se il comando è attuale
            # In produzione si salva msg_id nel DB.
            
            return testo, msg_id
    except:
        return None, None

# --- CORE DELL'APP ---

# 1. Controlla se ci sono comandi Telegram (Solo se siamo in Admin mode o refresh)
# Nota: Questo funziona solo quando l'app è attiva nel browser
query_params = st.query_params
mode = query_params.get("mode", "daily")

if mode == "admin":
    cmd, _ = check_telegram_updates()
    
    if cmd == "/agent":
        notifica_telegram("🤖 Ricevuto comando /agent. Avvio generazione...")
        report = agente_ia.run_agent()
        notifica_telegram(f"✅ Fatto! Generati nuovi messaggi.")
        
    elif cmd == "/stats":
        stats = calcola_statistiche()
        notifica_telegram(stats)

# --- INTERFACCIA UTENTE ---
def get_contenuto(mood_target):
    # (Logica standard invariata...)
    try:
        sh = connect_db()
        ws = sh.worksheet("Contenuti")
        df = pd.DataFrame(ws.get_all_records())
        oggi = datetime.now().strftime("%Y-%m-%d")
        
        if 'Data_Specifica' in df.columns:
            df['Data_Specifica'] = df['Data_Specifica'].astype(str)
            
        # Manuale
        manuale = df[(df['Mood'] == 'Manuale') & (df['Data_Specifica'] == oggi)]
        if not manuale.empty: return manuale.iloc[0]['Link_Testo']
            
        # Buongiorno Oggi
        if mood_target == "Buongiorno":
            daily = df[(df['Mood'] == 'Buongiorno') & (df['Data_Specifica'] == oggi)]
            if not daily.empty: return daily.iloc[-1]['Link_Testo']
            
        # Mood Generico
        filtro = df[df['Mood'] == mood_target]
        if filtro.empty: return "Ti amo ❤️"
        return filtro.sample().iloc[0]['Link_Testo']
    except:
        return "Ti amo (Errore DB)"

def salva_log(mood):
    try:
        sh = connect_db()
        ws = sh.worksheet("Log_Mood")
        ws.append_row([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M"), mood])
    except: pass

# --- UI VISIBILE ---
if mode == "daily":
    st.title("☀️ Buongiorno Amore")
    st.markdown(f"### *{get_contenuto('Buongiorno')}*")
    
elif mode == "mood":
    st.title("Come ti senti?")
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    
    if c1.button("😔 Triste"):
        salva_log("Triste")
        notifica_telegram("⚠️ LEI È TRISTE")
        st.info(get_contenuto("Triste"))
    if c2.button("🥰 Felice"):
        salva_log("Felice")
        notifica_telegram("ℹ️ Lei è felice!")
        st.success(get_contenuto("Felice"))
    if c3.button("🕰️ Nostalgica"):
        salva_log("Nostalgica")
        notifica_telegram("ℹ️ Lei è nostalgica")
        st.warning(get_contenuto("Nostalgica"))
    if c4.button("🤯 Stressata"):
        salva_log("Stressata")
        notifica_telegram("⚠️ Lei è STRESSATA")
        st.error(get_contenuto("Stressata"))

elif mode == "admin":
    st.header("🛠️ Admin & Telegram Bot")
    st.info("💡 Per attivare i comandi Telegram, questa pagina deve essere aperta.")
    
    if st.button("Forza Lettura Comandi Telegram"):
        cmd, id_msg = check_telegram_updates()
        if cmd:
            st.success(f"Ultimo comando letto: {cmd}")
            if cmd == "/stats":
                 s = calcola_statistiche()
                 st.write(s)
                 notifica_telegram(s)
            elif cmd == "/agent":
                 with st.spinner("Lavoro..."):
                     rep = agente_ia.run_agent()
                     st.write(rep)
                     notifica_telegram("Generazione completata.")
        else:
            st.warning("Nessun comando nuovo trovato.")
            
    st.divider()
    if st.button("Lancia Agente Manualmente"):
        agente_ia.run_agent()
        st.success("Fatto")
