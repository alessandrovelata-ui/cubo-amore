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
        @import url('https://fonts.googleapis.com/css2?family=Dancing+Script:wght@600&display=swap');

        /* Stile Apple - SF Pro Display */
        .stApp { 
            background: linear-gradient(135deg, #faf5ff 0%, #e8d5f2 100%);
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
        }

        /* Titolo stile Apple */
        .main-title { 
            color: #3d2952 !important; 
            text-align: center; 
            font-size: 32px !important; 
            font-weight: 600; 
            letter-spacing: -0.5px;
            margin-top: 20px;
            margin-bottom: 8px;
        }

        /* Cuore con effetto glassmorphism */
        .heart { 
            font-size: 72px; 
            text-align: center; 
            margin: 20px 0; 
            filter: drop-shadow(0 8px 16px rgba(0,0,0,0.12));
            animation: pulse 2.5s infinite ease-in-out; 
        }
        @keyframes pulse { 
            0%, 100% { transform: scale(1); } 
            50% { transform: scale(1.08); } 
        }

        /* Message box con glassmorphism Apple */
        .message-box { 
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(20px) saturate(180%);
            -webkit-backdrop-filter: blur(20px) saturate(180%);
            padding: 32px 24px; 
            border-radius: 20px; 
            border: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08),
                        0 2px 8px rgba(0, 0, 0, 0.04);
            font-family: 'Dancing Script', cursive;
            font-size: 28px !important; 
            color: #1d1d1f !important; 
            text-align: center; 
            line-height: 1.4;
            margin: 24px 0;
        }

        /* Bottoni stile Apple */
        div.stButton > button { 
            width: 100%; 
            border-radius: 12px; 
            font-weight: 500; 
            height: 56px; 
            background: linear-gradient(180deg, #8B5CF6 0%, #7C3AED 100%);
            color: white; 
            border: none; 
            font-size: 17px !important;
            letter-spacing: -0.2px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 4px 16px rgba(139, 92, 246, 0.25);
        }
        
        div.stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(139, 92, 246, 0.35);
        }
        
        div.stButton > button:active {
            transform: translateY(0);
        }
        
        /* Bottone Spegni stile Apple grigio */
        .off-container div.stButton > button, .small-btn div.stButton > button, .btn-off div.stButton > button {
            background: rgba(142, 142, 147, 0.12) !important;
            color: #1d1d1f !important;
            height: 44px !important;
            font-size: 15px !important;
            font-weight: 500;
            box-shadow: none;
            border: 0.5px solid rgba(0, 0, 0, 0.04);
        }
        
        .off-container div.stButton > button:hover, .btn-off div.stButton > button:hover {
            background: rgba(142, 142, 147, 0.18) !important;
            transform: translateY(-1px);
        }

        .timer-text { 
            text-align: center; 
            color: #86868b; 
            font-size: 13px; 
            font-weight: 400;
            margin-top: 12px;
            letter-spacing: -0.1px;
        }

        /* Stile decorativo */
        .decorative-clouds {
            text-align: center;
            font-size: 20px;
            margin: 16px 0;
            opacity: 0.6;
        }

        /* Container principale */
        .block-container { 
            padding-top: 2rem !important; 
            padding-bottom: 2rem !important;
            max-width: 600px !important;
        }
        
        /* Nascondi elementi Streamlit */
        #MainMenu, footer, header {visibility: hidden;}
        
        /* Progress bar stile Apple */
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, #8B5CF6 0%, #C084FC 100%);
            border-radius: 10px;
        }
        
        /* Toast personalizzato */
        .stToast {
            background: rgba(255, 255, 255, 0.95) !important;
            backdrop-filter: blur(20px);
            border-radius: 14px !important;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15) !important;
        }
        
        /* Spinner stile Apple */
        .stSpinner > div {
            border-color: #8B5CF6 !important;
        }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource(ttl=600)
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

