import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import json
import os

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Il Nostro Cubo", page_icon="🧊")

# Funzione per connettersi a Google Sheet
def connect_db():
    scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/drive']
    # Recuperiamo il JSON dai secrets di Streamlit
    json_creds = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
    client = gspread.authorize(creds)
    # IMPORTANTE: Assicurati che il nome del file qui sotto sia ESATTO a quello su Google Sheets
    return client.open("CuboAmoreDB") 

# Funzione Notifica Telegram
def notifica_telegram(testo):
    try:
        # Recupera i segreti in modo sicuro
        token = st.secrets.get("TELEGRAM_TOKEN")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
        
        # Invia solo se i token esistono e non sono valori finti
        if token and chat_id and "temp" not in token:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.get(url, params={"chat_id": chat_id, "text": testo})
    except Exception as e:
        print(f"Errore Telegram (non bloccante): {e}")

# --- LOGICA CONTENUTI ---
def get_contenuto(mood_target):
    try:
        sh = connect_db()
        ws = sh.worksheet("Contenuti")
        df = pd.DataFrame(ws.get_all_records())
        
        oggi = datetime.now().strftime("%Y-%m-%d")
        
        # 1. Controllo Manuale (Priorità)
        if 'Mood' in df.columns and 'Data_Specifica' in df.columns:
            # Converte la colonna data in stringa per sicurezza
            df['Data_Specifica'] = df['Data_Specifica'].astype(str)
            manuale = df[(df['Mood'] == 'Manuale') & (df['Data_Specifica'] == oggi)]
            if not manuale.empty:
                return manuale.iloc[0]['Link_Testo']
        
        # 2. Pesca dal Database
        filtro = df[df['Mood'] == mood_target]
        if filtro.empty:
            return "Sei speciale. (Database in caricamento...)"
            
        return filtro.sample().iloc[0]['Link_Testo']
        
    except Exception as e:
        return f"Errore di connessione: {str(e)}"

def salva_log(mood):
    try:
        sh = connect_db()
        ws = sh.worksheet("Log_Mood")
        ws.append_row([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M"), mood])
    except:
        pass # Se fallisce il log, fa niente

# --- INTERFACCIA ---
query_params = st.query_params
mode = query_params.get("mode", "daily") # Default daily

if mode == "daily":
    st.title("☀️ Buongiorno Amore")
    frase = get_contenuto("Buongiorno")
    st.markdown(f"### *{frase}*")
    
elif mode == "mood":
    st.title("Come ti senti?")
    col1, col2 = st.columns(2)
    
    if col1.button("😔 Triste"):
        salva_log("Triste")
        notifica_telegram("⚠️ NOTIFICA: Lei ha cliccato TRISTE sul cubo!")
        frase = get_contenuto("Triste")
        st.info(frase)
        
    if col2.button("🥰 Felice"):
        salva_log("Felice")
        notifica_telegram("ℹ️ Lei è felice!")
        frase = get_contenuto("Felice")
        st.success(frase)

elif mode == "admin":
    st.warning("Area riservata - Accesso Admin")
