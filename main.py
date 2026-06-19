import os
import logging
from flask import Flask
from threading import Thread
from telegram.ext import Application, CommandHandler, ContextTypes
import ccxt
import pandas as pd

# ---------- CONFIG ----------
TELEGRAM_BOT_TOKEN = os.environ["8487551708:AAE4G5ioDGRq8G6ytbL_KgkjeoQqKuEYVvo"]
openai.api_key = os.environ.get("OPENAI_API_KEY", "")
YOUR_CHAT_ID = int(os.environ["8487551708"])
AI_ENABLED = bool(OPENAI_API_KEY)
SYMBOLS = ["SOL/USDT", "BTC/USDT", "ETH/USDT"]
SCAN_INTERVAL = 15 * 60  # seconds

logging.basicConfig(level=logging.INFO)

# ---------- Flask server to keep alive ----------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# ---------- Trading logic (unchanged) ----------
def fetch_ohlcv(symbol='SOL/USDT', timeframe='5m', limit=100):
    exchange = ccxt.binance()
    bars = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp','open','high','low','close','volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def detect_breakout(df, symbol):
    df['high_20'] = df['high'].rolling(20).max()
    df['low_20'] = df['low'].rolling(20).min()
    df['avg_vol'] = df['volume'].rolling(20).mean()
    last, prev = df.iloc[-1], df.iloc[-2]
    signal = None
    if last['close'] > prev['high_20'] and last['volume'] > last['avg_vol'] * 1.5:
        signal = 'BUY'
    elif last['close'] < prev['low_20'] and last['volume'] > last['avg_vol'] * 1.5:
        signal = 'SELL'
    if signal:
        atr = (df['high'].rolling(14).max() - df['low'].rolling(14).min()).iloc[-1]
        sl = last['close'] - atr * 1.5 if signal == 'BUY' else last['close'] + atr * 1.5
        tp = last['close'] + atr * 3 if signal == 'BUY' else last['close'] - atr * 3
        return {
            'symbol': symbol, 'signal': signal,
            'entry': round(last['close'], 4),
            'stop_loss': round(sl, 4), 'take_profit': round(tp, 4)
        }
    return None

def ai_confidence(signal):
    if not AI_ENABLED:
        return 80
    import openai
    openai.api_key = OPENAI_API_KEY
    prompt = f"Trade: {signal['signal']} {signal['symbol']} at {signal['entry']}. Chance of profit in 4h? 0-100."
    try:
        resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], max_tokens=5, temperature=0)
        return int(resp.choices[0].message.content.strip().replace('%',''))
    except:
        return 50

async def scan_and_alert(context: ContextTypes.DEFAULT_TYPE):
    for sym in SYMBOLS:
        try:
            df = fetch_ohlcv(sym)
            signal = detect_breakout(df, sym)
            if signal:
                conf = ai_confidence(signal)
                if conf >= 70:
                    msg = f"🚨 {signal['signal']} {signal['symbol']}\nEntry: {signal['entry']}\nStop: {signal['stop_loss']}\nTP: {signal['take_profit']}\nConf: {conf}%"
                    await context.bot.send_message(chat_id=YOUR_CHAT_ID, text=msg)
        except Exception as e:
            logging.error(f"{sym}: {e}")

async def start(update, context):
    await update.message.reply_text("Bot online. Scanning every 15 min.")

async def signals_cmd(update, context):
    await update.message.reply_text("Manual scan...")
    await scan_and_alert(context)

# ---------- Main ----------
def main():
    # Start Flask in a separate thread
    Thread(target=run_flask).start()

    # Start Telegram bot polling
    app_tg = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app_tg.add_handler(CommandHandler("start", start))
    app_tg.add_handler(CommandHandler("signals", signals_cmd))
    app_tg.job_queue.run_repeating(scan_and_alert, interval=SCAN_INTERVAL, first=10)
    app_tg.run_polling()

if __name__ == "__main__":
    main()