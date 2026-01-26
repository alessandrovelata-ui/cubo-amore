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

# --- GESTIONE FOGLI E DATE ---
def setup_fogli(client):
    """Crea i fogli se non esistono"""
    db = client.open("CuboAmoreDB")
    
    # Foglio Calendario (Buongiorno)
    try:
        ws_cal = db.worksheet("Calendario")
    except:
        ws_cal = db.add_worksheet(title="Calendario", rows=1000, cols=5)
        ws_cal.append_row(["Data", "Mood", "Frase", "Tipo", "Marker"]) # Intestazione
        
    # Foglio Emozioni (Random)
    try:
        ws_emo = db.worksheet("Emozioni")
    except:
        ws_emo = db.add_worksheet(title="Emozioni", rows=1000, cols=4)
        ws_emo.append_row(["Mood", "Frase", "Tipo"]) # Intestazione
        
    return ws_cal, ws_emo

def trova_data_start(ws_cal):
    try:
        df = pd.DataFrame(ws_cal.get_all_records())
        if df.empty or 'Data' not in df.columns:
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Converte e trova il max
        df['Data'] = pd.to_datetime(df['Data'], format="%Y-%m-%d", errors='coerce')
        ultima_data = df['Data'].max()
        
        if pd.isna(ultima_data):
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
        return ultima_data + timedelta(days=1)
    except:
        return datetime.now()

def aggiorna_marker_next(ws_cal):
    """Mette una stella ⭐️ accanto alla data di domani"""
    try:
        df = pd.DataFrame(ws_cal.get_all_records())
        domani = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Resetta colonna Marker (scrive vuoto ovunque)
        # Nota: questo consuma write requests, facciamolo smart se possibile
        # Per semplicità e risparmio quote:
        # Non cancelliamo tutto, cerchiamo solo la riga di domani.
        
        # Trova indice riga domani
        row_idx = -1
        rows = ws_cal.get_all_values() # Legge tutto come lista
        
        for i, row in enumerate(rows):
            if i == 0: continue # Salta header
            if row[0] == domani: # Colonna 0 è Data
                row_idx = i + 1 # gspread è 1-based
                break
        
        if row_idx > 0:
            # Scrive il marker
            ws_cal.update_cell(row_idx, 5, "⭐️ NEXT") # Colonna 5 è Marker
            
    except Exception as e:
        print(f"Errore marker: {e}")

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
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        # Setup Fogli Separati
        ws_cal, ws_emo = setup_fogli(client)
        
        # 2. CALCOLO DATA
        data_partenza = trova_data_start(ws_cal)
        data_log_str = data_partenza.strftime("%d-%m-%Y")

        # 3. MEMORIA (Unisci le frasi di entrambi i fogli per evitare ripetizioni)
        frasi_usate_recenti = []
        df_cal = pd.DataFrame(ws_cal.get_all_records())
        df_emo = pd.DataFrame(ws_emo.get_all_records())
        
        if not df_cal.empty and 'Frase' in df_cal.columns:
            frasi_usate_recenti += df_cal['Frase'].tail(150).tolist()
        if not df_emo.empty and 'Frase' in df_emo.columns:
            frasi_usate_recenti += df_emo['Frase'].tail(150).tolist()

        # 4. MODELLO
        generation_config = {"temperature": 1, "response_mime_type": "application/json"}
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
        
        report_log = []
        totale_generate = 0
        
        invia_notifica_telegram(f"🚀 Avvio generazione su fogli separati.\n📅 Calendario riparte dal: {data_log_str}")

        # --- CICLO 4 SETTIMANE ---
        for settimana in range(4):
            offset_giorni = settimana * 7
            report_log.append(f"\n🗓️ **Settimana +{settimana}:**")
            
            try:
                prompt = f"""
                Sei un fidanzato innamorato. Genera contenuti per una intera settimana.
                OUTPUT JSON: chiavi "Buongiorno", "Triste", "Felice", "Nostalgica", "Stressata".
                Ogni chiave deve avere una lista di 7 frasi.
                REGOLE:
                1. Stile: dolce, breve. 2 CITAZIONI incluse per lista.
                2. USA SOLO APICE SINGOLO ('). NO virgolette doppie (").
                3. Evita: {str(frasi_usate_recenti[-30:])}
                """

                response = model.generate_content(prompt)
                text_clean = response.text.strip().replace("```json", "").replace("```", "")
                dati_settimana = json.loads(text_clean)
                
                # --- SCRITTURA SEPARATA ---
                rows_cal = [] # Per foglio Calendario
                rows_emo = [] # Per foglio Emozioni
                
                for mood, lista_frasi in dati_settimana.items():
                    local_count = 0
                    for frase in lista_frasi:
                        if frase in frasi_usate_recenti: continue 
                        
                        tipo_info = "Frase"
                        
                        if mood == "Buongiorno":
                            # Logica Calendario
                            giorni_da_aggiungere = offset_giorni + local_count
                            data_target = data_partenza + timedelta(days=giorni_da_aggiungere)
                            data_str = data_target.strftime("%Y-%m-%d")
                            
                            check_giorno = data_target.day
                            check_mese = data_target.month
                            if check_giorno == 14: tipo_info = "Anniv/Mesi (Nascosta)"
                            elif check_mese == 4 and check_giorno == 12: tipo_info = "Compleanno (Nascosta)"
                            elif check_mese == 12 and check_giorno == 25: tipo_info = "Natale (Nascosta)"
                            
                            # [Data, Mood, Frase, Tipo, Marker]
                            rows_cal.append([data_str, mood, frase, tipo_info, ""])
                        else:
                            # Logica Emozioni Random
                            # [Mood, Frase, Tipo]
                            rows_emo.append([mood, frase, tipo_info])
                        
                        frasi_usate_recenti.append(frase)
                        local_count += 1
                    
                    totale_generate += local_count
                
                # Scrittura Batch sui due fogli
                if rows_cal: ws_cal.append_rows(rows_cal)
                if rows_emo: ws_emo.append_rows(rows_emo)
                
                report_log.append("   ✅ Dati salvati.")
                time.sleep(3) 

            except Exception as e:
                err = f"❌ Errore Settimana {settimana}: {e}"
                report_log.append(err)
                time.sleep(5)
        
        # 5. EVIDENZIA IL PROSSIMO
        aggiorna_marker_next(ws_cal)

        stats_text = analizza_e_salva_stats(client)
        messaggio_finale = f"✅ **AGGIORNAMENTO COMPLETATO**\n📅 Fogli separati aggiornati.\nTotale: {totale_generate}\n{stats_text}"
        invia_notifica_telegram(messaggio_finale)
        return report_log

    except Exception as e:
        err = f"❌ ERRORE CRITICO: {str(e)}"
        invia_notifica_telegram(err)
        return [err]
