import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
import random

# --- CONFIGURAZIONE ---
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive"]
CREDS_FILE = 'credentials.json' 
SHEET_NAME = 'CuboAmoreDB'
WORKSHEET_NAME = 'Emozioni' # Il nome del foglio con le colonne Mood, Frase, Tipo, Marker

# --- FUNZIONI DI CONNESSIONE ---
@st.cache_resource
def get_connection():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

# --- FUNZIONI LOGICHE ---

def get_stato_luce():
    """Legge se la luce è ON o OFF dal foglio Config"""
    try:
        sh = get_connection()
        worksheet = sh.worksheet("Config")
        val = worksheet.acell('B1').value
        return val if val else 'OFF'
    except Exception as e:
        return 'OFF'

def set_luce_off():
    """Spegne la luce sul foglio Config"""
    try:
        sh = get_connection()
        worksheet = sh.worksheet("Config")
        worksheet.update_acell('B1', 'OFF')
    except Exception as e:
        st.error(f"Errore spegnimento: {e}")

def aggiungi_frase(mood, frase, tipo):
    """Aggiunge una nuova riga: Mood, Frase, Tipo, Marker"""
    sh = get_connection()
    worksheet = sh.worksheet(WORKSHEET_NAME)
    # Marker di default è AVAILABLE
    worksheet.append_row([mood, frase, tipo, "AVAILABLE"])

def gestisci_frasi_e_aggiorna_db():
    """
    Logica marker:
    1. NEXT -> USED
    2. AVAILABLE (random) -> NEXT
    """
    sh = get_connection()
    worksheet = sh.worksheet(WORKSHEET_NAME)
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    # Convertiamo Marker in stringa per sicurezza
    df['Marker'] = df['Marker'].astype(str)

    # 1. Cerca la frase NEXT
    frase_next_row = df[df['Marker'] == 'NEXT']
    
    # Fallback: se non c'è NEXT, prendi una AVAILABLE
    if frase_next_row.empty:
        frase_next_row = df[df['Marker'] == 'AVAILABLE']
        if frase_next_row.empty:
            return "Nessuna frase disponibile!"
        
        # Imposta subito questa come NEXT nel DB
        idx_emerg = frase_next_row.index[0]
        col_marker = df.columns.get_loc('Marker') + 1
        worksheet.update_cell(idx_emerg + 2, col_marker, 'NEXT')
        
        # Ricarica
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        frase_next_row = df[df['Marker'] == 'NEXT']

    # Recupera il testo
    indice_next = frase_next_row.index[0]
    testo_frase = frase_next_row.iloc[0]['Frase'] # Colonna 'Frase'
    
    # Calcola posizioni
    riga_sheet = indice_next + 2 
    col_marker = df.columns.get_loc('Marker') + 1

    # 2. Aggiorna: NEXT -> USED
    worksheet.update_cell(riga_sheet, col_marker, 'USED')
    
    # 3. Prepara la prossima: AVAILABLE -> NEXT
    frasi_available = df[df['Marker'] == 'AVAILABLE']
    
    if not frasi_available.empty:
        idx_nuova = random.choice(frasi_available.index)
        worksheet.update_cell(idx_nuova + 2, col_marker, 'NEXT')
    
    return testo_frase

# --- INTERFACCIA UTENTE ---

st.set_page_config(page_title="Cubo Amore", page_icon="❤️", layout="centered")

# CSS per pulizia visiva
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# Inizializzazione Session State
if 'luce_accesa' not in st.session_state:
    st.session_state['luce_accesa'] = False

# Controllo iniziale (solo se timer non attivo)
if 'timer_attivo' not in st.session_state:
    stato_reale = get_stato_luce()
    st.session_state['luce_accesa'] = (stato_reale == 'ON')

# ==========================================
# SCENARIO A: LUCE ACCESA (Ti sto pensando)
# ==========================================
if st.session_state['luce_accesa']:
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #E91E63; font-size: 50px;'>Ti sto pensando ❤️</h1>", unsafe_allow_html=True)
    st.markdown("---")

    if 'frase_svelata' not in st.session_state:
        st.session_state['frase_svelata'] = False
        st.session_state['testo_da_mostrare'] = ""

    # PULSANTE
    if not st.session_state['frase_svelata']:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("C'è una frase per te 💌", use_container_width=True, type="primary"):
                with st.spinner("Apro il bigliettino..."):
                    frase = gestisci_frasi_e_aggiorna_db()
                    st.session_state['testo_da_mostrare'] = frase
                    st.session_state['frase_svelata'] = True
                st.rerun()

    # VISUALIZZAZIONE + TIMER
    else:
        st.markdown(f"""
        <div style='background-color: #ffeef0; padding: 30px; border-radius: 10px; border: 2px solid #E91E63; text-align: center; margin-bottom: 20px;'>
            <h2 style='color: #333; font-family: sans-serif;'>✨ {st.session_state['testo_da_mostrare']} ✨</h2>
        </div>
        """, unsafe_allow_html=True)

        st.info("🕒 Timer attivo: la lampada si spegnerà tra 5 minuti.")
        
        my_bar = st.progress(0)
        
        # Loop 5 minuti (300 sec)
        tempo_totale = 300 
        for i in range(tempo_totale):
            time.sleep(1)
            my_bar.progress((i + 1) / tempo_totale)

        set_luce_off()
        st.session_state['luce_accesa'] = False
        st.session_state['frase_svelata'] = False
        st.rerun()

# ==========================================
# SCENARIO B: LUCE SPENTA (Menu)
# ==========================================
else:
    menu = st.sidebar.radio("Navigazione", ["Emozioni", "Admin"])
    
    if st.sidebar.button("🔄 Controlla Luce"):
        st.rerun()

    # PAGINA EMOZIONI
    if menu == "Emozioni":
        st.title("Le tue emozioni 💭")
        
        try:
            sh = get_connection()
            worksheet = sh.worksheet(WORKSHEET_NAME)
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)
            
            # Filtra e mostra
            for index, row in df.iterrows():
                try:
                    marker = str(row['Marker'])
                    frase = row['Frase']
                    mood = row['Mood'] # Opzionale: mostra anche il mood se vuoi
                    
                    if marker == 'USED':
                        st.success(f"✅ {frase}")
                    elif marker == 'NEXT':
                        st.info("🔒 (Sorpresa in arrivo...)")
                    elif marker == 'AVAILABLE':
                        st.write("⬜ (In attesa)")
                except KeyError:
                    st.error("Errore nelle colonne del file Excel.")
                    
        except Exception as e:
            st.error(f"Errore connessione: {e}")

    # PAGINA ADMIN
    elif menu == "Admin":
        st.title("Aggiungi Frase 🛠️")
        
        with st.form("nuova_frase"):
            colA, colB = st.columns(2)
            with colA:
                mood_input = st.selectbox("Mood", ["Amore", "Malinconia", "Gioia", "Passione"])
            with colB:
                tipo_input = st.selectbox("Tipo", ["Canzone", "Poesia", "Pensiero", "Citazione"])
            
            txt_frase = st.text_area("Frase:")
            
            if st.form_submit_button("Salva nel Cubo"):
                if txt_frase:
                    aggiungi_frase(mood_input, txt_frase, tipo_input)
                    st.success("Salvata!")
                    time.sleep(1)
                    st.rerun()
