import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
import random
import json
import requests
from datetime import datetime

# --- CONFIGURAZIONE ---
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive"]
SHEET_NAME = 'CuboAmoreDB'

# Nomi Fogli
WS_CALENDARIO = 'Calendario'
WS_EMOZIONI = 'Emozioni'
WS_CONFIG = 'Config'

# --- CSS "CUTE" & STYLING ---
def set_cute_style():
    st.markdown("""
    <style>
        /* Sfondo generale rosato/crema */
        .stApp {
            background-color: #fff0f5;
            background-image: linear-gradient(to bottom right, #fff0f5, #ffe4e1);
        }
        
        /* Nascondi menu standard */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Stile Titoli */
        h1 {
            color: #ff69b4;
            font-family: 'Comic Sans MS', 'Chalkboard SE', sans-serif;
            text-shadow: 2px 2px 4px #ffc0cb;
            text-align: center;
        }
        
        /* Stile Pulsanti Cute */
        .stButton>button {
            width: 100%;
            height: 60px;
            border-radius: 25px;
            border: 3px solid #ffb7b2;
            background-color: #ffffff;
            color: #ff69b4;
            font-size: 18px;
            font-weight: bold;
            box-shadow: 0px 4px 6px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        
        .stButton>button:hover {
            transform: scale(1.05);
            background-color: #ffb7b2;
            color: white;
            border-color: white;
        }
        
        /* Box Messaggi */
        .cute-box {
            background-color: white;
            padding: 25px;
            border-radius: 20px;
            border: 2px dashed #ff69b4;
            text-align: center;
            box-shadow: 0 4px 15px rgba(255, 105, 180, 0.2);
            margin-bottom: 20px;
            font-size: 20px;
            color: #555;
            font-family: 'Georgia', serif;
        }
    </style>
    """, unsafe_allow_html=True)

# --- CONNESSIONE ---
@st.cache_resource
def get_connection():
    if "GOOGLE_SHEETS_JSON" in st.secrets:
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    else:
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPE)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

# --- GESTIONE LUCE ---
def get_stato_luce():
    try:
        sh = get_connection()
        return sh.worksheet(WS_CONFIG).acell('B1').value or 'OFF'
    except: return 'OFF'

def set_luce_off():
    try:
        sh = get_connection()
        sh.worksheet(WS_CONFIG).update_acell('B1', 'OFF')
    except: pass

# --- RECUPERO FRASI ---

def get_frase_calendario_oggi():
    """Logica Buongiorno (Data di oggi)"""
    sh = get_connection()
    ws = sh.worksheet(WS_CALENDARIO)
    df = pd.DataFrame(ws.get_all_records())
    
    # Pulizia dati
    if 'Data' not in df.columns: return None, "Errore: Colonna Data mancante."
    
    # Formatta data oggi come nel foglio (YYYY-MM-DD)
    oggi = datetime.now().strftime("%Y-%m-%d")
    
    # Cerca corrispondenza
    row = df[df['Data'].astype(str).str.strip() == oggi]
    
    if row.empty:
        return None, "Non c'è una frase programmata per oggi sul calendario! 📅"
    
    frase = row.iloc[0]['Frase']
    mood = row.iloc[0]['Mood']
    return mood, frase

def get_frase_ti_penso():
    """Logica Lampada ON -> Mood 'Pensiero'"""
    return get_frase_da_emozioni("Pensiero", "💡 LAMPADA")

def get_frase_da_emozioni(mood_target, fonte_notifica):
    """
    Logica Robusta per pescare da Emozioni.
    Accetta 'AVAILABLE' anche se scritto male o con spazi.
    """
    sh = get_connection()
    ws = sh.worksheet(WS_EMOZIONI)
    df = pd.DataFrame(ws.get_all_records())
    
    # 1. Normalizza colonne (rimuove spazi vuoti e mette maiuscolo)
    df['Mood'] = df['Mood'].astype(str).str.strip()
    df['Marker'] = df['Marker'].astype(str).str.strip().str.upper()
    
    # 2. Filtra: Mood contiene la parola cercata E Marker è AVAILABLE
    # Usa 'contains' così se nel foglio c'è "Tristezza" e cerchi "Triste" funziona lo stesso
    candidati = df[
        (df['Mood'].str.contains(mood_target, case=False)) & 
        (df['Marker'] == 'AVAILABLE')
    ]
    
    if candidati.empty:
        # Fallback: Se non trova nulla, prova a cercarne una QUALSIASI 'AVAILABLE' 
        # per non lasciare lo schermo vuoto (opzionale, ma evita il messaggio di errore)
        fallback = df[df['Marker'] == 'AVAILABLE']
        if not fallback.empty:
            candidati = fallback
        else:
            return "Non ho nuove frasi nel barattolo, ma ricordati che ti amo ❤️"
    
    # 3. Pesca casuale
    idx_scelto = random.choice(candidati.index)
    frase = candidati.loc[idx_scelto, 'Frase']
    
    # 4. Segna come USED
    # Ricorda: gspread usa indice partendo da 1 + 1 header = riga 2
    riga_excel = idx_scelto + 2
    
    # Trova indice colonna Marker dinamicamente
    col_marker_idx = df.columns.get_loc('Marker') + 1
    ws.update_cell(riga_excel, col_marker_idx, 'USED')
    
    # Notifica Telegram (silenziosa se fallisce)
    try:
        token = st.secrets.get("TELEGRAM_TOKEN")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
        if token and chat_id:
            msg = f"{fonte_notifica}: Lei ha letto un biglietto '{mood_target}': {frase}"
            requests.get(f"https://api.telegram.org/bot{token}/sendMessage", params={"chat_id": chat_id, "text": msg})
    except: pass
    
    return frase

