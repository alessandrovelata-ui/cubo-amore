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

# --- CSS "CUTE" MA AD ALTO CONTRASTO ---
def set_cute_style():
    st.markdown("""
    <style>
        /* Sfondo: Manteniamo il rosato ma molto pallido per far risaltare il testo */
        .stApp {
            background-color: #fff5f8;
        }
        
        /* Nascondi menu standard */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* TITOLI: Rosa Scuro/Lampone per alto contrasto */
        h1 {
            color: #C2185B; /* Rosa scuro forte */
            font-family: 'Comic Sans MS', 'Chalkboard SE', sans-serif;
            text-align: center;
            font-weight: 800;
        }
        
        h2, h3 {
            color: #880E4F; /* Quasi bordeaux */
            text-align: center;
        }
        
        p, div, span {
            color: #212121; /* Grigio molto scuro (quasi nero) per leggibilità */
            font-size: 18px;
        }
        
        /* PULSANTI: Bordo scuro e testo scuro */
        .stButton>button {
            width: 100%;
            height: 65px;
            border-radius: 20px;
            border: 2px solid #D81B60; /* Bordo rosa scuro */
            background-color: #ffffff;
            color: #880E4F; /* Testo del bottone scuro */
            font-size: 20px !important;
            font-weight: bold !important;
            box-shadow: 0px 4px 6px rgba(0,0,0,0.15);
            transition: all 0.2s ease;
        }
        
        .stButton>button:hover {
            transform: scale(1.02);
            background-color: #ffeef2;
            border-color: #C2185B;
        }
        
        /* BOX MESSAGGI */
        .cute-box {
            background-color: #ffffff;
            padding: 30px;
            border-radius: 20px;
            border: 3px solid #F48FB1; /* Bordo rosa medio */
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            font-size: 24px;
            font-weight: 600;
            color: #333333; /* Testo messaggio scuro */
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

# --- LOGICA RECUPERO FRASI (CORRETTA) ---

def get_frase_calendario_oggi():
    sh = get_connection()
    ws = sh.worksheet(WS_CALENDARIO)
    df = pd.DataFrame(ws.get_all_records())
    
    if 'Data' not in df.columns: return None, "Errore DB: Colonna Data mancante"
    
    oggi = datetime.now().strftime("%Y-%m-%d")
    # Pulisce la colonna data da spazi
    row = df[df['Data'].astype(str).str.strip() == oggi]
    
    if row.empty:
        return None, "Nessuna frase programmata per oggi! 📅"
    
    frase = row.iloc[0]['Frase']
    mood = row.iloc[0]['Mood']
    return mood, frase

def get_frase_ti_penso():
    return get_frase_da_emozioni("Pensiero", "💡 LAMPADA")

def get_frase_da_emozioni(mood_target, fonte_notifica):
    """
    Logica corretta per colonne: Mood (A), Frase (B), Tipo (C), Marker (D)
    """
    sh = get_connection()
    ws = sh.worksheet(WS_EMOZIONI)
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    
    # 1. PULIZIA TOTALE DATI (Fondamentale)
    # Rimuove spazi vuoti prima e dopo e mette tutto minuscolo per il confronto
    df['Mood_Clean'] = df['Mood'].astype(str).str.strip().str.lower()
    df['Marker_Clean'] = df['Marker'].astype(str).str.strip().str.lower()
    
    target_clean = mood_target.strip().lower()
    
    # 2. FILTRO (Cerca 'mood' dentro la colonna Mood E 'available' nel Marker)
    # Usa 'contains' così se c'è "Tristezza" e cerchi "Triste" la trova uguale
    candidati = df[
        (df['Mood_Clean'].str.contains(target_clean)) & 
        (df['Marker_Clean'] == 'available')
    ]
    
    if candidati.empty:
        # Fallback: se non trova quel mood specifico, cerca QUALSIASI available
        # pur di non dare errore
        candidati = df[df['Marker_Clean'] == 'available']
        if candidati.empty:
            return "Non ci sono nuove frasi nel barattolo, ma ti amo ❤️"
    
    # 3. PESCA E AGGIORNA
    idx_scelto = random.choice(candidati.index)
    frase = df.loc[idx_scelto, 'Frase'] # Prende la frase originale (colonna B)
    
    # Calcolo riga Excel (Indice pandas + 2 perché header è riga 1)
    riga_excel = idx_scelto + 2
    
    # Aggiorna colonna Marker (Colonna D = 4)
    try:
        ws.update_cell(riga_excel, 4, 'USED') # Forza aggiornamento colonna 4
    except Exception as e:
        print(f"Errore update: {e}")
        
    # Notifica
    try:
        tk = st.secrets.get("TELEGRAM_TOKEN")
        cid = st.secrets.get("TELEGRAM_CHAT_ID")
        if tk and cid:
            msg = f"{fonte_notifica}: Letto '{mood_target}': {frase}"
            requests.get(f"https://api.telegram.org/bot{tk}/sendMessage", params={"chat_id": cid, "text": msg})
    except: pass
    
    return frase

# --- APP STREAMLIT ---
st.set_page_config(page_title="Cubo Amore", page_icon="🧸", layout="centered")
set_cute_style()

# Gestione URL
params = st.query_params
mode = params.get("mode", "home")

# ==============================================================================
# PAGINA EMOZIONI (Link: ?mode=mood)
# ==============================================================================
if mode == "mood":
    st.markdown("<h1>Come ti senti, amore? ☁️</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;'>Scegli un'emozione:</p>", unsafe_allow_html=True)

    if 'msg_mood' not in st.session_state: st.session_state['msg_mood'] = ""

    # Pulsanti Emozioni
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

    # Box Messaggio
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
# PAGINA HOME (Link Normale)
# ==============================================================================
else:
    # Check stato luce
    if 'luce_on' not in st.session_state: st.session_state['luce_on'] = False
    
    # Aggiorna stato luce (solo se non sta leggendo)
    if 'reading' not in st.session_state:
        st.session_state['luce_on'] = (get_stato_luce() == 'ON')
        st.session_state['reading'] = False

    # SCENARIO A: LAMPADA ACCESA
    if st.session_state['luce_on']:
        st.markdown("<h1>Ti sto pensando... ❤️</h1>", unsafe_allow_html=True)
        
        if not st.session_state['reading']:
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("💌 Apri Messaggio"):
                    st.session_state['testo_lampada'] = get_frase_ti_penso()
                    st.session_state['reading'] = True
                    st.rerun()
        else:
            st.markdown(f"""
            <div class="cute-box" style="border-color: #C2185B; background-color: #fff;">
                <h3>{st.session_state['testo_lampada']}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            st.info("🕒 La luce si spegnerà tra 5 minuti...")
            
            bar = st.progress(0)
            for i in range(300):
                time.sleep(1)
                bar.progress((i + 1) / 300)
            
            set_luce_off()
            st.session_state['luce_on'] = False
            st.session_state['reading'] = False
            st.rerun()

    # SCENARIO B: BUONGIORNO
    else:
        st.markdown("<h1>Buongiorno Amore! ☀️</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align:center; color:#555;'>{datetime.now().strftime('%d %B %Y')}</p>", unsafe_allow_html=True)
        
        if 'frase_giorno' not in st.session_state: st.session_state['frase_giorno'] = ""

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
                    st.warning("Nessuna frase per oggi.")
        else:
            st.markdown(f"""
            <div class="cute-box">
                ☕ {st.session_state['frase_giorno']}
            </div>
            """, unsafe_allow_html=True)
