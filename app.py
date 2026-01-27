import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
import random

# --- CONFIGURAZIONE ---
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive"]
CREDS_FILE = 'credentials.json' # Il tuo file json delle chiavi
SHEET_NAME = 'CuboAmoreDB' # Il nome del tuo file Google Sheet

# --- FUNZIONI DI CONNESSIONE ---
def get_connection():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPE)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME)

# --- FUNZIONI LOGICHE ---

def get_stato_luce():
    """Legge se la luce è ON o OFF dal foglio Config"""
    sh = get_connection()
    # Ipotizziamo che lo stato della luce sia nel foglio 'Config', cella B1
    worksheet = sh.worksheet("Config") 
    return worksheet.acell('B1').value # Ritorna 'ON' o 'OFF'

def set_luce_off():
    """Spegne la luce sul foglio"""
    sh = get_connection()
    worksheet = sh.worksheet("Config")
    worksheet.update('B1', 'OFF') # Aggiorna la cella B1 a OFF

def gestisci_frasi_e_aggiorna_db():
    """
    1. Trova la frase 'NEXT'.
    2. La marca come 'USED'.
    3. Trova una nuova frase 'AVAILABLE' e la marca come 'NEXT'.
    4. Restituisce il testo della frase che era 'NEXT'.
    """
    sh = get_connection()
    worksheet = sh.worksheet("Frasi") # Assumi che il foglio si chiami 'Frasi'
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    # 1. Trova la frase 'NEXT' (quella da mostrare oggi)
    frase_next_row = df[df['Stato'] == 'NEXT']
    
    if frase_next_row.empty:
        return "Nessuna frase programmata per oggi!"
    
    indice_next = frase_next_row.index[0] # Indice nel DataFrame
    testo_frase = frase_next_row.iloc[0]['Frase']
    
    # Calcolo la riga reale nel foglio (gspread parte da 1 + 1 header = riga 2)
    riga_sheet_next = indice_next + 2 

    # 2. Aggiorna la frase attuale da NEXT a USED
    worksheet.update_cell(riga_sheet_next, df.columns.get_loc('Stato') + 1, 'USED')
    
    # 3. Prepara la frase per DOMANI (o la prossima volta)
    # Cerca tutte le frasi ancora AVAILABLE
    frasi_available = df[df['Stato'] == 'AVAILABLE']
    
    if not frasi_available.empty:
        # Ne sceglie una a caso (o la prima della lista, come preferisci)
        indice_nuova = random.choice(frasi_available.index)
        riga_sheet_nuova = indice_nuova + 2
        # Marca la nuova frase come NEXT
        worksheet.update_cell(riga_sheet_nuova, df.columns.get_loc('Stato') + 1, 'NEXT')
    else:
        st.warning("Attenzione: Frasi finite! Aggiungine altre nel database.")

    return testo_frase

# --- INTERFACCIA UTENTE ---

st.set_page_config(page_title="Cubo Amore", page_icon="❤️")

# 1. CONTROLLO STATO LUCE
# Se non è in session state, lo leggiamo dal DB. 
# Usiamo session state per evitare di rileggere il DB ad ogni micro-interazione, 
# ma forziamo la rilettura se necessario.
if 'luce_accesa' not in st.session_state:
    stato_db = get_stato_luce()
    st.session_state['luce_accesa'] = (stato_db == 'ON')

# Pulsante di debug per ricaricare lo stato (utile se accendi da Telegram mentre hai la pagina aperta)
if st.sidebar.button("🔄 Aggiorna Stato"):
    stato_db = get_stato_luce()
    st.session_state['luce_accesa'] = (stato_db == 'ON')
    st.rerun()

# --- SCENARIO A: LUCE ACCESA (Ti sto pensando) ---
if st.session_state['luce_accesa']:
    
    st.markdown("<h1 style='text-align: center; color: #ff4b4b;'>Ti sto pensando ❤️</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Variabile per tracciare se il pulsante è stato premuto
    if 'frase_mostrata' not in st.session_state:
        st.session_state['frase_mostrata'] = False
        st.session_state['testo_da_leggere'] = ""

    # Pulsante principale
    if not st.session_state['frase_mostrata']:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            if st.button("C'è una frase per te 💌", use_container_width=True):
                # Qui avviene la magia: aggiornamento DB e recupero frase
                with st.spinner("Sto aprendo il bigliettino..."):
                    frase = gestisci_frasi_e_aggiorna_db()
                    st.session_state['testo_da_leggere'] = frase
                    st.session_state['frase_mostrata'] = True
                st.rerun()

    # Mostra la frase e gestisci il timer
    else:
        st.markdown(f"<h2 style='text-align: center; padding: 20px;'>✨ {st.session_state['testo_da_leggere']} ✨</h2>", unsafe_allow_html=True)
        
        st.info("🕒 La lampada si spegnerà automaticamente tra 5 minuti.")
        
        # Barra di progresso o spinner per il timer
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Timer di 5 minuti (300 secondi)
        total_time = 300 
        for i in range(total_time):
            # Aggiorna ogni secondo
            time.sleep(1)
            progresso = (i + 1) / total_time
            progress_bar.progress(progresso)
            remaining = total_time - i - 1
            status_text.text(f"Spegnimento tra {remaining // 60}m {remaining % 60}s...")
        
        # Fine del timer
        status_text.text("Spegnimento in corso...")
        set_luce_off() # Aggiorna Google Sheet a OFF
        st.session_state['luce_accesa'] = False # Aggiorna stato locale
        st.session_state['frase_mostrata'] = False # Resetta per la prossima volta
        st.rerun()

# --- SCENARIO B: LUCE SPENTA (Pagina Emozioni / Admin) ---
else:
    # Sidebar per navigazione
    page = st.sidebar.radio("Menu", ["Emozioni", "Admin"])

    if page == "Emozioni":
        st.title("Le tue emozioni 💭")
        
        # Carica dati per sola lettura
        try:
            sh = get_connection()
            worksheet = sh.worksheet("Frasi")
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)

            # Mostra le frasi con i marker
            for index, row in df.iterrows():
                frase = row['Frase']
                stato = row['Stato']
                
                if stato == 'USED':
                    st.success(f"✅ {frase}") # Frase già letta
                elif stato == 'NEXT':
                    st.info(f"🔒 (Prossima frase in attesa)") # Non mostrare il testo della prossima!
                else:
                    st.write(f"⬜ {frase}") # Frase disponibile ma futura
                    
        except Exception as e:
            st.error(f"Errore caricamento dati: {e}")

    elif page == "Admin":
        st.title("Pannello di Controllo 🛠️")
        st.write("Qui puoi aggiungere nuove frasi al foglio Google.")
        # ... qui puoi mettere il tuo vecchio codice per aggiungere frasi ...
        st.write(f"Stato Luce attuale: {'ACCESA' if st.session_state['luce_accesa'] else 'SPENTA'}")
