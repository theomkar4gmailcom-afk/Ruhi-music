import asyncio
import logging
import os
import re
from pathlib import Path
from collections import defaultdict, deque

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from dotenv import load_dotenv
from pyrogram import Client
from pytgcalls import PyTgCalls, filters as call_filters
from pytgcalls.types import StreamEnded

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger("ruhi-music")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "").strip()
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/")
UPDATES_URL = os.getenv("UPDATES_URL", "https://t.me/")
OWNER_URL = os.getenv("OWNER_URL", "https://t.me/")
BANNER_PATH = Path(os.getenv("BANNER_PATH", "assets/ruhi_music_banner.jpg"))
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing in .env")
if not API_ID or not API_HASH or not SESSION_STRING:
    raise RuntimeError("API_ID, API_HASH and SESSION_STRING are required for voice-chat playback")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# A separate MTProto user session is used only as the voice-chat assistant.
assistant = Client(
    "ruhi_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)
calls = PyTgCalls(assistant)

queues = defaultdict(deque)
current = {}
volume = defaultdict(lambda: 100)
locks = defaultdict(asyncio.Lock)


def home_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ ADD ME IN YOUR GROUP ➕",
                              url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton(text="📚 HELP AND COMMANDS", callback_data="help")],
        [
            InlineKeyboardButton(text="🛠 SUPPORT", url=SUPPORT_URL),
            InlineKeyboardButton(text="🌀 UPDATES", url=UPDATES_URL),
        ],
        [InlineKeyboardButton(text="👑 OWNER", url=OWNER_URL)],
    ])


def help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎵 MUSIC COMMANDS", callback_data="music_help")],
        [InlineKeyboardButton(text="🏠 HOME", callback_data="home")],
    ])


def player_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏸ PAUSE", callback_data="pause"),
            InlineKeyboardButton(text="▶️ RESUME", callback_data="resume"),
        ],
        [
            InlineKeyboardButton(text="⏭ SKIP", callback_data="skip"),
            InlineKeyboardButton(text="⏹ STOP", callback_data="stop"),
        ],
    ])


WELCOME = (
    "<b>Hᴏʟᴏᴏ - !!</b> ✨\n\n"
    "<b>I AM THE FAST AND POWERFUL MUSIC PLAYER BOT WITH SOME AWESOME FEATURES.</b>\n\n"
    "<blockquote>"
    "🎶 <b>HIGH-QUALITY MUSIC PLAYER BOT FOR TELEGRAM GROUPS</b>\n\n"
    "🔥 INSTANT STREAMING\n"
    "❤️ SMOOTH PLAYBACK\n"
    "🎧 CRYSTAL SOUND | NO LAG"
    "</blockquote>\n\n"
    "<b>Click on the Help button to get information about my modules and commands.</b>"
)


async def send_home(message: Message):
    me = await bot.get_me()
    keyboard = home_keyboard(me.username or "your_bot")
    if BANNER_PATH.exists():
        await message.answer_photo(
            FSInputFile(BANNER_PATH),
            caption=WELCOME,
            reply_markup=keyboard,
        )
    else:
        await message.answer(WELCOME, reply_markup=keyboard)


@dp.message(CommandStart())
async def start_handler(message: Message):
    await send_home(message)


@dp.callback_query(F.data == "home")
async def home_callback(query: CallbackQuery):
    await query.answer()
    await query.message.edit_caption(
        caption=WELCOME,
        reply_markup=home_keyboard((await bot.get_me()).username or "your_bot"),
    )


@dp.callback_query(F.data == "help")
async def help_callback(query: CallbackQuery):
    await query.answer()
    await query.message.edit_caption(
        caption=(
            "<b>📚 RUHI MUSIC — HELP MENU</b>\n\n"
            "🎵 Add the bot and assistant account to your group.\n"
            "🎙 Start a group voice chat manually.\n"
            "📩 Reply to an audio file with <code>/play</code>.\n\n"
            "<b>Commands</b>\n"
            "/play — play replied audio\n"
            "/pause — pause playback\n"
            "/resume — resume playback\n"
            "/skip — skip current track\n"
            "/stop — stop and clear queue\n"
            "/queue — show waiting tracks\n"
            "/volume 1-200 — set playback volume\n"
            "/help — show this menu"
        ),
        reply_markup=help_keyboard(),
    )


