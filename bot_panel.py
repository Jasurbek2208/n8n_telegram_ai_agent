"""Telegram boshqaruv paneli.

Egasi (dasturlashni bilmaydigan odam) telefonidagi Telegramdan shu botga kirib,
tugmalarni bosib profil qo'shadi, o'chiradi, sessiya tugaganda qayta kiradi.
Terminal umuman kerak emas.
"""

import asyncio
import logging
import re
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import account_manager as am
from account_manager import AccountManager
from app_config import save_config

log = logging.getLogger("userbot")

CANCEL_BTN = InlineKeyboardButton("✖️ Bekor qilish", "cancel")
BACK_BTN = InlineKeyboardButton("⬅️ Orqaga", "menu")


def kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([list(r) for r in rows])


MAIN_MENU = kb(
    [InlineKeyboardButton("➕ Yangi profil qo'shish", "add")],
    [InlineKeyboardButton("📋 Profillar ro'yxati", "list")],
    [
        InlineKeyboardButton("💾 Zaxira nusxa", "backup"),
        InlineKeyboardButton("❓ Yordam", "help"),
    ],
)

HELP_TEXT = (
    "❓ <b>Buyruqlar</b>\n\n"
    "Odatda tugmalardan foydalanasiz, lekin buyruq yozish ham mumkin:\n\n"
    "/menu — asosiy menyu\n"
    "/list — profillar ro'yxati\n"
    "/backup — zaxira nusxani fayl qilib yuboradi\n"
    "/off <code>nom</code> — profilni <b>to'xtatish</b> (o'chirilmaydi)\n"
    "/on <code>nom</code> — to'xtatilgan profilni qayta yoqish\n"
    "/delete <code>nom</code> — profilni <b>butunlay o'chirish</b>\n"
    "/status — server va profillar holati\n"
    "/id — Telegram ID ingiz\n\n"
    "<b>Boshqaruvchilar:</b>\n"
    "/admins — kim boshqara olishi\n"
    "/addadmin <code>ID</code> — yangi boshqaruvchi qo'shish\n"
    "/deladmin <code>ID</code> — boshqaruvchini olib tashlash\n\n"
    "<i>Misol:</i> <code>/off acc2</code>\n\n"
    "<b>To'xtatish</b> — profil vaqtincha javob bermaydi, lekin saqlanadi.\n"
    "<b>O'chirish</b> — profil ro'yxatdan butunlay olib tashlanadi."
)


