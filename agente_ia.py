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

# --- FUNZIONE DI SUPPORTO: NOTIFICA TELEGRAM ---
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
        print(f"Errore invio Telegram: {e}")

# --- FUNZIONE DI SUPPORTO: STATISTICHE ---
def analizza_e_salva_stats(client):
    try:
        sheet_log = client.open("CuboAmoreDB").worksheet("Log_Mood")
        df = pd.DataFrame(sheet_log.get_all_records())
        
        if df.empty: return "Nessun dato nel Log."

        # Statistiche ultimi 7 giorni
        colonna_mood = df.columns[2] 
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

# --- FUNZIONE PRINCIPALE ---
def run_agent():
    # SETUP CREDENZIALI
    try:
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
        
        # MEMORIA
        df = pd.DataFrame(sheet.get_all_records())
        frasi_usate_recenti = []
        if not df.empty and 'Link_Testo' in df.columns:
            frasi_usate_recenti = df['Link_Testo'].tail(150).tolist()

        # --- MOTORE GEMINI PRO ---
        # Impostiamo il modello PRO richiesto
        # Usiamo response_mime_type per forzare il JSON ed evitare errori di virgole
        generation_config = {
            "temperature": 1, 
            "response_mime_type": "application/json",
        }
        
        # NOTA: Se 'gemini-2.5-pro' ti dà errore 404, prova 'gemini-1.5-pro'
        model = genai.GenerativeModel('gemini-2.5-pro', generation_config=generation_config)
        
        report_log = []
        moods = ["Buongiorno", "Triste", "Felice", "Nostalgica", "Stressata"]
        oggi = datetime.now()
        totale_generate = 0

        for m in moods:
            try:
                prompt = f"""
                Sei un fidanzato poeta e innamorato. Genera un array JSON di 7 frasi uniche per il mood: {m}.
                
                REGOLE:
                - 5 frasi tue: profonde, emotive, dolci (max 20 parole).
                - 2 frasi CITAZIONI: usa citazioni d'autore (Film, Poeti, Canzoni) coerenti. Metti autore tra parentesi.
                - MEMORIA: NON usare queste frasi recenti: {str(frasi_usate_recenti[-15:])}
                
                OUTPUT: Solo JSON Array di stringhe. Esempio: ["Frase 1", "Frase 2 (Autore)"]
                """

                response = model.generate_content(prompt)
                lista_frasi = json.loads(response.text)
                
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
                report_log.append(f"✅ {m} (Pro): +{local_count}")
                
                # --- PAUSA PRO (30 Secondi) ---
                # I modelli Pro hanno limiti più bassi (RPM). 
                # Aumentiamo la pausa per evitare il blocco "429 Quota Exceeded".
                time.sleep(30) 
                
            except Exception as e:
                err = f"❌ Errore {m}: {e}"
                report_log.append(err)
                # Se fallisce, potrebbe essere per il nome del modello o rate limit
                invia_notifica_telegram(f"⚠️ {err}")
                time.sleep(30)

        # REPORT FINALE
        stats_text = analizza_e_salva_stats(client)
        
        messaggio_finale = f"✅ **AGENTE PRO COMPLETATO**\n\n"
        messaggio_finale += f"Frasi create: {totale_generate}\n"
        messaggio_finale += "\n".join(report_log)
        messaggio_finale += f"\n{stats_text}"
        
        invia_notifica_telegram(messaggio_finale)
        
        return report_log

    except Exception as e_critico:
        err_msg = f"❌ ERRORE CRITICO AGENTE: {str(e_critico)}"
        invia_notifica_telegram(err_msg)
        return [err_msg]

if __name__ == "__main__":
    print(run_agent())
