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

# تعداد ارسال‌ها در روز بر اساس user_id → (count, date)
user_gif_sticker_count = {}

# محدودیت‌های مجاز برای کاربران (user_id → (allowed_count, set_by_user_id))
user_limits = {}

# دستور محدود کردن کاربر با تعداد دلخواه
async def restrict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    from_user_id = update.effective_user.id
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("این دستور فقط در گروه‌ها قابل استفاده است.")
        return

    # گرفتن اطلاعات ادمین‌ها و صاحب گروه
    member = await context.bot.get_chat_member(chat.id, from_user_id)
    if not member.status in ['administrator', 'creator']:
        await update.message.reply_text("⚠️ فقط ادمین‌ها اجازه استفاده از این دستور را دارند.")
        return

    owner_id = None
    admins = await context.bot.get_chat_administrators(chat.id)
    for admin in admins:
        if admin.status == 'creator':
            owner_id = admin.user.id
            break

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("مثال:\n/restrict @username 3")
        return

    # دریافت user_id هدف
    target_user_id = None
    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
    else:
        username_or_id = context.args[0]
        try:
            if username_or_id.isdigit():
                target_user_id = int(username_or_id)
            else:
                member = await context.bot.get_chat_member(chat.id, username_or_id)
                target_user_id = member.user.id
        except:
            await update.message.reply_text("نتونستم کاربر رو پیدا کنم یا عضو گروه نیست.")
            return

    # بررسی اینکه ادمین بتواند فقط کاربرانی غیر صاحب گروه را محدود کند
    if target_user_id == owner_id and from_user_id != owner_id:
        await update.message.reply_text("❌ فقط صاحب گروه می‌تواند خودش را محدود کند.")
        return

    try:
        limit = int(context.args[1])
    except:
        await update.message.reply_text("عدد معتبر وارد کن برای محدودیت.")
        return

    user_limits[target_user_id] = (limit, from_user_id)
    await update.message.reply_text(f"✅ محدودیت برای کاربر {target_user_id} روی {limit} گیف/استیکر در روز تنظیم شد.")

# دستور حذف محدودیت
async def unrestrict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    from_user_id = update.effective_user.id
    chat = update.effective_chat
    if chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("این دستور فقط در گروه‌ها قابل استفاده است.")
        return

    # گرفتن اطلاعات ادمین‌ها و صاحب گروه
    member = await context.bot.get_chat_member(chat.id, from_user_id)
    if not member.status in ['administrator', 'creator']:
        await update.message.reply_text("⚠️ فقط ادمین‌ها اجازه استفاده از این دستور را دارند.")
        return

    owner_id = None
    admins = await context.bot.get_chat_administrators(chat.id)
    for admin in admins:
        if admin.status == 'creator':
            owner_id = admin.user.id
            break

    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text("مثال:\n/unrestrict @username یا ریپلای پیام کاربر")
        return

    # دریافت user_id هدف
    target_user_id = None
    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
    else:
        username_or_id = context.args[0]
        try:
            if username_or_id.isdigit():
                target_user_id = int(username_or_id)
            else:
                member = await context.bot.get_chat_member(chat.id, username_or_id)target_user_id = member.user.id
        except:
            await update.message.reply_text("نتونستم کاربر رو پیدا کنم یا عضو گروه نیست.")
            return

    if target_user_id in user_limits:
        limit, set_by_user = user_limits[target_user_id]
        # فقط صاحب گروه می‌تواند محدودیتی را که خودش گذاشته بردارد
        if set_by_user == owner_id and from_user_id != owner_id:
            await update.message.reply_text("❌ فقط صاحب گروه می‌تواند محدودیت روی این کاربر را بردارد.")
            return

        del user_limits[target_user_id]
        await update.message.reply_text(f"❌ محدودیت برای کاربر {target_user_id} حذف شد.")
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

            allowed_count, _ = user_limits[user_id]

            if count > allowed_count:
                try:
                    await message.delete()
                except:
                    pass
                await context.bot.send_message(
                    chat_id=message.chat_id,
                    text=f"⚠️ شما فقط {allowed_count} عدد گیف یا استیکر در روز می‌تونید بفرستید."
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
