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

# --- CSS PER NASCONDERE MENU E STILE APP ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stApp {
                background-color: #ffffff;
            }
            /* Stile Bottoni Grandi e Arrotondati */
            .stButton>button {
                width: 100%;
                height: 3.5em;
                font-size: 22px !important;
                border-radius: 15px;
                font-weight: 600;
                background-color: #f0f2f6;
                color: #31333F;
                border: 1px solid #dce1e6;
                transition: all 0.2s;
            }
            .stButton>button:active {
                transform: scale(0.98);
                background-color: #ffe4e1; /* Un tocco rosa quando premi */
            }
            /* Titoli centrati */
            h1 {
                text-align: center;
                font-family: 'Helvetica Neue', sans-serif;
                color: #ff4b4b;
            }
            .markdown-text-container {
                text-align: center;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- FUNZIONI DI SERVIZIO ---
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
        
        # Gestione colonne
        if 'Data_Specifica' in df.columns:
            df['Data_Specifica'] = df['Data_Specifica'].astype(str)
            
        # 1. Priorità Manuale
        manuale = df[(df['Mood'] == 'Manuale') & (df['Data_Specifica'] == oggi)]
        if not manuale.empty: return manuale.iloc[0]['Link_Testo']
            
        # 2. Priorità Buongiorno Oggi
        if mood_target == "Buongiorno":
            daily = df[(df['Mood'] == 'Buongiorno') & (df['Data_Specifica'] == oggi)]
            if not daily.empty: return daily.iloc[-1]['Link_Testo']
            
        # 3. Pesca Casuale dal Mood
        filtro = df[df['Mood'] == mood_target]
        if filtro.empty: return "Ti amo ❤️ (Server in pausa caffè)"
        
        # Qui potresti aggiungere la logica per non ripetere frasi appena viste,
        # ma per semplicità di lettura lasciamo il sample.
        return filtro.sample().iloc[0]['Link_Testo']

    except Exception as e:
        return f"Amore infinito ❤️ ({str(e)})"

# --- INTERFACCIA UTENTE ---
query_params = st.query_params
mode = query_params.get("mode", "daily")

# 1. MODO ADMIN (Nascosto)
if mode == "admin":
    st.markdown("### 🛠️ Centro di Controllo")
    pwd = st.text_input("Password", type="password")
    
    if pwd == "1234":
        st.success("Accesso Autorizzato")
        st.info("Clicca qui sotto una volta a settimana (Domenica sera).")
        
        if st.button("🚀 LANCIA AGENTE (Generazione + Report)"):
            with st.spinner("L'IA sta scrivendo poesie e calcolando statistiche..."):
                report = agente_ia.run_agent()
                st.write("### Log Operazioni:")
                st.write(report)
                st.balloons()
                st.success("Operazione completata! Controlla Telegram.")
    else:
        if pwd: st.error("Password errata")

# 2. MODO BUONGIORNO (Tag Sole)
elif mode == "daily":
    st.title("☀️")
    st.markdown("## Buongiorno Amore")
    st.divider()
    frase = get_contenuto('Buongiorno')
    st.markdown(f"<h3 style='text-align: center; color: #444;'>{frase}</h3>", unsafe_allow_html=True)
    st.balloons()

# 3. MODO EMOZIONI (Tag Luna)
elif mode == "mood":
    st.title("Come ti senti?")
    st.write("") # Spazio vuoto
    
    # Layout a griglia per i pulsanti grandi
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    
    # Pulsanti
    if c1.button("😔 Triste"):
        salva_log("Triste")
        notifica_telegram("⚠️ LEI È TRISTE - Serve coccole")
        st.info(get_contenuto("Triste"))
        
    if c2.button("🥰 Felice"):
        salva_log("Felice")
        notifica_telegram("ℹ️ Lei è felice!")
        st.success(get_contenuto("Felice"))
        st.snow() # Effetto coriandoli/neve
        
    if c3.button("🕰️ Nostalgica"):
        salva_log("Nostalgica")
        notifica_telegram("ℹ️ Lei è nostalgica")
        st.warning(get_contenuto("Nostalgica"))
        
    if c4.button("🤯 Stressata"):
        salva_log("Stressata")
        notifica_telegram("⚠️ Lei è STRESSATA - Supporto immediato")
        st.error(get_contenuto("Stressata"))
