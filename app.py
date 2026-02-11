import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json, requests, time
from datetime import datetime

SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "CuboAmoreDB"

def set_style():
    st.markdown("""<style>
        .stApp { background-color: #FFF0F5; }
        .main-title { color: #C2185B !important; text-align: center; font-size: 38px !important; font-weight: 800; margin-top: 20px;}
        .heart { font-size: 100px; text-align: center; margin: 40px 0; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
        .message-box { background: white; padding: 25px; border-radius: 20px; border: 4px dashed #F06292; font-size: 24px; color: #4A142F !important; text-align: center; font-weight: 700; margin-bottom: 20px; }
        div.stButton > button { width: 100%; border-radius: 20px; font-weight: bold; height: 70px; font-size: 20px !important; background-color: #D81B60; color: white; border: none; margin-bottom: 10px; }
        .timer-text { text-align: center; color: #AD1457; font-size: 14px; margin-top: 10px; }
    </style>""", unsafe_allow_html=True)

@st.cache_resource
def get_db():
    creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
    return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=SCOPE)).open(SHEET_NAME)

def invia_notifica(txt):
    try:
        requests.get(f"https://api.telegram.org/bot{st.secrets['TELEGRAM_TOKEN']}/sendMessage", 
                     params={"chat_id": st.secrets['TELEGRAM_CHAT_ID'], "text": txt}, timeout=5)
    except: pass

def update_lamp(tag, frase=""):
    try:
        db = get_db(); conf = db.worksheet("Config")
        # Aggiornamento massivo per ridurre la latenza
        conf.update('B1:B3', [['ON'], [tag.upper()], [str(frase)]])
    except: pass

def get_frase_emo(mood):
    with st.spinner("Sto scegliendo una frase dolce..."):
        db = get_db(); ws = db.worksheet("Emozioni")
        df = pd.DataFrame(ws.get_all_records()); df.columns = df.columns.str.strip()
        cand = df[(df['Mood'].str.contains(mood, case=False)) & (df['Marker'] == 'AVAILABLE')]
        frase = cand.iloc[0]['Frase'] if not cand.empty else "Sei speciale! ❤️"
        if not cand.empty: ws.update_cell(cand.index[0] + 2, 4, 'USED')
        update_lamp(mood, frase)
        invia_notifica(f"Mood: {mood} ☁️\nHa letto: \"{frase}\"")
        return frase

def spegni_tutto():
    try:
        db = get_db(); conf = db.worksheet("Config")
        conf.update('B1:B3', [['OFF'], ['OFF'], ['']])
        invia_notifica("🌑 La lampada si è spenta.")
    except: pass

st.set_page_config(page_title="Cubo Amore", page_icon="🧸")
set_style()

if 'view' not in st.session_state: st.session_state.view = "LANDING"
db = get_db()
conf = db.worksheet("Config")

def start_auto_off(seconds=300):
    minuti = seconds // 60
    st.markdown(f'<p class="timer-text">La lampada si spegnerà tra {minuti} minuti...</p>', unsafe_allow_html=True)
    p = st.progress(0)
    for i in range(seconds):
        time.sleep(1)
        p.progress((i + 1) / seconds)
    spegni_tutto()
    st.session_state.view = "MOODS"
    st.rerun()

# Priorità Pensiero di Ale
if st.session_state.view == "MOODS": # Controllo solo se siamo nella dashboard
    check_status = conf.batch_get(['B1', 'B2', 'B3'])
    if check_status[0][0][0] == 'ON' and check_status[1][0][0] == 'PENSIERO':
        st.session_state.view = "FIXED"
        st.session_state.testo = check_status[2][0][0] if check_status[2][0] else "Ti penso! ❤️"
        conf.update_acell('B3', '')
        st.rerun()

