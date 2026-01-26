import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import json
import agente_ia

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Cubo Amore", page_icon="❤️", layout="centered")

# --- CSS: STILE ESTETICO AVANZATO ---
hide_st_style = """
            <style>
            .stApp { background-color: #FFF5F7; }
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            [data-testid="stToolbar"] {visibility: hidden;}
            .stDeployButton {display:none;}
            
            h1 {
                color: #D64161 !important;
                text-align: center;
                font-family: 'Helvetica Neue', sans-serif;
                font-weight: 700;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
            h2, h3, p, div {
                color: #4A4A4A !important;
                text-align: center;
            }
            
            /* Stile speciale per il Counter */
            .counter-box {
                background-color: #fff;
                border: 2px solid #D64161;
                border-radius: 15px;
                padding: 15px;
                margin-top: 10px;
                margin-bottom: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            }
            .counter-big { font-size: 1.2em; font-weight: bold; color: #D64161 !important; }
            
            .stButton>button {
                width: 100%;
                height: 3.5em;
                font-size: 20px !important;
                font-weight: 600;
                background-color: #ffffff;
                color: #D64161;
                border: 2px solid #FFD1DC;
                border-radius: 25px;
                box-shadow: 0 4px 6px rgba(214, 65, 97, 0.1);
                transition: all 0.3s ease;
            }
            .stButton>button:hover {
                border-color: #D64161;
                background-color: #FFF0F5;
                transform: translateY(-2px);
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- FUNZIONI DI SERVIZIO ---
def connect_db():
    scope = ["[https://spreadsheets.google.com/feeds](https://spreadsheets.google.com/feeds)",'[https://www.googleapis.com/auth/drive](https://www.googleapis.com/auth/drive)']
    json_creds = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
    client = gspread.authorize(creds)
    return client.open("CuboAmoreDB") 

def notifica_telegram(testo):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){token}/sendMessage"
        requests.get(url, params={"chat_id": chat_id, "text": testo})
    except: pass

def salva_log(mood):
    try:
        sh = connect_db()
        ws = sh.worksheet("Log_Mood")
        ws.append_row([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M"), mood])
    except: pass

def get_contenuto(mood_target):
    try:
        sh = connect_db()
        ws = sh.worksheet("Contenuti")
        df = pd.DataFrame(ws.get_all_records())
        oggi = datetime.now().strftime("%Y-%m-%d")
        
        if 'Data_Specifica' in df.columns:
            df['Data_Specifica'] = df['Data_Specifica'].astype(str)
            
        manuale = df[(df['Mood'] == 'Manuale') & (df['Data_Specifica'] == oggi)]
        if not manuale.empty: return manuale.iloc[0]['Link_Testo']
            
        if mood_target == "Buongiorno":
            daily = df[(df['Mood'] == 'Buongiorno') & (df['Data_Specifica'] == oggi)]
            if not daily.empty: return daily.iloc[-1]['Link_Testo']
            
        filtro = df[df['Mood'] == mood_target]
        if filtro.empty: return "Ti amo ❤️"
        return filtro.sample().iloc[0]['Link_Testo']
    except: return "Ti amo all'infinito ❤️"

# --- CALENDARIO SPECIALE E COUNTER ---
def check_special_event():
    now = datetime.now()
    
    # DATA INIZIO RELAZIONE: 14 Febbraio 2022
    start_date = datetime(2022, 2, 14, 0, 0, 0)
    
    # Calcoli Counter
    delta = now - start_date
    giorni_totali = delta.days
    ore_totali = int(delta.total_seconds() // 3600)
    
    # Calcolo anni/mesi approssimato per display
    anni = now.year - start_date.year
    if (now.month, now.day) < (start_date.month, start_date.day):
        anni -= 1
    mesi_diff = (now.year - start_date.year) * 12 + now.month - start_date.month
    if now.day < start_date.day:
        mesi_diff -= 1
    mesi_reali = mesi_diff % 12
    
    # --- LOGICA EVENTI ---
    
    # 1. ANNIVERSARIO (14 Febbraio)
    if now.month == 2 and now.day == 14:
        msg = f"Buon Anniversario Amore Mio! ❤️\nSono passati esattamente {anni} anni."
        counter = f"Ovvero {giorni_totali} giorni e {ore_totali} ore che mi sopporti! 😂❤️"
        return "🎉 Anniversario", msg, counter
        
    # 2. MESIVERSARIO (Giorno 14 di altri mesi)
    if now.day == 14:
        msg = f"Buon Mesiversario! 🌹\n{anni} Anni e {mesi_reali} Mesi insieme."
        counter = f"Il contatore segna: {giorni_totali} giorni totali di noi."
        return "🌹 Mesiversario", msg, counter

    # 3. COMPLEANNO LEI (12 Aprile)
    if now.month == 4 and now.day == 12:
        return "🎂 Buon Compleanno!", "Tanti auguri al mio Sole! Sei il regalo più bello del mondo.", None

    # 4. SOLSTIZI E EQUINOZI (Date approssimative fisse)
    # Solstizio Estate (Sole)
    if now.month == 6 and now.day in [20, 21]:
        return "☀️ Solstizio d'Estate", "Oggi è il giorno più lungo dell'anno, ma tu brilli più del sole.", None
    # Solstizio Inverno
    if now.month == 12 and now.day in [21, 22]:
        return "❄️ Solstizio d'Inverno", "Fuori è la notte più lunga, ma tu sei la mia luce che scalda tutto.", None
    
    # 5. FESTIVITÀ CLASSICHE
    if now.month == 12 and now.day == 25:
        return "🎄 Buon Natale", "Il mio regalo sei tu. Ti amo!", None
    if now.month == 1 and now.day == 1:
        return "🥂 Buon Anno", "Un altro anno da scrivere insieme a te.", None
        
    return None, None, None

# --- INTERFACCIA ---
query_params = st.query_params
mode = query_params.get("mode", "daily")

if mode == "admin":
    st.markdown("### 🛠️ Centro di Controllo")
    pwd = st.text_input("Password", type="password")
    if pwd == "1234":
        if st.button("🚀 LANCIA AGENTE"):
            with st.spinner("Generazione in corso..."):
                report = agente_ia.run_agent()
                st.write(report)
                st.success("Fatto! Telegram avvisato.")

elif mode == "daily":
    st.title("☀️")
    
    # Controllo Eventi Speciali
    titolo_speciale, msg_speciale, counter_info = check_special_event()
    
    if titolo_speciale:
        # VISUALIZZAZIONE EVENTO SPECIALE
        st.markdown(f"<h1>{titolo_speciale}</h1>", unsafe_allow_html=True)
        st.markdown(f"<h3>{msg_speciale}</h3>", unsafe_allow_html=True)
        
        if counter_info:
            st.markdown(f"""
            <div class="counter-box">
                <p class="counter-big">⏳ Il nostro tempo</p>
                <p>{counter_info}</p>
            </div>
            """, unsafe_allow_html=True)
        st.balloons()
    else:
        # GIORNO NORMALE
        st.markdown("## Buongiorno Amore")
        st.divider()
        frase = get_contenuto('Buongiorno')
        st.markdown(f"<h3 style='text-align: center; color: #444;'>{frase}</h3>", unsafe_allow_html=True)

elif mode == "mood":
    st.title("Come ti senti?")
    st.write("") 
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
        st.snow()
        
    if c3.button("🕰️ Nostalgica"):
        salva_log("Nostalgica")
        notifica_telegram("ℹ️ Lei è nostalgica")
        st.warning(get_contenuto("Nostalgica"))
        
    if c4.button("🤯 Stressata"):
        salva_log("Stressata")
        notifica_telegram("⚠️ Lei è STRESSATA")
        st.error(get_contenuto("Stressata"))
