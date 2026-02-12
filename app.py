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
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700&family=Dancing+Script:wght@600&display=swap');

        /* Sfondo Gradiente Dark come da immagine */
        .stApp { 
            background: linear-gradient(180deg, #0F0C29 0%, #20133A 50%, #24243E 100%);
            font-family: 'Montserrat', sans-serif;
            color: white;
        }

        /* Titolo Allineato a Sinistra (Welcome style) */
        .main-title { 
            color: #FFFFFF !important; 
            text-align: left; 
            font-size: 28px !important; 
            font-weight: 700; 
            margin-top: 20px;
            padding-left: 10px;
        }

        /* Card Messaggio (Stile Weather Widget) */
        .message-box { 
            background: rgba(255, 255, 255, 0.07); 
            backdrop-filter: blur(15px);
            padding: 25px; 
            border-radius: 25px; 
            border: 1px solid rgba(255, 255, 255, 0.1);
            font-family: 'Dancing Script', cursive;
            font-size: 28px !important; 
            color: #E0E0E0 !important; 
            text-align: center; 
            margin: 20px 0;
            box-shadow: 0 15px 35px rgba(0,0,0,0.2);
        }

        /* Pulsanti stile "Your Rooms" (Card quadrate e trasparenti) */
        div.stButton > button { 
            width: 100%; 
            border-radius: 22px; 
            font-weight: 600; 
            height: 120px; /* Più alti per somigliare alle card dell'immagine */
            background: rgba(255, 255, 255, 0.05) !important; 
            color: white !important; 
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            font-size: 18px !important;
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }
        
        div.stButton > button:hover {
            background: rgba(255, 255, 255, 0.12) !important;
            border: 1px solid rgba(255, 255, 255, 0.3) !important;
            transform: translateY(-5px);
        }

        /* Heart animato con glow */
        .heart { 
            font-size: 50px; 
            text-align: center; 
            margin: 15px 0;
            filter: drop-shadow(0 0 15px rgba(126, 87, 194, 0.6));
            animation: pulse 2s infinite ease-in-out;
        }
        @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }

        /* Bottone Spegni (Discreto in fondo) */
        .off-container div.stButton > button {
            background: rgba(255, 75, 75, 0.1) !important;
            height: 50px !important;
            font-size: 14px !important;
            margin-top: 20px;
            border-radius: 15px;
        }

        .timer-text { 
            text-align: center; 
            color: rgba(255,255,255,0.4); 
            font-size: 12px; 
            margin-top: 15px; 
        }

        /* Ottimizzazione Mobile */
        .block-container { padding: 1rem !important; }
        #MainMenu, footer, header {visibility: hidden;}

        /* Effetto cerchio dietro le emoji (simulato) */
        .stButton button::before {
            content: '';
            position: absolute;
            width: 40px;
            height: 40px;
            background: rgba(255,255,255,0.05);
            border-radius: 50%;
            z-index: -1;
            top: 20%;
        }
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
    with st.spinner("Cerco un pensiero per te..."):
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

st.set_page_config(page_title="Cubo Amore", page_icon="🧸", layout="centered")
set_style()

if 'view' not in st.session_state: st.session_state.view = "LANDING"
db = get_db()
conf = db.worksheet("Config")

def start_auto_off(seconds=300):
    minuti = seconds // 60
    st.markdown(f'<p class="timer-text">Spegnimento tra {minuti} min...</p>', unsafe_allow_html=True)
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
    st.markdown('<div class="main-title">Welcome, Anita</div>', unsafe_allow_html=True)
    st.markdown('<div class="heart">🌙✨</div>', unsafe_allow_html=True)
    if st.button("Entra nel nostro mondo ❤️"):
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
    st.markdown('<div class="main-title">Dedicato a te...</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.testo}</div>', unsafe_allow_html=True)
    if st.button("Vai alle Emozioni ☁️"):
        st.session_state.view = "MOODS"; st.rerun()
    start_auto_off(300)

# --- 3. VISTA BUONGIORNO ---
elif st.session_state.view == "BUONGIORNO":
    st.markdown('<div class="main-title">Buongiorno Cucciola...</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.testo}</div>', unsafe_allow_html=True)
    if st.button("Vai alle Emozioni ☁️"): 
        st.session_state.view = "MOODS"; st.rerun()
    start_auto_off(300)

# --- 4. VISTA: COUNTDOWN ---
elif st.session_state.view == "COUNTDOWN":
    st.markdown('<div class="main-title">Manca poco...</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.countdown_msg}</div>', unsafe_allow_html=True)
    if st.button("Torna alle Emozioni ☁️"):
        st.session_state.view = "MOODS"; st.rerun()
    start_auto_off(900)

# --- 5. VISTA EMOZIONI ---
elif st.session_state.view == "MOODS":
    st.markdown('<div class="main-title">Your Moods</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:rgba(255,255,255,0.5); padding-left:10px; margin-bottom:20px;">Scegli come illuminare il cuore</div>', unsafe_allow_html=True)
    
    if 'm_msg' not in st.session_state: st.session_state.m_msg = ""
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💧\nTriste"): st.session_state.m_msg = get_frase_emo("Triste"); st.rerun()
        if st.button("💖\nFelice"): st.session_state.m_msg = get_frase_emo("Felice"); st.rerun()
        if st.button("⏳\nCountdown"):
            with st.spinner("Calcolo..."):
                try:
                    ws_ev = db.worksheet("events")
                    dati = ws_ev.get_values("B2:D2")[0]
                    data_fine_str = dati[0]; evento = dati[1]; percentuale = dati[2]
                    data_fine = datetime.strptime(data_fine_str, "%d/%m/%Y")
                    differenza = (data_fine - datetime.now()).days + 1
                    st.session_state.countdown_msg = f"Mancano {differenza} giorni a {evento} ❤️"
                    update_lamp("COUNTDOWN", str(percentuale))
                    invia_notifica(f"⏳ Anita ha attivato il Countdown")
                    st.session_state.view = "COUNTDOWN"; st.rerun()
                except: st.error("Errore!")

    with c2:
        if st.button("⚡\nStressata"): st.session_state.m_msg = get_frase_emo("Stressata"); st.rerun()
        if st.button("🌙\nNostalgica"): st.session_state.m_msg = get_frase_emo("Nostalgica"); st.rerun()
    
    st.markdown('<div class="off-container">', unsafe_allow_html=True)
    if st.button("🌑 Spegni Lampada"):
        spegni_tutto(); st.session_state.m_msg = ""; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    if st.session_state.m_msg:
        st.markdown(f'<div class="message-box">{st.session_state.m_msg}</div>', unsafe_allow_html=True)
        start_auto_off(300)
