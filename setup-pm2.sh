#!/bin/bash
# ============================================
#  Ubuntu Server — bir martalik o'rnatish
#  (bu skriptni FAQAT dasturchi bir marta ishlatadi)
# ============================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LOGS_DIR="$PROJECT_DIR/logs"

echo "🚀 O'rnatish boshlandi: $PROJECT_DIR"

# 1. Python muhiti
echo "📦 Python muhiti tayyorlanmoqda..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "✅ Virtual environment yaratildi"
fi
"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
echo "✅ Kutubxonalar o'rnatildi"

# 2. Papkalar
mkdir -p "$LOGS_DIR" "$PROJECT_DIR/sessions"
echo "✅ Papkalar tayyor"

# 3. config.json tekshiruvi
if [ ! -f "$PROJECT_DIR/config.json" ]; then
    cat > "$PROJECT_DIR/config.json" <<'EOF'
{
  "bot_token": "",
  "admin_ids": [],
  "default_api_id": 0,
  "default_api_hash": "",
  "default_n8n_webhook": ""
}
EOF
    echo "📝 config.json yaratildi"
fi

BOT_TOKEN=$(python3 -c "import json;print(json.load(open('$PROJECT_DIR/config.json')).get('bot_token',''))" 2>/dev/null || echo "")
if [ -z "$BOT_TOKEN" ]; then
    echo ""
    echo "⚠️  DIQQAT: config.json dagi \"bot_token\" bo'sh!"
    echo "   1) Telegramda @BotFather ga kiring"
    echo "   2) /newbot buyrug'ini yuboring, nom bering"
    echo "   3) Olingan tokenni config.json ga yozing:"
    echo "        nano $PROJECT_DIR/config.json"
    echo "   4) So'ng shu skriptni qayta ishga tushiring."
    echo ""
    read -p "Davom etaveraymi? (ha/yo'q): " ans
    [ "$ans" = "ha" ] || exit 1
fi

# 4. PM2
if ! command -v pm2 &> /dev/null; then
    echo "🔧 PM2 o'rnatilmoqda..."
    sudo npm install -g pm2
fi
echo "✅ PM2 tayyor"

# 5. Ishga tushirish
cd "$PROJECT_DIR"
pm2 delete n8n-telegram-userbot 2>/dev/null || true
pm2 start ecosystem.config.js
pm2 save

# 6. Server qayta yuklansa avtomatik ishga tushsin
STARTUP_CMD=$(pm2 startup systemd -u "$(whoami)" --hp "$HOME" | grep "sudo env" || true)
if [ -n "$STARTUP_CMD" ]; then
    echo "🔄 Avtomatik ishga tushirish sozlanmoqda..."
    eval "$STARTUP_CMD"
    pm2 save
fi

echo ""
echo "======================================"
echo "✅ O'RNATISH TUGADI"
echo "======================================"
echo ""
echo "Keyingi qadam — Telegramda:"
echo "  1) Yaratgan botingizni oching va /start yuboring."
echo "  2) Agar config.json dagi admin_ids bo'sh bo'lsa, /start yozgan"
echo "     BIRINCHI odam egasi bo'lib qoladi (shuni egasining o'zi bajarsin)."
echo "  3) «➕ Yangi profil qo'shish» tugmasi bilan profillar qo'shiladi."
echo ""
echo "Foydali buyruqlar:"
echo "  pm2 status"
echo "  pm2 logs n8n-telegram-userbot"
echo "  ./manage-pm2.sh"
echo ""
