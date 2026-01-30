import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json, requests, time
from datetime import datetime

# --- SETUP ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "CuboAmoreDB"

def set_style():
    st.markdown("""
    <style>
        .stApp { background-color: #FFF0F5; }
        #MainMenu, footer, header {visibility: hidden;}
        .main-title { color: #C2185B !important; font-family: sans-serif; text-align: center; font-size: 38px !important; font-weight: 800; margin-bottom: 20px; }
        .sub-text { color: #880E4F !important; text-align: center; font-family: sans-serif; font-size: 20px; font-weight: bold; margin-bottom: 10px; }
        div.stButton > button {
            width: 100%; height: 75px; background: white; color: #D81B60 !important;
            font-size: 22px !important; font-weight: bold; border-radius: 20px;
            border: 3px solid #F48FB1; box-shadow: 0 4px 6px rgba(216, 27, 96, 0.1);
        }
        .message-box {
            background: white; padding: 25px; border-radius: 20px; border: 4px dashed #F06292;
            font-size: 24px; color: #4A142F !important; text-align: center;
            box-shadow: 0 10px 20px rgba(0,0,0,0.05); margin-top: 20px; font-weight: 700;
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
    
    # --- FIX KEYERROR: Pulizia intestazioni ---
    df.columns = df.columns.str.strip() # Rimuove spazi bianchi
    
    # Se la colonna 'Mood' o 'Marker' mancano ancora, usiamo il fallback
    if 'Mood' not in df.columns or 'Marker' not in df.columns:
        return f"Ciao {random.choice(['Tata', 'Cucciola', 'Baby', 'Bimba'])}, ti penso tanto! ❤️"

    # Filtro intelligente
    cand = df[(df['Mood'].str.contains(mood_richiesto, case=False, na=False)) & 
              (df['Marker'].str.strip().str.upper() == 'AVAILABLE')]
    
    if cand.empty:
        # Se non ci sono frasi disponibili per quel mood, prendine una a caso disponibile
        cand = df[df['Marker'].str.strip().str.upper() == 'AVAILABLE']
    
    if cand.empty:
        return "Sei la mia vita! ❤️"

    idx_originale = cand.index[0]
    frase = cand.loc[idx_originale, 'Frase']
    
    # Aggiorna il Marker su USED (usiamo idx+2 perché Excel parte da 1 e c'è l'intestazione)
    ws.update_cell(idx_originale + 2, 4, 'USED')
    
    # Log
    db.worksheet("Log_Mood").append_row([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"), mood_richiesto])
    invia_notifica(f"💌 {mood_richiesto}: Cucciola ha letto '{frase}'")
    return frase

# --- LOGICA DI NAVIGAZIONE ---
st.set_page_config(page_title="Cubo Amore", page_icon="🧸")
set_style()

if 'view' not in st.session_state:
    conf = get_db().worksheet("Config")
    lamp_on = conf.acell('B1').value == 'ON'
    mode = conf.acell('B2').value
    
    # 1. Priorità: Pensiero da Telegram
    if lamp_on and mode == "PENSIERO":
        st.session_state.view = "FIXED"
        st.session_state.testo = get_frase_emo("Pensiero")
        st.session_state.title = "Ti sto pensando... ❤️"
    else:
        # 2. Controllo Buongiorno
        log_ws = get_db().worksheet("Log_Mood")
        log_df = pd.DataFrame(log_ws.get_all_records())
        oggi = datetime.now().strftime("%Y-%m-%d")
        
        # Verifica se 'Buongiorno' è già stato fatto oggi
        gia_letto = False
        if not log_df.empty:
            log_df.columns = log_df.columns.str.strip()
            gia_letto = not log_df[(log_df['Data'] == oggi) & (log_df['Mood'] == 'Buongiorno')].empty
        
        if not gia_letto:
            conf.update_acell('B1', 'ON')
            conf.update_acell('B2', 'BUONGIORNO')
            cal = pd.DataFrame(get_db().worksheet("Calendario").get_all_records())
            cal.columns = cal.columns.str.strip()
            row = cal[cal['Data'].astype(str) == oggi]
            
            st.session_state.testo = row.iloc[0]['Frase'] if not row.empty else "Buongiorno Bimba! ❤️"
            st.session_state.view = "FIXED"
            st.session_state.title = "Buongiorno Amore! ☀️"
            log_ws.append_row([oggi, datetime.now().strftime("%H:%M:%S"), "Buongiorno"])
            invia_notifica(f"☀️ BUONGIORNO: Letto '{st.session_state.testo}'")
        else:
            st.session_state.view = "MOODS"

# --- RENDER INTERFACCIA ---
if st.session_state.view == "MOODS":
    st.markdown('<div class="main-title">Come ti senti, amore? ☁️</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-text">Scegli un\'emozione per me:</div>', unsafe_allow_html=True)
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
        if st.button("Chiudi ✖️"): st.session_state.m_msg = ""; st.rerun()

elif st.session_state.view == "FIXED":
    st.markdown(f'<div class="main-title">{st.session_state.title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.testo}</div>', unsafe_allow_html=True)
    
    prog = st.progress(0)
    for i in range(300): # 5 Minuti
        time.sleep(1)
        prog.progress((i + 1) / 300)
    
    get_db().worksheet("Config").update_acell('B1', 'OFF')
    invia_notifica("🌑 NOTIFICA: Lampada spenta automaticamente.")
    st.session_state.view = "MOODS"
    st.rerun()
