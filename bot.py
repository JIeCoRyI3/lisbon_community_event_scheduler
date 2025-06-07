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
from telegram.constants import ParseMode
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

ADMINS_FILE = "admins.txt"
SUPERADMINS_FILE = "superadmins.txt"


def _load_list(filename: str) -> set[str]:
    if not os.path.exists(filename):
        return set()
    with open(filename) as f:
        return {line.strip() for line in f if line.strip()}


def load_admins() -> set[str]:
    return _load_list(ADMINS_FILE)


def load_superadmins() -> set[str]:
    return _load_list(SUPERADMINS_FILE)


ADMINS = load_admins()
SUPERADMINS = load_superadmins()


def is_superadmin(update: Update) -> bool:
    user = update.effective_user
    return user and user.username in SUPERADMINS


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return user and (
        user.username in ADMINS or user.username in SUPERADMINS
    )

logging.basicConfig(level=logging.INFO)

TITLE, DESCRIPTION, DATE_PICKER, TIME, LOCATION, DELETE_CHOOSE, DELETE_CONFIRM, REMOVE_ADMIN_CHOOSE = range(8)

HELP_TEXT = (
    "Available commands:\n"
    "/start - show main menu\n"
    "/schedule - schedule event\n"
    "/show - show events\n"
    "/cancel - cancel current action\n"
    "/help - show this message"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Schedule event", callback_data="schedule")],
        [InlineKeyboardButton("Show events", callback_data="show")],
    ]
    if is_admin(update):
        keyboard.append([InlineKeyboardButton("Delete event", callback_data="delete")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose an option:", reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a list of available commands."""
    text = HELP_TEXT
    if is_admin(update):
        text += "\n/delete - delete event"
    if is_superadmin(update):
        text += "\n/refresh - reload admin lists"
        text += "\n/add_admin - add a new admin"
        text += "\n/remove_admin - remove an admin"
    await update.message.reply_text(text)


def format_events(events) -> str:
    """Return events formatted for display."""
    lines = [
        f"<b>{t}</b>\n{desc}\n\U0001F550 When? {d} at {ti}\n\U0001F4CD {loc}"
        for t, desc, d, ti, loc in events
    ]
    return "\n\n".join(lines)


def format_event_with_users(title: str, description: str, date: str, time: str, location: str, users: list[str]) -> str:
    text = (
        f"<b>{title}</b>\n{description}\n\U0001F550 When? {date} at {time}\n\U0001F4CD {location}"
    )
    if users:
        user_list = ", ".join(
            f'<a href="https://t.me/{u}">@{u}</a>' for u in users
        )
        text += f"\nWill go: {user_list}"
    return text


async def _send_event_list(message, chat_id: int, username: str):
    events = database.list_events_with_ids(chat_id)
    if not events:
        await message.reply_text("No events found")
        return
    for event_id, title, desc, d, ti, loc in events:
        users = database.list_applicants(event_id)
        applied = username in users
        button_text = "Cancel application" if applied else "Apply to the event"
        callback = f"cancel_app:{event_id}" if applied else f"apply:{event_id}"
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(button_text, callback_data=callback)]]
        )
        text = format_event_with_users(title, desc, d, ti, loc, users)
        await message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start scheduling via /schedule command."""
    await update.message.reply_text("Enter event title:")
    return TITLE


async def show_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show events via /show command."""
    username = update.effective_user.username or update.effective_user.first_name
    await _send_event_list(update.message, update.message.chat_id, username)


async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_superadmin(update):
        await update.message.reply_text("You are not authorized to refresh roles.")
        return
    global ADMINS, SUPERADMINS
    ADMINS = load_admins()
    SUPERADMINS = load_superadmins()
    await update.message.reply_text("Roles reloaded")


def _normalize_username(name: str) -> str:
    name = name.strip()
    if name.startswith("@"):  # @username
        return name[1:]
    if "t.me/" in name:
        return name.split("t.me/")[-1]
    return name


async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_superadmin(update):
        await update.message.reply_text("You are not authorized to add admins.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /add_admin @username")
        return
    username = _normalize_username(context.args[0])
    if not username:
        await update.message.reply_text("Invalid username")
        return
    if username in ADMINS:
        await update.message.reply_text("User is already an admin")
        return
    ADMINS.add(username)
    with open(ADMINS_FILE, "a") as f:
        f.write(username + "\n")
    await update.message.reply_text(f"Added {username} as admin")