# --- 1. LANDING PAGE ---
if st.session_state.view == "LANDING":
    st.markdown('<div class="main-title">Ciao Bimba... ❤️</div>', unsafe_allow_html=True)
    st.markdown('<div class="heart">❤️</div>', unsafe_allow_html=True)
    if st.button("Entra nel nostro mondo ✨"):
        invia_notifica("🔔 Anita è entrata nell'app")
        oggi = datetime.now().strftime("%Y-%m-%d")
        status_row = conf.row_values(4) # Legge riga 4 per il log
        ultimo_log = status_row[1] if len(status_row) > 1 else ""
        
        if ultimo_log != oggi:
            ws_cal = db.worksheet("Calendario"); df_cal = pd.DataFrame(ws_cal.get_all_records())
            frase = df_cal[df_cal['Data'] == oggi].iloc[0]['Frase'] if not df_cal[df_cal['Data'] == oggi].empty else "Buongiorno! ❤️"
            st.session_state.testo = frase
            conf.update_acell('B4', oggi)
            update_lamp("BUONGIORNO", frase)
            st.session_state.view = "BUONGIORNO"
            st.rerun()
        else:
            st.session_state.view = "MOODS"; st.rerun()

# --- 2. VISTA PENSIERO (FIXED) ---
elif st.session_state.view == "FIXED":
    st.markdown('<div class="main-title">Dedicato a te... ❤️</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.testo}</div>', unsafe_allow_html=True)
    if st.button("Vai alle Emozioni ☁️"):
        st.session_state.view = "MOODS"; st.rerun()
    start_auto_off(300)

# --- 3. VISTA BUONGIORNO ---
elif st.session_state.view == "BUONGIORNO":
    st.markdown('<div class="main-title">Buongiorno Cucciola! ☀️</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.testo}</div>', unsafe_allow_html=True)
    if st.button("Vai alle Emozioni ☁️"): 
        st.session_state.view = "MOODS"; st.rerun()
    start_auto_off(300)

# --- 4. VISTA: COUNTDOWN ---
elif st.session_state.view == "COUNTDOWN":
    st.markdown('<div class="main-title">Manca poco... ⏳</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.countdown_msg}</div>', unsafe_allow_html=True)
    if st.button("Torna alle Emozioni ☁️"):
        st.session_state.view = "MOODS"; st.rerun()
    start_auto_off(900)

# --- 5. VISTA EMOZIONI ---
elif st.session_state.view == "MOODS":
    st.markdown('<div class="main-title">Come ti senti oggi? ☁️</div>', unsafe_allow_html=True)
    if 'm_msg' not in st.session_state: st.session_state.m_msg = ""
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("😢 Triste"): st.session_state.m_msg = get_frase_emo("Triste"); st.rerun()
        if st.button("🥰 Felice"): st.session_state.m_msg = get_frase_emo("Felice"); st.rerun()
        
        # --- FIX COUNTDOWN (Velocizzato) ---
        if st.button("⏳ Countdown"):
            with st.spinner("Sto calcolando quanto manca..."):
                try:
                    ws_ev = db.worksheet("events")
                    # Leggo B2, C2, D2 in un colpo solo!
                    dati = ws_ev.get_values("B2:D2")[0]
                    data_fine_str = dati[0]
                    evento = dati[1]
                    percentuale = dati[2]
                    
                    data_fine = datetime.strptime(data_fine_str, "%d/%m/%Y")
                    differenza = (data_fine - datetime.now()).days + 1
                    
                    st.session_state.countdown_msg = f"Mancano {differenza} giorni a {evento} ❤️"
                    update_lamp("COUNTDOWN", str(percentuale))
                    invia_notifica(f"⏳ Anita ha attivato il Countdown per: {evento}")
                    st.session_state.view = "COUNTDOWN"
                    st.rerun()
                except Exception as e:
                    st.error("Assicurati di aver configurato il countdown su Telegram!")

    with c2:
        if st.button("😤 Stressata"): st.session_state.m_msg = get_frase_emo("Stressata"); st.rerun()
        if st.button("🍂 Nostalgica"): st.session_state.m_msg = get_frase_emo("Nostalgica"); st.rerun()
        if st.button("🌑 Spegni tutto"):
            spegni_tutto(); st.session_state.m_msg = ""; st.rerun()
    
    if st.session_state.m_msg:
        st.markdown(f'<div class="message-box">{st.session_state.m_msg}</div>', unsafe_allow_html=True)
        start_auto_off(300)
