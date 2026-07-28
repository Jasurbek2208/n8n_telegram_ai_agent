"""Akkauntlarni boshqarish — TERMINALSIZ.

Bu modulning eng muhim jihati: Pyrogram'ning `client.start()` metodi sessiya
yo'q yoki eskirgan bo'lsa konsoldan `input()` orqali kod so'raydi. PM2 esa
non-interaktiv ishlaydi (stdin yo'q) => EOFError => jarayon o'ladi.

Shuning uchun bu yerda past darajali API ishlatiladi:
    connect() -> send_code() -> sign_in() -> check_password()
Bu metodlar hech qanday terminal so'ramaydi — kod va parolni biz beramiz
(Telegram bot paneli orqali).
"""

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Awaitable, Callable, Optional

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.errors import (
    ApiIdInvalid,
    AuthKeyDuplicated,
    AuthKeyUnregistered,
    FloodWait,
    PasswordHashInvalid,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    PhoneNumberBanned,
    PhoneNumberInvalid,
    SessionExpired,
    SessionPasswordNeeded,
    SessionRevoked,
    UserDeactivated,
)

from handlers import make_handle_message

log = logging.getLogger("userbot")

BASE_DIR = Path(__file__).resolve().parent
ACCOUNTS_FILE = BASE_DIR / "accounts.json"
SESSIONS_DIR = BASE_DIR / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

# Sessiya o'lganini bildiruvchi xatolar — bularda qayta login qilish kerak
AUTH_DEAD_ERRORS = (
    AuthKeyUnregistered,
    AuthKeyDuplicated,
    SessionRevoked,
    SessionExpired,
    UserDeactivated,
)

# --- Holatlar ---
ONLINE = "online"          # ishlayapti
NEEDS_AUTH = "needs_auth"  # sessiya tugagan, qayta kirish kerak
STOPPED = "stopped"        # egasi qo'lda to'xtatgan
ERROR = "error"            # boshqa xato

STATUS_EMOJI = {
    ONLINE: "✅",
    NEEDS_AUTH: "⚠️",
    STOPPED: "⏸",
    ERROR: "❌",
}

STATUS_TEXT = {
    ONLINE: "ishlayapti",
    NEEDS_AUTH: "qayta kirish kerak",
    STOPPED: "to'xtatilgan",
    ERROR: "xatolik",
}


class LoginFlow:
    """Bitta akkaunt uchun boshlangan, lekin hali tugallanmagan login jarayoni."""

    def __init__(self, cfg: dict, client: Client, phone_code_hash: str, is_new: bool):
        self.cfg = cfg
        self.client = client
        self.phone_code_hash = phone_code_hash
        self.is_new = is_new  # yangi akkauntmi yoki mavjudini qayta loginmi

    async def cleanup(self):
        try:
            if self.client.is_connected:
                await self.client.disconnect()
        except Exception:
            pass


