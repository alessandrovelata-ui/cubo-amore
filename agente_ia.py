import os
import pandas as pd
import gspread
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
import json
import streamlit as st
import time
from datetime import datetime, timedelta
import locale

# Proviamo a impostare l'italiano per i nomi dei giorni (es. Lunedì)
try:
    locale.setlocale(locale.LC_TIME, 'it_IT.utf8')
except:
    pass # Se non ce l'ha, userà l'inglese o default, non importa

def run_agent():
    # --- SETUP CREDENZIALI ---
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
    
    # Leggiamo i dati esistenti per dare contesto
    dati = pd.DataFrame(sheet.get_all_records())
    model = genai.GenerativeModel('gemini-2.5-flash')
    report = []

    # --- FASE 1: GENERAZIONE DEI 7 BUONGIORNO (Uno per giorno) ---
    oggi = datetime.now()
    
    for i in range(7):
        # Calcoliamo la data: Oggi, Domani, Dopodomani...
        data_target = oggi + timedelta(days=i)
        data_str = data_target.strftime("%Y-%m-%d")
        nome_giorno = data_target.strftime("%A") # Es. Lunedì, Martedì...
        
        # Recupera esempi vecchi
        if not dati.empty and 'Mood' in dati.columns:
            esempi = dati[dati['Mood'] == 'Buongiorno']['Link_Testo'].tail(3).tolist()
        else:
            esempi = ["Buongiorno amore", "Svegliarmi con te è un sogno"]

        prompt = f"""
        Scrivi una frase di BUONGIORNO per la mia ragazza.
        
        CONTESTO: Deve essere specifica per il giorno: {nome_giorno}.
        DATA: {data_str}
        STILE: Breve (max 15 parole), dolce, motivante.
        ESEMPI STILE: {esempi}

        REGOLE:
        1. Rispondi SOLO con il testo della frase.
        2. Niente virgolette, elenchi o commenti.
        """
        
        try:
            response = model.generate_content(prompt)
            frase_pulita = response.text.strip().replace('"', '').replace('*', '').split('\n')[0]
            
            # SALVIAMO CON LA DATA SPECIFICA!
            # Mood, Tipo, Testo, Data_Specifica
            sheet.append_row(["Buongiorno", "Frase", frase_pulita, data_str])
            report.append(f"✅ Buongiorno del {data_str} ({nome_giorno}): {frase_pulita}")
            
            time.sleep(15) # Pausa obbligatoria
            
        except Exception as e:
            report.append(f"❌ Errore Buongiorno {data_str}: {e}")
            time.sleep(15)

    # --- FASE 2: RIMPOLPARE I MOOD (1 nuovo per tipo a settimana) ---
    moods_extra = ["Triste", "Felice", "Nostalgica", "Stressata"]
    
    for m in moods_extra:
        try:
            # Recupera esempi
            if not dati.empty and 'Mood' in dati.columns:
                esempi = dati[dati['Mood'] == m]['Link_Testo'].tail(3).tolist()
            else:
                esempi = ["Ti amo", "Coraggio"]

            prompt = f"""
            Scrivi una frase per la mia ragazza.
            MOOD LEI: {m}
            STILE: Breve (max 15 parole), empatica.
            ESEMPI: {esempi}
            REGOLE: Solo testo, niente commenti.
            """
            
            response = model.generate_content(prompt)
            frase_pulita = response.text.strip().replace('"', '').replace('*', '').split('\n')[0]
            
            # Qui la data la lasciamo vuota, così vale "per sempre"
            sheet.append_row([m, "Frase", frase_pulita, ""])
            report.append(f"✅ Mood {m}: {frase_pulita}")
            
            time.sleep(15)
            
        except Exception as e:
            report.append(f"❌ Errore Mood {m}: {e}")
            time.sleep(15)

    return report

if __name__ == "__main__":
    print(run_agent())
