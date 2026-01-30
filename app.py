import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
import random
import json
import requests
from datetime import datetime

# ==============================================================================
# ⚙️ CONFIGURAZIONE
# ==============================================================================
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive"]
SHEET_NAME = 'CuboAmoreDB'

WS_CALENDARIO = 'Calendario'
WS_EMOZIONI = 'Emozioni'
WS_CONFIG = 'Config'
WS_LOG = 'Log_Mood' 

# ==============================================================================
# 🎨 STILE CUTE AD ALTO CONTRASTO (CORRETTO)
# ==============================================================================
def set_style():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600&family=Nunito:wght@400;700&display=swap');
        .stApp { background-color: #FFF0F5; }
        #MainMenu, footer, header {visibility: hidden;}
        h1 { color: #880E4F !important; font-family: 'Fredoka', sans-serif; text-align: center; font-size: 40px !important; }
        p { color: #880E4F !important; text-align: center; font-size: 20px; font-weight: 600; }
        div.stButton > button {
            width: 100%; height: 75px; background: white; color: #D81B60 !important;
            font-size: 24px !important; font-weight: 700 !important; border-radius: 20px;
            border: 2px solid #F48FB1; margin-bottom: 12px;
        }
        .message-box {
            background-color: #FFFFFF; padding: 30px; border-radius: 20px; border: 3px dashed #F06292;
            text-align: center; font-size: 24px; font-weight: 700; color: #4A142F !important;
            line-height: 1.5; box-shadow: 0 10px 25px rgba(194,24,91,0.1);
        }
        .icon { font-size: 50px; display: block; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 🔌 CONNESSIONI E LOGICHE
# ==============================================================================

@st.cache_resource
def get_connection():
    if "GOOGLE_SHEETS_JSON" in st.secrets:
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    else:
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPE)
    return gspread.authorize(creds).open(SHEET_NAME)

def invia_notifica(text):
    try:
        tk = st.secrets.get("TELEGRAM_TOKEN")
        cid = st.secrets.get("TELEGRAM_CHAT_ID")
        if tk and cid: requests.get(f"https://api.telegram.org/bot{tk}/sendMessage", params={"chat_id": cid, "text": text})
    except: pass

def buongiorno_gia_letto():
    try:
        ws = get_connection().worksheet(WS_LOG)
        df = pd.DataFrame(ws.get_all_records())
        oggi = datetime.now().strftime("%Y-%m-%d")
        return not df[(df['Data'] == oggi) & (df['Mood'] == 'Buongiorno')].empty
    except: return False

def get_pensiero():
    try:
        ws = get_connection().worksheet(WS_EMOZIONI)
        df = pd.DataFrame(ws.get_all_records())
        cand = df[(df['Mood'].str.contains("Pensiero", case=False)) & (df['Marker'] == 'AVAILABLE')]
        if cand.empty: cand = df[df['Marker'] == 'AVAILABLE']
        idx = random.choice(cand.index)
        frase = cand.loc[idx, 'Frase']
        ws.update_cell(idx + 2, 4, 'USED')
        return frase
    except: return "Ti penso! ❤️"

# ==============================================================================
# 📱 INTERFACCIA
# ==============================================================================
st.set_page_config(page_title="Cubo Amore", page_icon="🧸")
set_style()

# Controllo Stato Iniziale
if 'view' not in st.session_state:
    sh = get_connection().worksheet(WS_CONFIG)
    lampada_on = sh.acell('B1').value == 'ON'
    tipo = sh.acell('B2').value # PENSIERO o BUONGIORNO
    
    # 1. OVERRIDE: Se la lampada è ON da Telegram (PENSIERO)
    if lampada_on and tipo == "PENSIERO":
        st.session_state.view = "PENSUIERO"
        st.session_state.testo = get_pensiero()
        invia_notifica(f"💡 LAMPADA: Cucciola ha letto il tuo pensiero: {st.session_state.testo}")
    
    # 2. PRIMA SCANSIONE: Buongiorno
    elif not buongiorno_gia_letto():
        sh.update_acell('B1', 'ON')
        sh.update_acell('B2', 'BUONGIORNO')
        st.session_state.view = "BUONGIORNO"
        # Pesca da Calendario
        df_cal = pd.DataFrame(get_connection().worksheet(WS_CALENDARIO).get_all_records())
        oggi = datetime.now().strftime("%Y-%m-%d")
        row = df_cal[df_cal['Data'].astype(str).str.strip() == oggi]
        st.session_state.testo = row.iloc[0]['Frase'] if not row.empty else "Buongiorno! ❤️"
        # Log
        get_connection().worksheet(WS_LOG).append_row([oggi, datetime.now().strftime("%H:%M:%S"), "Buongiorno"])
        invia_notifica(f"☀️ BUONGIORNO: Prima scansione di oggi. Letto: {st.session_state.testo}")
    
    # 3. SCANSIONI SUCCESSIVE: Emozioni
    else:
        st.session_state.view = "EMOZIONI"

# --- VISUALIZZAZIONE ---
if st.session_state.view == "EMOZIONI":
    st.markdown("<h1>Come ti senti, amore? ☁️</h1>")
    if 'msg' not in st.session_state: st.session_state.msg = ""
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("😢 Triste"): 
            st.session_state.msg = get_pensiero() # O specifica logica per mood
            invia_notifica("😢 EMOZIONI: Ha selezionato 'Triste'")
            st.rerun()
    # ... altri bottoni ...
    if st.session_state.msg:
        st.markdown(f'<div class="message-box">{st.session_state.msg}</div>', unsafe_allow_html=True)
        if st.button("Chiudi"): st.session_state.msg = ""; st.rerun()

elif st.session_state.view in ["BUONGIORNO", "PENSUIERO"]:
    icona = "☕" if st.session_state.view == "BUONGIORNO" else "💡"
    st.markdown(f"<h1>{st.session_state.view}</h1>", unsafe_allow_html=True)
    st.markdown(f'<div class="message-box"><span class="icon">{icona}</span>{st.session_state.testo}</div>', unsafe_allow_html=True)
    
    prog = st.progress(0)
    for i in range(300):
        time.sleep(1)
        prog.progress((i + 1) / 300)
    
    # FINE
    get_connection().worksheet(WS_CONFIG).update_acell('B1', 'OFF')
    invia_notifica("🌑 NOTIFICA: Lampada spenta dopo 5 minuti.")
    del st.session_state.view
    st.rerun()