def spegni_tutto():
    try:
        db = get_db(); conf = db.worksheet("Config")
        conf.update('B1:B3', [['OFF'], ['OFF'], ['']])
        invia_notifica("🌑 La lampada si è spenta.")
        st.session_state.feedback = "Comando ricevuto: Lampada spenta! 🌑"
    except:
        st.session_state.feedback = "Errore di connessione ⚠️"

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

# --- INIZIO APP ---
st.set_page_config(page_title="Cubo Amore", page_icon="🧸", layout="centered")
set_style()

# --- FIX: Inizializzazione sicura st.session_state ---
if 'view' not in st.session_state: st.session_state.view = "LANDING"
if 'testo' not in st.session_state: st.session_state.testo = ""
if 'm_msg' not in st.session_state: st.session_state.m_msg = ""
if 'countdown_msg' not in st.session_state: st.session_state.countdown_msg = ""

# Mostra il feedback dello spegnimento se presente
if 'feedback' in st.session_state:
    st.toast(st.session_state.feedback, icon="✨")
    del st.session_state.feedback

db = get_db()
conf = db.worksheet("Config")

def start_auto_off(seconds=300):
    minuti = seconds // 60
    st.markdown(f'<p class="timer-text">Spegnimento automatico tra {minuti} minuti</p>', unsafe_allow_html=True)
    p = st.progress(0)
    for i in range(seconds):
        time.sleep(1)
        p.progress((i + 1) / seconds)
    spegni_tutto()
    st.session_state.view = "MOODS"
    st.rerun()

# --- LOGICA DASHBOARD ---
if st.session_state.view == "MOODS":
    try:
        check_status = conf.batch_get(['B1', 'B2', 'B3'])
        if check_status and check_status[0][0][0] == 'ON' and check_status[1][0][0] == 'PENSIERO':
            st.session_state.view = "FIXED"
            st.session_state.testo = check_status[2][0][0] if check_status[2][0] else "Ti penso! ❤️"
            conf.update_acell('B3', '')
            st.rerun()
    except: pass

# --- 1. LANDING PAGE ---
if st.session_state.view == "LANDING":
    st.markdown('<div class="main-title">Ciao Bimba...</div>', unsafe_allow_html=True)
    st.markdown('<div class="heart">✨💜✨</div>', unsafe_allow_html=True)
    if st.button("Entra nel nostro mondo ❤️"):
        invia_notifica("🔔 Anita è entrata nell'app")
        oggi = datetime.now().strftime("%Y-%m-%d")
        
        # Leggiamo B4: se è diverso da oggi, procediamo (anche se ha saltato mesi)
        ultimo_log = conf.acell('B4').value if conf.acell('B4').value else ""
        
        if ultimo_log != oggi:
            # RIGIDITÀ: È un giorno nuovo, carichiamo la sorpresa
            ws_cal = db.worksheet("Calendario")
            
            # get_all_values è "blindato": legge il foglio così com'è, zero inferenze
            dati_grezzi = ws_cal.get_all_values()
            
            # Trasformiamo in DataFrame forzando tutto a "stringa"
            df_cal = pd.DataFrame(dati_grezzi[1:], columns=dati_grezzi[0]).astype(str)
            df_cal.columns = df_cal.columns.str.strip()
            
            # Cerchiamo la data di oggi
            match = df_cal[df_cal['Data'] == oggi]
            
            if not match.empty:
                frase = match.iloc[0]['Frase']
                st.session_state.testo = frase
                conf.update_acell('B4', oggi)
                update_lamp("BUONGIORNO", frase)
                st.session_state.view = "BUONGIORNO"
            else:
                # Se oggi non è nel calendario, la mandiamo ai mood senza crashare
                # (Succede se ti dimentichi di scrivere la riga di oggi)
                st.session_state.view = "MOODS"
            
            st.rerun()
        else:
            # È già entrata oggi
            st.session_state.view = "MOODS"
            st.rerun()

