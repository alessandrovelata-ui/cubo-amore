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
# ⚙️ CONFIGURAZIONE (Link Unico)
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
        .stApp {
            background-color: #FFF0F5;
            background-image: radial-gradient(#ffebf2 20%, transparent 20%);
            background-size: 20px 20px;
        }
        #MainMenu, footer, header {visibility: hidden;}
        
        h1 {
            color: #880E4F !important;
            font-family: 'Fredoka', sans-serif;
            font-size: 42px !important;
            text-align: center;
            margin-bottom: 20px;
        }
        
        .message-box {
            background-color: #FFFFFF;
            padding: 35px;
            border-radius: 20px;
            border: 4px dashed #F06292;
            text-align: center;
            font-size: 26px;
            font-weight: 700;
            color: #4A142F !important;
            font-family: 'Nunito', sans-serif;
            line-height: 1.6;
            box-shadow: 0 10px 30px rgba(194, 24, 91, 0.15);
            margin: 20px 0;
        }
        
        .icon { font-size: 50px; display: block; margin-bottom: 15px; }
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
        if tk and cid: 
            requests.get(f"https://api.telegram.org/bot{tk}/sendMessage", params={"chat_id": cid, "text": text})
    except: pass

def get_stato_luce():
    try:
        sh = get_connection()
        return sh.worksheet(WS_CONFIG).acell('B1').value or 'OFF'
    except: return 'OFF'

def set_luce_stato(stato):
    try:
        sh = get_connection()
        sh.worksheet(WS_CONFIG).update_acell('B1', stato)
    except: pass

def salva_log(mood):
    try:
        ws = get_connection().worksheet(WS_LOG)
        ws.append_row([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"), mood])
    except: pass

# ==============================================================================
# 📖 RECUPERO FRASI
# ==============================================================================

def get_buongiorno_oggi():
    try:
        df = pd.DataFrame(get_connection().worksheet(WS_CALENDARIO).get_all_records())
        oggi = datetime.now().strftime("%Y-%m-%d")
        row = df[df['Data'].astype(str).str.strip() == oggi]
        return row.iloc[0]['Frase'] if not row.empty else "Buongiorno amore mio! ❤️"
    except: return "Buongiorno vita mia! ❤️"

def get_pensiero_ia():
    try:
        ws = get_connection().worksheet(WS_EMOZIONI)
        df = pd.DataFrame(ws.get_all_records())
        df['Mood_Clean'] = df['Mood'].astype(str).str.strip().str.lower()
        df['Marker_Clean'] = df['Marker'].astype(str).str.strip().str.lower()
        
        candidati = df[(df['Mood_Clean'].str.contains("pensiero")) & (df['Marker_Clean'] == 'available')]
        if candidati.empty: candidati = df[df['Marker_Clean'] == 'available']
        
        idx = random.choice(candidati.index)
        frase = df.loc[idx, 'Frase']
        ws.update_cell(idx + 2, 4, 'USED')
        return frase
    except: return "Ti sto pensando intensamente... ❤️"

# ==============================================================================
# 📱 LOGICA UNIFICATA
# ==============================================================================

st.set_page_config(page_title="Cubo Amore", page_icon="🧸")
set_style()

# 1. Capiamo se siamo in modalità Sorpresa (Luce già ON) o Buongiorno (Luce OFF)
if 'session_init' not in st.session_state:
    st.session_state.stato_iniziale = get_stato_luce()
    st.session_state.session_init = True
    
    # Se la luce è spenta, è il rito del buongiorno: ACCENDIAMO!
    if st.session_state.stato_iniziale == 'OFF':
        set_luce_stato('ON')
        st.session_state.tipo_messaggio = "BUONGIORNO"
        st.session_state.testo = get_buongiorno_oggi()
        salva_log("Buongiorno (NFC)")
        invia_notifica(f"☀️ RITO DEL MATTINO: Lei ha scansionato il tag. Luce accesa e messaggio inviato: {st.session_state.testo}")
    else:
        # La luce era già accesa da Telegram
        st.session_state.tipo_messaggio = "SORPRESA"
        st.session_state.testo = get_pensiero_ia()
        invia_notifica(f"💡 SORPRESA LETTA: Ha visto il tuo 'Ti sto pensando': {st.session_state.testo}")

# 2. Visualizzazione
if st.session_state.tipo_messaggio == "BUONGIORNO":
    st.markdown("<h1>Buongiorno Amore! ☀️</h1>", unsafe_allow_html=True)
    icona = "☕"
else:
    st.markdown("<h1>Ti sto pensando... ❤️</h1>", unsafe_allow_html=True)
    icona = "💡"

st.markdown(f"""
    <div class="message-box">
        <span class="icon">{icona}</span>
        {st.session_state.testo}
    </div>
""", unsafe_allow_html=True)

# 3. Timer di spegnimento (5 minuti)
st.info("🕒 La lampada si spegnerà automaticamente tra 5 minuti...")
bar = st.progress(0)
for i in range(300):
    time.sleep(1)
    bar.progress((i + 1) / 300)

# 4. Fine: Spegnimento e Reset
set_luce_stato('OFF')
invia_notifica("🌑 NOTIFICA: Il tempo è scaduto, la lampada si è spenta.")
st.success("La lampada si è spenta. Buona giornata amore! ❤️")
time.sleep(5)
# Reset per la prossima scansione
for key in list(st.session_state.keys()):
    del st.session_state[key]
st.rerun()
