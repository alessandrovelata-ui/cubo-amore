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
# ⚙️ CONFIGURAZIONE UNIFICATA
# ==============================================================================
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive"]
SHEET_NAME = 'CuboAmoreDB'

WS_CALENDARIO = 'Calendario'
WS_EMOZIONI = 'Emozioni'
WS_CONFIG = 'Config'
WS_LOG = 'Log_Mood' 

# ==============================================================================
# 🎨 STILE CUTE AD ALTO CONTRASTO
# ==============================================================================
def set_style():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600&family=Nunito:wght@400;700&display=swap');
        .stApp { background-color: #FFF0F5; background-image: radial-gradient(#ffebf2 20%, transparent 20%); background-size: 20px 20px; }
        #MainMenu, footer, header {visibility: hidden;}
        h1, h2, h3, p, span { color: #880E4F !important; text-align: center; font-family: 'Fredoka', sans-serif; }
        h1 { font-size: 40px !important; }
        div.stButton > button {
            width: 100%; height: 70px; background: white; color: #D81B60 !important;
            font-family: 'Nunito', sans-serif; font-size: 22px !important; font-weight: 700 !important;
            border-radius: 20px; border: 2px solid #F48FB1; box-shadow: 0 4px 6px rgba(216, 27, 96, 0.1);
            margin-bottom: 10px;
        }
        div.stButton > button:hover { transform: scale(1.02); border-color: #C2185B; }
        .message-box {
            background-color: #FFFFFF; padding: 25px; border-radius: 15px; border: 3px dashed #F06292;
            text-align: center; font-size: 22px; font-weight: 700; color: #4A142F !important;
            font-family: 'Nunito', sans-serif; line-height: 1.5; box-shadow: 0 10px 20px rgba(194, 24, 91, 0.1);
            margin-top: 20px; margin-bottom: 20px;
        }
        .icon { font-size: 40px; display: block; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 🔌 CONNESSIONI E NOTIFICHE
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

def set_luce_stato(stato):
    try: get_connection().worksheet(WS_CONFIG).update_acell('B1', stato)
    except: pass

def salva_log(mood):
    try:
        ws = get_connection().worksheet(WS_LOG)
        ws.append_row([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"), mood])
    except: pass

def buongiorno_gia_letto():
    """Controlla se esiste un log 'Buongiorno' per la data di oggi"""
    try:
        ws = get_connection().worksheet(WS_LOG)
        df = pd.DataFrame(ws.get_all_records())
        if df.empty: return False
        oggi = datetime.now().strftime("%Y-%m-%d")
        return not df[(df['Data'] == oggi) & (df['Mood'] == 'Buongiorno')].empty
    except: return False

# --- RECUPERO FRASI ---
def get_frase_calendario():
    try:
        df = pd.DataFrame(get_connection().worksheet(WS_CALENDARIO).get_all_records())
        oggi = datetime.now().strftime("%Y-%m-%d")
        row = df[df['Data'].astype(str).str.strip() == oggi]
        return row.iloc[0]['Frase'] if not row.empty else "Buongiorno amore! ❤️"
    except: return "Buongiorno vita mia! ❤️"

def get_frase_emozioni(mood_target, context):
    try:
        ws = get_connection().worksheet(WS_EMOZIONI)
        df = pd.DataFrame(ws.get_all_records())
        df['Mood_C'] = df['Mood'].astype(str).str.strip().str.lower()
        df['Mark_C'] = df['Marker'].astype(str).str.strip().str.lower()
        candidati = df[(df['Mood_C'].str.contains(mood_target.lower())) & (df['Mark_C'] == 'available')]
        if candidati.empty: candidati = df[df['Mark_C'] == 'available']
        idx = random.choice(candidati.index)
        frase = df.loc[idx, 'Frase']
        ws.update_cell(idx + 2, 4, 'USED')
        salva_log(mood_target)
        invia_notifica(f"💌 {context}: Ha letto ({mood_target}): {frase}")
        return frase
    except: return "Ti amo! ❤️"

# ==============================================================================
# 📱 LOGICA DI NAVIGAZIONE
# ==============================================================================
st.set_page_config(page_title="Cubo Amore", page_icon="🧸")
set_style()

if 'view' not in st.session_state:
    sh = get_connection()
    luce_remota = sh.worksheet(WS_CONFIG).acell('B1').value == 'ON'
    
    # 1. PRIORITÀ: Luce Accesa da Telegram (Sorpresa)
    if luce_remota:
        st.session_state.view = "PENSUIERO"
        st.session_state.testo = get_frase_emozioni("Pensiero", "💡 LAMPADA")
    
    # 2. RITO DEL MATTINO (Se Buongiorno non ancora letto)
    elif not buongiorno_gia_letto():
        set_luce_stato('ON')
        st.session_state.view = "BUONGIORNO"
        st.session_state.testo = get_frase_calendario()
        salva_log("Buongiorno")
        invia_notifica(f"☀️ BUONGIORNO: Ha scansionato il tag per la prima volta oggi. Frase: {st.session_state.testo}")
    
    # 3. INTERFACCIA EMOZIONI (Se già letto tutto ed è tutto OFF)
    else:
        st.session_state.view = "EMOZIONI"

# ==============================================================================
# 🖥️ VISUALIZZAZIONE
# ==============================================================================

if st.session_state.view == "EMOZIONI":
    st.markdown("<h1>Come ti senti, amore? ☁️</h1>", unsafe_allow_html=True)
    if 'msg' not in st.session_state: st.session_state.msg = ""
    
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        if st.button("😢 Triste"): st.session_state.msg = get_frase_emozioni("Triste", "🎫 BARATTOLO"); st.rerun()
        if st.button("🥰 Felice"): st.session_state.msg = get_frase_emozioni("Felice", "🎫 BARATTOLO"); st.rerun()
    with c2:
        if st.button("😤 Stressata"): st.session_state.msg = get_frase_emozioni("Stressata", "🎫 BARATTOLO"); st.rerun()
        if st.button("🍂 Nostalgica"): st.session_state.msg = get_frase_emozioni("Nostalgica", "🎫 BARATTOLO"); st.rerun()

    if st.session_state.msg:
        st.markdown(f'<div class="message-box"><span class="icon">💌</span>{st.session_state.msg}</div>', unsafe_allow_html=True)
        if st.button("Chiudi ✖️"): st.session_state.msg = ""; st.rerun()

elif st.session_state.view in ["BUONGIORNO", "PENSUIERO"]:
    titolo = "Buongiorno Amore! ☀️" if st.session_state.view == "BUONGIORNO" else "Ti sto pensando... ❤️"
    icona = "☕" if st.session_state.view == "BUONGIORNO" else "💡"
    
    st.markdown(f"<h1>{titolo}</h1>", unsafe_allow_html=True)
    st.markdown(f'<div class="message-box"><span class="icon">{icona}</span>{st.session_state.testo}</div>', unsafe_allow_html=True)
    
    st.info("🕒 La lampada si spegnerà tra 5 minuti...")
    bar = st.progress(0)
    for i in range(300):
        time.sleep(1)
        bar.progress((i + 1) / 300)
    
    set_luce_stato('OFF')
    invia_notifica(f"🌑 NOTIFICA: Il timer è scaduto. La lampada si è spenta.")
    del st.session_state.view
    st.rerun()
