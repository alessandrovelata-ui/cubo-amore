import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
import random
import json
import requests
from datetime import datetime

# ==============================================================================
# ⚙️ CONFIGURAZIONE
# ==============================================================================
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive"]
SHEET_NAME = 'CuboAmoreDB'

# Nomi Fogli
WS_CALENDARIO = 'Calendario'
WS_EMOZIONI = 'Emozioni'
WS_CONFIG = 'Config'
WS_LOG = 'Log_Mood' # Nuovo foglio per lo storico

# ==============================================================================
# 🎨 STILE CUTE & LEGGIBILE (CORRETTO)
# ==============================================================================
def set_style():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600&family=Nunito:wght@400;700&display=swap');

        /* SFONDO */
        .stApp {
            background-color: #FFF0F5;
            background-image: radial-gradient(#ffebf2 20%, transparent 20%);
            background-size: 20px 20px;
        }
        
        /* NASCONDI MENU */
        #MainMenu, footer, header {visibility: hidden;}
        
        /* TITOLI - FORZIAMO IL COLORE SCURO (Risolve il problema del testo bianco) */
        h1, h2, h3, p, div, span, label {
            color: #880E4F !important; /* Bordeaux scuro sempre */
            text-align: center;
        }

        h1 {
            font-family: 'Fredoka', sans-serif;
            font-size: 40px !important;
            margin-bottom: 10px;
            text-shadow: none !important; /* Rimosso ombreggiatura che sporcava */
        }
        
        /* BOTTONI */
        div.stButton > button {
            width: 100%;
            height: 70px;
            background: white;
            color: #D81B60 !important;
            font-family: 'Nunito', sans-serif;
            font-size: 22px !important;
            font-weight: 700 !important;
            border-radius: 20px;
            border: 2px solid #F48FB1;
            box-shadow: 0 4px 6px rgba(216, 27, 96, 0.1);
            transition: all 0.2s ease;
            margin-bottom: 10px;
        }
        
        div.stButton > button:hover {
            transform: scale(1.02);
            border-color: #C2185B;
        }

        /* BOX MESSAGGIO (Sistemato per non sovrapporre emoji) */
        .message-box {
            background-color: #FFFFFF;
            padding: 25px;
            border-radius: 15px;
            border: 3px dashed #F06292;
            text-align: center;
            font-size: 22px;
            font-weight: 700;
            color: #4A142F !important;
            font-family: 'Nunito', sans-serif;
            line-height: 1.5;
            box-shadow: 0 10px 20px rgba(194, 24, 91, 0.1);
            margin-top: 20px;
            margin-bottom: 20px;
        }
        
        /* Icona decorativa sopra il testo (non sovrapposta) */
        .message-icon {
            font-size: 40px;
            display: block;
            margin-bottom: 10px;
        }

        /* BOTTONE CHIUDI */
        .close-btn button {
            height: 40px !important;
            font-size: 16px !important;
            border: 1px solid #ccc !important;
            color: #555 !important;
            background: #f9f9f9 !important;
        }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 🔌 CONNESSIONI E LOGGING
# ==============================================================================

@st.cache_resource
def get_connection():
    if "GOOGLE_SHEETS_JSON" in st.secrets:
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    else:
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPE)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

def salva_log_mood(mood):
    """Salva il click nel foglio Log_Mood"""
    try:
        sh = get_connection()
        try:
            ws = sh.worksheet(WS_LOG)
        except:
            ws = sh.add_worksheet(title=WS_LOG, rows=1000, cols=3)
            ws.append_row(["Data", "Orario", "Mood"])
        
        now = datetime.now()
        # Append riga: YYYY-MM-DD | HH:MM:SS | Mood
        ws.append_row([now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), mood])
    except Exception as e:
        print(f"Errore log: {e}")

def invia_notifica(text):
    try:
        tk = st.secrets.get("TELEGRAM_TOKEN")
        cid = st.secrets.get("TELEGRAM_CHAT_ID")
        if tk and cid: 
            requests.get(f"https://api.telegram.org/bot{tk}/sendMessage", params={"chat_id": cid, "text": text})
    except: pass

def get_stato_luce():
    try:
        sh = get_connection()
        val = sh.worksheet(WS_CONFIG).acell('B1').value
        return val if val else 'OFF'
    except: return 'OFF'

def set_luce_off():
    try:
        sh = get_connection()
        sh.worksheet(WS_CONFIG).update_acell('B1', 'OFF')
    except: pass

# --- RECUPERO FRASI ---

def get_frase_calendario_oggi():
    try:
        client = get_connection()
        ws = client.worksheet(WS_CALENDARIO)
        df = pd.DataFrame(ws.get_all_records())
        if 'Data' not in df.columns: return None, "Errore DB"

        oggi = datetime.now().strftime("%Y-%m-%d")
        row = df[df['Data'].astype(str).str.strip() == oggi]
        
        if row.empty: return None, "Nessun messaggio per oggi... ❤️"
        return row.iloc[0]['Mood'], row.iloc[0]['Frase']
    except: return None, "Errore lettura calendario"

