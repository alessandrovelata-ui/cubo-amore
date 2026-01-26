import os
import pandas as pd
import gspread
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
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

        colonna_mood = df.columns[2] # Assumiamo colonna 3 = Mood
        conteggio = df[colonna_mood].value_counts().to_dict()
        
        oggi = datetime.now()
        report_text = "\n📊 **Report Settimanale:**\n"
        riga_excel = [oggi.strftime("%Y-%m-%d")]
        
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

# --- MOTORE AGENTE ---
def run_agent():
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
        
        scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("CuboAmoreDB").worksheet("Contenuti")
        
        # 2. MEMORIA
        df = pd.DataFrame(sheet.get_all_records())
        frasi_usate_recenti = []
        if not df.empty and 'Link_Testo' in df.columns:
            frasi_usate_recenti = df['Link_Testo'].tail(150).tolist()

        # 3. MODELLO
        generation_config = {
            "temperature": 1,
            "response_mime_type": "application/json",
        }
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
        
        report_log = []
        moods = ["Buongiorno", "Triste", "Felice", "Nostalgica", "Stressata"]
        oggi = datetime.now()
        totale_generate = 0

        for m in moods:
            try:
                # --- PROMPT CORRETTO PER EVITARE ERRORE JSON ---
                # Abbiamo aggiunto la regola sulle virgolette singole/doppie
                prompt = f"""
                Sei un fidanzato innamorato. Genera un array JSON di 7 frasi per il mood: {m}.
                
                REGOLE TASSATIVE:
                1. Genera 5 frasi originali e dolci.
                2. Genera 2 CITAZIONI (Film, Libri, Canzoni).
                3. IMPORTANTE: All'interno del testo delle frasi, usa SOLO l'apice singolo ('). 
                   NON usare MAI virgolette doppie (") all'interno del testo, altrimenti rompi il codice.
                   Esempio GIUSTO: "L'amore conta"
                   Esempio SBAGLIATO: "L"amore" conta"
                4. Evita queste frasi recenti: {str(frasi_usate_recenti[-15:])}
                
                OUTPUT: Solo JSON Array di stringhe. Esempio: ["Frase 1", "Frase 2"]
                """

                response = model.generate_content(prompt)
                
                # --- PULIZIA DI SICUREZZA ---
                # A volte il modello mette testo prima o dopo il JSON. Puliamo.
                text_clean = response.text.strip()
                if "```json" in text_clean:
                    text_clean = text_clean.replace("```json", "").replace("```", "")
                
                lista_frasi = json.loads(text_clean)
                
                local_count = 0
                for frase in lista_frasi:
                    if frase in frasi_usate_recenti: continue 
                    
                    data_str = ""
                    if m == "Buongiorno":
                        data_target = oggi + timedelta(days=local_count)
                        data_str = data_target.strftime("%Y-%m-%d")
                    
                    sheet.append_row([m, "Frase", frase, data_str])
                    local_count += 1
                
                totale_generate += local_count
                report_log.append(f"✅ {m}: +{local_count}")
                time.sleep(5) 
                
            except json.JSONDecodeError as e_json:
                # Se fallisce il JSON, proviamo a salvare l'errore specifico ma continuiamo
                err = f"❌ Errore Formato JSON su {m}. Riprovo al prossimo giro."
                report_log.append(err)
                print(f"JSON Error content: {response.text}")
                time.sleep(5)
            except Exception as e:
                err = f"❌ Errore {m}: {e}"
                report_log.append(err)
                time.sleep(5)

        # REPORT FINALE
        stats_text = analizza_e_salva_stats(client)
        
        messaggio_finale = f"✅ **AGENTE COMPLETATO**\n"
        messaggio_finale += f"Frasi create: {totale_generate}\n"
        messaggio_finale += "\n".join(report_log)
        messaggio_finale += f"\n{stats_text}"
        
        invia_notifica_telegram(messaggio_finale)
        
        return report_log

    except Exception as e_critico:
        err_msg = f"❌ ERRORE CRITICO: {str(e_critico)}"
        invia_notifica_telegram(err_msg)
        return [err_msg]

if __name__ == "__main__":
    print(run_agent())