async def remove_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_superadmin(update):
        await update.message.reply_text("You are not authorized to remove admins.")
        return ConversationHandler.END
    if not ADMINS:
        await update.message.reply_text("No admins to remove")
        return ConversationHandler.END
    keyboard = [
        [InlineKeyboardButton(u, callback_data=f"rm_admin:{u}")]
        for u in sorted(ADMINS)
    ]
    await update.message.reply_text(
        "Choose admin to remove:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REMOVE_ADMIN_CHOOSE


async def remove_admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_superadmin(update):
        await update.callback_query.answer()
        return ConversationHandler.END
    username = update.callback_query.data.split(":", 1)[1]
    await update.callback_query.answer()
    if username in ADMINS:
        ADMINS.remove(username)
        with open(ADMINS_FILE, "w") as f:
            for u in sorted(ADMINS):
                f.write(u + "\n")
        await update.callback_query.message.edit_text(f"Removed {username} from admins")
    else:
        await update.callback_query.message.edit_text("User not found")
    return ConversationHandler.END


async def _show_delete_list(message, chat_id):
    events = database.list_events_with_ids(chat_id)
    if not events:
        await message.reply_text("No events found")
        return ConversationHandler.END
    keyboard = [
        [
            InlineKeyboardButton(
                f"{t} on {d} at {ti}", callback_data=f"del:{event_id}"
            )
        ]
        for event_id, t, _desc, d, ti, _ in events
    ]
    await message.reply_text(
        "Select event to delete:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DELETE_CHOOSE


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("You are not authorized to delete events.")
        return ConversationHandler.END
    return await _show_delete_list(update.message, update.effective_chat.id)


async def delete_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("You are not authorized to delete events.")
        return ConversationHandler.END
    await update.callback_query.answer()
    return await _show_delete_list(update.callback_query.message, update.effective_chat.id)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "schedule":
        await query.answer()
        await query.message.reply_text("Enter event title:")
        return TITLE
    elif data == "show":
        await query.answer()
        username = query.from_user.username or query.from_user.first_name
        await _send_event_list(query.message, query.message.chat_id, username)
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
    await update.message.reply_text("Enter event description:")
    return DESCRIPTION


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = update.message.text
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
        context.user_data["description"],
        context.user_data["date"],
        context.user_data["time"],
        context.user_data["location"],
    )
    await update.message.reply_text("Event saved!")
    # Show the main menu again so the user can immediately view events
    await start(update, context)
    return ConversationHandler.END


async def choose_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    event_id = int(query.data.split(":", 1)[1])
    context.user_data["delete_id"] = event_id
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Confirm", callback_data="confirm_delete")],
        [InlineKeyboardButton("Cancel", callback_data="cancel_delete")],
    ]
    await query.message.reply_text(
        "Delete this event?", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DELETE_CONFIRM


async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    if data == "confirm_delete":
        event_id = context.user_data.get("delete_id")
        if event_id:
            database.delete_event(event_id)
        await query.message.edit_text("Event deleted")
    else:
        await query.message.edit_text("Deletion cancelled")
    return ConversationHandler.END


async def apply_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    event_id = int(query.data.split(":", 1)[1])
    user = query.from_user
    username = user.username or user.first_name
    database.apply_to_event(event_id, username)
    event = database.get_event(event_id)
    users = database.list_applicants(event_id)
    text = format_event_with_users(event[2], event[3], event[4], event[5], event[6], users)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Cancel application", callback_data=f"cancel_app:{event_id}")]]
    )
    await query.answer("Applied")
    await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def cancel_application_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    event_id = int(query.data.split(":", 1)[1])
    user = query.from_user
    username = user.username or user.first_name
    database.cancel_application(event_id, username)
    event = database.get_event(event_id)
    users = database.list_applicants(event_id)
    text = format_event_with_users(event[2], event[3], event[4], event[5], event[6], users)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Apply to the event", callback_data=f"apply:{event_id}")]]
    )
    await query.answer("Cancelled")
    await query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled")
    return ConversationHandler.END


async def setup_bot(application: Application) -> None:
    """Configure commands and the menu button after initialization."""
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Show main menu"),
            BotCommand("schedule", "Schedule event"),
            BotCommand("show", "Show events"),
            BotCommand("delete", "Delete event"),
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
        entry_points=[CallbackQueryHandler(button, pattern="^(schedule|show)$"), CommandHandler("schedule", schedule_command)],
        states={
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)],
            DATE_PICKER: [CallbackQueryHandler(calendar_handler)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_time)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_location)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    delete_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_button, pattern="^delete$"), CommandHandler("delete", delete_command)],
        states={
            DELETE_CHOOSE: [CallbackQueryHandler(choose_delete, pattern="^del:")],
            DELETE_CONFIRM: [CallbackQueryHandler(confirm_delete, pattern="^(confirm_delete|cancel_delete)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("refresh", refresh_command))
    application.add_handler(CommandHandler("add_admin", add_admin_command))
    application.add_handler(CommandHandler("show", show_command))
    application.add_handler(conv_handler)
    application.add_handler(delete_conv_handler)
    application.add_handler(CallbackQueryHandler(apply_event, pattern="^apply:"))
    application.add_handler(CallbackQueryHandler(cancel_application_button, pattern="^cancel_app:"))
    remove_admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("remove_admin", remove_admin_list)],
        states={
            REMOVE_ADMIN_CHOOSE: [CallbackQueryHandler(remove_admin_button, pattern="^rm_admin:")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(remove_admin_conv_handler)

    application.run_polling()


if __name__ == "__main__":
    main()
