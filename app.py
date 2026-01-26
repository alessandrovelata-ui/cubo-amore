import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import json
import agente_ia

st.set_page_config(page_title="Il Nostro Cubo", page_icon="🧊")

def connect_db():
    scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/drive']
    json_creds = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
    client = gspread.authorize(creds)
    return client.open("CuboAmoreDB") 

def notifica_telegram(testo):
    try:
        token = st.secrets.get("TELEGRAM_TOKEN")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
        if token and chat_id and "temp" not in token:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.get(url, params={"chat_id": chat_id, "text": testo})
    except:
        pass

# --- FUNZIONE CONTENUTI AGGIORNATA ---
def get_contenuto(mood_target):
    try:
        sh = connect_db()
        ws = sh.worksheet("Contenuti")
        df = pd.DataFrame(ws.get_all_records())
        
        oggi = datetime.now().strftime("%Y-%m-%d")
        
        # Convertiamo la colonna Data in stringa per sicurezza
        if 'Data_Specifica' in df.columns:
            df['Data_Specifica'] = df['Data_Specifica'].astype(str)
        
        # 1. PRIORITÀ ASSOLUTA: Messaggio MANUALE per oggi (scritto da te)
        manuale = df[(df['Mood'] == 'Manuale') & (df['Data_Specifica'] == oggi)]
        if not manuale.empty:
            return manuale.iloc[0]['Link_Testo']
            
        # 2. PRIORITÀ ALTA: Buongiorno IA generato per OGGI
        if mood_target == "Buongiorno":
            buongiorno_oggi = df[(df['Mood'] == 'Buongiorno') & (df['Data_Specifica'] == oggi)]
            if not buongiorno_oggi.empty:
                # Prende l'ultimo generato per oggi (in caso di duplicati)
                return buongiorno_oggi.iloc[-1]['Link_Testo']
        
        # 3. STANDARD: Pesca a caso dal mazzo (per Mood o Buongiorno generici)
        # Filtra per mood
        filtro = df[df['Mood'] == mood_target]
        
        # Se stiamo cercando un Buongiorno ma non c'è quello di oggi, prendiamone uno generico (senza data o data vecchia)
        if mood_target == "Buongiorno" and filtro.empty:
             return "Buongiorno amore mio! (Oggi il server dorme, ma io ti amo)"

        if filtro.empty:
            return "Non ho trovato frasi, ma ti amo lo stesso. ❤️"
            
        return filtro.sample().iloc[0]['Link_Testo']

    except Exception as e:
        return f"Errore: {str(e)}"

def salva_log(mood):
    try:
        sh = connect_db()
        ws = sh.worksheet("Log_Mood")
        ws.append_row([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M"), mood])
    except:
        pass

# --- INTERFACCIA ---
query_params = st.query_params
mode = query_params.get("mode", "daily") 

if mode == "daily":
    st.title("☀️ Buongiorno Amore")
    frase = get_contenuto("Buongiorno")
    st.markdown(f"### *{frase}*")
    
elif mode == "mood":
    st.title("Come ti senti?")
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    
    if col1.button("😔 Triste"):
        salva_log("Triste")
        notifica_telegram("⚠️ LEI È TRISTE")
        st.info(get_contenuto("Triste"))
        
    if col2.button("🥰 Felice"):
        salva_log("Felice")
        notifica_telegram("ℹ️ Lei è felice!")
        st.balloons()
        st.success(get_contenuto("Felice"))

    if col3.button("🕰️ Nostalgica"):
        salva_log("Nostalgica")
        notifica_telegram("ℹ️ Lei è nostalgica")
        st.warning(get_contenuto("Nostalgica"))

    if col4.button("🤯 Stressata"):
        salva_log("Stressata")
        notifica_telegram("⚠️ Lei è STRESSATA")
        st.error(get_contenuto("Stressata"))

elif mode == "admin":
    st.header("🛠️ Pannello Admin")
    pwd = st.text_input("Password", type="password")
    if pwd == "1234":
        st.success("Loggato")
        if st.button("Lancia Generazione Settimanale (Lungo)"):
            with st.spinner("Sto generando 7 giorni di buongiorno e i mood... (Ci vorranno circa 3 minuti)"):
                report = agente_ia.run_agent()
                st.write(report)
