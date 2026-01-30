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

# --- RECUPERO CHIAVI ---
TELEGRAM_TOKEN = "8583117209:AAHJkbze27JpY-ubsusIIruUg_qiGCZuqyE"
CHAT_ID = "1627105623"
GEMINI_KEY = "AIzaSyDYCtkkOZSti09UcpUpx-mbCWZx55wtxNo"
# Usa le credenziali che hai già nel sistema
from credentials_dict import GOOGLE_CREDS_DICT 

SHEET_NAME = "CuboAmoreDB"
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def get_connection():
    creds = Credentials.from_service_account_info(GOOGLE_CREDS_DICT, scopes=SCOPE)
    return gspread.authorize(creds).open(SHEET_NAME)

# --- STATISTICHE & REPORT ---
def analizza_e_salva_stats(client):
    try:
        ws_log = client.worksheet("Log_Mood")
        df = pd.DataFrame(ws_log.get_all_records())
        if df.empty: return "Nessun dato."
        
        conteggio = df['Mood'].value_counts().to_dict()
        oggi = datetime.now().strftime("%Y-%m-%d")
        
        moods = ["Triste", "Felice", "Nostalgica", "Stressata", "Pensiero", "Buongiorno"]
        riga = [oggi] + [conteggio.get(m, 0) for m in moods]

        try: ws_rep = client.worksheet("Report_Settimanali")
        except: 
            ws_rep = client.add_worksheet("Report_Settimanali", 100, 7)
            ws_rep.append_row(["Data Report", "Triste", "Felice", "Nostalgica", "Stressata", "Pensiero", "Buongiorno"])
        
        ws_rep.append_row(riga)
        return f"📊 Stats: {conteggio}"
    except: return "⚠️ Errore statistiche."

# --- GENERATORE 4 SETTIMANE ---
def run_ai_generation():
    try:
        db = get_connection()
        ws_cal = db.worksheet("Calendario")
        ws_emo = db.worksheet("Emozioni")

        df_cal = pd.DataFrame(ws_cal.get_all_records())
        if df_cal.empty: start = datetime.now()
        else:
            df_cal['Data'] = pd.to_datetime(df_cal['Data'], format="%Y-%m-%d", errors='coerce')
            start = df_cal['Data'].max() + timedelta(days=1)

        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
        
        bot.send_message(CHAT_ID, f"🚀 Genero 4 settimane dal {start.strftime('%d/%m')}")

        for s in range(4):
            prompt = f"""
            Sei un fidanzato innamorato. Genera 1 settimana di contenuti.
            Usa i soprannomi: Tata, Cucciola, Baby, Bimba.
            JSON: "Buongiorno" (7), "Triste" (5), "Felice" (5), "Nostalgica" (5), "Stressata" (5), "Pensiero" (5).
            'Pensiero' deve essere brevissimo (max 5 parole).
            """
            res = model.generate_content(prompt)
            dati = json.loads(res.text)

            rows_c, rows_e = [], []
            for i, f in enumerate(dati.get("Buongiorno", [])):
                dt = start + timedelta(days=(s*7)+i)
                rows_c.append([dt.strftime("%Y-%m-%d"), "Buongiorno", f, "AI", ""])
            for k, v in dati.items():
                if k != "Buongiorno":
                    for f in v: rows_e.append([k, f, "AI", "AVAILABLE"])
            ws_cal.append_rows(rows_c)
            ws_emo.append_rows(rows_e)
            time.sleep(2)

        bot.send_message(CHAT_ID, f"✅ Generazione completata. {analizza_e_salva_stats(db)}")
    except Exception as e: bot.send_message(CHAT_ID, f"❌ Errore IA: {e}")

# --- COMANDI BOT ---
@bot.message_handler(commands=['accendi', 'on'])
def on(m):
    ws = get_connection().worksheet("Config")
    ws.update_acell('B1', 'ON')
    ws.update_acell('B2', 'PENSIERO') # Override priorità
    bot.reply_to(m, "💡 Lampada ON - Modalità Pensiero ❤️")

@bot.message_handler(commands=['spegni', 'off'])
def off(m):
    ws = get_connection().worksheet("Config")
    ws.update_acell('B1', 'OFF')
    ws.update_acell('B2', 'NONE')
    bot.reply_to(m, "🌑 Lampada OFF.")

@bot.message_handler(commands=['genera'])
def gen(m): run_ai_generation()

# Thread per controllo automatico calendario
def auto_check():
    while True:
        try:
            ws = get_connection().worksheet("Calendario")
            df = pd.DataFrame(ws.get_all_records())
            df['Data'] = pd.to_datetime(df['Data'], format="%Y-%m-%d", errors='coerce')
            if df['Data'].max() < datetime.now() + timedelta(days=3): run_ai_generation()
        except: pass
        time.sleep(14400)

threading.Thread(target=auto_check, daemon=True).start()
bot.infinity_polling(skip_pending=True)
