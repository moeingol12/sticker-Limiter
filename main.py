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

# محدودیت‌های مجاز برای کاربران (user_id → (limit, setter_user_id))
user_limits = {}

async def restrict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat = update.effective_chat
    sender = update.effective_user

    # چک کنیم فقط ادمین‌ها اجازه داشته باشند
    sender_member = await context.bot.get_chat_member(chat.id, sender.id)
    if sender_member.status not in ('administrator', 'creator'):
        await update.message.reply_text("❌ فقط ادمین‌ها می‌توانند این دستور را اجرا کنند.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("مثال:\n/restrict @username 3")
        return

    # تلاش برای پیدا کردن user_id
    target_user_id = None
    if context.args[0].startswith('@'):
        try:
            target_member = await context.bot.get_chat_member(chat.id, context.args[0])
            target_user_id = target_member.user.id
        except:
            await update.message.reply_text("نتوانستم کاربر را پیدا کنم یا عضو گروه نیست.")
            return
    else:
        try:
            target_user_id = int(context.args[0])
        except:
            await update.message.reply_text("شناسه کاربر نامعتبر است.")
            return

    # چک کنیم که روی صاحب گروه محدودیت نگذاریم
    chat_creator = None
    async for member in context.bot.get_chat_administrators(chat.id):
        if member.status == 'creator':
            chat_creator = member.user.id
            break

    if target_user_id == chat_creator:
        await update.message.reply_text("❌ نمی‌توانید روی صاحب گروه محدودیت بگذارید.")
        return

    try:
        limit = int(context.args[1])
        if limit < 0:
            raise ValueError
    except:
        await update.message.reply_text("عدد معتبر وارد کن برای محدودیت (مثلاً 3).")
        return

    user_limits[target_user_id] = (limit, sender.id)
    await update.message.reply_text(f"✅ محدودیت {limit} گیف/استیکر در روز برای کاربر با آی‌دی {target_user_id} تنظیم شد.")

async def unrestrict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat = update.effective_chat
    sender = update.effective_user

    # فقط ادمین‌ها اجازه دارند
    sender_member = await context.bot.get_chat_member(chat.id, sender.id)
    if sender_member.status not in ('administrator', 'creator'):
        await update.message.reply_text("❌ فقط ادمین‌ها می‌توانند این دستور را اجرا کنند.")
        return

    if not context.args:
        await update.message.reply_text("مثال:\n/unrestrict @username")
        return

    target_user_id = None
    if context.args[0].startswith('@'):
        try:
            target_member = await context.bot.get_chat_member(chat.id, context.args[0])
            target_user_id = target_member.user.id
        except:
            await update.message.reply_text("نتوانستم کاربر را پیدا کنم یا عضو گروه نیست.")
            return
    else:
        try:
            target_user_id = int(context.args[0])
        except:
            await update.message.reply_text("شناسه کاربر نامعتبر است.")
            return

    # صاحب گروه کیه؟
    chat_creator = None
    async for member in context.bot.get_chat_administrators(chat.id):
        if member.status == 'creator':
            chat_creator = member.user.id
            break

    if target_user_id == chat_creator:
        await update.message.reply_text("❌ نمی‌توانید محدودیت صاحب گروه را بردارید.")
        return

    # بررسی محدودیت موجود
    if target_user_id not in user_limits:
        await update.message.reply_text("این کاربر محدودیتی نداشته است.")
        return

    limit, setter_id = user_limits[target_user_id]# اگر محدودیت رو صاحب گروه گذاشته باشه، فقط خودش می‌تونه برداره
    if setter_id == chat_creator and sender.id != chat_creator:
        await update.message.reply_text("❌ فقط صاحب گروه می‌تواند محدودیت روی این کاربر را بردارد.")
        return

    # بقیه ادمین‌ها می‌تونن محدودیت‌هایی که خودشون گذاشتند بردارند
    if setter_id != sender.id and sender.id != chat_creator:
        await update.message.reply_text("❌ فقط کسی که محدودیت را گذاشته یا صاحب گروه می‌تواند آن را بردارد.")
        return

    del user_limits[target_user_id]
    await update.message.reply_text(f"✅ محدودیت کاربر با آی‌دی {target_user_id} برداشته شد.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user_id = update.effective_user.id
    message = update.message
    chat = update.effective_chat

    if message.sticker or message.animation:
        today = datetime.now().date()

        if user_id in user_limits:
            count, last_date = user_gif_sticker_count.get(user_id, (0, today))
            if last_date != today:
                count = 0  # ریست روزانه
            count += 1

            limit, _ = user_limits[user_id]

            if count > limit:
                try:
                    await message.delete()
                except:
                    pass  # ممکنه پیام حذف نشه

                await context.bot.send_message(
                    chat_id=chat.id,
                    text=f"⚠️ شما فقط {limit} عدد گیف یا استیکر در روز می‌توانید بفرستید."
                )
            else:
                user_gif_sticker_count[user_id] = (count, today)

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
