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
# 🎨 STILE CUTE MA LEGGIBILE (CSS)
# ==============================================================================
def set_style():
    st.markdown("""
    <style>
        /* Sfondo Generale: Rosa pallidissimo (quasi bianco) per contrasto */
        .stApp {
            background-color: #FFF5F8;
        }
        
        /* Nascondi menu Streamlit */
        #MainMenu, footer, header {visibility: hidden;}
        
        /* TITOLI: Grande, font leggibile, colore scuro (Bordeaux) */
        h1 {
            color: #880E4F;
            font-family: 'Helvetica Neue', sans-serif;
            font-weight: 800;
            text-align: center;
            font-size: 38px !important;
            margin-bottom: 20px;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
        }
        
        /* Sottotitoli */
        h3, p {
            color: #4A142F; /* Molto scuro per leggibilità */
            text-align: center;
            font-size: 20px;
            font-weight: 500;
        }
        
        /* BOTTONI PRINCIPALI: Grandi, bianchi con bordo evidente */
        div.stButton > button {
            width: 100%;
            height: 75px;  /* Altezza fissa comoda */
            background-color: white;
            color: #C2185B; /* Testo Rosa Scuro */
            font-size: 24px !important;
            font-weight: 700 !important;
            border-radius: 18px;
            border: 3px solid #F06292; /* Bordo Rosa Acceso */
            box-shadow: 0 4px 0px rgba(240, 98, 146, 0.4); /* Effetto 3D */
            transition: all 0.1s ease;
            margin-bottom: 12px;
        }
        
        div.stButton > button:active {
            transform: translateY(4px); /* Effetto pressione */
            box-shadow: none;
            background-color: #FCE4EC;
        }

        /* BOX MESSAGGIO: Il bigliettino */
        .message-box {
            background-color: #FFFFFF;
            padding: 30px;
            border-radius: 20px;
            border: 4px dashed #AD1457; /* Bordo tratteggiato scuro */
            text-align: center;
            font-size: 26px;
            font-weight: 600;
            color: #333333; /* Testo nero/grigio scuro per massima leggibilità */
            font-family: 'Georgia', serif;
            line-height: 1.5;
            box-shadow: 0 10px 25px rgba(173, 20, 87, 0.15);
            margin-top: 10px;
            margin-bottom: 20px;
        }
        
        /* Pulsante Chiudi piccolo */
        .close-btn button {
            height: 45px !important;
            font-size: 18px !important;
            border: 2px solid #ccc !important;
            color: #666 !important;
            box-shadow: none !important;
        }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 🔌 CONNESSIONI E FUNZIONI
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

# --- RECUPERO FRASI ---

def get_frase_calendario_oggi():
    """Pesca la frase del giorno (Data)"""
    try:
        client = get_connection()
        ws = client.worksheet(WS_CALENDARIO)
        df = pd.DataFrame(ws.get_all_records())
        
        if 'Data' not in df.columns: return None, "Errore DB"

        oggi = datetime.now().strftime("%Y-%m-%d")
        # Pulisce spazi e confronta stringhe
        row = df[df['Data'].astype(str).str.strip() == oggi]
        
        if row.empty:
            return None, "Nessun messaggio per oggi... ❤️"
        
        return row.iloc[0]['Mood'], row.iloc[0]['Frase']
    except Exception as e:
        return None, f"Errore: {str(e)}"

def get_frase_da_emozioni(mood_target, context_name="EMOZIONI"):
    """
    Pesca frase da foglio Emozioni.
    Logica: Cerca Mood (es. Triste) + Marker (AVAILABLE).
    """
    try:
        client = get_connection()
        ws = client.worksheet(WS_EMOZIONI)
        df = pd.DataFrame(ws.get_all_records())
        
        # Pulizia colonne per evitare errori di spazi/maiuscole
        df['Mood_Clean'] = df['Mood'].astype(str).str.strip().str.lower()
        df['Marker_Clean'] = df['Marker'].astype(str).str.strip().str.lower()
        target = mood_target.strip().lower()
        
        # Filtro
        candidati = df[
            (df['Mood_Clean'].str.contains(target)) & 
            (df['Marker_Clean'] == 'available')
        ]
        
        # Fallback: se non c'è quel mood, prendi una disponibile a caso
        if candidati.empty:
            candidati = df[df['Marker_Clean'] == 'available']
            if candidati.empty: return "Non ho bigliettini nuovi, ma ti amo! ❤️"
            
        # Pesca casuale
        idx = random.choice(candidati.index)
        frase = df.loc[idx, 'Frase']
        
        # Aggiorna Marker a USED (Colonna D = 4)
        ws.update_cell(idx + 2, 4, 'USED')
        
        # Notifica Telegram
        invia_notifica(f"💌 {context_name}: Lei ha letto ({mood_target}): {frase}")
        
        return frase
    except Exception as e:
        return f"Errore sistema: {str(e)}"

# ==============================================================================
# 📱 APP STREAMLIT
# ==============================================================================

st.set_page_config(page_title="Cubo Amore", page_icon="🧸", layout="centered")
set_style() # Applica il CSS

# Gestione Parametri URL
params = st.query_params
mode = params.get("mode", "home")

# ------------------------------------------------------------------------------
# PAGINA 2: BARATTOLO EMOZIONI (Link: ?mode=mood)
# ------------------------------------------------------------------------------
if mode == "mood":
    st.markdown("<h1>Come ti senti, amore? ☁️</h1>", unsafe_allow_html=True)
    st.markdown("<p>Scegli un'emozione per aprire un bigliettino:</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if 'msg_mood' not in st.session_state: 
        st.session_state['msg_mood'] = ""

    # Griglia pulsanti (2 colonne)
    c1, c2 = st.columns(2)
    
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

    # Se c'è un messaggio svelato
    if st.session_state['msg_mood']:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="message-box">
            ✨ {st.session_state['msg_mood']} ✨
        </div>
        """, unsafe_allow_html=True)
        
        # Bottone chiudi centrato
        cc1, cc2, cc3 = st.columns([1,2,1])
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
    # Check stato luce (solo se non sta già leggendo per non interrompere)
    if 'reading_lamp' not in st.session_state:
        st.session_state['reading_lamp'] = False
        st.session_state['luce_on'] = (get_stato_luce() == 'ON')
    
    # ----------------------------
    # SCENARIO A: LAMPADA ACCESA (Ti penso)
    # ----------------------------
    if st.session_state['luce_on']:
        st.markdown("<h1>Ti sto pensando... ❤️</h1>", unsafe_allow_html=True)
        st.markdown("<p>Si è accesa una luce per te.</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        if not st.session_state['reading_lamp']:
            # Pulsante singolo centrale
            c_spacer, c_main, c_spacer2 = st.columns([1, 4, 1])
            with c_main:
                if st.button("💌 Apri Messaggio"):
                    # Pesca frase 'Pensiero' dalla tabella Emozioni
                    st.session_state['testo_lampada'] = get_frase_da_emozioni("Pensiero", context_name="💡 LAMPADA")
                    st.session_state['reading_lamp'] = True
                    st.rerun()
        else:
            # Messaggio Mostrato + Timer
            st.markdown(f"""
            <div class="message-box" style="border-color: #C2185B;">
                {st.session_state['testo_lampada']}
            </div>
            """, unsafe_allow_html=True)
            
            st.info("🕒 La luce si spegnerà tra 5 minuti...")
            
            # Barra Timer
            prog_bar = st.progress(0)
            for i in range(300): # 300 secondi = 5 min
                time.sleep(1)
                prog_bar.progress((i + 1) / 300)
            
            # Reset Finale
            set_luce_off()
            st.session_state['luce_on'] = False
            st.session_state['reading_lamp'] = False
            st.rerun()

    # ----------------------------
    # SCENARIO B: BUONGIORNO (Luce Spenta)
    # ----------------------------
    else:
        st.markdown("<h1>Buongiorno Amore! ☀️</h1>", unsafe_allow_html=True)
        oggi_str = datetime.now().strftime('%d %B %Y')
        st.markdown(f"<p style='color:#666;'>{oggi_str}</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
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
