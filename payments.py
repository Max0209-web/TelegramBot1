import logging

import aiohttp

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

import database as db
from config import CRYPTOBOT_TOKEN, PLANS, BOT_USERNAME
from keyboards import (
    check_crypto_keyboard,
    main_menu_keyboard,
    payment_method_keyboard,
)

router = Router()

CRYPTOBOT_API = "https://pay.crypt.bot/api"

logger = logging.getLogger(__name__)


async def _cryptobot_post(method: str, payload: dict) -> dict:
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{CRYPTOBOT_API}/{method}", json=payload, headers=headers
        ) as resp:
            return await resp.json()


async def _cryptobot_get(method: str, params: dict) -> dict:
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{CRYPTOBOT_API}/{method}", params=params, headers=headers
        ) as resp:
            return await resp.json()


@router.callback_query(lambda c: c.data and c.data.startswith("plan_"))
async def select_plan(call: CallbackQuery):
    plan_key = call.data[5:]
    plan = PLANS.get(plan_key)
    if not plan:
        await call.answer("Тариф не найден.", show_alert=True)
        return

    await call.answer()
    await call.message.delete()
    await call.message.answer(
        f"💳 Выбран тариф: {plan['label']}\n\nВыберите способ оплаты:",
        reply_markup=payment_method_keyboard(plan_key),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("pay_stars_"))
async def pay_with_stars(call: CallbackQuery, bot: Bot):
    plan_key = call.data[10:]
    plan = PLANS.get(plan_key)
    if not plan:
        await call.answer("Тариф не найден.", show_alert=True)
        return

    days_label = "Безлимит" if plan["days"] == 0 else f"{plan['days']} дней"
    await call.answer()
    await call.message.delete()
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=f"Подписка: {days_label}",
        description=f"Доступ к боту на {days_label}",
        payload=f"sub_{call.from_user.id}_{plan_key}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Stars", amount=plan["stars"])],
    )



@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split("_")
    if len(parts) != 3 or parts[0] != "sub":
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        return

    plan_key = parts[2]
    plan = PLANS.get(plan_key)
    if not plan:
        return

    if plan["days"] == 0:
        await db.extend_subscription(user_id, 0, unlimited=True)
        text = "✅ Оплата прошла!\nПодписка «Безлимит» активирована."
    else:
        await db.extend_subscription(user_id, plan["days"])
        text = f"✅ Оплата прошла!\nПодписка на {plan['days']} дней активирована."

    await message.answer(text, reply_markup=main_menu_keyboard())


@router.callback_query(lambda c: c.data and c.data.startswith("pay_crypto_"))
async def pay_with_crypto(call: CallbackQuery):
    plan_key = call.data[11:]
    plan = PLANS.get(plan_key)
    if not plan:
        await call.answer("Тариф не найден.", show_alert=True)
        return

    days_label = "Безлимит" if plan["days"] == 0 else f"{plan['days']} дней"
    payload = f"sub_{call.from_user.id}_{plan_key}"

    result = await _cryptobot_post(
        "createInvoice",
        {
            "asset": "USDT",
            "amount": str(round(plan["usdt"], 2)),
            "description": f"Подписка: {days_label}",
            "payload": payload,
            "paid_btn_name": "callback",
            "paid_btn_url": f"https://t.me/{BOT_USERNAME}",
        },
    )

    if not result.get("ok"):
        logger.error("CryptoBot error: %s", result)
        await call.answer(
            f"Ошибка: {result.get('error', {}).get('name', 'Unknown')}", show_alert=True
        )
        return

    invoice = result["result"]
    invoice_id = str(invoice["invoice_id"])
    pay_url = invoice["pay_url"]

    await db.create_payment(call.from_user.id, "crypto", plan_key, invoice_id)
    await call.answer()
    await call.message.delete()
    await call.message.answer(
        f"₿ Счёт создан!\n\n"
        f"Сумма: {plan['usdt']} USDT\n"
        f"Тариф: {days_label}\n\n"
        "После оплаты нажмите «Проверить оплату».",
        reply_markup=check_crypto_keyboard(invoice_id, pay_url),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("check_crypto_"))
async def check_crypto_payment(call: CallbackQuery):
    invoice_id = call.data[13:]

    result = await _cryptobot_get("getInvoices", {"invoice_ids": invoice_id})
    if not result.get("ok"):
        await call.answer("Ошибка проверки. Попробуйте позже.", show_alert=True)
        return

    items = result["result"].get("items", [])
    if not items:
        await call.answer("Счёт не найден.", show_alert=True)
        return

    if items[0]["status"] != "paid":
        await call.answer(
            "⏳ Оплата ещё не поступила. Попробуйте чуть позже.", show_alert=True
        )
        return

    payment = await db.get_payment_by_invoice(invoice_id)
    if not payment:
        await call.answer("Платёж уже обработан.", show_alert=True)
        return

    plan = PLANS.get(payment["plan_key"])
    if not plan:
        await call.answer("Ошибка тарифа.", show_alert=True)
        return

    await db.complete_payment(payment["id"])

    if plan["days"] == 0:
        await db.extend_subscription(payment["user_id"], 0, unlimited=True)
        text = "✅ Оплата подтверждена!\nПодписка «Безлимит» активирована."
    else:
        await db.extend_subscription(payment["user_id"], plan["days"])
        text = f"✅ Оплата подтверждена!\nПодписка на {plan['days']} дней активирована."

    await call.answer()
    await call.message.delete()
    await call.message.answer(text, reply_markup=main_menu_keyboard())
