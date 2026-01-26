import os
import pandas as pd
import gspread
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
import json
import streamlit as st
import time
from datetime import datetime, timedelta

def run_agent():
    # --- SETUP ---
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

    # CONFIGURAZIONE MODELLO PER JSON PURO
    # Questo risolve l'errore "Expecting delimiter"
    generation_config = {
        "temperature": 1,
        "response_mime_type": "application/json",
    }
    model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
    
    report = []
    moods = ["Buongiorno", "Triste", "Felice", "Nostalgica", "Stressata"]
    oggi = datetime.now()

    for m in moods:
        try:
            # PROMPT OTTIMIZZATO
            prompt = f"""
            Sei un fidanzato innamorato. Genera una lista di 7 frasi per il mood: {m}.
            
            REGOLE:
            - 5 frasi tue, originali, dolci (max 15 parole).
            - 2 frasi DEVONO essere citazioni celebri (Film, Libri, Canzoni) coerenti col mood.
            - NON usare mai queste frasi recenti: {str(frasi_usate_recenti[-10:])}
            
            OUTPUT: Devi rispondere ESCLUSIVAMENTE con un array JSON di stringhe.
            Esempio: ["Frase 1", "Frase 2", "Frase 3 (Citazione)"]
            """

            response = model.generate_content(prompt)
            
            # Parsing JSON (Ora è sicuro grazie al mime_type)
            lista_frasi = json.loads(response.text)
            
            count = 0
            for frase in lista_frasi:
                if frase in frasi_usate_recenti:
                    continue 
                
                data_str = ""
                if m == "Buongiorno":
                    data_target = oggi + timedelta(days=count)
                    data_str = data_target.strftime("%Y-%m-%d")
                
                sheet.append_row([m, "Frase", frase, data_str])
                count += 1
            
            report.append(f"✅ {m}: Generate {count} nuove frasi.")
            time.sleep(10) # Pausa anti-blocco
            
        except Exception as e:
            report.append(f"❌ Errore {m}: {e}")
            time.sleep(10)

    return report

if __name__ == "__main__":
    print(run_agent())
