import asyncio

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import database as db
from config import ADMIN_IDS
from keyboards import admin_keyboard, broadcast_confirm_keyboard, main_menu_keyboard

router = Router()


class AdminBroadcastState(StatesGroup):
    content = State()
    confirm = State()


class AdminPromoState(StatesGroup):
    code_name = State()
    code_days = State()
    code_uses = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def extract_file_info(message: Message) -> dict:
    if message.photo:
        return {"photo_file_id": message.photo[-1].file_id}
    if message.video:
        return {"video_file_id": message.video.file_id}
    if message.document:
        return {"document_file_id": message.document.file_id}
    if message.animation:
        return {"animation_file_id": message.animation.file_id}
    if message.voice:
        return {"voice_file_id": message.voice.file_id}
    return {}


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🔧 Панель администратора:", reply_markup=admin_keyboard())


@router.callback_query(lambda c: c.data == "admin_close")
async def admin_close(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.clear()
    await call.message.delete()
    await call.answer()


@router.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    stats = await db.get_stats()
    await call.answer()
    await call.message.delete()
    await call.message.answer(
        f"📊 Статистика бота:\n\n"
        f"👥 Всего пользователей: {stats['total']}\n"
        f"✅ Активных подписок: {stats['active']}",
        reply_markup=admin_keyboard(),
    )


@router.callback_query(lambda c: c.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.set_state(AdminBroadcastState.content)
    await call.answer()
    await call.message.delete()
    await call.message.answer(
        "📢 Отправьте сообщение для рассылки (текст, фото, видео, документ или анимация):"
    )


@router.message(AdminBroadcastState.content)
async def admin_broadcast_content(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    file_info = extract_file_info(message)
    caption = message.caption or message.text or ""
    await state.update_data(text=caption, file_info=file_info)
    await state.set_state(AdminBroadcastState.confirm)
    preview = caption[:100] if caption else "(только медиа)"
    await message.answer(
        f"📢 Предпросмотр рассылки:\n{preview}\n\nОтправить всем пользователям?",
        reply_markup=broadcast_confirm_keyboard(),
    )


@router.callback_query(lambda c: c.data == "admin_broadcast_cancel")
async def broadcast_cancel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.clear()
    await call.answer()
    await call.message.delete()
    await call.message.answer("❌ Рассылка отменена.", reply_markup=admin_keyboard())


@router.callback_query(lambda c: c.data == "admin_broadcast_confirm")
async def broadcast_confirm(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer()
        return

    data = await state.get_data()
    await state.clear()
    text: str = data.get("text", "")
    file_info: dict = data.get("file_info", {})

    users = await db.get_all_users()
    await call.answer()
    await call.message.delete()
    status_msg = await call.message.answer(f"⏳ Выполняется рассылка по {len(users)} пользователям...")

    sent = 0
    failed = 0
    for user in users:
        uid = user["user_id"]
        try:
            if file_info.get("photo_file_id"):
                await bot.send_photo(uid, file_info["photo_file_id"], caption=text)
            elif file_info.get("video_file_id"):
                await bot.send_video(uid, file_info["video_file_id"], caption=text)
            elif file_info.get("document_file_id"):
                await bot.send_document(uid, file_info["document_file_id"], caption=text)
            elif file_info.get("animation_file_id"):
                await bot.send_animation(uid, file_info["animation_file_id"], caption=text)
            elif file_info.get("voice_file_id"):
                await bot.send_voice(uid, file_info["voice_file_id"], caption=text)
            elif text:
                await bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}",
        reply_markup=admin_keyboard(),
    )


@router.callback_query(lambda c: c.data == "admin_create_promo")
async def admin_create_promo_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.set_state(AdminPromoState.code_name)
    await call.answer()
    await call.message.delete()
    await call.message.answer("🎟 Введите код промокода (только латинские буквы и цифры):")


@router.message(AdminPromoState.code_name)
async def admin_promo_code_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    code = message.text.strip().upper()
    if not code.isalnum() or len(code) < 3:
        await message.answer("❌ Промокод должен содержать только буквы/цифры (мин. 3 символа).")
        return
    await state.update_data(code=code)
    await state.set_state(AdminPromoState.code_days)
    await message.answer(f"Код: <b>{code}</b>\n\nВведите количество дней подписки:")


@router.message(AdminPromoState.code_days)
async def admin_promo_code_days(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit() or int(message.text.strip()) <= 0:
        await message.answer("❌ Введите положительное целое число.")
        return
    days = int(message.text.strip())
    await state.update_data(days=days)
    await state.set_state(AdminPromoState.code_uses)
    await message.answer(
        f"Дней: <b>{days}</b>\n\nВведите максимальное количество использований (0 = безлимит):"
    )


@router.message(AdminPromoState.code_uses)
async def admin_promo_code_uses(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("❌ Введите целое число (0 для безлимита).")
        return
    max_uses = int(message.text.strip())
    data = await state.get_data()
    await state.clear()

    await db.create_promo_code(data["code"], data["days"], max_uses)
    uses_label = "безлимит" if max_uses == 0 else str(max_uses)
    await message.answer(
        f"✅ Промокод создан!\n\n"
        f"Код: <b>{data['code']}</b>\n"
        f"Дней: <b>{data['days']}</b>\n"
        f"Использований: <b>{uses_label}</b>",
        reply_markup=admin_keyboard(),
    )
