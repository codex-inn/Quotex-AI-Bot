"""Telegram-only demo analysis bot. No broker connection or trade execution."""
import os, asyncio, logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from market_data import fetch_candles
from analyzer import analyze

load_dotenv()
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
log=logging.getLogger("quotex-ai")
PAIRS=[p.strip() for p in os.getenv("PAIRS","EUR/USD,GBP/USD,USD/JPY,USD/CHF,AUD/USD,USD/CAD,NZD/USD").split(",") if p.strip()]
MIN_SCORE=int(os.getenv("MIN_SCORE","4"))
CHAT_ID=os.getenv("TELEGRAM_CHAT_ID","").strip()

def format_signal(pair, result):
    icon="🟢" if result["signal"]=="CALL" else ("🔴" if result["signal"]=="PUT" else "⚪")
    lines=[f"{icon} DEMO ANALYSIS — {pair}",f"Signal: {result['signal']}",
      f"Rule score: {result.get('score',0)}/5 (not a probability)",
      f"RSI: {result.get('rsi','n/a')}",f"Patterns: {', '.join(result.get('patterns',[])) or 'none'}",
      f"Candle: {result.get('candle_time','unknown')}",
      "Reasons: "+("; ".join(result.get("reasons",[])) or "No confirmation"),
      "External spot-FX data; not Quotex OTC. No trade was placed."]
    return "\n".join(lines)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Quotex AI Analysis Bot — DEMO ONLY. Commands: /scan, /pairs, /help. No orders are executed.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/scan — analyse configured forex pairs\n/pairs — list pairs\n/chatid — show this chat ID for deployment setup\nSignals are educational rule-based alerts, not probabilities or financial advice.")

async def pairs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Configured pairs: "+", ".join(PAIRS))

async def chatid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram chat ID is: {update.effective_chat.id}\\nAdd this as TELEGRAM_CHAT_ID in your cloud host environment variables.")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg=await update.message.reply_text("Fetching 1-minute candles and analysing…")
    outputs=[]
    for pair in PAIRS:
        try:
            df=await asyncio.to_thread(fetch_candles,pair,120)
            result=analyze(df,MIN_SCORE)
            outputs.append(format_signal(pair,result))
        except Exception as exc:
            log.warning("Pair %s skipped: %s",pair,exc)
            outputs.append(f"⚠️ {pair}: data unavailable ({exc})")
    text="\n\n".join(outputs)
    for i in range(0,len(text),3900):
        await msg.reply_text(text[i:i+3900])

async def scheduled_scan(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID: return
    outputs=[]
    for pair in PAIRS:
        try:
            df=await asyncio.to_thread(fetch_candles,pair,120)
            result=analyze(df,MIN_SCORE)
            if result["signal"]!="NO TRADE": outputs.append(format_signal(pair,result))
        except Exception as exc: log.warning("Scheduled %s failed: %s",pair,exc)
    if outputs:
        await context.bot.send_message(chat_id=CHAT_ID,text="\n\n".join(outputs)[:4000])

def main():
    token=os.getenv("TELEGRAM_BOT_TOKEN","").strip()
    if not token: raise SystemExit("Set TELEGRAM_BOT_TOKEN in environment")
    app=Application.builder().token(token).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("help",help_cmd))
    app.add_handler(CommandHandler("pairs",pairs_cmd))
    app.add_handler(CommandHandler("chatid",chatid_cmd))
    app.add_handler(CommandHandler("scan",scan))
    seconds=max(60,int(os.getenv("POLL_SECONDS","60")))
    if app.job_queue and CHAT_ID:
        app.job_queue.run_repeating(scheduled_scan,interval=seconds,first=10)
    app.run_polling()

if __name__=="__main__": main()
