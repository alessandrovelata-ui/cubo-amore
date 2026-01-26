import os
import pandas as pd
import gspread
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
import json
import streamlit as st
import time
import requests # Serve per le notifiche
from datetime import datetime, timedelta

# --- FUNZIONE DI SUPPORTO: NOTIFICA TELEGRAM ---
def invia_notifica_telegram(testo):
    try:
        # Recupera i segreti (funziona sia su Streamlit Cloud che locale)
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

# --- FUNZIONE DI SUPPORTO: CALCOLO E SALVATAGGIO STATISTICHE ---
def analizza_e_salva_stats(client):
    try:
        # 1. Leggi i dati dal log
        sheet_log = client.open("CuboAmoreDB").worksheet("Log_Mood")
        df = pd.DataFrame(sheet_log.get_all_records())
        
        if df.empty:
            return "Nessun dato nel Log."

        # Assumiamo che le colonne siano: Data, Ora, Mood (Indice 0, 1, 2)
        # Filtriamo gli ultimi 7 giorni
        oggi = datetime.now()
        sette_giorni_fa = today = datetime.now() - timedelta(days=7)
        
        # Statistiche semplici (conta totale per Mood)
        colonna_mood = df.columns[2] # Terza colonna
        conteggio = df[colonna_mood].value_counts().to_dict()
        
        # 2. Prepara il report testuale per Telegram
        report_text = "\n📊 **Report Settimanale:**\n"
        riga_excel = [oggi.strftime("%Y-%m-%d")] # Iniziamo la riga per l'Excel con la data
        
        # Ordine fisso per Excel: Triste, Felice, Nostalgica, Stressata
        moods_order = ["Triste", "Felice", "Nostalgica", "Stressata"]
        
        for m in moods_order:
            num = conteggio.get(m, 0)
            report_text += f"- {m}: {num}\n"
            riga_excel.append(num)

        # 3. Salva nel nuovo foglio "Report_Settimanali"
        try:
            sheet_report = client.open("CuboAmoreDB").worksheet("Report_Settimanali")
        except:
            # Se non esiste, lo crea
            sheet_report = client.open("CuboAmoreDB").add_worksheet(title="Report_Settimanali", rows=100, cols=10)
            sheet_report.append_row(["Data Report", "Triste", "Felice", "Nostalgica", "Stressata"])
        
        sheet_report.append_row(riga_excel)
        return report_text

    except Exception as e:
        return f"\n⚠️ Errore calcolo statistiche: {e}"

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
        
        # CONNESSIONE DB
        scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("CuboAmoreDB").worksheet("Contenuti")
        
        # MEMORIA ANTI-DUPLICATI
        df = pd.DataFrame(sheet.get_all_records())
        frasi_usate_recenti = []
        if not df.empty and 'Link_Testo' in df.columns:
            frasi_usate_recenti = df['Link_Testo'].tail(150).tolist()

        # CONFIGURAZIONE MODELLO (Fix Errore Virgola)
        generation_config = {
            "temperature": 1,
            "response_mime_type": "application/json",
        }
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
        
        report_log = []
        moods = ["Buongiorno", "Triste", "Felice", "Nostalgica", "Stressata"]
        oggi = datetime.now()
        totale_generate = 0

        # --- CICLO DI GENERAZIONE ---
        for m in moods:
            try:
                # Prompt con Citazioni e Batch 7x
                prompt = f"""
                Sei un fidanzato innamorato. Genera un array JSON di 7 frasi diverse per il mood: {m}.
                
                REGOLE:
                - 5 frasi tue: dolci, brevi (max 15 parole).
                - 2 frasi CITAZIONI: usa citazioni famose (Film, Canzoni, Libri) adatte al mood. Metti l'autore tra parentesi.
                - MEMORIA: Evita assolutamente queste frasi recenti: {str(frasi_usate_recenti[-15:])}
                
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
                report_log.append(f"✅ {m}: +{local_count}")
                time.sleep(5) # Pausa veloce
                
            except Exception as e:
                report_log.append(f"❌ Errore {m}: {e}")
                invia_notifica_telegram(f"⚠️ Errore parziale durante {m}: {str(e)}")
                time.sleep(5)

        # --- FASE FINALE: STATISTICHE E NOTIFICA ---
        stats_text = analizza_e_salva_stats(client)
        
        messaggio_finale = f"✅ **AGENTE COMPLETATO**\n\n"
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
