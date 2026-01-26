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

# --- FUNZIONE: TROVA PROSSIMA DATA ---
def trova_data_start(sheet):
    """
    Legge il foglio e trova l'ultima data inserita per il Buongiorno.
    Ritorna: L'ultima data + 1 giorno.
    Se vuoto: Ritorna Oggi.
    """
    try:
        df = pd.DataFrame(sheet.get_all_records())
        
        # Se il DF è vuoto o non ha le colonne giuste
        if df.empty or 'Data_Specifica' not in df.columns or 'Mood' not in df.columns:
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Filtra solo i Buongiorno (che hanno date sequenziali)
        df_daily = df[df['Mood'] == 'Buongiorno'].copy()
        
        if df_daily.empty:
             return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
             
        # Converte la colonna in datetime
        df_daily['Data_Specifica'] = pd.to_datetime(df_daily['Data_Specifica'], format="%Y-%m-%d", errors='coerce')
        
        # Trova la data massima
        ultima_data = df_daily['Data_Specifica'].max()
        
        if pd.isna(ultima_data):
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
        # Ripartiamo dal giorno dopo
        return ultima_data + timedelta(days=1)
        
    except Exception as e:
        print(f"Errore calcolo data: {e}")
        return datetime.now()

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
        sheet = client.open("CuboAmoreDB").worksheet("Contenuti")
        
        # 2. CALCOLO DATA DI PARTENZA (CONTINUITÀ)
        data_partenza = trova_data_start(sheet)
        data_log_str = data_partenza.strftime("%d-%m-%Y")

        # 3. MEMORIA
        df = pd.DataFrame(sheet.get_all_records())
        frasi_usate_recenti = []
        if not df.empty and 'Link_Testo' in df.columns:
            frasi_usate_recenti = df['Link_Testo'].tail(300).tolist()

        # 4. MODELLO
        generation_config = {"temperature": 1, "response_mime_type": "application/json"}
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
        
        report_log = []
        totale_generate = 0
        
        invia_notifica_telegram(f"🚀 Avvio generazione 4 settimane.\n📅 Si riparte dal: {data_log_str}")

        # --- CICLO 4 SETTIMANE ---
        for settimana in range(4):
            offset_giorni = settimana * 7
            report_log.append(f"\n🗓️ **Settimana +{settimana}:**")
            
            try:
                # BATCH GENERATION
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
                
                for mood, lista_frasi in dati_settimana.items():
                    local_count = 0
                    for frase in lista_frasi:
                        if frase in frasi_usate_recenti: continue 
                        
                        data_str = ""
                        tipo_info = "Frase"

                        if mood == "Buongiorno":
                            # Calcolo data continua
                            giorni_da_aggiungere = offset_giorni + local_count
                            data_target = data_partenza + timedelta(days=giorni_da_aggiungere)
                            data_str = data_target.strftime("%Y-%m-%d")
                            
                            # LOGICA EVENTI SPECIALI NEL DB (Solo visuale per te)
                            # Se la data coincide con un evento, lo scriviamo nel DB come nota
                            # Così sai che quel giorno l'app mostrerà l'evento e non questa frase.
                            check_mese = data_target.month
                            check_giorno = data_target.day
                            
                            if check_giorno == 14: # Mesiversario o Anniversario
                                tipo_info = "Frase (Nascosta da Anniv/Mesi)"
                            elif check_mese == 4 and check_giorno == 12: # Compleanno
                                tipo_info = "Frase (Nascosta da Compleanno)"
                            elif check_mese == 12 and check_giorno == 25:
                                tipo_info = "Frase (Nascosta da Natale)"
                        
                        sheet.append_row([mood, tipo_info, frase, data_str])
                        frasi_usate_recenti.append(frase)
                        local_count += 1
                    
                    totale_generate += local_count
                
                report_log.append("   ✅ OK")
                time.sleep(2) 

            except Exception as e:
                err = f"❌ Errore Settimana {settimana}: {e}"
                report_log.append(err)
                time.sleep(5)

        stats_text = analizza_e_salva_stats(client)
        messaggio_finale = f"✅ **AGGIORNAMENTO COMPLETATO**\n📅 Nuove frasi dal: {data_log_str}\nTotale: {totale_generate}\n{stats_text}"
        invia_notifica_telegram(messaggio_finale)
        return report_log

    except Exception as e:
        err = f"❌ ERRORE CRITICO: {str(e)}"
        invia_notifica_telegram(err)
        return [err]
