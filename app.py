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

# Nomi dei fogli nel tuo Google Sheet
WS_CALENDARIO = 'Calendario' # Colonne: Data | Mood | Frase | Tipo | Marker
WS_EMOZIONI = 'Emozioni'     # Colonne: Mood | Frase | Tipo | Marker
WS_CONFIG = 'Config'         # Cella B1 per ON/OFF

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

# --- FUNZIONI NOTIFICHE ---
def invia_notifica(testo):
    try:
        token = st.secrets.get("TELEGRAM_TOKEN")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
        if token and chat_id:
            requests.get(f"https://api.telegram.org/bot{token}/sendMessage", params={"chat_id": chat_id, "text": testo})
    except: pass

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

# --- RECUPERO FRASI (LOGICHE DISTINTE) ---

def get_frase_calendario_oggi():
    """
    Logica BUONGIORNO (Luce Spenta):
    Cerca nel foglio 'Calendario' la frase che ha la data di OGGI.
    """
    sh = get_connection()
    ws = sh.worksheet(WS_CALENDARIO)
    df = pd.DataFrame(ws.get_all_records())
    
    # Assicuriamoci che la colonna Data sia stringa o data gestibile
    oggi = datetime.now().strftime("%Y-%m-%d")
    
    # Cerca la riga con la data di oggi
    # Nota: il formato nel foglio deve essere YYYY-MM-DD
    row = df[df['Data'].astype(str) == oggi]
    
    if row.empty:
        return None, "Nessuna frase programmata per oggi sul calendario!"
    
    frase = row.iloc[0]['Frase']
    mood = row.iloc[0]['Mood']
    return mood, frase

def get_frase_ti_penso():
    """
    Logica LAMPADA ON (Ti penso):
    Cerca nel foglio 'Emozioni' una frase con Mood = 'Pensiero'
    che sia 'AVAILABLE'. La marca come 'USED'.
    """
    return get_frase_da_emozioni("Pensiero", "💡 LAMPADA")

def get_frase_da_emozioni(mood_target, fonte_notifica):
    """
    Logica GENERICA per pescare da 'Emozioni' usando AVAILABLE -> USED
    Usata sia per la Lampada (Mood=Pensiero) sia per la pagina Emozioni (Mood=Triste, ecc)
    """
    sh = get_connection()
    ws = sh.worksheet(WS_EMOZIONI)
    df = pd.DataFrame(ws.get_all_records())
    
    # Filtra per Mood e Disponibilità
    # Convertiamo in stringa per sicurezza
    df['Marker'] = df['Marker'].astype(str)
    
    candidati = df[
        (df['Mood'].astype(str).str.contains(mood_target, case=False)) & 
        (df['Marker'] == 'AVAILABLE')
    ]
    
    if candidati.empty:
        return "Non ho nuove frasi per questo momento, ma ti amo ❤️"
    
    # Pesca a caso
    idx_scelto = random.choice(candidati.index)
    frase = candidati.loc[idx_scelto, 'Frase']
    
    # Aggiorna a USED
    riga_excel = idx_scelto + 2
    col_marker = df.columns.get_loc('Marker') + 1
    ws.update_cell(riga_excel, col_marker, 'USED')
    
    invia_notifica(f"{fonte_notifica}: Lei ha letto un biglietto '{mood_target}': {frase}")
    return frase

# --- INTERFACCIA ---
st.set_page_config(page_title="Cubo Amore", page_icon="❤️", layout="centered")
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} .stButton>button {width: 100%; border-radius: 12px; height: 3.5em; border: none;}</style>""", unsafe_allow_html=True)

# Gestione Parametri URL
params = st.query_params
mode = params.get("mode", "home") 

# ==============================================================================
# PAGINA 2: EMOZIONI (Token 2 -> ?mode=mood)
# ==============================================================================
if mode == "mood":
    st.title("Come ti senti? 💭")
    st.write("Scegli un'emozione per aprire un bigliettino.")
    
    if 'msg_mood' not in st.session_state: st.session_state['msg_mood'] = ""

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

    if st.session_state['msg_mood']:
        st.success(f"✨ {st.session_state['msg_mood']}")
        if st.button("Chiudi"):
            st.session_state['msg_mood'] = ""
            st.rerun()

# ==============================================================================
# PAGINA 1: HOME (Token 1 -> Link normale)
# ==============================================================================
else:
    # Controlla se la luce è accesa
    if 'luce_on' not in st.session_state: st.session_state['luce_on'] = False
    
    # Verifica stato solo se non siamo già in modalità lettura
    if 'reading' not in st.session_state:
        st.session_state['luce_on'] = (get_stato_luce() == 'ON')
        st.session_state['reading'] = False

    # ------------------------------------------------
    # CASO A: LAMPADA ACCESA (Priority Override)
    # ------------------------------------------------
    if st.session_state['luce_on']:
        st.markdown("<br><h1 style='text-align: center; color: #ff4b4b;'>Ti sto pensando ❤️</h1>", unsafe_allow_html=True)
        st.markdown("---")
        
        if not st.session_state['reading']:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("💌 C'è un messaggio per te", type="primary"):
                    st.session_state['testo_lampada'] = get_frase_ti_penso() # Prende frase "Pensiero"
                    st.session_state['reading'] = True
                    st.rerun()
        else:
            # Mostra frase + Timer
            st.markdown(f"<div style='background:#fff0f5;padding:20px;border-radius:10px;text-align:center;'><h3>{st.session_state['testo_lampada']}</h3></div>", unsafe_allow_html=True)
            st.info("Spegnimento in 5 minuti...")
            
            bar = st.progress(0)
            for i in range(300):
                time.sleep(1)
                bar.progress((i + 1) / 300)
            
            set_luce_off()
            st.session_state['luce_on'] = False
            st.session_state['reading'] = False
            st.rerun()

    # ------------------------------------------------
    # CASO B: BUONGIORNO (Luce Spenta - Default)
    # ------------------------------------------------
    else:
        st.title("Buongiorno Amore! ☀️")
        st.write(f"Oggi è il {datetime.now().strftime('%d/%m/%Y')}")
        
        if 'frase_giorno' not in st.session_state:
            st.session_state['frase_giorno'] = ""

        # Logica Calendario
        if not st.session_state['frase_giorno']:
             if st.button("📅 Leggi la frase di oggi"):
                mood_oggi, testo_oggi = get_frase_calendario_oggi()
                st.session_state['frase_giorno'] = testo_oggi
                invia_notifica(f"☀️ CALENDARIO: Lei ha letto il buongiorno: {testo_oggi}")
                st.rerun()
        else:
            st.success(f"✨ {st.session_state['frase_giorno']}")
            
        # Pulsante refresh nascosto per vedere se la luce si accende
        if st.button("🔄"): st.rerun()
