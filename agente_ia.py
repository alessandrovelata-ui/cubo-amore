import os
import pandas as pd
import gspread
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
import json
import streamlit as st

# Funzione principale che verrà chiamata dal bottone o dal timer
def run_agent():
    # SETUP CREDENZIALI
    try:
        # Se siamo su Streamlit Cloud
        GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
        creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_JSON"])
    except:
        # Se siamo in locale o GitHub Actions
        GEMINI_KEY = os.environ["GEMINI_API_KEY"]
        GOOGLE_JSON = os.environ["GOOGLE_SHEETS_JSON"]
        creds_dict = json.loads(GOOGLE_JSON)

    genai.configure(api_key=GEMINI_KEY)
    
    # CONNESSIONE DB
    scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("CuboAmoreDB").worksheet("Contenuti")
    
    # LETTURA DATI ESISTENTI
    dati = pd.DataFrame(sheet.get_all_records())
    
    # I 5 MOOD DA GENERARE
    moods = ["Buongiorno", "Triste", "Felice", "Nostalgica", "Stressata"]
    
    report = []
    
    for m in moods:
        try:
            # CERCA ESEMPI PRECEDENTI
            if not dati.empty and 'Mood' in dati.columns:
                esempi_df = dati[dati['Mood'] == m]['Link_Testo']
                if not esempi_df.empty:
                    esempi = esempi_df.tail(3).tolist()
                else:
                    esempi = ["Nessun esempio"]
            else:
                esempi = ["Ti amo", "Sei unica"] 
            
            # --- MODIFICA FONDAMENTALE QUI SOTTO ---
            # Usiamo il modello aggiornato 'gemini-1.5-flash'
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            Agisci come il fidanzato perfetto. Scrivi una frase per la tua ragazza.
            MOOD LEI: {m}
            OBBIETTIVO: {get_obiettivo(m)}
            STILE: Breve (max 15 parole), dolce, diretto.
            ESEMPI PASSATI: {esempi}
            """
            response = model.generate_content(prompt)
            nuova_frase = response.text.strip().replace('"', '')
            
            # SALVA NEL DB
            sheet.append_row([m, "Frase", nuova_frase, ""])
            report.append(f"✅ {m}: {nuova_frase}")
            
        except Exception as e:
            report.append(f"❌ Errore {m}: {e}")
            
    return report

def get_obiettivo(mood):
    if mood == "Buongiorno": return "Motivare e dare amore per la giornata."
    if mood == "Triste": return "Consolare, far sentire la vicinanza."
    if mood == "Felice": return "Celebrare, amplificare la gioia."
    if mood == "Nostalgica": return "Ricordare un momento bello o rassicurare sul futuro."
    if mood == "Stressata": return "Calmare, dire che andrà tutto bene, 'respira'."
    return "Amore."

if __name__ == "__main__":
    print(run_agent())