def get_frase_da_emozioni(mood_target, context_name="EMOZIONI"):
    try:
        # 1. LOGGA L'UMORE (Nuova funzione richiesta)
        salva_log_mood(mood_target)

        client = get_connection()
        ws = client.worksheet(WS_EMOZIONI)
        df = pd.DataFrame(ws.get_all_records())
        
        df['Mood_Clean'] = df['Mood'].astype(str).str.strip().str.lower()
        df['Marker_Clean'] = df['Marker'].astype(str).str.strip().str.lower()
        target = mood_target.strip().lower()
        
        candidati = df[(df['Mood_Clean'].str.contains(target)) & (df['Marker_Clean'] == 'available')]
        
        if candidati.empty:
            candidati = df[df['Marker_Clean'] == 'available']
            if candidati.empty: return "Non ho bigliettini nuovi, ma ti amo! ❤️"
            
        idx = random.choice(candidati.index)
        frase = df.loc[idx, 'Frase']
        ws.update_cell(idx + 2, 4, 'USED')
        
        invia_notifica(f"💌 {context_name}: Lei ha letto ({mood_target}): {frase}")
        return frase
    except Exception as e: return f"Errore: {str(e)}"

# ==============================================================================
# 📱 INTERFACCIA
# ==============================================================================

st.set_page_config(page_title="Cubo Amore", page_icon="🧸", layout="centered")
set_style() 

params = st.query_params
mode = params.get("mode", "home")

# --------------------------
# PAGINA EMOZIONI
# --------------------------
if mode == "mood":
    st.markdown("<h1>Come ti senti, amore? ☁️</h1>", unsafe_allow_html=True)
    st.markdown("<p>Scegli un'emozione per aprire un bigliettino:</p>", unsafe_allow_html=True)
    st.write("") 

    if 'msg_mood' not in st.session_state: st.session_state['msg_mood'] = ""

    c1, c2 = st.columns([1, 1], gap="medium")
    with c1:
        if st.button("😢 Triste"):
            st.session_state['msg_mood'] = get_frase_da_emozioni("Triste")
            st.rerun()
        if st.button("🥰 Felice"):
            st.session_state['msg_mood'] = get_frase_da_emozioni("Felice")
            st.rerun()
    with c2:
        if st.button("😤 Stressata"):
            st.session_state['msg_mood'] = get_frase_da_emozioni("Stressata")
            st.rerun()
        if st.button("🍂 Nostalgica"):
            st.session_state['msg_mood'] = get_frase_da_emozioni("Nostalgica")
            st.rerun()

    if st.session_state['msg_mood']:
        st.markdown("<br>", unsafe_allow_html=True)
        # Box con icona separata per evitare sovrapposizioni
        st.markdown(f"""
        <div class="message-box">
            <span class="message-icon">💌</span>
            {st.session_state['msg_mood']}
            <span class="message-icon" style="margin-top:10px; font-size:25px;">✨</span>
        </div>
        """, unsafe_allow_html=True)
        
        cc1, cc2, cc3 = st.columns([1.5, 1, 1.5])
        with cc2:
            st.markdown('<div class="close-btn">', unsafe_allow_html=True)
            if st.button("Chiudi ✖️"):
                st.session_state['msg_mood'] = ""
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# --------------------------
# PAGINA HOME / BUONGIORNO
# --------------------------
else:
    if 'reading_lamp' not in st.session_state:
        st.session_state['reading_lamp'] = False
        st.session_state['luce_on'] = (get_stato_luce() == 'ON')
    
    if st.session_state['luce_on']:
        st.markdown("<h1>Ti sto pensando... ❤️</h1>", unsafe_allow_html=True)
        st.markdown("<p>Si è accesa una luce per te.</p>", unsafe_allow_html=True)
        st.write("")
        
        if not st.session_state['reading_lamp']:
            c_spacer, c_main, c_spacer2 = st.columns([1, 4, 1])
            with c_main:
                if st.button("💌 C'è un messaggio per te"):
                    st.session_state['testo_lampada'] = get_frase_da_emozioni("Pensiero", context_name="💡 LAMPADA")
                    st.session_state['reading_lamp'] = True
                    st.rerun()
        else:
            st.markdown(f"""
            <div class="message-box">
                <span class="message-icon">💡</span>
                {st.session_state['testo_lampada']}
            </div>
            """, unsafe_allow_html=True)
            st.info("🕒 La luce si spegnerà tra 5 minuti...")
            prog_bar = st.progress(0)
            for i in range(300):
                time.sleep(1)
                prog_bar.progress((i + 1) / 300)
            set_luce_off()
            st.session_state['luce_on'] = False
            st.session_state['reading_lamp'] = False
            st.rerun()

    else:
        st.markdown("<h1>Buongiorno Amore! ☀️</h1>", unsafe_allow_html=True)
        st.markdown(f"<p>{datetime.now().strftime('%d %B %Y')}</p>", unsafe_allow_html=True)
        st.write("")
        
        if 'frase_giorno' not in st.session_state: st.session_state['frase_giorno'] = ""

        if not st.session_state['frase_giorno']:
            c_spacer, c_main, c_spacer2 = st.columns([1, 4, 1])
            with c_main:
                if st.button("☕ Leggi la frase di oggi"):
                    mood, testo = get_frase_calendario_oggi()
                    if testo:
                        st.session_state['frase_giorno'] = testo
                        # Salviamo anche il Buongiorno nel log
                        salva_log_mood("Buongiorno") 
                        invia_notifica(f"☀️ CALENDARIO: Ha letto il buongiorno: {testo}")
                        st.rerun()
                    else:
                        st.warning("Nessuna frase trovata per questa data.")
        else:
            st.markdown(f"""
            <div class="message-box">
                <span class="message-icon">☕</span>
                {st.session_state['frase_giorno']}
            </div>
            """, unsafe_allow_html=True)
