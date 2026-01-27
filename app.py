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
WORKSHEET_NAME = 'Emozioni' # Dove ci sono le frasi (Mood | Frase | Tipo | Marker)
WORKSHEET_LOG = 'Log_Mood'  # Dove salviamo lo storico

# --- FUNZIONI DI CONNESSIONE ---
@st.cache_resource
def get_connection():
    if "GOOGLE_SHEETS_JSON" in st.secrets:
        try:
            creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
        except Exception as e:
            st.error(f"Errore Secrets: {e}")
            st.stop()
    else:
        try:
            creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPE)
        except FileNotFoundError:
            st.error("Nessuna credenziale trovata.")
            st.stop()
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

# --- NOTIFICHE TELEGRAM ---
def invia_notifica(testo):
    try:
        token = st.secrets.get("TELEGRAM_TOKEN")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
        if token and chat_id:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.get(url, params={"chat_id": chat_id, "text": testo})
    except: pass

# --- FUNZIONI LOGICHE ---

def get_stato_luce():
    try:
        sh = get_connection()
        return sh.worksheet("Config").acell('B1').value or 'OFF'
    except: return 'OFF'

def set_luce_off():
    try:
        sh = get_connection()
        sh.worksheet("Config").update_acell('B1', 'OFF')
    except: pass

def salva_log_buongiorno(mood):
    """Logga l'umore del Buongiorno e notifica"""
    try:
        sh = get_connection()
        try: ws = sh.worksheet(WORKSHEET_LOG)
        except: ws = sh.add_worksheet(title=WORKSHEET_LOG, rows=1000, cols=3)
        
        now = datetime.now()
        ws.append_row([now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), mood])
        invia_notifica(f"☀️ BUONGIORNO: Lei si sente {mood}")
        return True
    except: return False

def pesca_frase_lampada():
    """Logica per la Lampada (Token 1 - Luce ON): Prende la frase NEXT"""
    sh = get_connection()
    worksheet = sh.worksheet(WORKSHEET_NAME)
    df = pd.DataFrame(worksheet.get_all_records())
    df['Marker'] = df['Marker'].astype(str)

    # Cerca NEXT
    target = df[df['Marker'] == 'NEXT']
    
    # Se non c'è, prendi una AVAILABLE a caso
    if target.empty:
        avail = df[df['Marker'] == 'AVAILABLE']
        if avail.empty: return "Nessuna frase pronta ❤️"
        idx = avail.index[0] # Prendi la prima disponibile
        target = avail.iloc[[0]]
        # Aggiorna subito a NEXT per coerenza, poi la useremo
        worksheet.update_cell(idx + 2, df.columns.get_loc('Marker') + 1, 'NEXT')
    
    # Logica di consumo
    idx_real = target.index[0]
    frase = target.iloc[0]['Frase']
    col_mark = df.columns.get_loc('Marker') + 1
    
    # 1. Segna come USATA
    worksheet.update_cell(idx_real + 2, col_mark, 'USED')
    
    # 2. Prepara la prossima (NEXT) prendendo una AVAILABLE a caso
    avail = df[df['Marker'] == 'AVAILABLE']
    # Escludiamo quella appena usata se il dataframe non è aggiornato
    avail = avail[avail.index != idx_real] 
    
    if not avail.empty:
        idx_new = random.choice(avail.index)
        worksheet.update_cell(idx_new + 2, col_mark, 'NEXT')
        
    return frase

def pesca_frase_mood(mood_scelto):
    """Logica per il Barattolo (Token 2): Pesca una frase di quel MOOD specifico"""
    sh = get_connection()
    worksheet = sh.worksheet(WORKSHEET_NAME)
    df = pd.DataFrame(worksheet.get_all_records())
    df['Marker'] = df['Marker'].astype(str)
    
    # Filtra per Mood E per Marker AVAILABLE
    # Nota: Assumiamo che nel foglio la colonna Mood contenga parole chiave (Triste, Felice...)
    candidati = df[
        (df['Mood'].str.contains(mood_scelto, case=False, na=False)) & 
        (df['Marker'] == 'AVAILABLE')
    ]
    
    if candidati.empty:
        return "Non ho bigliettini nuovi per questo umore, ma ti amo lo stesso ❤️"
    
    # Ne pesca una a caso
    idx_scelto = random.choice(candidati.index)
    frase = candidati.loc[idx_scelto, 'Frase']
    
    # La marca come USED (così non esce due volte)
    col_mark = df.columns.get_loc('Marker') + 1
    worksheet.update_cell(idx_scelto + 2, col_mark, 'USED')
    
    invia_notifica(f"🎫 BARATTOLO: Lei ha aperto un biglietto '{mood_scelto}'")
    return frase

# --- INTERFACCIA ---
st.set_page_config(page_title="Cubo Amore", page_icon="❤️", layout="centered")

