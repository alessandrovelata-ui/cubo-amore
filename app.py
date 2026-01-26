import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import json
import agente_ia

st.set_page_config(page_title="Il Nostro Cubo", page_icon="🧊")

# Funzioni DB e Notifica standard
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
    except: return "Ti amo (Errore Connessione)"

# --- INTERFACCIA ---
query_params = st.query_params
mode = query_params.get("mode", "daily")

if mode == "admin":
    st.header("🛠️ Centro di Controllo")
    pwd = st.text_input("Password", type="password")
    
    if pwd == "1234":
        st.success("Accesso Autorizzato")
        st.info("Clicca il pulsante qui sotto una volta a settimana.")
        
        if st.button("🚀 LANCIA AGENTE (Generazione + Statistiche + Notifica)"):
            with st.spinner("L'IA sta lavorando... Riceverai una notifica su Telegram alla fine."):
                report = agente_ia.run_agent()
                st.write("### Log Operazioni:")
                st.write(report)
                st.success("Operazione completata! Controlla Telegram.")
    else:
        st.warning("Inserisci password")

elif mode == "daily":
    st.title("☀️ Buongiorno Amore")
    st.markdown(f"### *{get_contenuto('Buongiorno')}*")
    
elif mode == "mood":
    st.title("Come ti senti?")
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    
    # Pulsanti Mood
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
