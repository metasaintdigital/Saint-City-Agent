import os
import logging
import smtplib
from email.message import EmailMessage
from datetime import datetime
import google.generativeai as genai
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ==============================================================================
# CONFIGURATION & MEMORY
# ==============================================================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_KEY')
YOUR_EMAIL = os.getenv('YOUR_EMAIL')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD') # Gmail App Password

genai.configure(api_key=GEMINI_KEY)

# Using latest stable models
MODEL_FLASH = 'gemini-2.5-flash'
MODEL_PRO = 'gemini-2.5-pro'

# In-memory state tracking (Mode and Reflection Turn)
user_states = {}

HARDCODED_SAGE_CONTEXT = """
Future Malik — Sage Context
This is Malik Saint St. Hilaire — 20 years from now.
Not a fantasy. A destination.
He has built Saint City based on Mansa Musa's wealth infrastructure and Jesus's wisdom.
He is not frantic. He does not lecture. He asks.
One question at a time. Never stacked.
If Malik says "brainstorm" or "game plan", give 3 specific moves connecting micro actions to macro goals.
"""

HARDCODED_Q2_GOALS = """
12-Week Goals — Q2 2026
Pillar 1: Agency - 15 clients on monthly subscription, ads running. $10k MRR.
Pillar 2: AI for Business 101 - Course launched as lead nurture funnel.
Pillar 3: Thought Leadership - Belize government partnership, US small business reach.
"""

# ==============================================================================
# HELPERS: LOGGING & EMAIL
# ==============================================================================

def append_to_daily_log(text):
    date_str = datetime.now().strftime('%Y-%m-%d')
    filename = f"Daily_Log.md"
    mode = 'a' if os.path.exists(filename) else 'w'
    with open(filename, mode, encoding='utf-8') as f:
        if mode == 'w':
            f.write(f"# Raw Daily Log - {date_str}\n\n")
        f.write(text + "\n")

def package_and_email_log():
    filename = f"Daily_Log.md"
    if not os.path.exists(filename):
        return

    date_str = datetime.now().strftime('%Y-%m-%d')
    msg = EmailMessage()
    msg['Subject'] = f"Saint City Infrastructure: End of Day Log [{date_str}]"
    msg['From'] = YOUR_EMAIL
    msg['To'] = YOUR_EMAIL
    msg.set_content("Malik, here is the raw flight recorder data from today. Drop this file into Claude to process into the Obsidian Vault. Rest well.")

    with open(filename, 'rb') as f:
        msg.add_attachment(f.read(), maintype='text', subtype='markdown', filename=f"Malik_Daily_Log_{date_str}.md")

    # Send via Gmail SMTP
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(YOUR_EMAIL, EMAIL_PASSWORD)
            smtp.send_message(msg)
        # Wipe file after sending
        os.remove(filename)
    except Exception as e:
        print(f"Email failed: {e}")

# ==============================================================================
# GEMINI ENGINE
# ==============================================================================

async def call_gemini(user_text, audio_path, model_name, system_instruction):
    try:
        model = genai.GenerativeModel(model_name, system_instruction=system_instruction)
        contents = []
        
        if audio_path:
            # Upload audio to Gemini
            audio_file = genai.upload_file(path=audio_path)
            contents.append(audio_file)
            
        if user_text:
            contents.append(user_text)

        response = model.generate_content(contents)
        
        # Cleanup uploaded file
        if audio_path:
            genai.delete_file(audio_file.name)
            
        return response.text
    except Exception as e:
        return f"[System Alert - AI Engine Failed]: {str(e)}"