class AccountManager:
    """Bir nechta Telegram akkauntini bitta jarayonda boshqaradi."""

    def __init__(self):
        self.clients: dict[str, Client] = {}
        self.status: dict[str, str] = {}
        self.last_error: dict[str, str] = {}
        self.logins: dict[str, LoginFlow] = {}
        # Panel ulanganda o'rnatiladi: egasiga xabar yuborish uchun
        self.notify: Optional[Callable[[str], Awaitable[None]]] = None

    # ---------- accounts.json ----------

    def load_accounts(self) -> list[dict]:
        if not ACCOUNTS_FILE.exists():
            return []
        try:
            return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            log.exception("accounts.json o'qib bo'lmadi")
            return []

    def save_accounts(self, accounts: list[dict]):
        ACCOUNTS_FILE.write_text(
            json.dumps(accounts, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def get_account(self, name: str) -> Optional[dict]:
        for cfg in self.load_accounts():
            if cfg["name"] == name:
                return cfg
        return None

    def upsert_account(self, cfg: dict):
        accounts = self.load_accounts()
        for i, existing in enumerate(accounts):
            if existing["name"] == cfg["name"]:
                accounts[i] = cfg
                break
        else:
            accounts.append(cfg)
        self.save_accounts(accounts)

    def name_exists(self, name: str) -> bool:
        return any(a["name"] == name for a in self.load_accounts())

    def next_free_name(self) -> str:
        """acc1, acc2, acc3 ... — bo'sh nomni topadi."""
        i = 1
        while self.name_exists(f"acc{i}"):
            i += 1
        return f"acc{i}"

    # ---------- Klient qurish ----------

    def _build_client(self, cfg: dict) -> Client:
        return Client(
            name=cfg.get("session_name", cfg["name"]),
            api_id=cfg["api_id"],
            api_hash=cfg["api_hash"],
            phone_number=cfg.get("phone"),
            workdir=str(SESSIONS_DIR),
            sleep_threshold=60,
        )

    def _attach_handlers(self, client: Client, name: str, n8n_webhook: str):
        client.add_handler(
            MessageHandler(
                make_handle_message(name, n8n_webhook),
                filters.private & ~filters.bot,
            ),
            group=0,
        )

    def session_file(self, cfg: dict) -> Path:
        return SESSIONS_DIR / f"{cfg.get('session_name', cfg['name'])}.session"

    # ---------- Ishga tushirish ----------

    async def start_all(self):
        """Barcha yoqilgan akkauntlarni ishga tushiradi.

        MUHIM: har biri alohida try/except ichida — bitta akkaunt buzilsa
        qolganlari baribir ishlayveradi (avval hammasi yiqilardi).
        """
        for cfg in self.load_accounts():
            name = cfg["name"]
            if not cfg.get("enabled", True):
                self.status[name] = STOPPED
                log.info("[%s] O'chirilgan (egasi to'xtatgan) — o'tkazib yuborildi.", name)
                continue
            await self.start_account(cfg, notify_on_fail=False)

    async def start_account(self, cfg: dict, notify_on_fail: bool = True) -> tuple[bool, str]:
        """Bitta akkauntni ishga tushiradi. Terminal SO'RAMAYDI."""
        name = cfg["name"]
        if name in self.clients:
            return True, "allaqachon ishlayapti"

        # Sessiya fayli yo'q bo'lsa — start() konsoldan kod so'ragan bo'lardi.
        # Uni umuman chaqirmaymiz, darhol "qayta kirish kerak" holatiga qo'yamiz.
        if not self.session_file(cfg).exists():
            self.status[name] = NEEDS_AUTH
            self.last_error[name] = "Sessiya fayli topilmadi"
            log.warning("[%s] ⚠️ Sessiya yo'q — Telegram bot orqali kirish kerak.", name)
            if notify_on_fail:
                await self._notify(
                    f"⚠️ <b>{name}</b> — sessiya topilmadi.\n"
                    f"Botdan «🔄 Qayta kirish» tugmasini bosing."
                )
            return False, "Sessiya yo'q"

        client = self._build_client(cfg)
        self._attach_handlers(client, name, cfg.get("n8n_webhook", ""))

        try:
            # start() ichida so'rov bo'lmasligi uchun avval avtorizatsiyani tekshiramiz
            await client.connect()
            try:
                await client.get_me()
            except AUTH_DEAD_ERRORS:
                raise
            await client.disconnect()

            await client.start()
            me = await client.get_me()
            self.clients[name] = client
            self.status[name] = ONLINE
            self.last_error.pop(name, None)
            log.info("[%s] ✅ Ulandi: id=%s | @%s | %s", name, me.id, me.username, me.first_name)
            return True, f"@{me.username or me.id}"

        except AUTH_DEAD_ERRORS as e:
            await self._safe_disconnect(client)
            self.status[name] = NEEDS_AUTH
            self.last_error[name] = type(e).__name__
            log.warning("[%s] ⚠️ Sessiya tugagan (%s) — qayta kirish kerak.", name, type(e).__name__)
            if notify_on_fail:
                await self._notify(
                    f"⚠️ <b>{name}</b> profilining sessiyasi tugadi.\n"
                    f"Botdan «🔄 Qayta kirish» tugmasini bosing."
                )
            return False, "Sessiya tugagan"

        except Exception as e:
            await self._safe_disconnect(client)
            self.status[name] = ERROR
            self.last_error[name] = f"{type(e).__name__}: {e}"
            log.exception("[%s] ❌ Ishga tushirishda xato", name)
            if notify_on_fail:
                await self._notify(f"❌ <b>{name}</b> ishga tushmadi:\n<code>{e}</code>")
            return False, str(e)

    async def _safe_disconnect(self, client: Client):
        try:
            if client.is_connected:
                await client.disconnect()
        except Exception:
            pass

    async def stop_account(self, name: str, mark: str = STOPPED):
        client = self.clients.pop(name, None)
        if client:
            try:
                await client.stop()
            except Exception:
                log.exception("[%s] To'xtatishda xato", name)
        self.status[name] = mark
        log.info("[%s] To'xtatildi.", name)

    async def stop_all(self):
        for name in list(self.clients):
            await self.stop_account(name, mark=STOPPED)

    async def set_enabled(self, name: str, enabled: bool) -> tuple[bool, str]:
        cfg = self.get_account(name)
        if not cfg:
            return False, "Profil topilmadi"
        cfg["enabled"] = enabled
        self.upsert_account(cfg)
        if enabled:
            return await self.start_account(cfg)
        await self.stop_account(name)
        return True, "To'xtatildi"

    async def remove_account(self, name: str) -> tuple[bool, str]:
        cfg = self.get_account(name)
        if not cfg:
            return False, "Profil topilmadi"
        await self.stop_account(name)
        # Sessiya faylini axlatga emas, backup'ga ko'chiramiz (xato bo'lsa qaytarish uchun)
        sf = self.session_file(cfg)
        if sf.exists():
            backup = SESSIONS_DIR / f"{sf.name}.deleted"
            try:
                shutil.move(str(sf), str(backup))
            except Exception:
                log.exception("[%s] Sessiya faylini ko'chirishda xato", name)
        self.save_accounts([a for a in self.load_accounts() if a["name"] != name])
        self.status.pop(name, None)
        self.last_error.pop(name, None)
        log.info("[%s] O'chirildi.", name)
        return True, "O'chirildi"

    # ---------- TERMINALSIZ LOGIN ----------

    async def begin_login(self, cfg: dict, is_new: bool) -> tuple[bool, str]:
        """1-qadam: Telegramga kod yuborishni so'raydi."""
        name = cfg["name"]
        await self.cancel_login(name)

        if name in self.clients:
            await self.stop_account(name, mark=NEEDS_AUTH)

        # Eski (o'lik yoki chala) sessiya fayli yangi loginga xalaqit beradi —
        # har qanday holatda toza boshlaymiz.
        sf = self.session_file(cfg)
        if sf.exists():
            try:
                sf.unlink()
            except Exception:
                log.exception("[%s] Eski sessiyani o'chirishda xato", name)

        client = self._build_client(cfg)
        try:
            await client.connect()
            sent = await client.send_code(cfg["phone"])
        except (PhoneNumberInvalid,):
            await self._safe_disconnect(client)
            return False, "Telefon raqam noto'g'ri. Masalan: +998901234567"
        except PhoneNumberBanned:
            await self._safe_disconnect(client)
            return False, "Bu raqam Telegram tomonidan bloklangan."
        except ApiIdInvalid:
            await self._safe_disconnect(client)
            return False, "API ID / API HASH noto'g'ri."
        except FloodWait as e:
            await self._safe_disconnect(client)
            mins = max(1, e.value // 60)
            return False, f"Telegram juda ko'p urinish deb hisobladi. {mins} daqiqadan keyin qayta urinib ko'ring."
        except Exception as e:
            await self._safe_disconnect(client)
            log.exception("[%s] send_code xatosi", name)
            return False, f"Xato: {e}"

        self.logins[name] = LoginFlow(cfg, client, sent.phone_code_hash, is_new)
        return True, "Kod yuborildi"

    async def submit_code(self, name: str, code: str) -> tuple[str, str]:
        """2-qadam. Natija: ok | password | bad_code | expired | error"""
        flow = self.logins.get(name)
        if not flow:
            return "error", "Login jarayoni topilmadi. Boshidan boshlang."

        # Telegramdan kelgan kodni tozalaymiz: "1-2-3-4-5" -> "12345"
        clean = "".join(ch for ch in code if ch.isdigit())
        if not clean:
            return "bad_code", "Kodda raqam yo'q."

        try:
            await flow.client.sign_in(flow.cfg["phone"], flow.phone_code_hash, clean)
        except SessionPasswordNeeded:
            return "password", "2FA parol kerak"
        except PhoneCodeInvalid:
            return "bad_code", "Kod noto'g'ri. Qayta yuboring."
        except PhoneCodeExpired:
            await self.cancel_login(name)
            return "expired", "Kodning muddati tugadi. Boshidan boshlang."
        except FloodWait as e:
            await self.cancel_login(name)
            mins = max(1, e.value // 60)
            return "error", f"Juda ko'p urinish. {mins} daqiqadan keyin urinib ko'ring."
        except Exception as e:
            log.exception("[%s] sign_in xatosi", name)
            await self.cancel_login(name)
            return "error", f"Xato: {e}"

        ok, msg = await self._finish_login(name)
        return ("ok" if ok else "error"), msg

    async def submit_password(self, name: str, password: str) -> tuple[str, str]:
        """3-qadam (2FA). Natija: ok | bad_password | error"""
        flow = self.logins.get(name)
        if not flow:
            return "error", "Login jarayoni topilmadi. Boshidan boshlang."

        try:
            await flow.client.check_password(password)
        except PasswordHashInvalid:
            return "bad_password", "Parol noto'g'ri. Qayta yuboring."
        except FloodWait as e:
            await self.cancel_login(name)
            mins = max(1, e.value // 60)
            return "error", f"Juda ko'p urinish. {mins} daqiqadan keyin urinib ko'ring."
        except Exception as e:
            log.exception("[%s] check_password xatosi", name)
            await self.cancel_login(name)
            return "error", f"Xato: {e}"

        ok, msg = await self._finish_login(name)
        return ("ok" if ok else "error"), msg

    async def _finish_login(self, name: str) -> tuple[bool, str]:
        """Login muvaffaqiyatli: sessiyani diskka yozamiz va akkauntni ishga tushiramiz."""
        flow = self.logins.pop(name)
        try:
            me = await flow.client.get_me()
            username = f"@{me.username}" if me.username else str(me.id)
        except Exception:
            username = ""
        # disconnect() sessiya faylini diskka saqlaydi
        await flow.cleanup()

        cfg = flow.cfg
        cfg["enabled"] = True
        self.upsert_account(cfg)

        ok, msg = await self.start_account(cfg)
        if ok:
            return True, username or msg
        return False, msg

    async def cancel_login(self, name: str):
        flow = self.logins.pop(name, None)
        if flow:
            await flow.cleanup()

    # ---------- Nazorat ----------

    async def watchdog_loop(self, interval: int = 300):
        """Har 5 daqiqada tekshiradi: sessiya o'lgan bo'lsa egasiga xabar beradi."""
        while True:
            await asyncio.sleep(interval)
            for name, client in list(self.clients.items()):
                try:
                    await client.get_me()
                except AUTH_DEAD_ERRORS as e:
                    log.warning("[%s] Sessiya o'ldi (%s)", name, type(e).__name__)
                    await self.stop_account(name, mark=NEEDS_AUTH)
                    self.last_error[name] = type(e).__name__
                    await self._notify(
                        f"⚠️ <b>{name}</b> profilidan chiqib ketildi.\n"
                        f"Botdan «🔄 Qayta kirish» tugmasini bosing."
                    )
                except Exception:
                    # Vaqtinchalik tarmoq muammosi — Pyrogram o'zi qayta ulanadi
                    pass

    async def _notify(self, text: str):
        if self.notify:
            try:
                await self.notify(text)
            except Exception:
                log.exception("Xabar yuborishda xato")

    # ---------- Ko'rinish ----------

    def overview(self) -> list[dict]:
        rows = []
        for cfg in self.load_accounts():
            name = cfg["name"]
            if not cfg.get("enabled", True):
                fallback = STOPPED
            elif not self.session_file(cfg).exists():
                fallback = NEEDS_AUTH
            else:
                fallback = ERROR
            st = self.status.get(name, fallback)
            rows.append(
                {
                    "name": name,
                    "phone": cfg.get("phone", ""),
                    "webhook": cfg.get("n8n_webhook", ""),
                    "status": st,
                    "emoji": STATUS_EMOJI.get(st, "❔"),
                    "text": STATUS_TEXT.get(st, "noma'lum"),
                    "error": self.last_error.get(name, ""),
                }
            )
        return rows