@dp.callback_query(F.data == "music_help")
async def music_help_callback(query: CallbackQuery):
    await query.answer()
    await query.message.edit_caption(
        caption=(
            "<b>🎵 MUSIC COMMANDS</b>\n\n"
            "1. Send an audio file in your group.\n"
            "2. Reply to that audio with <code>/play</code>.\n"
            "3. Keep a group voice chat running.\n\n"
            "<b>Playback:</b> /pause, /resume, /skip, /stop\n"
            "<b>Queue:</b> /queue\n"
            "<b>Volume:</b> /volume 1-200"
        ),
        reply_markup=help_keyboard(),
    )


async def is_admin(message: Message) -> bool:
    if message.chat.type == "private":
        return True
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    return member.status in ("administrator", "creator")


def replied_audio(message: Message):
    if not message.reply_to_message:
        return None
    item = message.reply_to_message
    if item.audio:
        return item.audio
    if item.document and (item.document.mime_type or "").startswith("audio/"):
        return item.document
    return None


async def start_next(chat_id: int):
    async with locks[chat_id]:
        if not queues[chat_id]:
            current.pop(chat_id, None)
            return False
        item = queues[chat_id].popleft()
        current[chat_id] = item
        try:
            await calls.play(chat_id, str(item["path"]))
            await calls.change_volume_call(chat_id, volume[chat_id])
            return True
        except Exception:
            log.exception("Could not start playback in %s", chat_id)
            current.pop(chat_id, None)
            try:
                item["path"].unlink(missing_ok=True)
            except Exception:
                pass
            return False


@calls.on_update(call_filters.stream_end())
async def stream_end_handler(_: PyTgCalls, update: StreamEnded):
    chat_id = update.chat_id
    item = current.pop(chat_id, None)
    if item:
        item["path"].unlink(missing_ok=True)
    await start_next(chat_id)


@dp.message(Command("play"))
async def play_handler(message: Message):
    audio = replied_audio(message)
    if not audio:
        await message.reply("🎵 Kisi audio file par reply karke <code>/play</code> bhejo.")
        return
    if message.chat.type == "private":
        await message.reply("🎧 Music playback ke liye group mein command use karo.")
        return
    if not await is_admin(message):
        await message.reply("⛔ Only group admins can control playback.")
        return

    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", audio.file_name or f"{audio.file_unique_id}.mp3")
    path = DOWNLOAD_DIR / f"{message.chat.id}_{audio.file_unique_id}_{safe_name}"
    try:
        await bot.download(audio, destination=path)
    except Exception as exc:
        log.exception("Audio download failed")
        await message.reply(f"❌ Audio download failed: <code>{type(exc).__name__}</code>")
        return

    queues[message.chat.id].append({
        "title": audio.file_name or "Telegram audio",
        "path": path,
        "by": message.from_user.full_name,
    })

    if message.chat.id not in current:
        ok = await start_next(message.chat.id)
        if ok:
            item = current[message.chat.id]
            await message.reply(
                f"🎶 <b>Now playing:</b> {item['title']}\n"
                f"👤 Requested by: {item['by']}",
                reply_markup=player_keyboard(),
            )
        else:
            await message.reply(
                "⚠️ Playback start nahi hua. Group voice chat active rakho aur assistant account ko group mein add karo."
            )
    else:
        await message.reply(f"➕ Added to queue: <b>{audio.file_name or 'Telegram audio'}</b>")


async def control_allowed(message: Message) -> bool:
    return await is_admin(message)


@dp.message(Command("pause"))
async def pause_handler(message: Message):
    if not await control_allowed(message):
        return await message.reply("⛔ Only admins can control playback.")
    try:
        await calls.pause(message.chat.id)
        await message.reply("⏸ Playback paused.")
    except Exception as exc:
        await message.reply(f"⚠️ {type(exc).__name__}: no active stream?")