# --- VISTE MESSAGGI ---
elif st.session_state.view == "FIXED":
    st.markdown('<div class="main-title">Per te...</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.testo}</div>', unsafe_allow_html=True)
    
    # Creazione di due colonne per i pulsanti orizzontali
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Emozioni ☁️"):
            st.session_state.view = "MOODS"
            st.rerun()
            
    with col2:
        st.markdown('<div class="btn-off">', unsafe_allow_html=True)
        if st.button("🌑 Spegni"):
            spegni_tutto()
            st.session_state.view = "MOODS"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
   #start_auto_off(300)

elif st.session_state.view == "BUONGIORNO":
    st.markdown('<div class="main-title">Buongiorno Cucciola...</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.testo}</div>', unsafe_allow_html=True)
    
    # Creazione di due colonne per i pulsanti orizzontali
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Emozioni ☁️"):
            st.session_state.view = "MOODS"
            st.rerun()
            
    with col2:
        st.markdown('<div class="btn-off">', unsafe_allow_html=True)
        if st.button("🌑 Spegni"):
            spegni_tutto()
            st.session_state.view = "MOODS"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    #start_auto_off(300)

elif st.session_state.view == "COUNTDOWN":
    st.markdown('<div class="main-title">Manca poco...</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="message-box">{st.session_state.countdown_msg}</div>', unsafe_allow_html=True)
    
    # Creazione di due colonne per i pulsanti orizzontali
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Emozioni ☁️"):
            st.session_state.view = "MOODS"
            st.rerun()
            
    with col2:
        st.markdown('<div class="btn-off">', unsafe_allow_html=True)
        if st.button("🌑 Spegni"):
            spegni_tutto()
            st.session_state.view = "MOODS"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    #start_auto_off(900)

# --- 5. VISTA EMOZIONI ---
elif st.session_state.view == "MOODS":
    st.markdown('<div class="main-title">Come ti senti oggi?</div>', unsafe_allow_html=True)
    st.markdown('<div class="decorative-clouds">☁️✨☁️</div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💧 Triste"): st.session_state.m_msg = get_frase_emo("Triste"); st.rerun()
        if st.button("💖 Felice"): st.session_state.m_msg = get_frase_emo("Felice"); st.rerun()
        
        if st.button("⏳\nCountdown"):
            with st.spinner("Calcolo in corso..."):
                successo = False
                for tentativo in range(3):
                    try:
                        ws_ev = db.worksheet("events")
                        dati_raw = ws_ev.get_values("B2:D2")
                        if dati_raw:
                            dati = dati_raw[0]
                            data_fine_str = dati[0]; evento = dati[1]; percentuale = dati[2]
                            data_fine = datetime.strptime(data_fine_str, "%d/%m/%Y")
                            differenza = (data_fine - datetime.now()).days + 1
                            st.session_state.countdown_msg = f"Mancano {differenza} giorni a {evento} ❤️"
                            st.session_state.view = "COUNTDOWN"
                            update_lamp("COUNTDOWN", str(percentuale))
                            invia_notifica(f"⏳ Anita ha attivato il Countdown")
                            successo = True
                            break 
                    except Exception:
                        st.cache_resource.clear() 
                        time.sleep(0.5) 
                        continue 
                if successo: st.rerun()
                else: st.error("Riprova tra un istante.")

    with c2:
        if st.button("⚡ Stressata"): st.session_state.m_msg = get_frase_emo("Stressata"); st.rerun()
        if st.button("🌙 Nostalgica"): st.session_state.m_msg = get_frase_emo("Nostalgica"); st.rerun()
    
    # Spegni Lampada in fondo
    st.markdown('<div class="off-container">', unsafe_allow_html=True)
    if st.button("🌑 Spegni Lampada"):
        spegni_tutto(); st.session_state.m_msg = ""; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    if st.session_state.m_msg:
        st.markdown(f'<div class="message-box">{st.session_state.m_msg}</div>', unsafe_allow_html=True)
       # start_auto_off(300)
