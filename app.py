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

# Nomi dei fogli esatti (Case Sensitive)
WS_CALENDARIO = 'Calendario'
WS_EMOZIONI = 'Emozioni'
WS_CONFIG = 'Config'

# ==============================================================================
# 🎨 STILE CUTE & LEGGIBILE (CSS AVANZATO)
# ==============================================================================
def set_style():
    st.markdown("""
    <style>
        /* IMPORT FONT CARINO (Google Fonts) */
        @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600&family=Nunito:wght@400;700&display=swap');

        /* SFONDO GENERALE */
        .stApp {
            background-color: #FFF0F5; /* Lavender Blush (Rosa chiarissimo) */
            background-image: radial-gradient(#ffebf2 20%, transparent 20%),
                              radial-gradient(#ffebf2 20%, transparent 20%);
            background-size: 20px 20px;
            background-position: 0 0, 10px 10px;
        }
        
        /* NASCONDI ELEMENTI STANDARD */
        #MainMenu, footer, header {visibility: hidden;}
        
        /* TITOLI (H1) - RISOLTO IL PROBLEMA DI VISIBILITÀ */
        h1 {
            color: #C2185B !important; /* Rosa Lampone Scuro */
            font-family: 'Fredoka', sans-serif;
            font-weight: 600;
            text-align: center;
            font-size: 42px !important;
            margin-bottom: 10px;
            text-shadow: 2px 2px 0px rgba(255,255,255,0.8);
            padding-top: 10px;
        }
        
        /* SOTTOTITOLI E TESTI (P) */
        p, h3 {
            color: #880E4F !important; /* Bordeaux per massimo contrasto */
            font-family: 'Nunito', sans-serif;
            text-align: center;
            font-size: 20px !important;
            font-weight: 600;
        }
        
        /* BOTTONI ELEGANTI */
        div.stButton > button {
            width: 100%;
            height: 70px;
            background: linear-gradient(to bottom, #FFFFFF, #FFF5F8);
            color: #D81B60 !important; /* Testo Rosa Scuro */
            font-family: 'Nunito', sans-serif;
            font-size: 22px !important;
            font-weight: 700 !important;
            border-radius: 20px;
            border: 2px solid #F48FB1; /* Bordo Rosa Confetto */
            box-shadow: 0 4px 6px rgba(216, 27, 96, 0.1);
            transition: all 0.2s ease;
            margin-bottom: 15px;
        }
        
        div.stButton > button:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 12px rgba(216, 27, 96, 0.2);
            border-color: #C2185B;
            background: #FFFFFF;
        }
        
        div.stButton > button:active {
            transform: translateY(2px);
            box-shadow: none;
            background-color: #FCE4EC;
        }

        /* BOX MESSAGGIO (EFFETTO LETTERA D'AMORE) */
        .message-box {
            background-color: #FFFFFF;
            padding: 30px;
            border-radius: 15px;
            border: 3px dashed #F06292; /* Bordo tratteggiato */
            text-align: center;
            font-size: 24px;
            font-weight: 700;
            color: #4A142F; /* Scritta scura */
            font-family: 'Nunito', sans-serif;
            line-height: 1.6;
            box-shadow: 0 10px 30px rgba(194, 24, 91, 0.15);
            margin-top: 20px;
            margin-bottom: 20px;
            position: relative;
        }
        
        /* Decorazione "Cuoricino" sopra il box (usando CSS after) */
        .message-box::after {
            content: "💌";
            display: block;
            font-size: 30px;
            margin-top: -55px;
            margin-bottom: 10px;
            text-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }

        /* BOTTONE CHIUDI PICCOLO */
        .close-btn button {
            height: 40px !important;
            font-size: 16px !important;
            border: 2px solid #E0E0E0 !important;
            color: #757575 !important;
            background: #FAFAFA !important;
            box-shadow: none !important;
            border-radius: 50px !important;
        }
        .close-btn button:hover {
            border-color: #D81B60 !important;
            color: #D81B60 !important;
        }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 🔌 CONNESSIONI E FUNZIONI DI BACKEND
# ==============================================================================

@st.cache_resource
def get_connection():
    """Connette a Google Sheets"""
    if "GOOGLE_SHEETS_JSON" in st.secrets:
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    else:
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPE)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

def invia_notifica(text):
    """Invia messaggio al tuo Telegram"""
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

# --- LOGICA RECUPERO FRASI ---

def get_frase_calendario_oggi():
    try:
        client = get_connection()
        ws = client.worksheet(WS_CALENDARIO)
        df = pd.DataFrame(ws.get_all_records())
        
        if 'Data' not in df.columns: return None, "Errore DB"

        oggi = datetime.now().strftime("%Y-%m-%d")
        row = df[df['Data'].astype(str).str.strip() == oggi]
        
        if row.empty:
            return None, "Nessun messaggio per oggi... ❤️"
        
        return row.iloc[0]['Mood'], row.iloc[0]['Frase']
    except Exception as e:
        return None, f"Errore: {str(e)}"

def get_frase_da_emozioni(mood_target, context_name="EMOZIONI"):
    try:
        client = get_connection()
        ws = client.worksheet(WS_EMOZIONI)
        df = pd.DataFrame(ws.get_all_records())
        
        # Pulizia dati
        df['Mood_Clean'] = df['Mood'].astype(str).str.strip().str.lower()
        df['Marker_Clean'] = df['Marker'].astype(str).str.strip().str.lower()
        target = mood_target.strip().lower()
        
        # Filtro
        candidati = df[
            (df['Mood_Clean'].str.contains(target)) & 
            (df['Marker_Clean'] == 'available')
        ]
        
        if candidati.empty:
            candidati = df[df['Marker_Clean'] == 'available']
            if candidati.empty: return "Non ho bigliettini nuovi, ma ti amo! ❤️"
            
        # Pesca e aggiorna
        idx = random.choice(candidati.index)
        frase = df.loc[idx, 'Frase']
        
        # Marker a USED (Colonna 4)
        ws.update_cell(idx + 2, 4, 'USED')
        
        invia_notifica(f"💌 {context_name}: Lei ha letto ({mood_target}): {frase}")
        return frase
    except Exception as e:
        return f"Errore sistema: {str(e)}"

# ==============================================================================
# 📱 INTERFACCIA UTENTE (UI)
# ==============================================================================

st.set_page_config(page_title="Cubo Amore", page_icon="🧸", layout="centered")
set_style() # Applica il CSS bello

# Gestione Parametri URL
params = st.query_params
mode = params.get("mode", "home")

# ------------------------------------------------------------------------------
# PAGINA 2: BARATTOLO EMOZIONI (Link: ?mode=mood)
# ------------------------------------------------------------------------------
if mode == "mood":
    # TITOLO SCURO E LEGGIBILE
    st.markdown("<h1>Come ti senti, amore? ☁️</h1>", unsafe_allow_html=True)
    st.markdown("<p>Scegli un'emozione per aprire un bigliettino:</p>", unsafe_allow_html=True)
    st.write("") # Spaziatore

    if 'msg_mood' not in st.session_state: 
        st.session_state['msg_mood'] = ""

    # GRIGLIA PULSANTI (Layout 2x2 con gap)
    col1, col2 = st.columns([1, 1], gap="medium")
    
    with col1:
        if st.button("😢 Triste"):
            st.session_state['msg_mood'] = get_frase_da_emozioni("Triste")
            st.rerun()
        if st.button("🥰 Felice"):
            st.session_state['msg_mood'] = get_frase_da_emozioni("Felice")
            st.rerun()
            
    with col2:
        if st.button("😤 Stressata"):
            st.session_state['msg_mood'] = get_frase_da_emozioni("Stressata")
            st.rerun()
        if st.button("🍂 Nostalgica"):
            st.session_state['msg_mood'] = get_frase_da_emozioni("Nostalgica")
            st.rerun()

    # MESSAGGIO SVELATO
    if st.session_state['msg_mood']:
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Box con stile "lettera"
        st.markdown(f"""
        <div class="message-box">
            ✨ {st.session_state['msg_mood']} ✨
        </div>
        """, unsafe_allow_html=True)
        
        # Bottone chiudi piccolo e centrato
        cc1, cc2, cc3 = st.columns([1.5, 1, 1.5])
        with cc2:
            st.markdown('<div class="close-btn">', unsafe_allow_html=True)
            if st.button("Chiudi ✖️"):
                st.session_state['msg_mood'] = ""
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# PAGINA 1: HOME / LAMPADA / BUONGIORNO (Link Normale)
# ------------------------------------------------------------------------------
else:
    if 'reading_lamp' not in st.session_state:
        st.session_state['reading_lamp'] = False
        st.session_state['luce_on'] = (get_stato_luce() == 'ON')
    
    # --- SCENARIO A: LAMPADA ACCESA (Ti penso) ---
    if st.session_state['luce_on']:
        st.markdown("<h1>Ti sto pensando... ❤️</h1>", unsafe_allow_html=True)
        st.markdown("<p>Si è accesa una luce per te.</p>", unsafe_allow_html=True)
        st.write("")
        
        if not st.session_state['reading_lamp']:
            c_spacer, c_main, c_spacer2 = st.columns([1, 4, 1])
            with c_main:
                # Pulsante Principale
                if st.button("💌 C'è un messaggio per te"):
                    st.session_state['testo_lampada'] = get_frase_da_emozioni("Pensiero", context_name="💡 LAMPADA")
                    st.session_state['reading_lamp'] = True
                    st.rerun()
        else:
            # Mostra messaggio
            st.markdown(f"""
            <div class="message-box">
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

    # --- SCENARIO B: BUONGIORNO (Luce Spenta) ---
    else:
        st.markdown("<h1>Buongiorno Amore! ☀️</h1>", unsafe_allow_html=True)
        oggi_str = datetime.now().strftime('%d %B %Y')
        st.markdown(f"<p style='color:#666 !important; font-size:16px !important;'>{oggi_str}</p>", unsafe_allow_html=True)
        st.write("")
        
        if 'frase_giorno' not in st.session_state: st.session_state['frase_giorno'] = ""

        if not st.session_state['frase_giorno']:
            c_spacer, c_main, c_spacer2 = st.columns([1, 4, 1])
            with c_main:
                if st.button("☕ Leggi la frase di oggi"):
                    mood, testo = get_frase_calendario_oggi()
                    if testo:
                        st.session_state['frase_giorno'] = testo
                        invia_notifica(f"☀️ CALENDARIO: Ha letto il buongiorno: {testo}")
                        st.rerun()
                    else:
                        st.warning("Nessuna frase trovata per questa data.")
        else:
            st.markdown(f"""
            <div class="message-box">
                {st.session_state['frase_giorno']}
            </div>
            """, unsafe_allow_html=True)
