import json

from aiogram import Bot, Router
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, Message

import database as db

router = Router()


def extract_file_info(message: Message) -> dict:
    if message.photo:
        return {"photo_file_id": message.photo[-1].file_id}
    if message.video:
        return {"video_file_id": message.video.file_id}
    if message.voice:
        return {"voice_file_id": message.voice.file_id}
    if message.audio:
        return {"audio_file_id": message.audio.file_id}
    if message.document:
        return {"document_file_id": message.document.file_id}
    if message.sticker:
        return {"sticker_file_id": message.sticker.file_id}
    if message.animation:
        return {"animation_file_id": message.animation.file_id}
    if message.video_note:
        return {"video_note_file_id": message.video_note.file_id}
    return {}


async def deliver_message(bot: Bot, chat_id: int, text: str, file_info: dict, header: str):
    caption = f"{header}\n{text}" if text else header

    if file_info.get("photo_file_id"):
        await bot.send_photo(chat_id, file_info["photo_file_id"], caption=caption)
    elif file_info.get("video_file_id"):
        await bot.send_video(chat_id, file_info["video_file_id"], caption=caption)
    elif file_info.get("voice_file_id"):
        if caption:
            await bot.send_message(chat_id, caption)
        await bot.send_voice(chat_id, file_info["voice_file_id"])
    elif file_info.get("audio_file_id"):
        await bot.send_audio(chat_id, file_info["audio_file_id"], caption=caption)
    elif file_info.get("document_file_id"):
        await bot.send_document(chat_id, file_info["document_file_id"], caption=caption)
    elif file_info.get("sticker_file_id"):
        if caption:
            await bot.send_message(chat_id, caption)
        await bot.send_sticker(chat_id, file_info["sticker_file_id"])
    elif file_info.get("animation_file_id"):
        await bot.send_animation(chat_id, file_info["animation_file_id"], caption=caption)
    elif file_info.get("video_note_file_id"):
        if caption:
            await bot.send_message(chat_id, caption)
        await bot.send_video_note(chat_id, file_info["video_note_file_id"])
    elif text:
        await bot.send_message(chat_id, caption)


@router.business_connection()
async def handle_business_connection(connection: BusinessConnection):
    await db.save_business_connection(
        connection.id,
        connection.user.id,
        connection.user_chat_id,
        connection.is_enabled,
    )


@router.business_message()
async def handle_business_message(message: Message):
    connection = await db.get_business_connection(message.business_connection_id)
    if not connection or not await db.is_subscription_active(connection["user_id"]):
        return

    await db.log_business_message(
        message.business_connection_id,
        message.chat.id,
        message.from_user.id if message.from_user else None,
        message.message_id,
        message.text or message.caption or "",
        extract_file_info(message),
        "new",
    )


@router.edited_business_message()
async def handle_edited_business_message(message: Message, bot: Bot):
    connection = await db.get_business_connection(message.business_connection_id)
    if not connection or not await db.is_subscription_active(connection["user_id"]):
        return

    original = await db.get_logged_message(
        message.business_connection_id, message.chat.id, message.message_id
    )

    await db.log_business_message(
        message.business_connection_id,
        message.chat.id,
        message.from_user.id if message.from_user else None,
        message.message_id,
        message.text or message.caption or "",
        extract_file_info(message),
        "edit",
    )

    if original:
        orig_file_info = json.loads(original["file_info"]) if original["file_info"] else {}
        orig_text = original["text"] or ""
        sender = message.from_user.first_name if message.from_user else "Неизвестный"
        header = f"✏️ Изменённое сообщение\n👤 От: {sender}\n\n— Было:"
        await deliver_message(bot, connection["user_chat_id"], orig_text, orig_file_info, header)


@router.deleted_business_messages()
async def handle_deleted_business_messages(deleted: BusinessMessagesDeleted, bot: Bot):
    connection = await db.get_business_connection(deleted.business_connection_id)
    if not connection or not await db.is_subscription_active(connection["user_id"]):
        return

    chat_label = deleted.chat.title or str(deleted.chat.id)
    for message_id in deleted.message_ids:
        original = await db.get_logged_message(
            deleted.business_connection_id, deleted.chat.id, message_id
        )
        if not original:
            continue
        file_info = json.loads(original["file_info"]) if original["file_info"] else {}
        text = original["text"] or ""
        header = f"🗑 Удалённое сообщение\n💬 Чат: {chat_label}"
        await deliver_message(bot, connection["user_chat_id"], text, file_info, header)
