import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json, requests, time, random
from datetime import datetime

# --- CONFIGURAZIONE ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "CuboAmoreDB"

def set_style():
    st.markdown("""
    <style>
        .stApp { background-color: #FFF0F5; }
        #MainMenu, footer, header {visibility: hidden;}
        .main-title { color: #C2185B !important; font-family: 'Fredoka', sans-serif; text-align: center; font-size: 36px !important; font-weight: bold; margin-bottom: 20px; }
        .sub-text { color: #880E4F !important; text-align: center; font-family: 'Nunito', sans-serif; font-size: 18px; font-weight: bold; margin-bottom: 20px; }
        
        /* Box del messaggio */
        .message-box {
            background: white; padding: 25px; border-radius: 20px; border: 4px dashed #F06292;
            font-size: 24px; color: #4A142F !important; text-align: center; font-weight: 700;
            box-shadow: 0 10px 20px rgba(0,0,0,0.05); margin-bottom: 25px;
        }

        /* Bottoni Emozioni */
        div.stButton > button {
            width: 100%; height: 70px; background: white; color: #D81B60 !important;
            font-size: 20px !important; font-weight: bold; border-radius: 15px;
            border: 2px solid #F48FB1; transition: 0.3s;
        }
        
        /* Bottone Spegni (Stile scuro) */
        .off-btn > div > button {
            background-color: #880E4F !important; color: white !important;
            border: none !important; height: 55px !important; margin-top: 10px;
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

def get_frase_emo(mood_richiesto):
    db = get_db()
    ws = db.worksheet("Emozioni")
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip() # Pulisce intestazioni
    
    # Filtro frasi disponibili
    cand = df[(df['Mood'].str.contains(mood_richiesto, case=False, na=False)) & 
              (df['Marker'].str.strip().str.upper() == 'AVAILABLE')]
    
    if cand.empty:
        cand = df[df['Marker'].str.strip().str.upper() == 'AVAILABLE']
    
    if cand.empty:
        return f"Ti amo immensamente, {random.choice(['Tata', 'Cucciola', 'Baby', 'Bimba'])}! ❤️"

    idx_originale = cand.index[0]
    frase = cand.loc[idx_originale, 'Frase']
    
    # Segna come usata
    ws.update_cell(idx_originale + 2, 4, 'USED')
    
    # Log e Notifica
    db.worksheet("Log_Mood").append_row([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"), mood_richiesto])
    invia_notifica(f"💌 {mood_richiesto}: La tua Bimba ha letto '{frase}'")
    return frase

# --- LOGICA DI NAVIGAZIONE ---
st.set_page_config(page_title="Cubo Amore", page_icon="🧸")
set_style()

if 'view' not in st.session_state:
    conf = get_db().worksheet("Config")
    lamp_status = conf.acell('B1').value
    mode = conf.acell('B2').value
    
    if lamp_status == 'ON':
        st.session_state.view = "FIXED"
        if mode == "PENSIERO":
            st.session_state.title = "Ti sto pensando... ❤️"
            st.session_state.testo = get_frase_emo("Pensiero")
        else:
            st.session_state.title = "Buongiorno Amore! ☀️"
            # Recupera buongiorno dal calendario
            cal = pd.DataFrame(get_db().worksheet("Calendario").get_all_records())
            cal.columns = cal.columns.str.strip()
            oggi = datetime.now().strftime("%Y-%m-%d")
            row = cal[cal['Data'].astype(str) == oggi]
            st.session_state.testo = row.iloc[0]['Frase'] if not row.empty else "Buongiorno Bimba! ❤️"
    else:
        st.session_state.view = "MOODS"

# --- VISTA 1: MESSAGGIO FISSO (Timer 3 min) ---
if st.session_state.view == "FIXED":
    st.markdown(f'<div class="main-title">{st.session_state.title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.testo}</div>', unsafe_allow_html=True)
    
    # Bottone Spegni Manuale
    st.markdown('<div class="off-btn">', unsafe_allow_html=True)
    if st.button("Spegni Lampada 🌑"):
        get_db().worksheet("Config").update_acell('B1', 'OFF')
        st.session_state.view = "MOODS"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Timer Progressivo (180 secondi = 3 minuti)
    prog_bar = st.progress(0)
    for i in range(180):
        time.sleep(1)
        prog_bar.progress((i + 1) / 180)
    
    # Auto-Spegni al termine
    get_db().worksheet("Config").update_acell('B1', 'OFF')
    st.session_state.view = "MOODS"
    st.rerun()

# --- VISTA 2: SCELTA EMOZIONI ---
elif st.session_state.view == "MOODS":
    st.markdown('<div class="main-title">Come ti senti oggi? ☁️</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-text">Scegli un\'emozione, Tata:</div>', unsafe_allow_html=True)
    
    if 'm_msg' not in st.session_state: st.session_state.m_msg = ""

    c1, c2 = st.columns(2)
    with c1:
        if st.button("😢 Triste"): st.session_state.m_msg = get_frase_emo("Triste"); st.rerun()
        if st.button("🥰 Felice"): st.session_state.m_msg = get_frase_emo("Felice"); st.rerun()
    with c2:
        if st.button("😤 Stressata"): st.session_state.m_msg = get_frase_emo("Stressata"); st.rerun()
        if st.button("🍂 Nostalgica"): st.session_state.m_msg = get_frase_emo("Nostalgica"); st.rerun()

    if st.session_state.m_msg:
        st.markdown(f'<div class="message-box">✨ {st.session_state.m_msg} ✨</div>', unsafe_allow_html=True)
        if st.button("Chiudi ✖️"): 
            st.session_state.m_msg = ""
            st.rerun()
