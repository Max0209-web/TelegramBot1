import aiosqlite
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from config import DB_PATH, INITIAL_PROMO_CODES

DB: aiosqlite.Connection = None


async def init_db():
    global DB
    DB = await aiosqlite.connect(DB_PATH)
    DB.row_factory = aiosqlite.Row
    await DB.execute("PRAGMA journal_mode=WAL")
    await DB.execute("PRAGMA foreign_keys=ON")
    await DB.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT NOT NULL,
            subscription_end TEXT,
            is_unlimited INTEGER DEFAULT 0,
            trial_used INTEGER DEFAULT 0,
            referrer_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS business_connections (
            connection_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            user_chat_id INTEGER NOT NULL,
            is_enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS message_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_connection_id TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            from_user_id INTEGER,
            message_id INTEGER NOT NULL,
            text TEXT,
            file_info TEXT,
            event_type TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            days INTEGER NOT NULL,
            max_uses INTEGER DEFAULT 0,
            uses_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS promo_uses (
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            used_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, code)
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            payment_type TEXT NOT NULL,
            plan_key TEXT NOT NULL,
            invoice_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    await DB.commit()

    for code in INITIAL_PROMO_CODES:
        await DB.execute(
            "INSERT OR IGNORE INTO promo_codes (code, days, max_uses) VALUES (?, 7, 0)",
            (code,),
        )
    await DB.commit()


async def close_db():
    if DB:
        await DB.close()


async def get_user(user_id: int) -> Optional[aiosqlite.Row]:
    async with DB.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
        return await cur.fetchone()


async def create_user(user_id: int, username: str, first_name: str, referrer_id: int = None):
    await DB.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, referrer_id) VALUES (?, ?, ?, ?)",
        (user_id, username, first_name, referrer_id),
    )
    await DB.commit()


async def is_subscription_active(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user:
        return False
    if user["is_unlimited"]:
        return True
    if not user["subscription_end"]:
        return False
    return datetime.fromisoformat(user["subscription_end"]) > datetime.now()


async def extend_subscription(user_id: int, days: int, unlimited: bool = False):
    if unlimited:
        await DB.execute(
            "UPDATE users SET is_unlimited = 1 WHERE user_id = ?", (user_id,)
        )
    else:
        user = await get_user(user_id)
        if user and user["is_unlimited"]:
            return
        now = datetime.now()
        if user and user["subscription_end"]:
            current_end = datetime.fromisoformat(user["subscription_end"])
            base = max(current_end, now)
        else:
            base = now
        new_end = (base + timedelta(days=days)).isoformat()
        await DB.execute(
            "UPDATE users SET subscription_end = ? WHERE user_id = ?",
            (new_end, user_id),
        )
    await DB.commit()


async def activate_trial(user_id: int):
    await extend_subscription(user_id, 7)
    await DB.execute(
        "UPDATE users SET trial_used = 1 WHERE user_id = ?", (user_id,)
    )
    await DB.commit()


async def apply_referral_bonus(referrer_id: int):
    await extend_subscription(referrer_id, 2)


async def get_promo_code(code: str) -> Optional[aiosqlite.Row]:
    async with DB.execute(
        "SELECT * FROM promo_codes WHERE code = ?", (code,)
    ) as cur:
        return await cur.fetchone()


async def use_promo_code(user_id: int, code: str) -> Dict[str, Any]:
    promo = await get_promo_code(code)
    if not promo:
        return {"success": False, "reason": "not_found"}

    async with DB.execute(
        "SELECT 1 FROM promo_uses WHERE user_id = ? AND code = ?", (user_id, code)
    ) as cur:
        if await cur.fetchone():
            return {"success": False, "reason": "already_used"}

    if promo["max_uses"] > 0 and promo["uses_count"] >= promo["max_uses"]:
        return {"success": False, "reason": "exhausted"}

    await DB.execute(
        "INSERT INTO promo_uses (user_id, code) VALUES (?, ?)", (user_id, code)
    )
    await DB.execute(
        "UPDATE promo_codes SET uses_count = uses_count + 1 WHERE code = ?", (code,)
    )
    await DB.commit()
    await extend_subscription(user_id, promo["days"])
    return {"success": True, "days": promo["days"]}


async def create_promo_code(code: str, days: int, max_uses: int = 0):
    await DB.execute(
        "INSERT OR REPLACE INTO promo_codes (code, days, max_uses) VALUES (?, ?, ?)",
        (code, days, max_uses),
    )
    await DB.commit()


async def log_business_message(
    connection_id: str,
    chat_id: int,
    from_user_id: Optional[int],
    message_id: int,
    text: str,
    file_info: dict,
    event_type: str,
):
    await DB.execute(
        """INSERT INTO message_logs
           (business_connection_id, chat_id, from_user_id, message_id, text, file_info, event_type)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (connection_id, chat_id, from_user_id, message_id, text, json.dumps(file_info), event_type),
    )
    await DB.commit()


async def get_logged_message(
    connection_id: str, chat_id: int, message_id: int
) -> Optional[aiosqlite.Row]:
    async with DB.execute(
        """SELECT * FROM message_logs
           WHERE business_connection_id = ? AND chat_id = ? AND message_id = ?
           ORDER BY created_at DESC LIMIT 1""",
        (connection_id, chat_id, message_id),
    ) as cur:
        return await cur.fetchone()


async def save_business_connection(
    connection_id: str, user_id: int, user_chat_id: int, is_enabled: bool
):
    await DB.execute(
        """INSERT OR REPLACE INTO business_connections
           (connection_id, user_id, user_chat_id, is_enabled)
           VALUES (?, ?, ?, ?)""",
        (connection_id, user_id, user_chat_id, 1 if is_enabled else 0),
    )
    await DB.commit()


async def get_business_connection(connection_id: str) -> Optional[aiosqlite.Row]:
    async with DB.execute(
        "SELECT * FROM business_connections WHERE connection_id = ?", (connection_id,)
    ) as cur:
        return await cur.fetchone()


async def get_all_users() -> List[aiosqlite.Row]:
    async with DB.execute("SELECT * FROM users") as cur:
        return await cur.fetchall()


async def get_stats() -> Dict[str, int]:
    async with DB.execute("SELECT COUNT(*) as total FROM users") as cur:
        total = (await cur.fetchone())["total"]
    now = datetime.now().isoformat()
    async with DB.execute(
        "SELECT COUNT(*) as active FROM users WHERE subscription_end > ? OR is_unlimited = 1",
        (now,),
    ) as cur:
        active = (await cur.fetchone())["active"]
    return {"total": total, "active": active}


async def create_payment(
    user_id: int, payment_type: str, plan_key: str, invoice_id: str = None
) -> int:
    cur = await DB.execute(
        "INSERT INTO payments (user_id, payment_type, plan_key, invoice_id) VALUES (?, ?, ?, ?)",
        (user_id, payment_type, plan_key, invoice_id),
    )
    await DB.commit()
    return cur.lastrowid


async def get_payment_by_invoice(invoice_id: str) -> Optional[aiosqlite.Row]:
    async with DB.execute(
        "SELECT * FROM payments WHERE invoice_id = ? AND status = 'pending'", (invoice_id,)
    ) as cur:
        return await cur.fetchone()


async def complete_payment(payment_id: int):
    await DB.execute(
        "UPDATE payments SET status = 'completed' WHERE id = ?", (payment_id,)
    )
    await DB.commit()
