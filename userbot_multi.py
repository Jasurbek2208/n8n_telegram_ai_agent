"""Multi-akkaunt Telegram userbot — PM2 uchun tayyor (terminal talab qilmaydi).

Nima o'zgardi (eski versiyaga nisbatan):
  1. `input()` chaqiruvlari olib tashlandi. PM2 non-interaktiv ishlaydi, stdin yo'q,
     shuning uchun eski kod `EOFError` bilan cheksiz qulab tushardi.
  2. Har bir akkaunt alohida try/except ichida ishga tushadi — bittasi buzilsa
     qolganlari ishlayveradi.
  3. Profil qo'shish / qayta kirish / to'xtatish — hammasi Telegram bot paneli
     orqali (bot_panel.py). Egasi telefonidan tugma bosib boshqaradi.

Terminal faqat dasturchi uchun, birinchi o'rnatishda (TTY bo'lsa) qo'shimcha
imkoniyat sifatida qoladi.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Yaratilgan barcha fayllar (sessiyalar, loglar, config) faqat egasiga o'qilsin.
# Sessiya fayli — bu Telegram akkauntiga kirish kaliti, uni boshqalar ko'rmasligi kerak.
os.umask(0o077)

# --- Yangi Python versiyalarida Pyrogram import xatosini oldini olish ---
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
# -----------------------------------------------------------------------

from pyrogram import idle

from account_manager import AccountManager
from app_config import load_config
from bot_panel import ControlPanel

BASE_DIR = Path(__file__).resolve().parent

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(BASE_DIR / "userbot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("userbot")

for noisy in ("pyrogram", "pyrogram.session", "pyrogram.connection", "pyrogram.methods"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


async def console_setup(manager: AccountManager):
    """Faqat TTY (haqiqiy terminal) bo'lsa ishlaydi — dasturchi uchun zaxira yo'l.

    PM2 ostida bu funksiya UMUMAN ishga tushmaydi.
    """
    while True:
        try:
            cmd = (await asyncio.to_thread(input, "\n[+] Yangi akkaunt: 'add' | chiqish: Ctrl+C > ")).strip().lower()
        except (EOFError, OSError):
            log.info("Terminal yo'q — konsol rejimi to'xtatildi.")
            return
        if cmd != "add":
            continue
        try:
            name = manager.next_free_name()
            print(f"Profil nomi: {name}")
            phone = (await asyncio.to_thread(input, "Telefon (+998...): ")).strip()
            api_id = int((await asyncio.to_thread(input, "API_ID: ")).strip())
            api_hash = (await asyncio.to_thread(input, "API_HASH: ")).strip()
            webhook = (await asyncio.to_thread(input, "n8n webhook URL: ")).strip()

            cfg = {
                "name": name,
                "session_name": name,
                "api_id": api_id,
                "api_hash": api_hash,
                "phone": phone,
                "n8n_webhook": webhook,
                "enabled": True,
            }
            ok, msg = await manager.begin_login(cfg, is_new=True)
            if not ok:
                print(f"❌ {msg}")
                continue

            code = (await asyncio.to_thread(input, "Telegramdan kelgan kod: ")).strip()
            result, msg = await manager.submit_code(name, code)
            if result == "password":
                import getpass
                pw = await asyncio.to_thread(getpass.getpass, "2FA parol: ")
                result, msg = await manager.submit_password(name, pw)
            print(("✅ " if result == "ok" else "❌ ") + msg)
        except Exception:
            log.exception("Akkaunt qo'shishda xato")


async def main():
    config = load_config()
    manager = AccountManager()
    panel = ControlPanel(config, manager)
    manager.notify = panel.notify_admins

    await manager.start_all()

    panel_ok = await panel.start()

    rows = manager.overview()
    online = sum(1 for r in rows if r["status"] == "online")
    log.info("👂 %d / %d ta profil faol.", online, len(rows))

    if not rows:
        log.warning("Hech qanday profil yo'q. Telegram bot orqali «➕ Yangi profil qo'shish».")
    if not panel_ok:
        log.error(
            "❌ Boshqaruv paneli ishlamayapti — config.json dagi bot_token ni to'ldiring va restart qiling."
        )
    else:
        # Ishga tushishda muammoli profillar bo'lsa — egasiga BITTA umumiy xabar
        # (har biri uchun alohida spam qilmaymiz).
        bad = [r for r in rows if r["status"] in ("needs_auth", "error")]
        if bad:
            lines = "\n".join(f"{r['emoji']} <b>{r['name']}</b> — {r['text']}" for r in bad)
            await panel.notify_admins(
                f"🔔 Tizim qayta ishga tushdi.\n\n"
                f"✅ Ishlayapti: <b>{online}</b>\n"
                f"E'tibor talab qiladi:\n{lines}\n\n"
                f"«📋 Profillar ro'yxati» dan tanlab, «🔄 Qayta kirish» ni bosing."
            )

    watchdog = asyncio.create_task(manager.watchdog_loop())

    console = None
    if sys.stdin is not None and sys.stdin.isatty():
        console = asyncio.create_task(console_setup(manager))

    await idle()

    watchdog.cancel()
    if console:
        console.cancel()
    await panel.stop()
    await manager.stop_all()


if __name__ == "__main__":
    print("✅ Multi-akkaunt userbot ishga tushmoqda...")
    asyncio.run(main())
