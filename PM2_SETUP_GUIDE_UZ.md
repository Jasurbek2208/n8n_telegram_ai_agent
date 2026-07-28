# Ubuntu Server — o'rnatish va PM2 (dasturchi uchun)

> Egasi uchun alohida qo'llanma bor: **[EGASIGA_QOLLANMA.md](EGASIGA_QOLLANMA.md)**.
> Egasi terminalga umuman tegmaydi — u faqat Telegram bot orqali ishlaydi.

---

## 🟢 PRODUCTION (2026-07-27 dan beri ishlamoqda)

| | |
|---|---|
| Server | `ubuntu@3.121.189.70` (AWS Lightsail, Ubuntu 24.04.4 LTS, 2 vCPU / 2 GB) |
| Kirish | `ssh -i ~/.ssh/id_rsa_yangi ubuntu@3.121.189.70` |
| Loyiha | `/home/ubuntu/n8ntelegram` |
| Boshqaruv boti | **@n8n_agent_for_telegram_bot** |
| PM2 app | `n8n-telegram-userbot` |
| Eski kod | `/home/ubuntu/_ESKI_n8naiagent` (o'chirilmagan, zaxira sifatida) |
| Deploydan oldingi to'liq zaxira | `/home/ubuntu/PRE-DEPLOY-BACKUP_2026-07-27_18-21.tar.gz` |

### Serverda nima sozlangan

**Xavfsizlik**
- UFW: `deny incoming`, faqat 22-port (`LIMIT` rejimida — brute-force sekinlashtiriladi)
- fail2ban: sshd jail, 5 urinish → 1 soat ban
- SSH: parol bilan kirish **yopiq**, faqat kalit; `MaxAuthTries 3`; `X11Forwarding no`; `AllowTcpForwarding no`
- `unattended-upgrades`: xavfsizlik yamoqlari avtomatik
- `config.json`, `accounts.json`, `sessions/*` → **600**, `sessions/` → **700**
- `os.umask(0o077)` — dastur yaratgan yangi sessiya fayllari ham avtomatik 600

**Barqarorlik / performance**
- 2 GB swap (`/swapfile`, `vm.swappiness=10`) — 2 GB RAM da OOM'dan himoya
- **TgCrypto** o'rnatildi — MTProto shifrlash C da, sof Python'ga nisbatan bir necha barobar tez
- `pm2-logrotate`: 10 MB da aylanadi, 7 ta saqlanadi, siqiladi
- `logrotate`: `userbot.log` haftalik
- `pm2 startup systemd` + `pm2 save` — reboot'dan keyin avtomatik
- Vaqt mintaqasi: **Asia/Tashkent**

**Zaxira**
- Har kuni **03:00** da cron: `/home/ubuntu/backup-userbot.sh` → `/home/ubuntu/backups/` (14 kun)
- Egasi istalgan vaqtda botdan **💾 Zaxira nusxa** olishi mumkin

### Zaxiradan tiklash

```bash
cd /home/ubuntu/n8ntelegram
pm2 stop n8n-telegram-userbot
tar xzf /home/ubuntu/backups/userbot_YYYY-MM-DD.tar.gz -C .
chmod 600 config.json accounts.json sessions/*
pm2 restart n8n-telegram-userbot
```

### Egasini boshqaruvchi qilib belgilash

`config.json` dagi `admin_ids` **bo'sh** — botga birinchi `/start` yozgan odam
egasi bo'lib qoladi. Agar noto'g'ri odam bo'lsa:

```bash
nano /home/ubuntu/n8ntelegram/config.json   # admin_ids ni tuzating
pm2 restart n8n-telegram-userbot
```

Yoki mavjud admin botda `/addadmin <ID>` va `/deladmin <ID>` yozishi mumkin —
SSH kerak emas.

---

## Arxitektura — nima uchun shunday qilingan

Muammo: Pyrogram profilga birinchi marta kirganda (yoki sessiya tugaganda)
konsoldan kod va 2FA parol so'raydi. PM2 esa **non-interaktiv** ishlaydi —
stdin yo'q. Natijada `input()` → `EOFError` → jarayon qulaydi → PM2 uni qayta
ishga tushiradi → yana qulaydi (cheksiz sikl).

Yechim — uch qismdan iborat:

| Qism | Fayl | Vazifasi |
|------|------|----------|
| **Terminalsiz login** | `account_manager.py` | `client.start()` o'rniga past darajali `connect()` → `send_code()` → `sign_in()` → `check_password()`. Bu metodlar hech narsa so'ramaydi — kod/parolni biz beramiz. |
| **Boshqaruv paneli** | `bot_panel.py` | BotFather boti. Egasi tugma bosib profil qo'shadi, kod/parolni chatga yozadi. |
| **Bosh jarayon** | `userbot_multi.py` | Hech qanday `input()` yo'q. Har bir akkaunt alohida `try/except` — bittasi buzilsa qolganlari ishlayveradi. |

Qo'shimcha: `watchdog_loop()` har 5 daqiqada sessiyalarni tekshiradi va
o'lgan bo'lsa egasiga Telegram orqali xabar yuboradi.

---

## 1. Bot yaratish (BotFather)

1. Telegramda **@BotFather** ga kiring
2. `/newbot` → nom va username bering
3. Tokenni nusxalang: `123456789:AAF...`

## 2. Serverga yuklash

```bash
scp -r n8ntelegram ubuntu@SERVER_IP:/home/ubuntu/
```

## 3. `config.json` ni to'ldirish

```bash
nano /home/ubuntu/n8ntelegram/config.json
```

```json
{
  "bot_token": "123456789:AAF...",
  "admin_ids": [],
  "default_api_id": 22519226,
  "default_api_hash": "fe2a98dca...",
  "default_n8n_webhook": "https://.../webhook/telegram-userbot"
}
```

| Maydon | Izoh |
|--------|------|
| `bot_token` | BotFather'dan olingan token. **Majburiy.** |
| `admin_ids` | Kim boshqara oladi. **Bo'sh qoldiring** — botga `/start` yozgan birinchi odam avtomatik egasi bo'ladi va shu faylga yoziladi. |
| `default_api_id` / `default_api_hash` | my.telegram.org dan. Bitta juftlikni **barcha profillar uchun** ishlatsa bo'ladi — shuning uchun egasidan bu so'ralmaydi. |
| `default_n8n_webhook` | Odatiy webhook. Egasi bir tugma bilan tanlaydi. |

> ⚠️ `admin_ids` ni bo'sh qoldirsangiz — **egasining o'zi** birinchi bo'lib
> `/start` yozsin. Aks holda siz egasi bo'lib qolasiz. Keyin tuzatish uchun
> `config.json` dagi ID ni almashtiring va `pm2 restart` qiling.

## 4. O'rnatish

```bash
cd /home/ubuntu/n8ntelegram
chmod +x setup-pm2.sh manage-pm2.sh
./setup-pm2.sh
```

Skript o'zi bajaradi: venv → kutubxonalar → `logs/` va `sessions/` → PM2 start →
server reboot bo'lsa avtomatik yoqilishi (`pm2 startup` + `pm2 save`).

Yo'llar `ecosystem.config.js` da **`__dirname` orqali avtomatik** aniqlanadi —
qo'lda tahrirlash shart emas.

## 5. Tekshirish

```bash
pm2 status
pm2 logs n8n-telegram-userbot --lines 50
```

Kutilayotgan natija:

```
🤖 Boshqaruv paneli ishga tushdi: @sizning_botingiz
👂 1 / 1 ta profil faol.
```

---

## Kundalik buyruqlar

```bash
pm2 status                              # holat
pm2 logs n8n-telegram-userbot           # jonli loglar
pm2 restart n8n-telegram-userbot        # qayta ishga tushirish
pm2 stop n8n-telegram-userbot           # to'xtatish
./manage-pm2.sh                         # menyu ko'rinishida
```

---

## Muhim texnik nuqtalar

### Telegram login kodini bekor qilishi

Telegram, login kodi **Telegram xabari orqali uzatilsa**, uni avtomatik bekor
qiladi (himoya mexanizmi). Shuning uchun egasi kodni `1-2-3-4-5` ko'rinishida
yozadi, kod esa raqamlarni ajratib oladi:

```python
clean = "".join(ch for ch in code if ch.isdigit())
```

Bu qoida `EGASIGA_QOLLANMA.md` da ham, bot xabarlarida ham alohida ta'kidlangan.

### Maxfiy ma'lumotlar

- 2FA parol va `api_hash` chatga yozilgach — bot xabarni **darhol o'chiradi**
- 2FA parol **hech qayerda saqlanmaydi**, faqat `check_password()` ga uzatiladi
- `sessions/*.session` fayllari — login kalitlari. Zaxira nusxa olsangiz shular
  bilan birga oling, aks holda tiklashda hamma profillar qaytadan login qiladi

### Zaxira nusxa (backup)

```bash
tar czf backup-$(date +%F).tar.gz accounts.json config.json sessions/
```

### Xatoliklar

| Belgi | Sabab | Yechim |
|-------|-------|--------|
| Panel ishga tushmadi | `bot_token` bo'sh | `config.json` ni to'ldiring, restart |
| Profil ⚠️ holatida | Sessiya tugagan | Egasi botdan «🔄 Qayta kirish» bosadi |
| Profil ❌ holatida | Tarmoq / API xatosi | `pm2 logs` dan matnni o'qing |
| `FloodWait` | Juda ko'p login urinishi | Xabarda ko'rsatilgan vaqt kutiladi |

---

## Fayllar

```
userbot_multi.py      # bosh jarayon (PM2 shuni ishga tushiradi)
account_manager.py    # akkauntlar + terminalsiz login
bot_panel.py          # Telegram boshqaruv paneli
handlers.py           # kelgan xabarni n8n ga yuborish
app_config.py         # config.json bilan ishlash
config.json           # bot_token, admin_ids, standart qiymatlar
accounts.json         # qo'shilgan profillar (bot o'zi yozadi)
sessions/             # Telegram sessiya fayllari
ecosystem.config.js   # PM2 konfiguratsiyasi
setup-pm2.sh          # bir martalik o'rnatish
manage-pm2.sh         # kundalik boshqaruv menyusi
EGASIGA_QOLLANMA.md   # egasi uchun qo'llanma
```