# --- APP STREAMLIT ---
st.set_page_config(page_title="Cubo Amore", page_icon="🧸", layout="centered")
set_cute_style() # Applica stile carino

# Gestione URL
params = st.query_params
mode = params.get("mode", "home")

# ==============================================================================
# PAGINA 2: BARATTOLO EMOZIONI (Link: ?mode=mood)
# ==============================================================================
if mode == "mood":
    st.markdown("<h1>Come ti senti, amore? ☁️</h1>", unsafe_allow_html=True)
    st.write("") # Spazio

    if 'msg_mood' not in st.session_state: st.session_state['msg_mood'] = ""

    # Griglia Pulsanti Cute
    c1, c2 = st.columns(2)
    with c1:
        if st.button("😢 Triste"):
            st.session_state['msg_mood'] = get_frase_da_emozioni("Triste", "🎫 EMOZIONI")
            st.rerun()
        if st.button("🥰 Felice"):
            st.session_state['msg_mood'] = get_frase_da_emozioni("Felice", "🎫 EMOZIONI")
            st.rerun()
    with c2:
        if st.button("😤 Stressata"):
            st.session_state['msg_mood'] = get_frase_da_emozioni("Stressata", "🎫 EMOZIONI")
            st.rerun()
        if st.button("🍂 Nostalgica"):
            st.session_state['msg_mood'] = get_frase_da_emozioni("Nostalgica", "🎫 EMOZIONI")
            st.rerun()

    # Mostra Frase Svelata
    if st.session_state['msg_mood']:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="cute-box">
            ✨ {st.session_state['msg_mood']} ✨
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Chiudi ✖️"):
            st.session_state['msg_mood'] = ""
            st.rerun()

# ==============================================================================
# PAGINA 1: HOME (Link Normale)
# ==============================================================================
else:
    # Check stato luce
    if 'luce_on' not in st.session_state: st.session_state['luce_on'] = False
    
    # Aggiorna stato luce (solo se non sta leggendo, per non interrompere)
    if 'reading' not in st.session_state:
        st.session_state['luce_on'] = (get_stato_luce() == 'ON')
        st.session_state['reading'] = False

    # ------------------------------------
    # SCENARIO A: LAMPADA ACCESA (SORPRESA)
    # ------------------------------------
    if st.session_state['luce_on']:
        st.markdown("<h1>Ti sto pensando... ❤️</h1>", unsafe_allow_html=True)
        
        if not st.session_state['reading']:
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                # Pulsante centrale pulsante
                if st.button("💌 Apri Messaggio"):
                    st.session_state['testo_lampada'] = get_frase_ti_penso()
                    st.session_state['reading'] = True
                    st.rerun()
        else:
            st.markdown(f"""
            <div class="cute-box" style="border-color: #ff4b4b; background-color: #fff0f5;">
                <h3>{st.session_state['testo_lampada']}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            st.info("🕒 La luce si spegnerà tra 5 minuti...")
            
            # Timer visivo carino
            bar = st.progress(0)
            for i in range(300):
                time.sleep(1)
                bar.progress((i + 1) / 300)
            
            set_luce_off()
            st.session_state['luce_on'] = False
            st.session_state['reading'] = False
            st.rerun()

    # ------------------------------------
    # SCENARIO B: BUONGIORNO (DEFAULT)
    # ------------------------------------
    else:
        st.markdown("<h1>Buongiorno Amore! ☀️</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align:center; color:#888;'>{datetime.now().strftime('%d %B %Y')}</p>", unsafe_allow_html=True)
        
        if 'frase_giorno' not in st.session_state: st.session_state['frase_giorno'] = ""

        # Mostra pulsante solo se frase non letta
        if not st.session_state['frase_giorno']:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📅 Leggi la frase di oggi"):
                mood, testo = get_frase_calendario_oggi()
                if testo:
                    st.session_state['frase_giorno'] = testo
                    # Notifica
                    try:
                        tk = st.secrets.get("TELEGRAM_TOKEN")
                        cid = st.secrets.get("TELEGRAM_CHAT_ID")
                        if tk and cid: requests.get(f"https://api.telegram.org/bot{tk}/sendMessage", params={"chat_id": cid, "text": f"☀️ CALENDARIO: Letto: {testo}"})
                    except: pass
                    st.rerun()
                else:
                    st.error("Nessuna frase trovata per oggi nel calendario.")
        else:
            st.markdown(f"""
            <div class="cute-box">
                ☕ {st.session_state['frase_giorno']}
            </div>
            """, unsafe_allow_html=True)
