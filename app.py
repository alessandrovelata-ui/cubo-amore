import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json, requests, time
from datetime import datetime

# --- CONFIGURAZIONE ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "CuboAmoreDB"

def set_style():
    st.markdown("""
    <style>
        .stApp { background-color: #FFF0F5; }
        h1, p, div { color: #880E4F !important; text-align: center; font-family: sans-serif; }
        h1 { font-size: 40px !important; font-weight: bold; }
        div.stButton > button {
            width: 100%; height: 80px; background: white; color: #D81B60 !important;
            font-size: 24px !important; font-weight: bold; border-radius: 20px;
            border: 3px solid #F48FB1; margin-bottom: 15px;
        }
        .message-box {
            background: white; padding: 30px; border-radius: 20px; border: 4px dashed #F06292;
            font-size: 26px; font-weight: bold; color: #4A142F !important; box-shadow: 0 10px 20px rgba(0,0,0,0.05);
        }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def get_db():
    creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    return gspread.authorize(creds).open(SHEET_NAME)

def invia_notifica(txt):
    requests.get(f"https://api.telegram.org/bot{st.secrets['TELEGRAM_TOKEN']}/sendMessage", 
                 params={"chat_id": st.secrets['TELEGRAM_CHAT_ID'], "text": txt})

def get_frase_emo(mood):
    ws = get_db().worksheet("Emozioni")
    df = pd.DataFrame(ws.get_all_records())
    df['Mark_C'] = df['Marker'].astype(str).str.strip().str.lower()
    cand = df[(df['Mood'].str.contains(mood, case=False)) & (df['Mark_C'] == 'available')]
    if cand.empty: cand = df[df['Mark_C'] == 'available']
    idx = cand.index[0]
    frase = cand.loc[idx, 'Frase']
    ws.update_cell(idx + 2, 4, 'USED')
    get_db().worksheet("Log_Mood").append_row([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"), mood])
    invia_notifica(f"💌 {mood}: Letto '{frase}'")
    return frase

# --- LOGICA ---
st.set_page_config(page_title="Cubo Amore", page_icon="🧸")
set_style()

if 'view' not in st.session_state:
    conf = get_db().worksheet("Config")
    lamp_on = conf.acell('B1').value == 'ON'
    mode = conf.acell('B2').value
    
    # 1. OVERRIDE PENSIERO
    if lamp_on and mode == "PENSIERO":
        st.session_state.view = "FIXED"
        st.session_state.testo = get_frase_emo("Pensiero")
        st.session_state.title = "Ti sto pensando... ❤️"
        invia_notifica("💡 PENSIERO: Ha letto il tuo messaggio speciale.")
    
    # 2. PRIMA SCANSIONE (BUONGIORNO)
    else:
        log = pd.DataFrame(get_db().worksheet("Log_Mood").get_all_records())
        oggi = datetime.now().strftime("%Y-%m-%d")
        if log.empty or oggi not in log[log['Mood'] == 'Buongiorno']['Data'].values:
            conf.update_acell('B1', 'ON')
            conf.update_acell('B2', 'BUONGIORNO')
            cal = pd.DataFrame(get_db().worksheet("Calendario").get_all_records())
            row = cal[cal['Data'].astype(str) == oggi]
            st.session_state.testo = row.iloc[0]['Frase'] if not row.empty else "Buongiorno! ❤️"
            st.session_state.view = "FIXED"
            st.session_state.title = "Buongiorno Amore! ☀️"
            get_db().worksheet("Log_Mood").append_row([oggi, datetime.now().strftime("%H:%M:%S"), "Buongiorno"])
            invia_notifica(f"☀️ BUONGIORNO: Prima scansione di oggi. Letto: {st.session_state.testo}")
        else:
            st.session_state.view = "MOODS"

# --- RENDER ---
if st.session_state.view == "MOODS":
    st.markdown("<h1>Come ti senti, amore? ☁️</h1>")
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

elif st.session_state.view == "FIXED":
    st.markdown(f"<h1>{st.session_state.title}</h1>")
    st.markdown(f'<div class="message-box">{st.session_state.testo}</div>', unsafe_allow_html=True)
    time.sleep(300)
    get_db().worksheet("Config").update_acell('B1', 'OFF')
    invia_notifica("🌑 NOTIFICA: Lampada spenta (timer 5 min).")
    st.session_state.view = "MOODS"
    st.rerun()
