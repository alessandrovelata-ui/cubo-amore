import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json, requests, time, random
from datetime import datetime

# ==============================================================================
# ⚙️ CONFIGURAZIONE E STILE
# ==============================================================================
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "CuboAmoreDB"

def set_style():
    st.markdown("""
    <style>
        .stApp { background-color: #FFF0F5; }
        #MainMenu, footer, header {visibility: hidden;}
        .main-title { color: #C2185B !important; font-family: sans-serif; text-align: center; font-size: 36px !important; font-weight: 800; margin-bottom: 20px; }
        .sub-text { color: #880E4F !important; text-align: center; font-family: sans-serif; font-size: 18px; font-weight: bold; margin-bottom: 20px; }
        
        .message-box {
            background: white; padding: 25px; border-radius: 20px; border: 4px dashed #F06292;
            font-size: 24px; color: #4A142F !important; text-align: center; font-weight: 700;
            box-shadow: 0 10px 20px rgba(0,0,0,0.05); margin-bottom: 25px;
        }

        div.stButton > button {
            width: 100%; height: 70px; background: white; color: #D81B60 !important;
            font-size: 20px !important; font-weight: bold; border-radius: 15px;
            border: 2px solid #F48FB1; transition: 0.3s;
        }
        
        .off-btn > div > button {
            background-color: #880E4F !important; color: white !important;
            border: none !important; height: 55px !important;
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

# ==============================================================================
# 🧠 LOGICA ESTRAZIONE FRASI
# ==============================================================================

def get_frase_emo(mood_richiesto):
    db = get_db()
    ws = db.worksheet("Emozioni")
    df = pd.DataFrame(ws.get_all_records())
    df.columns = df.columns.str.strip()
    
    # Filtro frasi disponibili per il mood scelto
    cand = df[(df['Mood'].str.contains(mood_richiesto, case=False, na=False)) & 
              (df['Marker'].str.strip().str.upper() == 'AVAILABLE')]
    
    if cand.empty:
        # Fallback se non ci sono frasi specifiche disponibili
        cand = df[df['Marker'].str.strip().str.upper() == 'AVAILABLE']
    
    if cand.empty:
        return f"Ti amo tanto, Bimba! ❤️"

    idx_originale = cand.index[0]
    frase = cand.loc[idx_originale, 'Frase']
    
    # Segna la frase come usata nel database
    ws.update_cell(idx_originale + 2, 4, 'USED')
    
    # Registra nel Log e manda notifica a te
    db.worksheet("Log_Mood").append_row([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"), mood_richiesto])
    invia_notifica(f"💌 {mood_richiesto}: La tua Bimba ha letto '{frase}'")
    
    return frase

# ==============================================================================
# 🚀 LOGICA DI NAVIGAZIONE (Sincronizzata con Google Sheet)
# ==============================================================================
st.set_page_config(page_title="Cubo Amore", page_icon="🧸")
set_style()

# Determiniamo quale schermata mostrare all'avvio
if 'view' not in st.session_state:
    db = get_db()
    conf_ws = db.worksheet("Config")
    lamp_status = conf_ws.acell('B1').value
    mode = conf_ws.acell('B2').value
    custom_msg = conf_ws.acell('B3').value # Testo inviato/confermato da Telegram

    if lamp_status == 'ON':
        st.session_state.view = "FIXED"
        st.session_state.title = "Ti sto pensando... ❤️" if mode == "PENSIERO" else "Buongiorno Amore! ☀️"
        
        # Se c'è un messaggio manuale in B3, usalo e poi svuota la cella
        if custom_msg and len(custom_msg.strip()) > 1:
            st.session_state.testo = custom_msg
            conf_ws.update_acell('B3', '') 
        else:
            # Altrimenti pesca dal calendario (se Buongiorno) o dalle emozioni
            if mode == "BUONGIORNO":
                df_cal = pd.DataFrame(db.worksheet("Calendario").get_all_records())
                row = df_cal[df_cal['Data'].astype(str) == datetime.now().strftime("%Y-%m-%d")]
                st.session_state.testo = row.iloc[0]['Frase'] if not row.empty else "Buongiorno Tata! ❤️"
            else:
                st.session_state.testo = "Sei nel mio cuore! ❤️"
        
        # Notifica Telegram del successo della lettura
        invia_notifica(f"🔔 LETTURA: La tua Bimba ha visualizzato: '{st.session_state.testo}'")
    else:
        st.session_state.view = "MOODS"

# --- VISTA A: MESSAGGIO D'AMORE (Timer 3 minuti) ---
if st.session_state.view == "FIXED":
    st.markdown(f'<div class="main-title">{st.session_state.title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.testo}</div>', unsafe_allow_html=True)
    
    st.write("")
    # Pulsante per spegnere manualmente e tornare subito alle emozioni
    st.markdown('<div class="off-btn">', unsafe_allow_html=True)
    if st.button("Spegni Lampada 🌑"):
        get_db().worksheet("Config").update_acell('B1', 'OFF')
        st.session_state.view = "MOODS"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Barra di progresso per il timer di 3 minuti (180 secondi)
    prog_bar = st.progress(0)
    for i in range(180):
        time.sleep(1)
        prog_bar.progress((i + 1) / 180)
    
    # Allo scadere del tempo: spegni lampada nel DB e resetta l'interfaccia
    get_db().worksheet("Config").update_acell('B1', 'OFF')
    st.session_state.view = "MOODS"
    st.rerun()

# --- VISTA B: SCELTA EMOZIONI (Stato di attesa) ---
elif st.session_state.view == "MOODS":
    st.markdown('<div class="main-title">Come ti senti, amore? ☁️</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-text">Scegli un\'emozione per me:</div>', unsafe_allow_html=True)
    
    if 'm_msg' not in st.session_state: st.session_state.m_msg = ""

    col1, col2 = st.columns(2)
    with col1:
        if st.button("😢 Triste"): st.session_state.m_msg = get_frase_emo("Triste"); st.rerun()
        if st.button("🥰 Felice"): st.session_state.m_msg = get_frase_emo("Felice"); st.rerun()
    with col2:
        if st.button("😤 Stressata"): st.session_state.m_msg = get_frase_emo("Stressata"); st.rerun()
        if st.button("🍂 Nostalgica"): st.session_state.m_msg = get_frase_emo("Nostalgica"); st.rerun()

    # Visualizza la frase dell'emozione scelta
    if st.session_state.m_msg:
        st.markdown(f'<div class="message-box">✨ {st.session_state.m_msg} ✨</div>', unsafe_allow_html=True)
        if st.button("Chiudi ✖️"): 
            st.session_state.m_msg = ""
            st.rerun()
