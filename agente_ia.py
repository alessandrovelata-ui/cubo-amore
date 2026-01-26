import os
import pandas as pd
import gspread
import google.generativeai as genai
from oauth2client.service_account import ServiceAccountCredentials
import json

# Setup recupero variabili ambiente
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
GOOGLE_JSON = os.environ["GOOGLE_SHEETS_JSON"]
genai.configure(api_key=GEMINI_KEY)

def genera_frase(mood, esempi):
    model = genai.GenerativeModel('gemini-pro')
    prompt = f"Scrivi una frase breve (max 15 parole) dolce e romantica per la mia ragazza. Mood: {mood}. Esempi stile: {esempi}"
    response = model.generate_content(prompt)
    return response.text.strip()

def main():
    # Decodifica le credenziali JSON
    creds_dict = json.loads(GOOGLE_JSON)
    scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Apre il foglio (assicurati che il nome sia corretto)
    sheet = client.open("CuboAmoreDB").worksheet("Contenuti")
    
    # Legge tutto
    dati = pd.DataFrame(sheet.get_all_records())
    
    # Genera per le 3 categorie
    moods = ["Buongiorno", "Triste", "Felice"]
    
    for m in moods:
        try:
            # Cerca esempi precedenti se esistono
            if not dati.empty and 'Mood' in dati.columns:
                esempi = dati[dati['Mood'] == m]['Link_Testo'].tail(3).tolist()
            else:
                esempi = ["Ti amo", "Sei unica"] # Fallback
            
            # Genera con l'IA
            nuova = genera_frase(m, esempi)
            print(f"Generato per {m}: {nuova}")
            
            # Salva: Mood, Tipo, Testo, Data(vuota)
            sheet.append_row([m, "Frase", nuova, ""])
            
        except Exception as e:
            print(f"Errore generazione {m}: {e}")

if __name__ == "__main__":
    main()
