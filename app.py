import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import json
import agente_ia # Importiamo il cervello IA per il test manuale

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Il Nostro Cubo", page_icon="🧊")

# Funzione DB
def connect_db():
    scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/drive']
    json_creds = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json_creds, scope)
    client = gspread.authorize(creds)
    return client.open("CuboAmoreDB") 

# Funzione Telegram
def notifica_telegram(testo):
    try:
        token = st.secrets.get("TELEGRAM_TOKEN")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
        if token and chat_id and "temp" not in token:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.get(url, params={"chat_id": chat_id, "text": testo})
    except:
        pass

# Funzione Contenuti
def get_contenuto(mood_target):
    try:
        sh = connect_db()
        ws = sh.worksheet("Contenuti")
        df = pd.DataFrame(ws.get_all_records())
        
        # 1. Priorità Manuale (Oggi)
        oggi = datetime.now().strftime("%Y-%m-%d")
        if 'Mood' in df.columns and 'Data_Specifica' in df.columns:
             # Converte in stringa per evitare errori di tipo
            df['Data_Specifica'] = df['Data_Specifica'].astype(str)
            manuale = df[(df['Mood'] == 'Manuale') & (df['Data_Specifica'] == oggi)]
            if not manuale.empty:
                return manuale.iloc[0]['Link_Testo']
        
        # 2. Pesca dal Database
        filtro = df[df['Mood'] == mood_target]
        if filtro.empty:
            return "Non ho trovato frasi per questo mood, ma ti amo lo stesso. ❤️"
            
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

# 1. MODO GIORNALIERO (SOLE)
if mode == "daily":
    st.title("☀️ Buongiorno Amore")
    frase = get_contenuto("Buongiorno")
    st.markdown(f"### *{frase}*")
    
# 2. MODO EMOZIONI (LUNA) - ORA CON 4 BOTTONI
elif mode == "mood":
    st.title("Come ti senti?")
    
    # Griglia 2x2
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    
    # Bottone 1: Triste
    if col1.button("😔 Triste"):
        salva_log("Triste")
        notifica_telegram("⚠️ LEI È TRISTE")
        st.info(get_contenuto("Triste"))
        
    # Bottone 2: Felice
    if col2.button("🥰 Felice"):
        salva_log("Felice")
        notifica_telegram("ℹ️ Lei è felice!")
        st.balloons()
        st.success(get_contenuto("Felice"))

    # Bottone 3: Nostalgica
    if col3.button("🕰️ Nostalgica"):
        salva_log("Nostalgica")
        notifica_telegram("ℹ️ Lei è nostalgica")
        st.warning(get_contenuto("Nostalgica"))

    # Bottone 4: Stressata
    if col4.button("🤯 Stressata"):
        salva_log("Stressata")
        notifica_telegram("⚠️ Lei è STRESSATA - Serve supporto")
        st.error(get_contenuto("Stressata"))

# 3. MODO ADMIN (TEST IA)
elif mode == "admin":
    st.header("🛠️ Pannello Admin")
    password = st.text_input("Password", type="password")
    
    if password == "1234": # Cambia la password se vuoi
        st.success("Accesso effettuato")
        
        st.subheader("🤖 Test Intelligenza Artificiale")
        st.write("Clicca qui sotto per far scrivere a Gemini 5 nuove frasi e salvarle nel DB.")
        
        if st.button("Lancia Agente IA Adesso"):
            with st.spinner("Gemini sta pensando e scrivendo..."):
                try:
                    report = agente_ia.run_agent() # Chiama la funzione dell'altro file
                    st.success("Operazione completata!")
                    st.write(report) # Ti mostra cosa ha scritto
                except Exception as e:
                    st.error(f"Errore: {e}")