# CSS Pulito
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stButton>button {
        width: 100%; border-radius: 12px; height: 3.5em; font-weight: bold; border: none;
    }
</style>
""", unsafe_allow_html=True)

# Recupera parametri URL (per capire quale Token è stato usato)
params = st.query_params
mode = params.get("mode", "home") # Default è "home" (Token 1)

# ==============================================================================
# TOKEN 2: PAGINA MOOD (Barattolo Emozioni) -> Link NFC: ?mode=mood
# ==============================================================================
if mode == "mood":
    st.title("Come ti senti? 💭")
    st.write("Scegli un'emozione e ti darò una frase dedicata.")
    
    if 'frase_mood_svelata' not in st.session_state:
        st.session_state['frase_mood_svelata'] = ""

    # Griglia 2x2
    c1, c2 = st.columns(2)
    
    bg_color = "#f0f2f6"
    messaggio = st.session_state['frase_mood_svelata']

    with c1:
        if st.button("😢 Triste"):
            st.session_state['frase_mood_svelata'] = pesca_frase_mood("Triste")
            st.rerun()
        if st.button("🥰 Felice"):
            st.session_state['frase_mood_svelata'] = pesca_frase_mood("Felice")
            st.rerun()
            
    with c2:
        if st.button("😤 Stressata"):
            st.session_state['frase_mood_svelata'] = pesca_frase_mood("Stressata")
            st.rerun()
        if st.button("🍂 Nostalgica"):
            st.session_state['frase_mood_svelata'] = pesca_frase_mood("Nostalgica")
            st.rerun()

    if messaggio:
        st.markdown("---")
        st.markdown(f"""
        <div style='background-color: #e3f2fd; padding: 20px; border-radius: 10px; border: 2px solid #2196f3; text-align: center;'>
            <h3 style='color: #0d47a1;'>{messaggio}</h3>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Chiudi"):
            st.session_state['frase_mood_svelata'] = ""
            st.rerun()


# ==============================================================================
# TOKEN 1: PAGINA PRINCIPALE (Lampada/Buongiorno) -> Link NFC: normale
# ==============================================================================
else:
    # Controlla stato luce
    if 'luce_accesa' not in st.session_state: st.session_state['luce_accesa'] = False
    if 'timer_attivo' not in st.session_state: 
        st.session_state['luce_accesa'] = (get_stato_luce() == 'ON')

    # SCENARIO A: LUCE ACCESA (SORPRESA)
    if st.session_state['luce_accesa']:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #ff4b4b;'>Ti sto pensando ❤️</h1>", unsafe_allow_html=True)
        
        if 'frase_lampada' not in st.session_state:
            st.session_state['frase_lampada'] = ""
            
        if not st.session_state['frase_lampada']:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💌 Leggi messaggio", type="primary"):
                    with st.spinner("..."):
                        frase = pesca_frase_lampada()
                        st.session_state['frase_lampada'] = frase
                        invia_notifica(f"💡 LAMPADA: Lei ha letto: {frase}")
                    st.rerun()
        else:
            st.markdown(f"""
            <div style='background-color: #fff0f5; padding: 30px; border-radius: 10px; border: 2px solid #ff4b4b; text-align: center;'>
                <h2>✨ {st.session_state['frase_lampada']} ✨</h2>
            </div>
            """, unsafe_allow_html=True)
            
            st.info("🕒 Spegnimento automatico in 5 minuti...")
            bar = st.progress(0)
            for i in range(300):
                time.sleep(1)
                bar.progress((i + 1) / 300)
            
            set_luce_off()
            st.session_state['luce_accesa'] = False
            st.session_state['frase_lampada'] = ""
            st.rerun()

    # SCENARIO B: LUCE SPENTA (BUONGIORNO)
    else:
        # Nascondiamo la pagina Ricordi come richiesto, mostriamo solo Buongiorno
        # Se ti serve Admin aggiungilo in sidebar, ma per lei deve essere pulito
        if st.sidebar.checkbox("Admin Mode"):
            st.title("Admin")
            st.write("Aggiungi frasi da qui o da Telegram")
        else:
            st.markdown("<br>", unsafe_allow_html=True)
            st.title("Buongiorno Amore! ☀️")
            st.write("Come ti senti adesso? Clicca per farmelo sapere.")
            st.markdown("---")
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🥰 Felice"):
                    salva_log_buongiorno("Felice")
                    st.success("Che bello vederti felice!")
                if st.button("😢 Triste"):
                    salva_log_buongiorno("Triste")
                    st.warning("Mi dispiace amore, ti chiamo presto.")
            with c2:
                if st.button("😴 Stanca"):
                    salva_log_buongiorno("Stanca")
                    st.info("Cerca di riposare un po'.")
                if st.button("❤️ Innamorata"):
                    salva_log_buongiorno("Innamorata")
                    st.balloons()
                    st.success("Ti amo tantissimo anche io!")
