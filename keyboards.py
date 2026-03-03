from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔗 Как подключить бота", url="https://t.me/dezhavu_info/6")
    )
    builder.row(
        InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_sub")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Пригласить друга", callback_data="referral"),
        InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="promo"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Мой статус", callback_data="status"),
        InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/dezhavu_support"),
    )
    return builder.as_markup()


def captcha_keyboard(options: List[int]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for opt in options:
        builder.add(InlineKeyboardButton(text=str(opt), callback_data=f"captcha_{opt}"))
    builder.adjust(2)
    return builder.as_markup()


def plans_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    plans = [
        ("7",         "7 дней — 50⭐"),
        ("30",        "30 дней — 150⭐"),
        ("90",        "90 дней — 300⭐"),
        ("180",       "180 дней — 450⭐"),
        ("360",       "360 дней — 600⭐"),
        ("unlimited", "♾ Безлимит — 999⭐"),
    ]
    for key, label in plans:
        builder.row(InlineKeyboardButton(text=label, callback_data=f"plan_{key}"))
    builder.row(
        InlineKeyboardButton(
            text="💳 Оплатить рублями", url="https://t.me/dezhavu_rubpay_bot"
        )
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    return builder.as_markup()


def payment_method_keyboard(plan_key: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⭐ Telegram Stars", callback_data=f"pay_stars_{plan_key}")
    )
    builder.row(
        InlineKeyboardButton(text="₿ CryptoBot (USDT)", callback_data=f"pay_crypto_{plan_key}")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="buy_sub"))
    return builder.as_markup()


def check_crypto_keyboard(invoice_id: str, pay_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Оплатить", url=pay_url))
    builder.row(
        InlineKeyboardButton(
            text="✅ Проверить оплату", callback_data=f"check_crypto_{invoice_id}"
        )
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="buy_sub"))
    return builder.as_markup()


def admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))
    builder.row(
        InlineKeyboardButton(text="🎟 Создать промокод", callback_data="admin_create_promo")
    )
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.row(InlineKeyboardButton(text="✖️ Закрыть", callback_data="admin_close"))
    return builder.as_markup()


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="admin_broadcast_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_broadcast_cancel"),
    )
    return builder.as_markup()



def back_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    return builder.as_markup()
