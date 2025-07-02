import logging
import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    ContextTypes, filters
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# تعداد ارسال‌ها در روز بر اساس user_id → [count, date]
user_gif_sticker_count = {}

# محدودیت‌های مجاز برای کاربران (user_id → allowed_count)
user_limits = {}

# دستور محدود کردن کاربر با تعداد دلخواه
async def restrict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("مثال:\n/restrict @username 3")
        return

    user_id = None
    username_or_id = context.args[0]
    limit_str = context.args[1]

    try:
        limit = int(limit_str)
    except:
        await update.message.reply_text("عدد معتبر وارد کن برای محدودیت.")
        return

    # اگر آرگومان اول عدد بود
    if username_or_id.isdigit():
        user_id = int(username_or_id)
    else:
        # حذف @ اگر هست
        username = username_or_id
        if username.startswith("@"):
            username = username[1:]
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, username)
            user_id = member.user.id
        except Exception:
            await update.message.reply_text("نتونستم کاربر رو پیدا کنم یا کاربر عضو گروه نیست.")
            return

    user_limits[user_id] = limit
    await update.message.reply_text(f"✅ محدودیت برای کاربر {user_id} روی {limit} گیف/استیکر در روز تنظیم شد.")

# دستور حذف محدودیت
async def unrestrict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("مثال:\n/unrestrict @username")
        return

    user_id = None
    username_or_id = context.args[0]

    if username_or_id.isdigit():
        user_id = int(username_or_id)
    else:
        username = username_or_id
        if username.startswith("@"):
            username = username[1:]
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, username)
            user_id = member.user.id
        except Exception:
            await update.message.reply_text("کاربر پیدا نشد یا عضو گروه نیست.")
            return

    if user_id in user_limits:
        del user_limits[user_id]
        await update.message.reply_text(f"❌ محدودیت برای کاربر {user_id} حذف شد.")
    else:
        await update.message.reply_text("کاربر محدود نشده بوده.")

# بررسی پیام‌ها
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.effective_user.id
    message = update.message

    # بررسی اینکه پیام گیف یا استیکر هست یا نه
    if message.sticker or message.animation:
        today = datetime.now().date()

        if user_id in user_limits:
            count, last_date = user_gif_sticker_count.get(user_id, (0, today))
            if last_date != today:
                count = 0  # ریست روزانه
            count += 1

            if count > user_limits[user_id]:
                await message.delete()
                await context.bot.send_message(
                    chat_id=message.chat_id,
                    text=f"⚠️ شما فقط {user_limits[user_id]} عدد گیف یا استیکر در روز می‌تونید بفرستید."
                )
            else:
                user_gif_sticker_count[user_id] = (count, today)

# راه‌اندازی ربات
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    TOKEN = os.getenv("BOT_TOKEN")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("restrict", restrict))
    app.add_handler(CommandHandler("unrestrict", unrestrict))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    print("✅ ربات فعال شد.")
    app.run_polling()
