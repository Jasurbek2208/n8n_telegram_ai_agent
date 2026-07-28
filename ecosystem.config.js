const path = require("path");

// Loyiha papkasi avtomatik aniqlanadi — qo'lda yozish shart emas.
const PROJECT_DIR = __dirname;
const PYTHON = path.join(PROJECT_DIR, ".venv", "bin", "python3");

module.exports = {
  apps: [
    {
      name: "n8n-telegram-userbot",
      script: PYTHON,
      args: "userbot_multi.py",
      cwd: PROJECT_DIR,
      interpreter: "none",
      watch: false,
      max_memory_restart: "1000M",
      error_file: path.join(PROJECT_DIR, "logs", "error.log"),
      out_file: path.join(PROJECT_DIR, "logs", "out.log"),
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      merge_logs: true,
      autorestart: true,
      // Cheksiz qayta urinsin: tarmoq uzilsa ham o'zi tiklanadi.
      max_restarts: 50,
      min_uptime: "20s",
      restart_delay: 5000,
      kill_timeout: 10000,
      env: {
        NODE_ENV: "production",
        PYTHONUNBUFFERED: "1",
        PYTHONIOENCODING: "utf-8",
      },
    },
  ],
};