@dp.message(Command("resume"))
async def resume_handler(message: Message):
    if not await control_allowed(message):
        return await message.reply("⛔ Only admins can control playback.")
    try:
        await calls.resume(message.chat.id)
        await message.reply("▶️ Playback resumed.")
    except Exception as exc:
        await message.reply(f"⚠️ {type(exc).__name__}: no paused stream?")


@dp.message(Command("skip"))
async def skip_handler(message: Message):
    if not await control_allowed(message):
        return await message.reply("⛔ Only admins can control playback.")
    item = current.pop(message.chat.id, None)
    if item:
        item["path"].unlink(missing_ok=True)
    try:
        await calls.leave_call(message.chat.id)
    except Exception:
        pass
    if await start_next(message.chat.id):
        item = current[message.chat.id]
        await message.reply(f"⏭ <b>Now playing:</b> {item['title']}", reply_markup=player_keyboard())
    else:
        await message.reply("⏭ Queue is empty.")


@dp.message(Command("stop"))
async def stop_handler(message: Message):
    if not await control_allowed(message):
        return await message.reply("⛔ Only admins can control playback.")
    item = current.pop(message.chat.id, None)
    if item:
        item["path"].unlink(missing_ok=True)
    while queues[message.chat.id]:
        queued = queues[message.chat.id].popleft()
        queued["path"].unlink(missing_ok=True)
    try:
        await calls.leave_call(message.chat.id)
    except Exception:
        pass
    await message.reply("⏹ Playback stopped. Queue cleared.")


@dp.message(Command("queue"))
async def queue_handler(message: Message):
    lines = []
    if message.chat.id in current:
        lines.append(f"▶️ <b>Playing:</b> {current[message.chat.id]['title']}")
    for index, item in enumerate(list(queues[message.chat.id]), 1):
        lines.append(f"{index}. {item['title']}")
    await message.reply("\n".join(lines) if lines else "📭 Queue is empty.")


@dp.message(Command("volume"))
async def volume_handler(message: Message):
    if not await control_allowed(message):
        return await message.reply("⛔ Only admins can control playback.")
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.reply("Usage: <code>/volume 1-200</code>")
    value = int(parts[1])
    if not 1 <= value <= 200:
        return await message.reply("Volume range: 1 to 200.")
    volume[message.chat.id] = value
    try:
        await calls.change_volume_call(message.chat.id, value)
    except Exception:
        pass
    await message.reply(f"🔊 Volume set to {value}%.")


@dp.message(Command("help"))
async def help_command(message: Message):
    await message.reply(
        "<b>RUHI MUSIC COMMANDS</b>\n"
        "/play — reply to an audio file\n"
        "/pause /resume /skip /stop\n"
        "/queue\n"
        "/volume 1-200"
    )


@dp.callback_query(F.data.in_({"pause", "resume", "skip", "stop"}))
async def player_controls(query: CallbackQuery):
    chat_id = query.message.chat.id
    action = query.data
    try:
        if action == "pause":
            await calls.pause(chat_id)
            await query.answer("Paused")
        elif action == "resume":
            await calls.resume(chat_id)
            await query.answer("Resumed")
        elif action == "skip":
            item = current.pop(chat_id, None)
            if item:
                item["path"].unlink(missing_ok=True)
            try:
                await calls.leave_call(chat_id)
            except Exception:
                pass
            await start_next(chat_id)
            await query.answer("Skipped")
        elif action == "stop":
            item = current.pop(chat_id, None)
            if item:
                item["path"].unlink(missing_ok=True)
            while queues[chat_id]:
                queues[chat_id].popleft()["path"].unlink(missing_ok=True)
            try:
                await calls.leave_call(chat_id)
            except Exception:
                pass
            await query.answer("Stopped")
    except Exception as exc:
        await query.answer(f"Playback error: {type(exc).__name__}", show_alert=True)


async def main():
    log.info("Starting Ruhi Music assistant...")
    await assistant.start()
    calls.start()
    log.info("Starting Telegram bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await calls.stop()
        await assistant.stop()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
