from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def persistent_reply_keyboard() -> ReplyKeyboardMarkup:
    """Persistent bottom reply keyboard defined in UI-UX.md §4.3."""
    keyboard = [
        [KeyboardButton(text="🏠 الرئيسية"), KeyboardButton(text="📚 الخدمات")],
        [
            KeyboardButton(text="🗂️ طلباتي"),
            KeyboardButton(text="🎧 الدعم"),
            KeyboardButton(text="✖️ إلغاء"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, is_persistent=True)


def cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    """Temporary input flow reply keyboard showing only cancel."""
    keyboard = [[KeyboardButton(text="✖️ إلغاء")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, is_persistent=True)
