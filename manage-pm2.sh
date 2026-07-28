#!/bin/bash
# ============================================
#  PM2 boshqaruvi (dasturchi uchun)
#  Egasi bu skriptga umuman tegmaydi — u Telegram bot orqali ishlaydi.
# ============================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROCESS_NAME="n8n-telegram-userbot"

show_menu() {
    echo ""
    echo "======================================"
    echo "  PM2 Process Manager"
    echo "======================================"
    echo "1) Status ko'rish"
    echo "2) Logs ko'rish (real-time)"
    echo "3) Restart qilish"
    echo "4) Stop qilish"
    echo "5) Start qilish"
    echo "6) Profillar holati (accounts.json)"
    echo "7) Chiqish"
    echo "======================================"
}

while true; do
    show_menu
    read -p "Tanlovni kiriting (1-7): " choice
    case $choice in
        1) pm2 status "$PROCESS_NAME" ;;
        2) echo "(Ctrl+C bilan chiqing)"; pm2 logs "$PROCESS_NAME" ;;
        3) pm2 restart "$PROCESS_NAME"; sleep 2; pm2 status "$PROCESS_NAME" ;;
        4) pm2 stop "$PROCESS_NAME" ;;
        5) cd "$PROJECT_DIR" && pm2 start ecosystem.config.js ;;
        6) cat "$PROJECT_DIR/accounts.json" 2>/dev/null || echo "accounts.json topilmadi" ;;
        7) echo "Chiqilmoqda..."; exit 0 ;;
        *) echo "❌ Noto'g'ri tanlov!" ;;
    esac
    read -p "Davom etish uchun Enter bosing..."
done
