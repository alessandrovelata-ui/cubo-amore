import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json, requests, time
from datetime import datetime

SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "CuboAmoreDB"

def set_style():
    st.markdown("""
    <style>
        .stApp { background-color: #FFF0F5; }
        .main-title { color: #C2185B !important; text-align: center; font-size: 38px !important; font-weight: 800; }
        .message-box {
            background: white; padding: 25px; border-radius: 20px; border: 4px dashed #F06292;
            font-size: 24px; color: #4A142F !important; text-align: center; font-weight: 700;
            box-shadow: 0 10px 20px rgba(0,0,0,0.05);
        }
        div.stButton > button { width: 100%; border-radius: 15px; font-weight: bold; height: 65px; background: white; color: #D81B60; border: 2px solid #F48FB1; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def get_db():
    creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
    return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=SCOPE)).open(SHEET_NAME)

def invia_notifica(txt):
    requests.get(f"https://api.telegram.org/bot{st.secrets['TELEGRAM_TOKEN']}/sendMessage", 
                 params={"chat_id": st.secrets['TELEGRAM_CHAT_ID'], "text": txt})

def get_frase_emo(mood):
    db = get_db(); ws = db.worksheet("Emozioni")
    df = pd.DataFrame(ws.get_all_records()); df.columns = df.columns.str.strip()
    cand = df[(df['Mood'].str.contains(mood, case=False)) & (df['Marker'] == 'AVAILABLE')]
    if cand.empty: return "Sei speciale! ❤️"
    ws.update_cell(cand.index[0] + 2, 4, 'USED')
    return cand.iloc[0]['Frase']

st.set_page_config(page_title="Cubo Amore", page_icon="🧸")
set_style()

# LOGICA CARICAMENTO
if 'view' not in st.session_state:
    db = get_db(); conf = db.worksheet("Config")
    if conf.acell('B1').value == 'ON':
        st.session_state.view = "FIXED"
        msg = conf.acell('B3').value
        st.session_state.testo = msg if (msg and len(msg.strip()) > 1) else "Ti penso tanto! ❤️"
        conf.update_acell('B3', '') # Svuota B3
        invia_notifica(f"🔔 Letto: '{st.session_state.testo}'")
    else:
        st.session_state.view = "MOODS"

# VISTA FIXED (TIMER 3 MIN)
if st.session_state.view == "FIXED":
    st.markdown(f'<div class="main-title">Dedicato a te... ❤️</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.testo}</div>', unsafe_allow_html=True)
    
    if st.button("Spegni Lampada 🌑"):
        get_db().worksheet("Config").update_acell('B1', 'OFF')
        st.session_state.view = "MOODS"; st.rerun()

    p = st.progress(0)
    for i in range(180):
        time.sleep(1); p.progress((i + 1) / 180)
    
    get_db().worksheet("Config").update_acell('B1', 'OFF')
    st.session_state.view = "MOODS"; st.rerun()

# VISTA MOODS
elif st.session_state.view == "MOODS":
    st.markdown('<div class="main-title">Come ti senti, amore? ☁️</div>', unsafe_allow_html=True)
    if 'm_msg' not in st.session_state: st.session_state.m_msg = ""
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("😢 Triste"): st.session_state.m_msg = get_frase_emo("Triste"); st.rerun()
        if st.button("🥰 Felice"): st.session_state.m_msg = get_frase_emo("Felice"); st.rerun()
    with c2:
        if st.button("😤 Stressata"): st.session_state.m_msg = get_frase_emo("Stressata"); st.rerun()
        if st.button("🍂 Nostalgica"): st.session_state.m_msg = get_frase_emo("Nostalgica"); st.rerun()

    if st.session_state.m_msg:
        st.markdown(f'<div class="message-box">{st.session_state.m_msg}</div>', unsafe_allow_html=True)
        if st.button("Chiudi ✖️"): st.session_state.m_msg = ""; st.rerun()
