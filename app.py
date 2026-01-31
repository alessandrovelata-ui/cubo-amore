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
        .main-title { color: #C2185B !important; text-align: center; font-size: 38px !important; font-weight: 800; margin-top: 20px;}
        .heart { font-size: 100px; text-align: center; margin: 40px 0; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
        .message-box {
            background: white; padding: 25px; border-radius: 20px; border: 4px dashed #F06292;
            font-size: 24px; color: #4A142F !important; text-align: center; font-weight: 700;
        }
        div.stButton > button { 
            width: 100%; border-radius: 20px; font-weight: bold; height: 70px; 
            font-size: 20px !important; background-color: #D81B60; color: white; border: none;
        }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def get_db():
    creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
    return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=SCOPE)).open(SHEET_NAME)

def invia_notifica(txt):
    requests.get(f"https://api.telegram.org/bot{st.secrets['TELEGRAM_TOKEN']}/sendMessage", 
                 params={"chat_id": st.secrets['TELEGRAM_CHAT_ID'], "text": txt})

def get_buongiorno():
    db = get_db(); ws = db.worksheet("Calendario")
    df = pd.DataFrame(ws.get_all_records())
    oggi = datetime.now().strftime("%Y-%m-%d")
    try:
        return df[df['Data'] == oggi].iloc[0]['Frase']
    except:
        return "Buongiorno Tata! Sei il mio primo pensiero. ❤️"

def get_frase_emo(mood):
    db = get_db(); ws = db.worksheet("Emozioni")
    df = pd.DataFrame(ws.get_all_records()); df.columns = df.columns.str.strip()
    cand = df[(df['Mood'].str.contains(mood, case=False)) & (df['Marker'] == 'AVAILABLE')]
    if cand.empty: return "Sei speciale! ❤️"
    ws.update_cell(cand.index[0] + 2, 4, 'USED')
    frase = cand.iloc[0]['Frase']
    # NOTIFICA: Invia il mood scelto e la frase che le è apparsa
    invia_notifica(f"Mood: {mood} ☁️\nHa letto: \"{frase}\"")
    return frase

st.set_page_config(page_title="Cubo Amore", page_icon="🧸")
set_style()

if 'view' not in st.session_state:
    st.session_state.view = "LANDING"

db = get_db(); conf = db.worksheet("Config")

# PRIORITÀ ASSOLUTA: Pensiero attivo (B1=ON)
if conf.acell('B1').value == 'ON' and st.session_state.view != "FIXED":
    st.session_state.view = "FIXED"
    msg = conf.acell('B3').value
    st.session_state.testo = msg if (msg and len(msg.strip()) > 1) else "Ti penso! ❤️"
    # NOTIFICA: Ti avvisa che sta leggendo il tuo pensiero speciale
    invia_notifica(f"💌 Sta leggendo il tuo pensiero: \"{st.session_state.testo}\"")
    conf.update_acell('B3', '') 

# --- 1. LANDING PAGE ---
if st.session_state.view == "LANDING":
    st.markdown('<div class="main-title">Ciao Bimba... ❤️</div>', unsafe_allow_html=True)
    st.markdown('<div class="heart">❤️</div>', unsafe_allow_html=True)
    
    if st.button("Entra nel nostro mondo ✨"):
        invia_notifica("🔔 La tua Tata è entrata nell'app!")
        
        oggi = datetime.now().strftime("%Y-%m-%d")
        ultimo_log = conf.acell('B4').value
        
        if ultimo_log != oggi:
            st.session_state.view = "BUONGIORNO"
            st.session_state.testo = get_buongiorno()
            conf.update_acell('B4', oggi)
            # NOTIFICA: Ti avvisa che ha letto il buongiorno del calendario
            invia_notifica(f"☀️ Ha letto il Buongiorno: \"{st.session_state.testo}\"")
            st.rerun()
        else:
            st.session_state.view = "MOODS"
            st.rerun()

# --- 2. VISTA PENSIERO (FIXED) ---
elif st.session_state.view == "FIXED":
    st.markdown('<div class="main-title">Dedicato a te... ❤️</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.testo}</div>', unsafe_allow_html=True)
    
    if st.button("Spegni Lampada 🌑"):
        conf.update_acell('B1', 'OFF')
        invia_notifica("🌑 Ha spento la lampada.")
        st.session_state.view = "MOODS"; st.rerun()

    p = st.progress(0)
    for i in range(180): 
        time.sleep(1); p.progress((i + 1) / 180)
    
    conf.update_acell('B1', 'OFF')
    st.session_state.view = "MOODS"; st.rerun()

# --- 3. VISTA BUONGIORNO ---
elif st.session_state.view == "BUONGIORNO":
    st.markdown('<div class="main-title">Buongiorno Cucciola! ☀️</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.testo}</div>', unsafe_allow_html=True)
    if st.button("Vai alle Emozioni ☁️"):
        st.session_state.view = "MOODS"; st.rerun()

# --- 4. VISTA EMOZIONI ---
elif st.session_state.view == "MOODS":
    st.markdown('<div class="main-title">Come ti senti oggi? ☁️</div>', unsafe_allow_html=True)
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
