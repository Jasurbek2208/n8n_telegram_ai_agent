"""config.json bilan ishlash."""

import json
import logging
from pathlib import Path

log = logging.getLogger("userbot")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"

DEFAULTS = {
    "bot_token": "",
    "admin_ids": [],
    "default_api_id": 0,
    "default_api_hash": "",
    "default_n8n_webhook": "",
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            log.exception("config.json o'qib bo'lmadi — standart qiymatlar ishlatiladi")
    else:
        save_config(cfg)
        log.warning("config.json yaratildi — bot_token ni to'ldiring.")
    return cfg


def save_config(cfg: dict):
    CONFIG_FILE.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )
