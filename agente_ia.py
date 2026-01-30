import os
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import json
import telebot
import time
import requests
import threading
from datetime import datetime, timedelta

# --- CONFIGURAZIONE SICURA ---
def get_env_var(key):
    return os.environ.get(key)

TELEGRAM_TOKEN = get_env_var("TELEGRAM_TOKEN")
CHAT_ID = get_env_var("TELEGRAM_CHAT_ID")
GEMINI_KEY = get_env_var("GEMINI_API_KEY")
GOOGLE_JSON = get_env_var("GOOGLE_SHEETS_JSON")

SHEET_NAME = "CuboAmoreDB"
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- CONNESSIONE ---
def get_connection():
    creds_dict = json.loads(GOOGLE_JSON)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    client = gspread.authorize(creds)
    return client

# --- CALCOLO STATISTICHE & REPORT ---
def analizza_e_salva_stats(client):
    try:
        db = client.open(SHEET_NAME)
        sheet_log = db.worksheet("Log_Mood")
        df = pd.DataFrame(sheet_log.get_all_records())
        if df.empty: return "Nessun dato nel Log."
        
        conteggio = df['Mood'].value_counts().to_dict()
        oggi = datetime.now().strftime("%Y-%m-%d")
        
        report_text = "\n📊 **Report Attività:**\n"
        riga_excel = [oggi]
        
        moods_order = ["Triste", "Felice", "Nostalgica", "Stressata", "Pensiero", "Buongiorno"]
        for m in moods_order:
            num = conteggio.get(m, 0)
            report_text += f"- {m}: {num}\n"
            riga_excel.append(num)

        try:
            sheet_report = db.worksheet("Report_Settimanali")
        except:
            sheet_report = db.add_worksheet(title="Report_Settimanali", rows=100, cols=10)
            sheet_report.append_row(["Data Report", "Triste", "Felice", "Nostalgica", "Stressata", "Pensiero", "Buongiorno"])
        
        sheet_report.append_row(riga_excel)
        return report_text
    except Exception as e:
        return f"\n⚠️ Errore statistiche: {e}"

# --- GENERAZIONE CONTENUTI (4 SETTIMANE) ---
def run_ai_generation():
    try:
        client = get_connection()
        db = client.open(SHEET_NAME)
        
        # Setup Fogli
        try: ws_cal = db.worksheet("Calendario")
        except: ws_cal = db.add_worksheet("Calendario", 2000, 5); ws_cal.append_row(["Data", "Mood", "Frase", "Tipo", "Marker"])
        try: ws_emo = db.worksheet("Emozioni")
        except: ws_emo = db.add_worksheet("Emozioni", 2000, 4); ws_emo.append_row(["Mood", "Frase", "Tipo", "Marker"])

        # Trova data inizio
        df_cal = pd.DataFrame(ws_cal.get_all_records())
        if df_cal.empty: data_partenza = datetime.now()
        else:
            df_cal['Data'] = pd.to_datetime(df_cal['Data'], format="%Y-%m-%d", errors='coerce')
            data_partenza = df_cal['Data'].max() + timedelta(days=1)

        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
        
        bot.send_message(CHAT_ID, f"🚀 Avvio generazione 4 settimane.\n📅 Inizio: {data_partenza.strftime('%d-%m-%Y')}")

        for settimana in range(4):
            prompt = f"""
            Sei un fidanzato innamorato. Genera contenuti per 1 settimana.
            Usa i soprannomi: Tata, Cucciola, Baby, Bimba.
            OUTPUT JSON: chiavi "Buongiorno", "Triste", "Felice", "Nostalgica", "Stressata", "Pensiero".
            REGOLE:
            1. "Buongiorno": 7 frasi uniche e dolci.
            2. Mood: 5 frasi ciascuno.
            3. "Pensiero": 5 frasi brevissime (max 6 parole).
            """
            response = model.generate_content(prompt)
            dati = json.loads(response.text)

            rows_c, rows_e = [], []
            for i, f in enumerate(dati.get("Buongiorno", [])):
                d_target = data_partenza + timedelta(days=(settimana*7)+i)
                rows_c.append([d_target.strftime("%Y-%m-%d"), "Buongiorno", f, "AI", ""])
            
            for k, v in dati.items():
                if k != "Buongiorno":
                    for f in v: rows_e.append([k, f, "AI", "AVAILABLE"])

            if rows_c: ws_cal.append_rows(rows_c)
            if rows_e: ws_emo.append_rows(rows_e)
            time.sleep(2)

        stats = analizza_e_salva_stats(client)
        bot.send_message(CHAT_ID, f"✅ Generazione completata!\n{stats}")

    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Errore IA: {e}")

# --- BOT COMMANDS ---
@bot.message_handler(commands=['accendi'])
def accendi(m):
    db = get_connection().open(SHEET_NAME).worksheet("Config")
    db.update_acell('B1', 'ON')
    db.update_acell('B2', 'PENSIERO')
    bot.reply_to(m, "💡 Lampada ON - Modalità 'Ti sto pensando' attivata.")

@bot.message_handler(commands=['spegni'])
def spegni(m):
    get_connection().open(SHEET_NAME).worksheet("Config").update_acell('B1', 'OFF')
    bot.reply_to(m, "🌑 Lampada OFF.")

@bot.message_handler(commands=['genera'])
def genera(m):
    run_ai_generation()

# --- BACKGROUND THREAD ---
def auto_check():
    while True:
        try:
            db = get_connection().open(SHEET_NAME).worksheet("Calendario")
            df = pd.DataFrame(db.get_all_records())
            df['Data'] = pd.to_datetime(df['Data'], format="%Y-%m-%d", errors='coerce')
            if df['Data'].max() < datetime.now() + timedelta(days=3):
                run_ai_generation()
        except: pass
        time.sleep(14400)

threading.Thread(target=auto_check, daemon=True).start()
bot.infinity_polling(skip_pending=True)
