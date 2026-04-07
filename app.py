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

        /* Stile Apple Premium - Sfondo bianco puro */
        .stApp { 
            background: #FFFFFF;
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
        }

        /* Titolo stile Apple - Più grande e bold */
        .main-title { 
            color: #1d1d1f !important; 
            text-align: center; 
            font-size: 34px !important; 
            font-weight: 700; 
            letter-spacing: -0.8px;
            margin-top: 24px;
            margin-bottom: 8px;
        }

        /* Cuore più prominente */
        .heart { 
            font-size: 80px; 
            text-align: center; 
            margin: 24px 0; 
            filter: drop-shadow(0 4px 12px rgba(139, 92, 246, 0.2));
            animation: pulse 2.5s infinite ease-in-out; 
        }
        @keyframes pulse { 
            0%, 100% { transform: scale(1); } 
            50% { transform: scale(1.06); } 
        }

        /* Message box elegante con bordo viola */
        .message-box { 
            background: #FFFFFF;
            padding: 40px 28px; 
            border-radius: 24px; 
            border: 1.5px solid #E9D5FF;
            box-shadow: 0 20px 40px rgba(139, 92, 246, 0.08),
                        0 4px 12px rgba(139, 92, 246, 0.04);
            font-family: 'Dancing Script', cursive;
            font-size: 30px !important; 
            color: #3d2952 !important; 
            text-align: center; 
            line-height: 1.5;
            margin: 28px 0;
        }

        /* Bottoni stile Apple iOS - Viola elegante */
        div.stButton > button { 
            width: 100%; 
            border-radius: 14px; 
            font-weight: 600; 
            height: 58px; 
            background: linear-gradient(180deg, #9333EA 0%, #7E22CE 100%);
            color: white; 
            border: none; 
            font-size: 17px !important;
            letter-spacing: -0.3px;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 8px 24px rgba(147, 51, 234, 0.3);
            margin-bottom: 12px;
        }
        
        div.stButton > button:hover {
            transform: translateY(-3px);
            box-shadow: 0 12px 32px rgba(147, 51, 234, 0.4);
            background: linear-gradient(180deg, #A855F7 0%, #9333EA 100%);
        }
        
        div.stButton > button:active {
            transform: translateY(-1px);
        }
        
        /* Bottone Spegni stile Apple - Più visibile */
        .off-container div.stButton > button, .small-btn div.stButton > button, .btn-off div.stButton > button {
            background: #F3F4F6 !important;
            color: #6B7280 !important;
            height: 48px !important;
            font-size: 16px !important;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06) !important;
            border: 1px solid #E5E7EB !important;
        }
        
        .off-container div.stButton > button:hover, .btn-off div.stButton > button:hover {
            background: #E5E7EB !important;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
        }

        .timer-text { 
            text-align: center; 
            color: #9CA3AF; 
            font-size: 14px; 
            font-weight: 500;
            margin-top: 16px;
            letter-spacing: -0.2px;
        }

        /* Stile decorativo - Più delicato */
        .decorative-clouds {
            text-align: center;
            font-size: 24px;
            margin: 20px 0;
            opacity: 0.5;
        }

        /* Container principale - Più arioso */
        .block-container { 
            padding-top: 2.5rem !important; 
            padding-bottom: 2.5rem !important;
            max-width: 560px !important;
        }
        
        /* Nascondi elementi Streamlit */
        #MainMenu, footer, header {visibility: hidden;}
        
        /* Progress bar stile Apple - Viola premium */
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, #9333EA 0%, #C084FC 100%);
            border-radius: 10px;
            height: 8px;
        }
        
        .stProgress > div > div > div {
            background-color: #F3F4F6;
            border-radius: 10px;
        }
        
        /* Toast personalizzato - Più elegante */
        .stToast {
            background: #FFFFFF !important;
            backdrop-filter: blur(20px);
            border-radius: 16px !important;
            box-shadow: 0 12px 48px rgba(0, 0, 0, 0.12), 
                        0 0 0 1px rgba(0, 0, 0, 0.06) !important;
            border: 1px solid #F3F4F6 !important;
        }
        
        .stToast > div {
            color: #1d1d1f !important;
            font-weight: 500;
        }
        
        .stToast [data-testid="stMarkdownContainer"] p {
            color: #1d1d1f !important;
            font-weight: 500;
        }
        
        /* Spinner stile Apple */
        .stSpinner > div {
            border-color: #9333EA !important;
        }
        
        /* Colonne - Spaziatura migliore */
        div[data-testid="column"] {
            padding: 0 6px !important;
        }
        
        /* Bottoni grandi centrali per Countdown e Buongiorno */
        .big-btn div.stButton > button {
            height: 64px !important;
            font-size: 18px !important;
            font-weight: 700;
            border-radius: 16px;
            margin-bottom: 16px;
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
    
    # Prima riga: Triste e Stressata
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💧 Triste"): st.session_state.m_msg = get_frase_emo("Triste"); st.rerun()
    with c2:
        if st.button("⚡ Stressata"): st.session_state.m_msg = get_frase_emo("Stressata"); st.rerun()
    
    # Seconda riga: Felice e Nostalgica
    c3, c4 = st.columns(2)
    with c3:
        if st.button("💖 Felice"): st.session_state.m_msg = get_frase_emo("Felice"); st.rerun()
    with c4:
        if st.button("🌙 Nostalgica"): st.session_state.m_msg = get_frase_emo("Nostalgica"); st.rerun()
    
    # Spazio
    st.markdown('<div style="margin: 20px 0;"></div>', unsafe_allow_html=True)
    
    # Bottone Countdown - Centrale e più grande
    st.markdown('<div class="big-btn">', unsafe_allow_html=True)
    if st.button("⏳ Countdown"):
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
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Bottone Buongiorno - Centrale e più grande
    st.markdown('<div class="big-btn">', unsafe_allow_html=True)
    if st.button("☀️ Rivedi Buongiorno"):
        # Recupera la frase del buongiorno di oggi senza rifare l'animazione
        oggi = datetime.now().strftime("%Y-%m-%d")
        ultimo_log = conf.acell('B4').value if conf.acell('B4').value else ""
        
        if ultimo_log == oggi:
            # È già entrata oggi, recuperiamo la frase dal calendario
            try:
                ws_cal = db.worksheet("Calendario")
                dati_grezzi = ws_cal.get_all_values()
                df_cal = pd.DataFrame(dati_grezzi[1:], columns=dati_grezzi[0]).astype(str)
                df_cal.columns = df_cal.columns.str.strip()
                match = df_cal[df_cal['Data'] == oggi]
                
                if not match.empty:
                    st.session_state.testo = match.iloc[0]['Frase']
                    st.session_state.view = "BUONGIORNO"
                    update_lamp("BUONGIORNO", st.session_state.testo)
                    st.rerun()
                else:
                    st.session_state.m_msg = "Nessun messaggio del buongiorno per oggi 💜"
                    st.rerun()
            except:
                st.session_state.m_msg = "Non riesco a recuperare il messaggio ⚠️"
                st.rerun()
        else:
            st.session_state.m_msg = "Non hai ancora aperto l'app oggi 💜"
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Spazio
    st.markdown('<div style="margin: 24px 0;"></div>', unsafe_allow_html=True)
    
    # Spegni Lampada in fondo
    st.markdown('<div class="off-container">', unsafe_allow_html=True)
    if st.button("🌑 Spegni Lampada"):
        spegni_tutto(); st.session_state.m_msg = ""; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    if st.session_state.m_msg:
        st.markdown(f'<div class="message-box">{st.session_state.m_msg}</div>', unsafe_allow_html=True)
       # start_auto_off(300)
