import os
import pandas as pd
import gspread
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
import json
import streamlit as st

def run_agent():
    # SETUP CREDENZIALI
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
    
    dati = pd.DataFrame(sheet.get_all_records())
    moods = ["Buongiorno", "Triste", "Felice", "Nostalgica", "Stressata"]
    report = []
    
    for m in moods:
        try:
            # Recupera esempi
            if not dati.empty and 'Mood' in dati.columns:
                esempi_df = dati[dati['Mood'] == m]['Link_Testo']
                esempi = esempi_df.tail(3).tolist() if not esempi_df.empty else ["Nessun esempio"]
            else:
                esempi = ["Ti amo", "Sei unica"] 
            
            # --- QUI USIAMO IL TUO MODELLO NUOVO ---
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            prompt = f"Scrivi una frase breve (max 15 parole) per la mia ragazza. Mood: {m}. Esempi: {esempi}"
            response = model.generate_content(prompt)
            nuova_frase = response.text.strip().replace('"', '')
            
            sheet.append_row([m, "Frase", nuova_frase, ""])
            report.append(f"✅ {m}: {nuova_frase}")
            
        except Exception as e:
            report.append(f"❌ Errore {m}: {e}")
            
    return report

if __name__ == "__main__":
    print(run_agent())
