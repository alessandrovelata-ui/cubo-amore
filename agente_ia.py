import os
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import json
import streamlit as st
import time
import requests
from datetime import datetime, timedelta

# --- NOTIFICHE TELEGRAM ---
def invia_notifica_telegram(testo):
    try:
        try:
            TOKEN = st.secrets["TELEGRAM_TOKEN"]
            CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
        except:
            TOKEN = os.environ.get("TELEGRAM_TOKEN")
            CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

        if TOKEN and CHAT_ID:
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            requests.get(url, params={"chat_id": CHAT_ID, "text": testo})
    except Exception as e:
        print(f"Errore Telegram: {e}")

# --- CALCOLO STATISTICHE ---
def analizza_e_salva_stats(client):
    try:
        sheet_log = client.open("CuboAmoreDB").worksheet("Log_Mood")
        df = pd.DataFrame(sheet_log.get_all_records())
        if df.empty: return "Nessun dato nel Log."
        
        colonna_mood = df.columns[2] 
        conteggio = df[colonna_mood].value_counts().to_dict()
        
        oggi = datetime.now().strftime("%Y-%m-%d")
        report_text = "\n📊 **Report Ultimi 7 Giorni:**\n"
        riga_excel = [oggi]
        
        moods_order = ["Triste", "Felice", "Nostalgica", "Stressata"]
        for m in moods_order:
            num = conteggio.get(m, 0)
            report_text += f"- {m}: {num}\n"
            riga_excel.append(num)

        try:
            sheet_report = client.open("CuboAmoreDB").worksheet("Report_Settimanali")
        except:
            sheet_report = client.open("CuboAmoreDB").add_worksheet(title="Report_Settimanali", rows=100, cols=10)
            sheet_report.append_row(["Data Report", "Triste", "Felice", "Nostalgica", "Stressata"])
        
        sheet_report.append_row(riga_excel)
        return report_text
    except Exception as e:
        return f"\n⚠️ Errore statistiche: {e}"

# --- MOTORE AGENTE (CON SIMULAZIONE) ---
def run_agent(weeks=4, data_start=None):
    try:
        # 1. SETUP
        try:
            GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
            creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
        except:
            GEMINI_KEY = os.environ["GEMINI_API_KEY"]
            GOOGLE_JSON = os.environ["GOOGLE_SHEETS_JSON"]
            creds_dict = json.loads(GOOGLE_JSON)

        genai.configure(api_key=GEMINI_KEY)
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open("CuboAmoreDB").worksheet("Contenuti")
        
        # 2. MEMORIA
        df = pd.DataFrame(sheet.get_all_records())
        frasi_usate_recenti = []
        if not df.empty and 'Link_Testo' in df.columns:
            frasi_usate_recenti = df['Link_Testo'].tail(200).tolist()

        # 3. MODELLO
        generation_config = {"temperature": 1, "response_mime_type": "application/json"}
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
        
        report_log = []
        moods = ["Buongiorno", "Triste", "Felice", "Nostalgica", "Stressata"]
        
        # Gestione Data Simulazione
        if data_start:
            oggi = data_start
            header_msg = f"🧪 TEST: Generazione simulata dal {oggi.strftime('%Y-%m-%d')}"
        else:
            oggi = datetime.now()
            header_msg = f"🚀 Avvio generazione reale ({weeks} settimane)"
            
        totale_generate = 0
        invia_notifica_telegram(f"{header_msg}...")

        # --- CICLO GENERAZIONE ---
        for settimana in range(weeks):
            offset_giorni_settimana = settimana * 7
            report_log.append(f"\n🗓️ **Settimana +{settimana}:**")
            
            for m in moods:
                try:
                    prompt = f"""
                    Sei un fidanzato innamorato. Genera un array JSON di 7 frasi uniche per il mood: {m}.
                    REGOLE:
                    1. 5 frasi tue (dolci) + 2 CITAZIONI.
                    2. USA SOLO APICE SINGOLO ('). NO virgolette doppie (").
                    3. Evita: {str(frasi_usate_recenti[-20:])}
                    OUTPUT: Solo JSON Array. Esempio: ['Frase 1', 'Frase 2']
                    """

                    response = model.generate_content(prompt)
                    text_clean = response.text.strip().replace("```json", "").replace("```", "")
                    lista_frasi = json.loads(text_clean)
                    
                    local_count = 0
                    for frase in lista_frasi:
                        if frase in frasi_usate_recenti: continue 
                        
                        data_str = ""
                        if m == "Buongiorno":
                            giorni_da_aggiungere = offset_giorni_settimana + local_count
                            data_target = oggi + timedelta(days=giorni_da_aggiungere)
                            data_str = data_target.strftime("%Y-%m-%d")
                        
                        sheet.append_row([m, "Frase", frase, data_str])
                        frasi_usate_recenti.append(frase)
                        local_count += 1
                    
                    totale_generate += local_count
                    report_log.append(f"   - {m}: +{local_count}")
                    time.sleep(2) 
                    
                except Exception as e:
                    report_log.append(f"   ❌ Errore {m}: {e}")
                    time.sleep(5)
            time.sleep(2)

        if not data_start:
            stats_text = analizza_e_salva_stats(client)
        else:
            stats_text = "\n(Statistiche ignorate in modalità Test)"
        
        messaggio_finale = f"✅ **COMPLETATO**\nFrasi: {totale_generate}\n{stats_text}"
        invia_notifica_telegram(messaggio_finale)
        return report_log

    except Exception as e:
        invia_notifica_telegram(f"❌ ERRORE: {str(e)}")
        return [str(e)]
