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

# محدودیت‌های مجاز برای کاربران (user_id → (allowed_count, set_by_user_id))
# مقدار دوم یعنی کاربری که محدودیت را گذاشته
user_limits = {}

# گرفتن ادمین‌ها و صاحب گروه
async def get_admins_and_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    admins = await context.bot.get_chat_administrators(chat.id)
    owner = None
    admin_ids = set()
    for admin in admins:
        admin_ids.add(admin.user.id)
        if admin.status == "creator":
            owner = admin.user.id
    return owner, admin_ids

# دستور محدود کردن کاربر با تعداد دلخواه
async def restrict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    owner_id, admin_ids = await get_admins_and_owner(update, context)
    from_user_id = update.effective_user.id

    if from_user_id not in admin_ids and from_user_id != owner_id:
        await update.message.reply_text("❌ فقط ادمین‌ها و صاحب گروه می‌تونن از این دستور استفاده کنن.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("مثال:\n/restrict @username 3")
        return

    user = update.message.parse_entities().get("mention")
    if user:
        user_id = user.id
    else:
        try:
            user_id = int(context.args[0]) if context.args[0].isdigit() else None
        except:
            user_id = None

    try:
        limit = int(context.args[1])
    except:
        await update.message.reply_text("عدد معتبر وارد کن برای محدودیت.")
        return

    if not user_id:
        # تلاش برای گرفتن کاربر از طریق @username
        try:
            member = await context.bot.get_chat_member(update.effective_chat.id, context.args[0])
            user_id = member.user.id
        except:
            await update.message.reply_text("نتونستم کاربر رو پیدا کنم یا عضو گروه نیست.")
            return

    # اگر محدودیتی روی این کاربر قبلا گذاشته شده و توسط صاحب گروه باشد،
    # فقط صاحب گروه اجازه دارد تغییر دهد.
    if user_id in user_limits:
        _, set_by_user = user_limits[user_id]
        if set_by_user == owner_id and from_user_id != owner_id:
            await update.message.reply_text("❌ فقط صاحب گروه می‌تواند محدودیت روی این کاربر را تغییر دهد.")
            return

    user_limits[user_id] = (limit, from_user_id)
    await update.message.reply_text(f"✅ محدودیت برای کاربر {user_id} روی {limit} گیف/استیکر در روز تنظیم شد.")

# دستور حذف محدودیت
async def unrestrict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    owner_id, admin_ids = await get_admins_and_owner(update, context)
    from_user_id = update.effective_user.id

    if from_user_id not in admin_ids and from_user_id != owner_id:
        await update.message.reply_text("❌ فقط ادمین‌ها و صاحب گروه می‌تونن از این دستور استفاده کنن.")
        return

    if not context.args:
        await update.message.reply_text("مثال:\n/unrestrict @username")
        return

    user_id = None
    try:
        if context.args[0].isdigit():
            user_id = int(context.args[0])
        else:
            member = await context.bot.get_chat_member(update.effective_chat.id, context.args[0])
            user_id = member.user.id
    except:
        await update.message.reply_text("کاربر پیدا نشد یا عضو گروه نیست.")
        return

    # اگر محدودیت روی این کاربر توسط صاحب گروه گذاشته شده:
    # فقط صاحب گروه اجازه حذف آن را دارد.
    if user_id in user_limits:
        _, set_by_user = user_limits[user_id]
        if set_by_user == owner_id and from_user_id != owner_id:
            await update.message.reply_text("❌ فقط صاحب گروه می‌تواند محدودیت روی این کاربر را بردارد.")return

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
