import os
import pandas as pd
import gspread
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
import json
import streamlit as st
import time
from datetime import datetime, timedelta
import random

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
    
    # --- MEMORIA (Anti-Repetizione) ---
    # Scarichiamo tutto il DB per controllare i duplicati
    df = pd.DataFrame(sheet.get_all_records())
    frasi_usate_recenti = []
    
    if not df.empty and 'Link_Testo' in df.columns:
        # Prendiamo le ultime 100 frasi (circa 1 mese di storico abbondante)
        frasi_usate_recenti = df['Link_Testo'].tail(150).tolist()

    model = genai.GenerativeModel('gemini-2.5-flash')
    report = []
    
    # Lista dei Mood da generare
    moods = ["Buongiorno", "Triste", "Felice", "Nostalgica", "Stressata"]
    
    oggi = datetime.now()

    for m in moods:
        try:
            # --- COSTRUZIONE DEL PROMPT INTELLIGENTE ---
            # Chiediamo 7 frasi in un colpo solo (Batch) per risparmiare richieste API
            
            prompt = f"""
            Agisci come un fidanzato innamorato e colto.
            Il tuo compito è generare una lista JSON di 7 frasi diverse per il mood: {m}.
            
            REGOLE DI CONTENUTO:
            - Totale frasi: 7
            - 5 frasi devono essere pensieri tuoi, dolci e diretti (max 15 parole).
            - 2 frasi DEVONO essere citazioni celebri (Film, Canzoni, Poesie, Libri) coerenti col mood.
              Per le citazioni: metti la frase tra virgolette e l'autore/fonte alla fine.
              Esempio citazione: "L'amor che move il sole e l'altre stelle." (Dante)
            
            REGOLE DI MEMORIA:
            - NON generare frasi uguali o troppo simili a queste usate di recente: {str(frasi_usate_recenti[-20:])}
            
            FORMATO OUTPUT RICHIESTO (Solo JSON Array puro, nient'altro):
            ["Frase 1...", "Frase 2...", "Frase 3 (Citazione)...", ...]
            """

            response = model.generate_content(prompt)
            
            # Pulizia e Parsing del JSON
            text_resp = response.text.strip()
            # A volte Gemini mette ```json all'inizio, lo togliamo
            if "```" in text_resp:
                text_resp = text_resp.replace("```json", "").replace("```", "")
            
            lista_frasi = json.loads(text_resp)
            
            # --- SALVATAGGIO ---
            count = 0
            for i, frase in enumerate(lista_frasi):
                # Controllo Duplicati Python-Side (Sicurezza extra)
                if frase in frasi_usate_recenti:
                    continue # Salta se esiste già
                
                # Se è Buongiorno, assegniamo una data specifica
                data_str = ""
                if m == "Buongiorno":
                    data_target = oggi + timedelta(days=count) # Usa count invece di i per non saltare giorni se ci sono duplicati
                    data_str = data_target.strftime("%Y-%m-%d")
                
                sheet.append_row([m, "Frase", frase, data_str])
                count += 1
            
            report.append(f"✅ {m}: Generate {count} nuove frasi (incluse citazioni).")
            
            # Pausa di sicurezza per il Rate Limit
            time.sleep(15)
            
        except Exception as e:
            report.append(f"❌ Errore generazione {m}: {e}")
            time.sleep(15)

    return report

if __name__ == "__main__":
    print(run_agent())