class ControlPanel:
    def __init__(self, config: dict, manager: AccountManager):
        self.config = config
        self.manager = manager
        self.bot: Client | None = None
        # Har bir admin uchun ochilgan "sehrgar" (wizard) holati
        self.wizard: dict[int, dict] = {}

    # ---------- Ruxsat ----------

    @property
    def admin_ids(self) -> list[int]:
        return [int(x) for x in self.config.get("admin_ids", [])]

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids

    def claim_admin(self, user_id: int):
        """admin_ids bo'sh bo'lsa — birinchi yozgan odam egasi bo'ladi."""
        self.config.setdefault("admin_ids", []).append(user_id)
        save_config(self.config)
        log.warning("🔑 Egasi belgilandi: %s (config.json ga yozildi)", user_id)

    # ---------- Ishga tushirish ----------

    async def start(self) -> bool:
        token = (self.config.get("bot_token") or "").strip()
        if not token:
            log.warning(
                "⚠️ config.json da bot_token bo'sh — boshqaruv paneli ishga tushmadi. "
                "Profil qo'shish/qayta kirish imkoni bo'lmaydi."
            )
            return False

        api_id = self.config.get("default_api_id") or 0
        api_hash = self.config.get("default_api_hash") or ""
        if not api_id or not api_hash:
            # Mavjud akkauntdan olamiz
            accounts = self.manager.load_accounts()
            if accounts:
                api_id = accounts[0]["api_id"]
                api_hash = accounts[0]["api_hash"]
            else:
                log.error(
                    "❌ Panel uchun default_api_id / default_api_hash kerak (config.json)."
                )
                return False

        self.bot = Client(
            name="control_bot",
            api_id=api_id,
            api_hash=api_hash,
            bot_token=token,
            workdir=str(am.SESSIONS_DIR),
            parse_mode=ParseMode.HTML,
        )
        self.bot.add_handler(CallbackQueryHandler(self._on_callback))
        self.bot.add_handler(MessageHandler(self._on_message, filters.private & filters.text))

        await self.bot.start()
        me = await self.bot.get_me()
        log.info("🤖 Boshqaruv paneli ishga tushdi: @%s", me.username)

        if not self.admin_ids:
            log.warning(
                "⚠️ config.json da admin_ids bo'sh. Botga /start yozgan BIRINCHI odam egasi bo'ladi."
            )
        return True

    async def stop(self):
        if self.bot:
            try:
                await self.bot.stop()
            except Exception:
                pass

    async def notify_admins(self, text: str):
        if not self.bot:
            return
        for uid in self.admin_ids:
            try:
                await self.bot.send_message(uid, text, reply_markup=MAIN_MENU)
            except Exception:
                log.exception("Adminga (%s) xabar yuborilmadi", uid)

    # ---------- Ekranlar ----------

    async def _send_menu(self, chat_id: int, prefix: str = ""):
        rows = self.manager.overview()
        online = sum(1 for r in rows if r["status"] == am.ONLINE)
        problem = sum(1 for r in rows if r["status"] == am.NEEDS_AUTH)
        text = (
            f"{prefix}"
            f"🤖 <b>Userbot boshqaruvi</b>\n\n"
            f"Jami profillar: <b>{len(rows)}</b>\n"
            f"✅ Ishlayapti: <b>{online}</b>\n"
        )
        if problem:
            text += f"⚠️ Qayta kirish kerak: <b>{problem}</b>\n"
        text += "\nQuyidagi tugmalardan birini tanlang:"
        await self.bot.send_message(chat_id, text, reply_markup=MAIN_MENU)

    def _list_keyboard(self) -> InlineKeyboardMarkup:
        rows = []
        for r in self.manager.overview():
            label = f"{r['emoji']} {r['name']} — {r['phone']}"
            rows.append([InlineKeyboardButton(label, f"acc:{r['name']}")])
        rows.append([InlineKeyboardButton("➕ Yangi profil qo'shish", "add")])
        rows.append([BACK_BTN])
        return InlineKeyboardMarkup(rows)

    def _account_screen(self, name: str) -> tuple[str, InlineKeyboardMarkup]:
        row = next((r for r in self.manager.overview() if r["name"] == name), None)
        if not row:
            return "Profil topilmadi.", kb([BACK_BTN])

        text = (
            f"{row['emoji']} <b>{row['name']}</b>\n\n"
            f"📱 Telefon: <code>{row['phone']}</code>\n"
            f"📊 Holat: <b>{row['text']}</b>\n"
        )
        if row["webhook"]:
            text += f"🔗 n8n: <code>{row['webhook']}</code>\n"
        if row["error"]:
            text += f"\n<i>{row['error']}</i>\n"

        buttons = []
        if row["status"] == am.NEEDS_AUTH:
            buttons.append([InlineKeyboardButton("🔄 Qayta kirish", f"relogin:{name}")])
        elif row["status"] == am.ONLINE:
            buttons.append([InlineKeyboardButton("⏸ To'xtatish", f"off:{name}")])
        else:
            buttons.append([InlineKeyboardButton("▶️ Yoqish", f"on:{name}")])
            buttons.append([InlineKeyboardButton("🔄 Qayta kirish", f"relogin:{name}")])
        buttons.append([InlineKeyboardButton("🗑 O'chirish", f"del:{name}")])
        buttons.append([InlineKeyboardButton("📋 Ro'yxatga", "list"), BACK_BTN])
        return text, InlineKeyboardMarkup(buttons)

    # ---------- Xabarlar ----------

    async def _on_message(self, client: Client, message):
        uid = message.from_user.id if message.from_user else 0
        text = (message.text or "").strip()

        if not self.is_admin(uid):
            if not self.admin_ids and text.startswith("/start"):
                self.claim_admin(uid)
                await message.reply(
                    "🔑 <b>Siz ushbu tizimning egasi sifatida ro'yxatdan o'tdingiz.</b>\n\n"
                    "Endi faqat siz boshqara olasiz."
                )
                await self._send_menu(message.chat.id)
                return
            await message.reply(
                f"⛔ Sizda ruxsat yo'q.\n\nSizning ID: <code>{uid}</code>"
            )
            return

        if text.startswith("/"):
            await self._handle_command(message, text)
            return

        state = self.wizard.get(uid)
        if not state:
            await self._send_menu(message.chat.id)
            return

        await self._wizard_input(message, state, text)

    # ---------- Buyruqlar ----------

    async def _handle_command(self, message, text: str):
        uid = message.from_user.id
        chat_id = message.chat.id
        parts = text.split()
        cmd = parts[0].split("@")[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/start", "/menu"):
            self.wizard.pop(uid, None)
            await self._send_menu(chat_id)
            return

        if cmd in ("/help", "/yordam"):
            await self.bot.send_message(chat_id, HELP_TEXT, reply_markup=MAIN_MENU)
            return

        if cmd == "/id":
            await self.bot.send_message(chat_id, f"🆔 Sizning ID: <code>{uid}</code>")
            return

        if cmd == "/list":
            await self._send_list(chat_id)
            return

        if cmd == "/backup":
            await self._do_backup(chat_id)
            return

        if cmd == "/status":
            await self._send_status(chat_id)
            return

        if cmd == "/admins":
            lines = "\n".join(f"• <code>{a}</code>" for a in self.admin_ids)
            await self.bot.send_message(
                chat_id,
                f"👤 <b>Boshqaruvchilar</b>\n\n{lines}\n\n"
                f"Yangi qo'shish: <code>/addadmin ID</code>\n"
                f"<i>Yangi odam botga /start yozsa, o'z ID sini ko'radi.</i>",
            )
            return

        if cmd in ("/addadmin", "/deladmin"):
            digits = re.sub(r"\D", "", arg)
            if not digits:
                await self.bot.send_message(
                    chat_id, f"❌ ID yozing.\n\n<i>Misol:</i> <code>{cmd} 123456789</code>"
                )
                return
            target = int(digits)
            admins = self.config.setdefault("admin_ids", [])

            if cmd == "/addadmin":
                if target in admins:
                    await self.bot.send_message(chat_id, "ℹ️ Bu odam allaqachon boshqaruvchi.")
                    return
                admins.append(target)
                save_config(self.config)
                await self.bot.send_message(
                    chat_id, f"✅ <code>{target}</code> boshqaruvchi qilib qo'shildi."
                )
                try:
                    await self.bot.send_message(
                        target,
                        "🎉 Sizga userbot tizimini boshqarish huquqi berildi.\n\n"
                        "/start yozib boshlang.",
                    )
                except Exception:
                    await self.bot.send_message(
                        chat_id,
                        "⚠️ Unga xabar yubora olmadim — u avval botga /start yozishi kerak.",
                    )
                return

            # /deladmin
            if target not in admins:
                await self.bot.send_message(chat_id, "❌ Bunday boshqaruvchi yo'q.")
                return
            if len(admins) == 1:
                await self.bot.send_message(
                    chat_id,
                    "⛔ Oxirgi boshqaruvchini olib tashlab bo'lmaydi — "
                    "aks holda botni hech kim boshqara olmay qoladi.",
                )
                return
            admins.remove(target)
            save_config(self.config)
            await self.bot.send_message(chat_id, f"✅ <code>{target}</code> olib tashlandi.")
            return

        if cmd in ("/off", "/on", "/delete"):
            if not arg:
                names = ", ".join(r["name"] for r in self.manager.overview()) or "yo'q"
                await self.bot.send_message(
                    chat_id,
                    f"❌ Profil nomini yozing.\n\n<i>Misol:</i> <code>{cmd} acc2</code>\n\n"
                    f"Mavjud profillar: {names}",
                )
                return
            if not self.manager.get_account(arg):
                await self.bot.send_message(chat_id, f"❌ <b>{arg}</b> nomli profil topilmadi.")
                return

            if cmd == "/delete":
                await self.bot.send_message(
                    chat_id,
                    f"🗑 <b>{arg}</b> profilini butunlay o'chirmoqchimisiz?",
                    reply_markup=kb(
                        [InlineKeyboardButton("🗑 Ha, o'chirilsin", f"delyes:{arg}")],
                        [InlineKeyboardButton("✖️ Yo'q", "menu")],
                    ),
                )
                return

            await self.bot.send_message(chat_id, "⏳ Bajarilmoqda...")
            ok, msg = await self.manager.set_enabled(arg, cmd == "/on")
            body, markup = self._account_screen(arg)
            prefix = "✅ " if ok else f"⚠️ {msg}\n\n"
            await self.bot.send_message(chat_id, prefix + body, reply_markup=markup)
            return

        await self.bot.send_message(
            chat_id, "❓ Bunday buyruq yo'q. /help yozing.", reply_markup=MAIN_MENU
        )

    async def _send_list(self, chat_id: int):
        await self.bot.send_message(
            chat_id,
            "📋 <b>Profillar</b>\n\n"
            "✅ ishlayapti · ⚠️ qayta kirish kerak · ⏸ to'xtatilgan · ❌ xatolik\n\n"
            "Batafsil ko'rish uchun profilni tanlang:",
            reply_markup=self._list_keyboard(),
        )

    async def _send_status(self, chat_id: int):
        rows = self.manager.overview()
        lines = [f"{r['emoji']} <b>{r['name']}</b> — {r['text']}" for r in rows] or ["(profil yo'q)"]
        disk = shutil.disk_usage(str(am.BASE_DIR))
        text = (
            "📊 <b>Holat</b>\n\n" + "\n".join(lines) + "\n\n"
            f"💾 Disk: {disk.free // (1024**3)} GB bo'sh\n"
            f"🕒 Server vaqti: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        await self.bot.send_message(chat_id, text, reply_markup=MAIN_MENU)

    # ---------- Zaxira nusxa ----------

    def _make_backup(self) -> Path:
        """accounts.json + config.json + sessiyalarni bitta .tar.gz ga yig'adi.

        Sessiya fayllari SQLite — ishlab turgan paytda oddiy nusxa olish
        buzuq fayl berishi mumkin. Shuning uchun SQLite backup API ishlatiladi
        (izchil snapshot).
        """
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        out = am.BASE_DIR / f"backup_{ts}.tar.gz"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            copied: list[tuple[Path, str]] = []

            for fname in ("accounts.json", "config.json"):
                src = am.BASE_DIR / fname
                if src.exists():
                    dst = tmp_dir / fname
                    shutil.copy2(src, dst)
                    copied.append((dst, fname))

            for sess in sorted(am.SESSIONS_DIR.glob("*.session")):
                dst = tmp_dir / sess.name
                try:
                    src_db = sqlite3.connect(f"file:{sess}?mode=ro", uri=True)
                    dst_db = sqlite3.connect(str(dst))
                    with dst_db:
                        src_db.backup(dst_db)
                    src_db.close()
                    dst_db.close()
                except Exception:
                    log.exception("Sessiyani nusxalashda xato: %s", sess.name)
                    shutil.copy2(sess, dst)
                copied.append((dst, f"sessions/{sess.name}"))

            with tarfile.open(out, "w:gz") as tar:
                for path, arcname in copied:
                    tar.add(path, arcname=arcname)

        return out

    async def _do_backup(self, chat_id: int):
        await self.bot.send_message(chat_id, "⏳ Zaxira nusxa tayyorlanmoqda...")
        try:
            path = await asyncio.to_thread(self._make_backup)
        except Exception as e:
            log.exception("Zaxira olishda xato")
            await self.bot.send_message(chat_id, f"❌ Zaxira olinmadi: <code>{e}</code>")
            return

        size_kb = path.stat().st_size // 1024
        n_sessions = len(list(am.SESSIONS_DIR.glob("*.session")))
        n_accounts = len(self.manager.load_accounts())
        try:
            await self.bot.send_document(
                chat_id,
                str(path),
                caption=(
                    f"💾 <b>Zaxira nusxa</b>\n\n"
                    f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                    f"👤 Profillar: {n_accounts}\n"
                    f"🔑 Sessiyalar: {n_sessions}\n"
                    f"📦 Hajmi: {size_kb} KB\n\n"
                    f"⚠️ <b>Bu faylni hech kimga bermang</b> — ichida profillarga "
                    f"kirish kalitlari bor.\n\n"
                    f"<i>Faylni Telegramda «Saqlangan xabarlar» ga yuborib qo'ying.</i>"
                ),
            )
        except Exception as e:
            log.exception("Zaxirani yuborishda xato")
            await self.bot.send_message(chat_id, f"❌ Fayl yuborilmadi: <code>{e}</code>")
        finally:
            try:
                path.unlink()
            except Exception:
                pass

    async def _delete_secret(self, message):
        """Maxfiy ma'lumot (api_hash, parol) chatda qolib ketmasin."""
        try:
            await message.delete()
        except Exception:
            pass

    async def _wizard_input(self, message, state: dict, text: str):
        step = state["step"]
        cfg = state["cfg"]
        chat_id = message.chat.id

        # --- Telefon ---
        if step == "phone":
            phone = re.sub(r"[^\d+]", "", text)
            if not phone.startswith("+"):
                phone = "+" + phone.lstrip("+")
            if len(phone) < 9:
                await message.reply("❌ Telefon raqam qisqa. Masalan: <code>+998901234567</code>")
                return
            cfg["phone"] = phone
            await self._ask_api(chat_id, state)
            return

        # --- API ID ---
        if step == "api_id":
            digits = re.sub(r"\D", "", text)
            if not digits:
                await message.reply("❌ API ID faqat raqamlardan iborat. Qayta yuboring.")
                return
            cfg["api_id"] = int(digits)
            state["step"] = "api_hash"
            await self.bot.send_message(
                chat_id,
                "3️⃣ Endi <b>API HASH</b> ni yuboring.\n\n"
                "<i>(my.telegram.org saytidagi uzun harf-raqamli kod)</i>",
                reply_markup=kb([CANCEL_BTN]),
            )
            return

        # --- API HASH ---
        if step == "api_hash":
            value = text.strip()
            await self._delete_secret(message)
            if len(value) < 16:
                await self.bot.send_message(chat_id, "❌ API HASH juda qisqa. Qayta yuboring.")
                return
            cfg["api_hash"] = value
            await self._ask_webhook(chat_id, state)
            return

        # --- n8n webhook ---
        if step == "webhook":
            url = text.strip()
            if not url.startswith("http"):
                await message.reply("❌ Havola <code>https://</code> bilan boshlanishi kerak.")
                return
            cfg["n8n_webhook"] = url
            await self._ask_confirm(chat_id, state)
            return

        # --- Telegramdan kelgan kod ---
        if step == "code":
            name = cfg["name"]
            await self.bot.send_message(chat_id, "⏳ Tekshirilmoqda...")
            result, msg = await self.manager.submit_code(name, text)

            if result == "password":
                state["step"] = "password"
                await self.bot.send_message(
                    chat_id,
                    "🔐 Bu profilda <b>ikki bosqichli himoya (2FA)</b> yoqilgan.\n\n"
                    "Telegram parolingizni yuboring.\n\n"
                    "<i>Xavfsizlik uchun xabaringiz darhol o'chiriladi va parol hech qayerda saqlanmaydi.</i>",
                    reply_markup=kb([CANCEL_BTN]),
                )
                return
            if result == "bad_code":
                await self.bot.send_message(
                    chat_id,
                    f"❌ {msg}\n\n<i>Eslatma: kodni <b>1-2-3-4-5</b> ko'rinishida yozing.</i>",
                    reply_markup=kb([CANCEL_BTN]),
                )
                return
            if result == "ok":
                self.wizard.pop(message.from_user.id, None)
                await self.bot.send_message(
                    chat_id,
                    f"✅ <b>{name}</b> profili muvaffaqiyatli ulandi! {msg}\n\n"
                    f"Endi u xabarlarni qabul qilib, n8n ga yuboradi.",
                )
                await self._send_menu(chat_id)
                return
            # expired / error
            self.wizard.pop(message.from_user.id, None)
            await self.bot.send_message(chat_id, f"❌ {msg}")
            await self._send_menu(chat_id)
            return

        # --- 2FA parol ---
        if step == "password":
            name = cfg["name"]
            await self._delete_secret(message)
            await self.bot.send_message(chat_id, "⏳ Tekshirilmoqda...")
            result, msg = await self.manager.submit_password(name, text)

            if result == "bad_password":
                await self.bot.send_message(
                    chat_id, f"❌ {msg}", reply_markup=kb([CANCEL_BTN])
                )
                return
            self.wizard.pop(message.from_user.id, None)
            if result == "ok":
                await self.bot.send_message(
                    chat_id, f"✅ <b>{name}</b> profili muvaffaqiyatli ulandi! {msg}"
                )
            else:
                await self.bot.send_message(chat_id, f"❌ {msg}")
            await self._send_menu(chat_id)
            return

        # Tugma kutilayotgan qadamda matn yozilsa
        await self.bot.send_message(
            chat_id, "👆 Yuqoridagi tugmalardan birini bosing."
        )

    # ---------- Sehrgar qadamlari ----------

    async def _ask_api(self, chat_id: int, state: dict):
        cfg = state["cfg"]
        def_id = self.config.get("default_api_id")
        def_hash = self.config.get("default_api_hash")
        if def_id and def_hash:
            cfg["api_id"] = int(def_id)
            cfg["api_hash"] = def_hash
            await self._ask_webhook(chat_id, state)
            return
        state["step"] = "api_id"
        await self.bot.send_message(
            chat_id,
            "2️⃣ <b>API ID</b> ni yuboring.\n\n"
            "<i>(my.telegram.org saytidan olinadi — faqat raqamlar)</i>",
            reply_markup=kb([CANCEL_BTN]),
        )

    async def _ask_webhook(self, chat_id: int, state: dict):
        cfg = state["cfg"]
        default = self.config.get("default_n8n_webhook") or ""
        state["step"] = "webhook"
        buttons = []
        if default:
            buttons.append([InlineKeyboardButton("✅ Odatdagi havolani ishlatish", "defwh")])
        buttons.append([CANCEL_BTN])
        text = "3️⃣ <b>n8n havolasini</b> yuboring.\n\n<i>(webhook URL — n8n dan nusxa oling)</i>"
        if default:
            text += f"\n\nOdatdagi: <code>{default}</code>"
        await self.bot.send_message(chat_id, text, reply_markup=kb(*buttons))

    async def _ask_confirm(self, chat_id: int, state: dict):
        cfg = state["cfg"]
        state["step"] = "confirm"
        await self.bot.send_message(
            chat_id,
            "📋 <b>Tekshirib ko'ring:</b>\n\n"
            f"Nomi: <b>{cfg['name']}</b>\n"
            f"📱 Telefon: <code>{cfg['phone']}</code>\n"
            f"🔗 n8n: <code>{cfg.get('n8n_webhook', '')}</code>\n\n"
            "Hammasi to'g'rimi?",
            reply_markup=kb(
                [InlineKeyboardButton("✅ Ha, davom etish", "confirm_add")],
                [CANCEL_BTN],
            ),
        )

    async def _start_login(self, chat_id: int, uid: int, cfg: dict, is_new: bool):
        name = cfg["name"]
        await self.bot.send_message(chat_id, "⏳ Telegramga kod so'ralmoqda...")
        ok, msg = await self.manager.begin_login(cfg, is_new=is_new)
        if not ok:
            self.wizard.pop(uid, None)
            await self.bot.send_message(chat_id, f"❌ {msg}")
            await self._send_menu(chat_id)
            return

        self.wizard[uid] = {"step": "code", "cfg": cfg}
        await self.bot.send_message(
            chat_id,
            f"📩 <b>{cfg['phone']}</b> raqamiga Telegram kod yubordi.\n\n"
            "Kodni shu yerga yozing.\n\n"
            "⚠️ <b>JUDA MUHIM:</b> kodni oddiy <code>12345</code> ko'rinishida yozsangiz, "
            "Telegram uni bekor qiladi.\n"
            "Shuning uchun raqamlar orasiga chiziqcha qo'ying:\n\n"
            "<b>1-2-3-4-5</b>",
            reply_markup=kb([CANCEL_BTN]),
        )

    # ---------- Tugmalar ----------

    async def _on_callback(self, client: Client, cq):
        uid = cq.from_user.id
        if not self.is_admin(uid):
            await cq.answer("Ruxsat yo'q", show_alert=True)
            return

        data = cq.data or ""
        chat_id = cq.message.chat.id
        await cq.answer()

        if data == "menu":
            self.wizard.pop(uid, None)
            await self._send_menu(chat_id)
            return

        if data == "cancel":
            state = self.wizard.pop(uid, None)
            if state and state.get("step") in ("code", "password"):
                await self.manager.cancel_login(state["cfg"]["name"])
            await self.bot.send_message(chat_id, "✖️ Bekor qilindi.")
            await self._send_menu(chat_id)
            return

        if data == "list":
            await self._send_list(chat_id)
            return

        if data == "backup":
            await self._do_backup(chat_id)
            return

        if data == "help":
            await self.bot.send_message(chat_id, HELP_TEXT, reply_markup=MAIN_MENU)
            return

        if data == "add":
            name = self.manager.next_free_name()
            self.wizard[uid] = {
                "step": "phone",
                "cfg": {"name": name, "session_name": name, "enabled": True},
            }
            await self.bot.send_message(
                chat_id,
                f"➕ <b>Yangi profil: {name}</b>\n\n"
                "1️⃣ Telefon raqamni yuboring.\n\n"
                "Masalan: <code>+998901234567</code>",
                reply_markup=kb([CANCEL_BTN]),
            )
            return

        if data == "defwh":
            state = self.wizard.get(uid)
            if not state:
                await self._send_menu(chat_id)
                return
            state["cfg"]["n8n_webhook"] = self.config.get("default_n8n_webhook", "")
            await self._ask_confirm(chat_id, state)
            return

        if data == "confirm_add":
            state = self.wizard.get(uid)
            if not state:
                await self._send_menu(chat_id)
                return
            await self._start_login(chat_id, uid, state["cfg"], is_new=True)
            return

        if ":" not in data:
            return
        action, name = data.split(":", 1)

        if action == "acc":
            text, markup = self._account_screen(name)
            await self.bot.send_message(chat_id, text, reply_markup=markup)
            return

        if action == "relogin":
            cfg = self.manager.get_account(name)
            if not cfg:
                await self.bot.send_message(chat_id, "❌ Profil topilmadi.")
                return
            await self._start_login(chat_id, uid, cfg, is_new=False)
            return

        if action in ("on", "off"):
            await self.bot.send_message(chat_id, "⏳ Bajarilmoqda...")
            ok, msg = await self.manager.set_enabled(name, action == "on")
            text, markup = self._account_screen(name)
            prefix = "✅ " if ok else f"⚠️ {msg}\n\n"
            await self.bot.send_message(chat_id, prefix + text, reply_markup=markup)
            return

        if action == "del":
            await self.bot.send_message(
                chat_id,
                f"🗑 <b>{name}</b> profilini o'chirmoqchimisiz?\n\n"
                "<i>Profil ro'yxatdan olib tashlanadi. Keyin qaytadan qo'shish mumkin.</i>",
                reply_markup=kb(
                    [InlineKeyboardButton("🗑 Ha, o'chirilsin", f"delyes:{name}")],
                    [InlineKeyboardButton("✖️ Yo'q", "list")],
                ),
            )
            return

        if action == "delyes":
            ok, msg = await self.manager.remove_account(name)
            await self.bot.send_message(
                chat_id,
                f"{'✅' if ok else '❌'} <b>{name}</b> — {msg}",
            )
            await self._send_menu(chat_id)
            return
