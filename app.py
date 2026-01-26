import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import requests
import json
import agente_ia

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Cubo Amore", page_icon="❤️", layout="centered")

# --- CSS ESTETICO ---
hide_st_style = """
            <style>
            .stApp { background-color: #FFF5F7; }
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            [data-testid="stToolbar"] {visibility: hidden;}
            .stDeployButton {display:none;}
            
            h1 { color: #D64161 !important; text-align: center; font-family: 'Helvetica Neue', sans-serif; font-weight: 700; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); margin-bottom: 20px; }
            h2, h3, p, div { color: #4A4A4A !important; text-align: center; }
            
            .counter-box { background-color: #fff; border: 2px solid #D64161; border-radius: 15px; padding: 15px; margin-top: 10px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
            .counter-big { font-size: 1.2em; font-weight: bold; color: #D64161 !important; }
            
            .stButton>button { width: 100%; height: 3.5em; font-size: 20px !important; font-weight: 600; background-color: #ffffff; color: #D64161; border: 2px solid #FFD1DC; border-radius: 25px; box-shadow: 0 4px 6px rgba(214, 65, 97, 0.1); transition: all 0.3s ease; }
            .stButton>button:hover { border-color: #D64161; background-color: #FFF0F5; transform: translateY(-2px); }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- CONNESSIONE DB ---
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

# --- FUNZIONE: LEGGI UNA VOLTA E BRUCIA 🔥 ---
def segna_messaggio_letto(sh, riga_index):
    try:
        ws = sh.worksheet("Contenuti")
        # Aggiorna la cella Mood (colonna 1) da "Manuale" a "Manuale_Letto"
        # gspread usa indici base-1. riga_index deve essere l'indice reale del foglio.
        ws.update_cell(riga_index, 1, "Manuale_Letto")
    except Exception as e:
        print(f"Errore aggiornamento DB: {e}")

# --- OVERRIDE TELEGRAM (SOLO PER BUONGIORNO) ---
def check_telegram_override(df_contenuti):
    try:
        oggi_str = datetime.now().strftime("%Y-%m-%d")
        # Se c'è già un Manuale (o Manuale_Letto) per oggi, non chiediamo a Telegram
        if not df_contenuti.empty and 'Data_Specifica' in df_contenuti.columns:
             check = df_contenuti[
                 (df_contenuti['Mood'].str.contains('Manuale')) & 
                 (df_contenuti['Data_Specifica'].astype(str) == oggi_str)
             ]
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
                    
                    # Se trovo un messaggio tuo di oggi
                    if sender_id == admin_id and data_msg == oggi_str and not testo.startswith("/"):
                        sh = connect_db()
                        ws = sh.worksheet("Contenuti")
                        ws.append_row(["Manuale", "TelegramOverride", testo, oggi_str])
                        st.rerun() 
                        return
    except: pass

# --- RECUPERO CONTENUTI ---
def get_contenuto(mood_target, date_check=None):
    try:
        sh = connect_db()
        ws = sh.worksheet("Contenuti")
        df = pd.DataFrame(ws.get_all_records())
        oggi = (date_check if date_check else datetime.now()).strftime("%Y-%m-%d")
        
        if 'Data_Specifica' in df.columns:
            df['Data_Specifica'] = df['Data_Specifica'].astype(str)
        
        # 1. CONTROLLO TELEGRAM (Solo se è Buongiorno e data reale)
        if mood_target == "Buongiorno" and not date_check:
            check_telegram_override(df)
            # Ricarichiamo il DF dopo eventuale override
            df = pd.DataFrame(ws.get_all_records())
            if 'Data_Specifica' in df.columns: df['Data_Specifica'] = df['Data_Specifica'].astype(str)

        # 2. CERCA MESSAGGIO MANUALE (PRIORITÀ ASSOLUTA)
        # Ma SOLO se stiamo chiedendo il Buongiorno!
        if mood_target == "Buongiorno":
            # Cerchiamo riga con Mood="Manuale" e Data=Oggi
            # Nota: usiamo l'indice + 2 perché gspread ha header (1) e base-1
            indices = df.index[(df['Mood'] == 'Manuale') & (df['Data_Specifica'] == oggi)].tolist()
            
            if indices:
                idx = indices[-1] # Prendiamo l'ultimo inserito
                messaggio = df.iloc[idx]['Link_Testo']
                
                # SE NON È UNA SIMULAZIONE -> SEGNA COME LETTO
                if not date_check:
                    segna_messaggio_letto(sh, idx + 2) 
                
                return messaggio
            
            # Se è già stato letto oggi, ignora e passa all'IA
            # (Il codice sotto cercherà 'Buongiorno')

        # 3. CERCA FRASE AUTOMATICA (IA)
        if mood_target == "Buongiorno":
            daily = df[(df['Mood'] == 'Buongiorno') & (df['Data_Specifica'] == oggi)]
            if not daily.empty: return daily.iloc[-1]['Link_Testo']
            
        # 4. EMOZIONI (Click Bottoni)
        filtro = df[df['Mood'] == mood_target]
        if filtro.empty: return "Ti amo ❤️"
        return filtro.sample().iloc[0]['Link_Testo']

    except Exception as e:
        return f"Amore infinito ❤️ ({str(e)})"

# --- LOGICA EVENTI ---
def check_special_event(date_check=None):
    now = date_check if date_check else datetime.now()
    start_date = datetime(2022, 2, 14, 0, 0, 0)
    
    delta = now - start_date
    giorni_totali = delta.days
    
    anni = now.year - start_date.year
    if (now.month, now.day) < (start_date.month, start_date.day): anni -= 1
    
    mesi_diff = (now.year - start_date.year) * 12 + now.month - start_date.month
    if now.day < start_date.day: mesi_diff -= 1
    mesi_reali = mesi_diff % 12
    
    if now.month == 2 and now.day == 14:
        return "🎉 Anniversario", f"Buon Anniversario! ❤️\n{anni} anni di Noi.", f"Sono {giorni_totali} giorni che mi sopporti!"
    if now.day == 14:
        return "🌹 Mesiversario", f"Buon Mesiversario! 🌹\n{anni} Anni e {mesi_reali} Mesi.", f"Giorni totali: {giorni_totali}"
    if now.month == 4 and now.day == 12:
        return "🎂 Buon Compleanno!", "Tanti auguri al mio Sole!", None
    if now.month == 6 and now.day in [20, 21]:
        return "☀️ Solstizio d'Estate", "Il giorno più lungo per l'amore più grande.", None
    if now.month == 12 and now.day in [21, 22]:
        return "❄️ Solstizio d'Inverno", "La notte più lunga, illuminata da te.", None
    if now.month == 12 and now.day == 25: return "🎄 Buon Natale", "Il mio regalo sei tu.", None
    if now.month == 1 and now.day == 1: return "🥂 Buon Anno", "Scriviamo un altro capitolo.", None
        
    return None, None, None

# --- INTERFACCIA ---
query_params = st.query_params
mode = query_params.get("mode", "daily")

if mode == "admin":
    st.markdown("### 🛠️ Centro di Controllo")
    pwd = st.text_input("Password", type="password")
    if pwd == "1234":
        
        st.write("### 🏗️ Azioni Reali")
        if st.button("🚀 Genera Mese Reale (Da Oggi)"):
            with st.spinner("Generazione in corso..."):
                report = agente_ia.run_agent(weeks=4)
                st.write(report)
                st.success("Fatto!")

        st.divider()
        st.write("### 🧪 Area Test / Simulazione")
        if st.button("🌹 SIMULA SETTIMANA 14 FEBBRAIO 2026"):
            data_test = datetime(2026, 2, 14, 9, 0, 0)
            st.info(f"⏳ Avvio simulazione al: {data_test.strftime('%d-%m-%Y')}...")
            
            with st.spinner("Creo il futuro..."):
                agente_ia.run_agent(weeks=1, data_start=data_test)
            
            st.success("✅ DB Aggiornato. Ecco l'anteprima:")
            for i in range(7):
                giorno_corrente = data_test + timedelta(days=i)
                data_str = giorno_corrente.strftime("%d-%m-%Y")
                titolo, msg, counter = check_special_event(giorno_corrente)
                frase_db = get_contenuto("Buongiorno", giorno_corrente)
                
                with st.expander(f"📅 {data_str}"):
                    if titolo:
                        st.markdown(f"**🌟 EVENTO:** {titolo}")
                        st.code(f"{msg}")
                    else:
                        st.markdown("**☀️ Normale:**")
                        st.write(f"Frase: *{frase_db}*")

elif mode == "daily":
    st.title("☀️")
    titolo_speciale, msg_speciale, counter_info = check_special_event()
    
    if titolo_speciale:
        st.markdown(f"<h1>{titolo_speciale}</h1>", unsafe_allow_html=True)
        st.markdown(f"<h3>{msg_speciale}</h3>", unsafe_allow_html=True)
        if counter_info:
            st.markdown(f"""<div class="counter-box"><p class="counter-big">⏳ Il nostro tempo</p><p>{counter_info}</p></div>""", unsafe_allow_html=True)
        st.balloons()
    else:
        st.markdown("## Buongiorno Amore")
        st.divider()
        # Qui controlla se c'è messaggio manuale. Se c'è, lo mostra e lo segna come letto.
        frase = get_contenuto('Buongiorno')
        st.markdown(f"<h3 style='text-align: center; color: #444;'>{frase}</h3>", unsafe_allow_html=True)

elif mode == "mood":
    st.title("Come ti senti?")
    st.write("") 
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    
    # Nota: Qui chiamiamo get_contenuto con "Triste", "Felice" etc.
    # Quindi la logica del messaggio manuale (legata a "Buongiorno") NON viene attivata.
    if c1.button("😔 Triste"):
        salva_log("Triste")
        notifica_telegram("⚠️ LEI È TRISTE")
        st.info(get_contenuto("Triste"))
    if c2.button("🥰 Felice"):
        salva_log("Felice")
        notifica_telegram("ℹ️ Lei è felice!")
        st.success(get_contenuto("Felice"))
        st.snow()
    if c3.button("🕰️ Nostalgica"):
        salva_log("Nostalgica")
        notifica_telegram("ℹ️ Lei è nostalgica")
        st.warning(get_contenuto("Nostalgica"))
    if c4.button("🤯 Stressata"):
        salva_log("Stressata")
        notifica_telegram("⚠️ Lei è STRESSATA")
        st.error(get_contenuto("Stressata"))
