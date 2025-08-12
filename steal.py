import asyncio
import time
import logging
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
from collections import defaultdict

TOKEN = "8159109377:AAHEO1b7CvTFVK2FwX_JWpU2qIp7fI8wMpQ"

MAIN_CHAT_ID = -1002632466747
LOG_CHAT_ID = -1002815139220

MAX_MESSAGES = 5
INTERVAL = 30
MUTE_DURATION_MINUTES = 30

# Логирование только наших сообщений (убираем httpx debug)
logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  
logger = logging.getLogger("antiflood_bot")

user_messages = defaultdict(list)

def local_time_str():
    return datetime.now().strftime("%H:%M:%S")

# Команды
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(f"Ваш ID: `{update.effective_user.id}`", parse_mode="Markdown")

async def chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(f"ID чата: `{update.effective_chat.id}`", parse_mode="Markdown")

# Пинг-понг
async def ping_pong(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if update.message.text.strip().lower() == "пинг":
        await update.message.reply_text("Понг 🏓")

# Антифлуд
async def antiflood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_chat.id != MAIN_CHAT_ID:
            return
        if update.effective_user.is_bot:
            return

        user_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name or "User"
        mention_plain = f"@{username}" if username else None
        mention_md = f"[{first_name}](tg://user?id={user_id})"

        now_ts = time.time()
        user_messages[user_id].append(now_ts)
        user_messages[user_id] = [t for t in user_messages[user_id] if now_ts - t <= INTERVAL]

        if len(user_messages[user_id]) >= MAX_MESSAGES:
            user_messages[user_id].clear()
            current_time = local_time_str()

            member = await context.bot.get_chat_member(MAIN_CHAT_ID, user_id)
            if member.status in ("administrator", "creator"):
                msg = f"{mention_plain or mention_md} не получил мут в `{current_time}` (админ)"
                logger.info(msg)
                await context.bot.send_message(chat_id=LOG_CHAT_ID, text=msg, parse_mode="Markdown")
                return

            bot = await context.bot.get_me()
            bot_member = await context.bot.get_chat_member(MAIN_CHAT_ID, bot.id)
            if bot_member.status != "creator" and not getattr(bot_member, "can_restrict_members", False):
                msg = f"Бот не имеет права мутить участников в чате `{MAIN_CHAT_ID}`"
                logger.info(msg)
                await context.bot.send_message(chat_id=LOG_CHAT_ID, text=msg, parse_mode="Markdown")
                return

            until_ts = int(time.time() + MUTE_DURATION_MINUTES * 60)
            try:
                await context.bot.restrict_chat_member(
                    chat_id=MAIN_CHAT_ID,
                    user_id=user_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until_ts,
                )
                msg = f"{mention_plain or mention_md} получил мут на `{MUTE_DURATION_MINUTES}` минут в `{current_time}` (антифлуд)"
                logger.info(msg)
                await context.bot.send_message(chat_id=LOG_CHAT_ID, text=msg, parse_mode="Markdown")
            except Exception as e:
                msg = f"{mention_plain or mention_md} не получил мут в `{current_time}` (ошибка: {e})"
                logger.info(msg)
                await context.bot.send_message(chat_id=LOG_CHAT_ID, text=msg, parse_mode="Markdown")

    except Exception as e:
        msg = f"Ошибка в антифлуде: {e}"
        logger.info(msg)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("chatid", chatid))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, antiflood))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ping_pong))

    app.run_polling()

if __name__ == "__main__":
    main()
