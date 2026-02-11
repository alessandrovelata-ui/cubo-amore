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
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;700;800&display=swap');

        /* Sfondo Viola Polvere Soft */
        .stApp { 
            background-color: #F3F0F7; 
            font-family: 'Montserrat', sans-serif;
        }

        /* Titolo Professionale */
        .main-title { 
            color: #2D2438 !important; 
            text-align: center; 
            font-size: 32px !important; 
            font-weight: 800; 
            letter-spacing: -1px;
            margin-top: 20px;
            padding-bottom: 10px;
        }

        /* Cuore più discreto ed elegante */
        .heart { 
            font-size: 80px; 
            text-align: center; 
            margin: 30px 0; 
            filter: drop-shadow(0 0 10px rgba(103, 58, 183, 0.2));
            animation: pulse 2s infinite ease-in-out; 
        }
        @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.05); } 100% { transform: scale(1); } }

        /* Box messaggi raffinato */
        .message-box { 
            background: white; 
            padding: 30px; 
            border-radius: 15px; 
            border-left: 8px solid #673AB7; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            font-size: 20px; 
            color: #453A54 !important; 
            text-align: center; 
            font-weight: 400; 
            line-height: 1.6;
            margin-bottom: 25px; 
        }

        /* Bottoni Minimal e Professionali */
        div.stButton > button { 
            width: 100%; 
            border-radius: 12px; 
            font-weight: 600; 
            height: 60px; 
            font-size: 16px !important; 
            background-color: #673AB7; 
            color: white; 
            border: none; 
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(103, 58, 183, 0.2);
            margin-bottom: 12px;
        }
        
        div.stButton > button:hover {
            background-color: #512DA8;
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(103, 58, 183, 0.3);
        }

        .timer-text { 
            text-align: center; 
            color: #8E849B; 
            font-size: 13px; 
            font-weight: 500;
            margin-top: 15px; 
        }
        
        /* Nasconde header e footer Streamlit per un look più app-like */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

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
    st.markdown(f'<p class="timer-text">La lampada si spegnerà automaticamente tra {minuti} minuti...</p>', unsafe_allow_html=True)
    p = st.progress(0)
    for i in range(seconds):
        time.sleep(1)
        p.progress((i + 1) / seconds)
    spegni_tutto()
    st.session_state.view = "MOODS"
    st.rerun()

if st.session_state.view == "MOODS":
    check_status = conf.batch_get(['B1', 'B2', 'B3'])
    if check_status[0][0][0] == 'ON' and check_status[1][0][0] == 'PENSIERO':
        st.session_state.view = "FIXED"
        st.session_state.testo = check_status[2][0][0] if check_status[2][0] else "Ti penso! ❤️"
        conf.update_acell('B3', '')
        st.rerun()

# --- 1. LANDING PAGE ---
if st.session_state.view == "LANDING":
    st.markdown('<div class="main-title">Ciao Bimba... ❤️</div>', unsafe_allow_html=True)
    st.markdown('<div class="heart">💜</div>', unsafe_allow_html=True)
    if st.button("Entra nel nostro mondo ✨"):
        invia_notifica("🔔 Anita è entrata nell'app")
        oggi = datetime.now().strftime("%Y-%m-%d")
        status_row = conf.row_values(4)
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
        
        if st.button("⏳ Countdown"):
            with st.spinner("Calcolo in corso..."):
                try:
                    ws_ev = db.worksheet("events")
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
                except:
                    st.error("Errore configurazione countdown.")

    with c2:
        if st.button("😤 Stressata"): st.session_state.m_msg = get_frase_emo("Stressata"); st.rerun()
        if st.button("🍂 Nostalgica"): st.session_state.m_msg = get_frase_emo("Nostalgica"); st.rerun()
        if st.button("🌑 Spegni tutto"):
            spegni_tutto(); st.session_state.m_msg = ""; st.rerun()
    
    if st.session_state.m_msg:
        st.markdown(f'<div class="message-box">{st.session_state.m_msg}</div>', unsafe_allow_html=True)
        start_auto_off(300)
