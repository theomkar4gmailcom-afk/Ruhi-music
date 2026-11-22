# Ruhi Music Telegram Bot

Python Telegram bot with a pink/purple anime welcome interface and group voice-chat playback.

## Included

- Screenshot-inspired `/start` banner and inline menu.
- Add-to-group, Help, Support, Updates and Owner buttons.
- `/play` by replying to an audio file in a group.
- `/pause`, `/resume`, `/skip`, `/stop`, `/queue`, `/volume`.
- Queue and inline playback controls.
- Audio comes from Telegram audio/document messages. No third-party music scraping or download service is included.

## Requirements

- Python 3.11
- FFmpeg installed on the host (recommended for media decoding)
- A Telegram bot token from BotFather
- Telegram API ID and API hash
- A Pyrogram user session string for the voice-chat assistant

## Setup

1. Create `.env` from `.env.example`.
2. Fill `BOT_TOKEN`, `API_ID`, `API_HASH`, `SESSION_STRING`, `OWNER_ID` and your support/update links.
3. Install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. Start a group voice chat manually in the target Telegram group.
5. Add the bot to the group and grant permission to send messages/media.
6. Add the assistant user account (the account used for `SESSION_STRING`) to the group.
7. Run:

   ```bash
   python main.py
   ```

8. In the group, send an audio file, reply to it with `/play`.

## Important behavior

- `/play` currently accepts a reply to a Telegram audio file or audio document. It does not search YouTube or other services.
- A group voice chat must already be active. The assistant account must be a member of that group.
- The Bot API download method has file-size limits. Keep test audio files small.
- Only group admins can control playback.
- Use audio you have permission to play/share.

## Hosting

Run as a persistent worker on a VPS or another host that supports long-running Python processes, FFmpeg and the PyTgCalls native dependencies. A serverless function is not suitable for continuous voice playback.

## UI customization

Replace `assets/ruhi_music_banner.jpg` with your own banner. Update Support, Updates and Owner URLs in `.env`.
