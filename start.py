import random

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import database as db
from keyboards import captcha_keyboard, main_menu_keyboard
from utils import main_menu_text

router = Router()


class CaptchaState(StatesGroup):
    solving = State()


def generate_captcha() -> tuple[str, int, list[int]]:
    op = random.choice(["+", "-"])
    a, b = random.randint(2, 20), random.randint(2, 15)
    if op == "+":
        answer = a + b
        question = f"{a} + {b}"
    else:
        if a < b:
            a, b = b, a
        answer = a - b
        question = f"{a} - {b}"

    wrongs: set[int] = set()
    while len(wrongs) < 3:
        delta = random.choice([-4, -3, -2, -1, 1, 2, 3, 4, 5])
        candidate = answer + delta
        if candidate != answer and candidate > 0:
            wrongs.add(candidate)

    options = [answer] + list(wrongs)
    random.shuffle(options)
    return question, answer, options


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    args = message.text.split()
    referrer_id: int | None = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            rid = int(args[1][4:])
            if rid != message.from_user.id:
                referrer_id = rid
        except ValueError:
            pass

    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            referrer_id,
        )
        user = await db.get_user(message.from_user.id)

    if user["trial_used"]:
        await message.answer(
            main_menu_text(message.from_user.first_name),
            reply_markup=main_menu_keyboard(),
        )
        return

    question, answer, options = generate_captcha()
    await state.set_state(CaptchaState.solving)
    await state.update_data(answer=answer, attempts=2)
    await message.answer(
        f"🤖 Для продолжения пройдите проверку.\n\nСколько будет: {question} = ?",
        reply_markup=captcha_keyboard(options),
    )


@router.callback_query(CaptchaState.solving)
async def captcha_callback(call: CallbackQuery, state: FSMContext):
    if not call.data.startswith("captcha_"):
        await call.answer()
        return

    try:
        chosen = int(call.data.split("_")[1])
    except ValueError:
        await call.answer()
        return

    data = await state.get_data()
    correct: int = data["answer"]
    attempts: int = data["attempts"]

    if chosen == correct:
        await state.clear()
        user = await db.get_user(call.from_user.id)
        await db.activate_trial(call.from_user.id)

        if user and user["referrer_id"]:
            referrer = await db.get_user(user["referrer_id"])
            if referrer:
                await db.apply_referral_bonus(user["referrer_id"])

        await call.message.edit_text(
            "✅ Проверка пройдена!\n"
            "🎁 Вам начислено 7 дней пробного периода!\n\n"
            + main_menu_text(call.from_user.first_name),
            reply_markup=main_menu_keyboard(),
        )
    elif attempts <= 0:
        await state.clear()
        await call.message.edit_text(
            "❌ Попытки исчерпаны. Отправьте /start чтобы попробовать снова."
        )
    else:
        question, answer, options = generate_captcha()
        await state.update_data(answer=answer, attempts=attempts - 1)
        await call.message.edit_text(
            f"❌ Неверно! Осталось попыток: {attempts}\n\n"
            f"🤖 Новый вопрос: {question} = ?",
            reply_markup=captcha_keyboard(options),
        )

    await call.answer()
