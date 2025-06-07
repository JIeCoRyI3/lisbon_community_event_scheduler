import logging
import os
from datetime import datetime, date
from calendar import monthcalendar, month_name

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    BotCommand,
    MenuButtonCommands,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import database

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN not set in .env")

logging.basicConfig(level=logging.INFO)

TITLE, DATE_PICKER, TIME, LOCATION = range(4)

HELP_TEXT = (
    "Available commands:\n"
    "/start - show main menu\n"
    "/cancel - cancel current action\n"
    "/help - show this message"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Schedule event", callback_data="schedule")],
        [InlineKeyboardButton("Show events", callback_data="show")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose an option:", reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a list of available commands."""
    await update.message.reply_text(HELP_TEXT)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "schedule":
        await query.answer()
        await query.message.reply_text("Enter event title:")
        return TITLE
    elif data == "show":
        await query.answer()
        events = database.list_events(query.message.chat_id)
        if not events:
            await query.message.reply_text("No events found")
        else:
            lines = [f"{t} on {d} at {ti} - {loc}" for t, d, ti, loc in events]
            await query.message.reply_text("\n".join(lines))
        return ConversationHandler.END


def build_calendar(year: int, month: int) -> InlineKeyboardMarkup:
    keyboard = []
    cal = monthcalendar(year, month)
    header = [InlineKeyboardButton(f"{month_name[month]} {year}", callback_data="ignore")]
    keyboard.append(header)
    week_days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    keyboard.append([InlineKeyboardButton(day, callback_data="ignore") for day in week_days])
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                row.append(InlineKeyboardButton(str(day), callback_data=f"day:{date_str}"))
        keyboard.append(row)
    navigation = [
        InlineKeyboardButton("<", callback_data=f"prev:{year}:{month}"),
        InlineKeyboardButton(">", callback_data=f"next:{year}:{month}"),
    ]
    keyboard.append(navigation)
    return InlineKeyboardMarkup(keyboard)


async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    now = date.today()
    context.user_data["calendar_year"] = now.year
    context.user_data["calendar_month"] = now.month
    markup = build_calendar(now.year, now.month)
    await update.message.reply_text("Select a date:", reply_markup=markup)
    return DATE_PICKER


def change_month(year: int, month: int, delta: int):
    month += delta
    if month > 12:
        month = 1
        year += 1
    elif month < 1:
        month = 12
        year -= 1
    return year, month


async def calendar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    year = context.user_data.get("calendar_year", date.today().year)
    month = context.user_data.get("calendar_month", date.today().month)
    if data.startswith("day:"):
        date_str = data.split(":", 1)[1]
        formatted = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
        context.user_data["date"] = formatted
        await query.answer()
        await query.message.edit_text(f"Selected {formatted}")
        await query.message.reply_text("Enter time (HH:MM, 24h):")
        return TIME
    elif data.startswith("next"):
        year, month = change_month(year, month, 1)
    elif data.startswith("prev"):
        year, month = change_month(year, month, -1)
    else:
        await query.answer()
        return DATE_PICKER

    context.user_data["calendar_year"] = year
    context.user_data["calendar_month"] = month
    markup = build_calendar(year, month)
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=markup)
    return DATE_PICKER


async def receive_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        datetime.strptime(update.message.text, "%H:%M")
    except ValueError:
        await update.message.reply_text("Invalid time format. Use HH:MM")
        return TIME
    context.user_data["time"] = update.message.text
    await update.message.reply_text("Enter location:")
    return LOCATION


async def receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["location"] = update.message.text

    database.add_event(
        update.message.chat_id,
        context.user_data["title"],
        context.user_data["date"],
        context.user_data["time"],
        context.user_data["location"],
    )
    await update.message.reply_text("Event saved!")
    # Show the main menu again so the user can immediately view events
    await start(update, context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled")
    return ConversationHandler.END


async def setup_bot(application: Application) -> None:
    """Configure commands and the menu button after initialization."""
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Show main menu"),
            BotCommand("help", "Show help message"),
            BotCommand("cancel", "Cancel current action"),
        ]
    )
    # Ensure users always see a button that opens the command list
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())


def main():
    database.init_db()
    application = (
        Application.builder().token(TOKEN).post_init(setup_bot).build()
    )

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
            DATE_PICKER: [CallbackQueryHandler(calendar_handler)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_time)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_location)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)

    application.run_polling()


if __name__ == "__main__":
    main()
