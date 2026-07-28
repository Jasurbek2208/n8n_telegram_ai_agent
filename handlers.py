import logging
import httpx

log = logging.getLogger("userbot")


def make_log_everything(account_name: str):
    """Har bir akkaunt uchun alohida debug-logger yaratadi (faqat shaxsiy xabarlarga ulanadi)."""

    async def log_everything(client, message):
        # Removed per-message logging - this was generating too many logs
        pass

    return log_everything


def make_handle_message(account_name: str, n8n_webhook: str):
    """Har bir akkaunt uchun asosiy javob beruvchi handlerni yaratadi (original logika o'zgarmagan)."""

    async def handle_message(client, message):
        if not n8n_webhook:
            log.warning("[%s] n8n havolasi bo'sh — xabar yuborilmadi.", account_name)
            return
        try:
            payload = {
                "account": account_name,
                "user_id": message.from_user.id if message.from_user else None,
                "username": message.from_user.username if message.from_user else None,
                "text": message.text,
                "chat_id": message.chat.id,
            }
            async with httpx.AsyncClient(timeout=30) as http_client:
                response = await http_client.post(n8n_webhook, json=payload)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                except Exception:
                    log.warning("[%s] Javob JSON emas, reply yuborilmadi.", account_name)
                    return
                ai_response = result.get("response", "Javob yo'q")
                await message.reply(ai_response)
            else:
                log.warning("[%s] Webhook %s, reply yuborilmadi.", account_name, response.status_code)
        except Exception as e:
            log.exception("[%s] handle_message ichida xato: %s", account_name, e)

    return handle_message