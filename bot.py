import logging
import os
from datetime import datetime, date
from calendar import monthcalendar, month_name

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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

TITLE, DATE_PICKER, TIME = range(3)


def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Schedule event", callback_data="schedule")],
        [InlineKeyboardButton("Show events", callback_data="show")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Choose an option:", reply_markup=reply_markup)


def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "schedule":
        query.answer()
        query.message.reply_text("Enter event title:")
        return TITLE
    elif data == "show":
        query.answer()
        events = database.list_events(query.message.chat_id)
        if not events:
            query.message.reply_text("No events found")
        else:
            lines = [f"{t} on {d} at {ti}" for t, d, ti in events]
            query.message.reply_text("\n".join(lines))
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


def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    now = date.today()
    context.user_data["calendar_year"] = now.year
    context.user_data["calendar_month"] = now.month
    markup = build_calendar(now.year, now.month)
    update.message.reply_text("Select a date:", reply_markup=markup)
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


def calendar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    year = context.user_data.get("calendar_year", date.today().year)
    month = context.user_data.get("calendar_month", date.today().month)
    if data.startswith("day:"):
        date_str = data.split(":", 1)[1]
        context.user_data["date"] = date_str
        query.answer()
        query.message.edit_text(f"Selected {date_str}")
        query.message.reply_text("Enter time (HH:MM, 24h):")
        return TIME
    elif data.startswith("next"):
        year, month = change_month(year, month, 1)
    elif data.startswith("prev"):
        year, month = change_month(year, month, -1)
    else:
        query.answer()
        return DATE_PICKER

    context.user_data["calendar_year"] = year
    context.user_data["calendar_month"] = month
    markup = build_calendar(year, month)
    query.answer()
    query.edit_message_reply_markup(reply_markup=markup)
    return DATE_PICKER


def receive_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        datetime.strptime(update.message.text, "%H:%M")
    except ValueError:
        update.message.reply_text("Invalid time format. Use HH:MM")
        return TIME
    context.user_data["time"] = update.message.text

    database.add_event(
        update.message.chat_id,
        context.user_data["title"],
        context.user_data["date"],
        context.user_data["time"],
    )
    update.message.reply_text("Event saved!")
    return ConversationHandler.END


def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update.message.reply_text("Cancelled")
    return ConversationHandler.END


def main():
    database.init_db()
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
            DATE_PICKER: [CallbackQueryHandler(calendar_handler)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    application.run_polling()


if __name__ == "__main__":
    main()
