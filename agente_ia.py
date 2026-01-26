import os
import pandas as pd
import gspread
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
import json
import streamlit as st
import time

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
            
            # USIAMO IL MODELLO 2.5 FLASH
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            # --- PROMPT BLINDATO ---
            # Gli diamo regole severe per evitare elenchi o commenti
            prompt = f"""
            Il tuo compito è generare ESATTAMENTE UNA singola frase romantica per la mia ragazza.
            
            MOOD RICHIESTO: {m}
            STILE: Breve (max 15 parole), dolce, intimo.
            ESEMPI DAL PASSATO (Imita questo stile): {esempi}

            REGOLE TASSATIVE (VIETATO SGARRARE):
            1. Rispondi SOLO con il testo della frase.
            2. NON mettere elenchi puntati.
            3. NON scrivere "Ecco alcune opzioni".
            4. NON scrivere il conteggio delle parole tra parentesi (es. "10 parole").
            5. NON usare virgolette.
            6. Devi produrre UNA sola riga di testo.
            """
            
            response = model.generate_content(prompt)
            
            # --- PULIZIA EXTRA (Python) ---
            # Se l'IA disubbidisce, puliamo noi il testo a forza
            testo_grezzo = response.text.strip()
            
            # 1. Se ci sono più righe, prendiamo solo la prima (che di solito è la frase migliore)
            prima_riga = testo_grezzo.split('\n')[0]
            
            # 2. Rimuoviamo caratteri sporchi (asterischi, virgolette, trattini elenco)
            nuova_frase = prima_riga.replace('*', '').replace('"', '').replace('-', '').strip()
            
            # 3. Rimuoviamo eventuali parentesi finali tipo "(10 parole)" se sono rimaste
            if "(" in nuova_frase:
                nuova_frase = nuova_frase.split('(')[0].strip()
            
            sheet.append_row([m, "Frase", nuova_frase, ""])
            report.append(f"✅ {m}: {nuova_frase}")
            
            # PAUSA ANTI-BLOCCO (15 secondi)
            time.sleep(15)
            
        except Exception as e:
            report.append(f"❌ Errore {m}: {e}")
            time.sleep(15)
            
    return report

if __name__ == "__main__":
    print(run_agent())
