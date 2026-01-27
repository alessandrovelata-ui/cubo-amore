import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import requests
import json
import agente_ia
import random

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Cubo Amore", page_icon="❤️", layout="centered")

# --- CSS STYLES ---
hide_st_style = """
            <style>
            .stApp { background-color: #FFF5F7; }
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            [data-testid="stToolbar"] {visibility: hidden;}
            .stDeployButton {display:none;}
            
            h1 { color: #D64161 !important; text-align: center; font-family: 'Helvetica Neue', sans-serif; font-weight: 700; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); margin-bottom: 20px; }
            h2 { font-style: italic !important; font-family: 'Georgia', serif; color: #D64161 !important; margin-bottom: 0px;}
            h3, p, div { color: #4A4A4A !important; text-align: center; }
            
            .counter-box { background-color: #fff; border: 2px solid #D64161; border-radius: 15px; padding: 15px; margin-top: 10px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
            .counter-big { font-size: 1.2em; font-weight: bold; color: #D64161 !important; }
            
            .stButton>button { width: 100%; height: 3.5em; font-size: 18px !important; font-weight: 600; background-color: #ffffff; color: #D64161; border: 2px solid #FFD1DC; border-radius: 25px; box-shadow: 0 4px 6px rgba(214, 65, 97, 0.1); transition: all 0.3s ease; }
            .stButton>button:hover { border-color: #D64161; background-color: #FFF0F5; transform: translateY(-2px); }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- DB CONNECTION ---
def connect_db():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    json_creds = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
    creds = Credentials.from_service_account_info(json_creds, scopes=scope)
    client = gspread.authorize(creds)
    return client.open("CuboAmoreDB") 

def notifica_telegram(testo):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.get(url, params={"chat_id": chat_id, "text": testo})
    except: pass

def salva_log(mood):
    try:
        sh = connect_db()
        ws = sh.worksheet("Log_Mood")
        ws.append_row([datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M"), mood])
    except: pass

# --- GESTIONE LETTURA MESSAGGI ---
def segna_messaggio_letto(sh, riga_index, foglio="Calendario"):
    try:
        ws = sh.worksheet(foglio)
        # Se è Calendario, Mood è colonna 2. Se Emozioni (manuale lampada), potrebbe variare.
        col = 2 if foglio == "Calendario" else 1 
        ws.update_cell(riga_index, col, "Manuale_Letto")
    except: pass

# --- CONTROLLO TELEGRAM & LAMPADA ---
def check_telegram_override(df_cal):
    try:
        oggi_str = datetime.now().strftime("%Y-%m-%d")
        # Se c'è già un messaggio attivo nel DB, non facciamo nulla
        if not df_cal.empty and 'Data' in df_cal.columns:
             check = df_cal[(df_cal['Mood'].str.contains('Manuale')) & (df_cal['Data'].astype(str) == oggi_str)]
             if not check.empty: return 
        
        token = st.secrets["TELEGRAM_TOKEN"]
        admin_id = str(st.secrets["TELEGRAM_CHAT_ID"])
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        resp = requests.get(url).json()
        
        if "result" in resp:
            messaggi = reversed(resp["result"])
            for update in messaggi:
                if "message" in update:
                    msg = update["message"]
                    sender_id = str(msg["from"]["id"])
                    timestamp = msg["date"]
                    testo = msg.get("text", "")
                    data_msg = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
                    
                    if sender_id == admin_id and data_msg == oggi_str and not testo.startswith("/"):
                        sh = connect_db()
                        
                        # LOGICA LAMPADA: Se il messaggio è il comando luce
                        if testo == "CMD_LIGHT_ON":
                             # Salva nel Calendario con Mood "Lampada"
                             # La frase non sarà CMD_LIGHT_ON, ma verrà pescata dopo.
                             ws = sh.worksheet("Calendario")
                             ws.append_row([oggi_str, "Lampada_Attiva", "Trigger", "TelegramOverride", ""])
                        else:
                             # Messaggio manuale normale
                             ws = sh.worksheet("Calendario")
                             ws.append_row([oggi_str, "Manuale", testo, "TelegramOverride", ""])
                        
                        st.rerun() 
                        return
    except: pass

# --- RECUPERO CONTENUTI ---
def get_contenuto(mood_target):
    try:
        sh = connect_db()
        oggi = datetime.now().strftime("%Y-%m-%d")

        if mood_target == "Buongiorno":
            ws_cal = sh.worksheet("Calendario")
            df = pd.DataFrame(ws_cal.get_all_records())
            
            # 1. Controlla Telegram (e Lampada)
            check_telegram_override(df)
            df = pd.DataFrame(ws_cal.get_all_records()) # Ricarica
            
            # 2. Cerca Messaggio LAMPADA ATTIVA
            lampada = df.index[(df['Mood'] == 'Lampada_Attiva') & (df['Data'] == oggi)].tolist()
            if lampada:
                # La lampada è accesa! Pesca una frase dolce dal foglio Emozioni
                idx = lampada[-1]
                segna_messaggio_letto(sh, idx + 2, "Calendario") # Consuma l'evento
                
                # Pesca frase "Pensiero"
                ws_emo = sh.worksheet("Emozioni")
                df_emo = pd.DataFrame(ws_emo.get_all_records())
                pensieri = df_emo[df_emo['Mood'] == 'Pensiero']
                
                if not pensieri.empty:
                    frase_dolce = pensieri.sample().iloc[0]['Frase']
                    return f"💡 {frase_dolce}"
                return "💡 Ti sto pensando..."

            # 3. Cerca Messaggio MANUALE (Testo scritto da te)
            manuale = df.index[(df['Mood'] == 'Manuale') & (df['Data'] == oggi)].tolist()
            if manuale:
                idx = manuale[-1]
                messaggio = df.iloc[idx]['Frase']
                segna_messaggio_letto(sh, idx + 2, "Calendario")
                return messaggio
            
            # 4. Buongiorno Automatico
            daily = df[(df['Mood'] == 'Buongiorno') & (df['Data'] == oggi)]
            if not daily.empty: return daily.iloc[-1]['Frase']
            return "Ti amo ❤️ (Calendario in aggiornamento)"

        else:
            # Mood Random (Luna)
            ws = sh.worksheet("Emozioni")
            df = pd.DataFrame(ws.get_all_records())
            filtro = df[df['Mood'] == mood_target]
            if filtro.empty: return "Ti amo ❤️"
            return filtro.sample().iloc[0]['Frase']

    except Exception as e:
        return f"Amore infinito ❤️ ({str(e)})"

# --- EVENTI SPECIALI ---
def check_special_event():
    now = datetime.now()
    start_date = datetime(2022, 2, 14, 0, 0, 0) # Esempio
    delta = now - start_date
    giorni = delta.days
    ore = int(delta.total_seconds() // 3600)
    
    anni = now.year - start_date.year
    if (now.month, now.day) < (start_date.month, start_date.day): anni -= 1
    
    # Eventi Fissi
    if now.month == 2 and now.day == 14:
        return "🎉 Anniversario", f"Buon Anniversario! {anni} anni di Noi.", f"{giorni} giorni insieme"
    if now.day == 14:
        return "🌹 Mesiversario", f"Buon Mesiversario! {anni} Anni e {(now.month - 2)%12} Mesi.", f"{giorni} giorni"
    
    return None, None, None

# --- UI ---
query_params = st.query_params
mode = query_params.get("mode", "daily")

if mode == "admin":
    st.markdown("### 🛠️ Centro di Controllo")
    pwd = st.text_input("Password", type="password")
    if pwd == "1234":
        if st.button("🚀 AGGIORNA FOGLI (Include Pensieri)"):
            with st.spinner("Genero Calendario e nuovi Pensieri..."):
                report = agente_ia.run_agent()
                st.write(report)
                st.success("Fatto!")
        
        st.divider()
        st.write("### 💡 Controllo Lampada")
        if st.button("❤️ Accendi Lampada + Messaggio"):
            # Manda il comando su Telegram. L'App lo intercetterà e mostrerà la frase "Pensiero"
            agente_ia.invia_notifica_telegram("CMD_LIGHT_ON")
            st.success("Lampada accesa e messaggio 'Pensiero' pronto!")

elif mode == "daily":
    st.title("☀️")
    
    # 1. Eventi Speciali (Hanno priorità e si vedono subito)
    titolo_speciale, msg_speciale, counter_info = check_special_event()
    
    if titolo_speciale:
        st.markdown(f"<h1>{titolo_speciale}</h1>", unsafe_allow_html=True)
        st.markdown(f"<h3>{msg_speciale}</h3>", unsafe_allow_html=True)
        if counter_info:
             st.markdown(f"""<div class="counter-box"><p class="counter-big">⏳ {counter_info}</p></div>""", unsafe_allow_html=True)
        st.balloons()
    
    else:
        # 2. Buongiorno Classico con Bottone Rivelatore
        st.markdown("## *Buongiorno Amore!*")
        st.divider()
        
        oggi_ita = datetime.now().strftime("%d/%m/%Y")
        
        # Gestione Sessione per il bottone
        if "revealed" not in st.session_state:
            st.session_state.revealed = False
            
        # Contenitore Vuoto per l'effetto apparizione
        contenitore_frase = st.empty()
        
        if not st.session_state.revealed:
            if st.button(f"💌 Scopri la frase di oggi - {oggi_ita}"):
                st.session_state.revealed = True
                notifica_telegram("👀 LEI HA APERTO IL BUONGIORNO!")
                st.rerun() # Ricarica per mostrare il contenuto
        
        if st.session_state.revealed:
            # Qui pesca il contenuto (Frase del giorno OPPURE Messaggio Lampada/Manuale)
            frase = get_contenuto('Buongiorno')
            st.markdown(f"<h3 style='text-align: center; color: #444; padding: 20px;'>{frase}</h3>", unsafe_allow_html=True)

elif mode == "mood":
    st.title("Come ti senti?")
    st.write("") 
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    
    # Funzione helper per evitare ripetizioni
    def handle_click(mood, emoji, msg_tg):
        salva_log(mood)
        notifica_telegram(msg_tg)
        st.info(f"{emoji} {get_contenuto(mood)}")

    if c1.button("😔 Triste"): handle_click("Triste", "", "⚠️ LEI È TRISTE")
    if c2.button("🥰 Felice"): 
        salva_log("Felice")
        notifica_telegram("ℹ️ Lei è felice!")
        st.success(get_contenuto("Felice"))
        st.snow()
    if c3.button("🕰️ Nostalgica"): handle_click("Nostalgica", "", "ℹ️ Lei è nostalgica")
    if c4.button("🤯 Stressata"): handle_click("Stressata", "", "⚠️ Lei è STRESSATA")
