from datetime import datetime

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import database as db
from keyboards import back_main_keyboard, main_menu_keyboard, plans_keyboard
from utils import main_menu_text
from config import BOT_USERNAME

router = Router()


class PromoState(StatesGroup):
    entering = State()


@router.callback_query(lambda c: c.data == "back_main")
async def back_to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer()
    await call.message.delete()
    await call.message.answer(
        main_menu_text(call.from_user.first_name),
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(lambda c: c.data == "buy_sub")
async def buy_subscription(call: CallbackQuery):
    await call.answer()
    await call.message.delete()
    await call.message.answer(
        "💳 Выберите тариф:\n\n"
        "7 дней — 50⭐\n"
        "30 дней — 150⭐\n"
        "90 дней — 300⭐\n"
        "180 дней — 450⭐\n"
        "360 дней — 600⭐\n"
        "♾ Безлимит — 999⭐",
        reply_markup=plans_keyboard(),
    )


@router.callback_query(lambda c: c.data == "referral")
async def referral_menu(call: CallbackQuery):
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{call.from_user.id}"
    await call.answer()
    await call.message.delete()
    await call.message.answer(
        f"👥 Ваша реферальная ссылка:\n{link}\n\n"
        "За каждого приглашённого друга вы получаете +2 дня подписки.",
        reply_markup=back_main_keyboard(),
    )


@router.callback_query(lambda c: c.data == "promo")
async def promo_menu(call: CallbackQuery, state: FSMContext):
    await state.set_state(PromoState.entering)
    await call.answer()
    await call.message.delete()
    await call.message.answer(
        "🎟 Введите промокод:",
        reply_markup=back_main_keyboard(),
    )


@router.message(PromoState.entering)
async def process_promo(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    result = await db.use_promo_code(message.from_user.id, code)
    await state.clear()

    if result["success"]:
        text = f"✅ Промокод применён! Начислено +{result['days']} дней подписки."
    elif result["reason"] == "not_found":
        text = "❌ Промокод не найден."
    elif result["reason"] == "already_used":
        text = "❌ Вы уже использовали этот промокод."
    else:
        text = "❌ Промокод недействителен или исчерпан."

    await message.answer(text, reply_markup=main_menu_keyboard())


@router.callback_query(lambda c: c.data == "status")
async def show_status(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    if not user:
        await call.answer("Пользователь не найден.", show_alert=True)
        return

    is_active = await db.is_subscription_active(call.from_user.id)

    if user["is_unlimited"]:
        text = "📊 Ваш статус:\n✅ Активна\n♾ Тариф: Безлимит"
    elif is_active and user["subscription_end"]:
        end = datetime.fromisoformat(user["subscription_end"])
        text = (
            f"📊 Ваш статус:\n"
            f"✅ Активна\n"
            f"📅 Истекает: {end.strftime('%d.%m.%Y %H:%M')}"
        )
    else:
        text = (
            "📊 Ваш статус:\n"
            "❌ Подписка неактивна\n\n"
            "Приобретите подписку для доступа к функциям."
        )

    await call.answer()
    await call.message.delete()
    await call.message.answer(text, reply_markup=back_main_keyboard())