# ==============================================================================
# MESSAGE ROUTING
# ==============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text or ""
    
    # Initialize state
    if chat_id not in user_states:
        user_states[chat_id] = {'mode': 'LOG', 'reflect_turn': 1}

    # KEYBOARD ROUTING
    if text == "📝 Log It":
        user_states[chat_id]['mode'] = 'LOG'
        await update.message.reply_text("Log It mode active. Speak or type. What just happened?")
        return
    elif text == "🧠 Sage Mode":
        user_states[chat_id]['mode'] = 'SAGE'
        await update.message.reply_text("Sage Mode active. Future Malik is listening.")
        return
    elif text == "🌙 Reflect":
        user_states[chat_id]['mode'] = 'REFLECT'
        user_states[chat_id]['reflect_turn'] = 1
        await update.message.reply_text("Evening Reflection. Turn 1: Walk me through today. What actually happened?")
        return

    # Let Telegram know we are thinking (stops the loop)
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    # Process Audio if exists
    audio_path = None
    if update.message.voice:
        file = await context.bot.get_file(update.message.voice.file_id)
        audio_path = f"temp_voice_{chat_id}.ogg"
        await file.download_to_drive(audio_path)

    current_mode = user_states[chat_id]['mode']

    if current_mode == 'LOG':
        sys_prompt = "You are Malik's AI agent. Context: Father, ELN Founder, building Saint City. Keep responses under 100 words. Acknowledge exactly what he said, then ask ONE question connecting it to his Q2 goals. Conversational."
        user_prompt = text if text else "Listen to this voice note and process the log."
        
        reply = await call_gemini(user_prompt, audio_path, MODEL_FLASH, sys_prompt)
        await update.message.reply_text(reply)
        append_to_daily_log(f"\n### Log [{datetime.now().strftime('%H:%M:%S')}]\n**Malik:** {text or '[Voice]'}\n**Agent:** {reply}")

    elif current_mode == 'SAGE':
        sys_prompt = f"You are Future Malik (20 years from now).\n\nSAGE CONTEXT:\n{HARDCODED_SAGE_CONTEXT}\n\nQ2 GOALS:\n{HARDCODED_Q2_GOALS}"
        user_prompt = text if text else "Listen to my voice note and respond as Future Malik."
        
        reply = await call_gemini(user_prompt, audio_path, MODEL_PRO, sys_prompt)
        await update.message.reply_text(reply)
        append_to_daily_log(f"\n### Sage Mode [{datetime.now().strftime('%H:%M:%S')}]\n**Malik:** {text or '[Voice]'}\n**Future Malik:** {reply}")

    elif current_mode == 'REFLECT':
        turn = user_states[chat_id]['reflect_turn']
        sys_prompt = "You are guiding Malik's 5-turn evening reflection. Warm, honest, holding the mirror steady.\nTurn 1: What happened?\nTurn 2: Acknowledge & ask what got in the way.\nTurn 3: Is the blocker recurring?\nTurn 4: What was shipped and what was chopped?\nTurn 5: Summarize, confirm handoff, wish him rest."
        user_prompt = f"I am on Turn {turn}. Here is my input: {text or '[Voice]'}. Advance to the next turn's response."
        
        reply = await call_gemini(user_prompt, audio_path, MODEL_FLASH, sys_prompt)
        await update.message.reply_text(reply)
        append_to_daily_log(f"\n**Reflection Turn {turn}:**\n**Malik:** {text or '[Voice]'}\n**Agent:** {reply}")

        if turn >= 4:
            package_and_email_log()
            user_states[chat_id]['mode'] = 'LOG'
            user_states[chat_id]['reflect_turn'] = 1
        else:
            user_states[chat_id]['reflect_turn'] += 1

    # Cleanup local audio file
    if audio_path and os.path.exists(audio_path):
        os.remove(audio_path)

# ==============================================================================
# MAIN ENGINE LAUNCH
# ==============================================================================

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT | filters.VOICE, handle_message))
    print("Saint City Infrastructure Python Engine Online...")
    app.run_polling(drop_pending_updates=True) # THIS KILLS ALL GHOST LOOPS AUTOMATICALLY

if __name__ == '__main__':
    main()
