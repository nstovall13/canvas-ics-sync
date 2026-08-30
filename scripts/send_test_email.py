"""One-off local test: confirms SMTP settings/credentials actually work before
relying on them in the daily workflow. Run manually, not part of CI.

Usage:
    python scripts/send_test_email.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import Config
from src.email_digest import send_email

if __name__ == "__main__":
    cfg = Config()
    if not cfg.smtp_username:
        print("SMTP_USERNAME is not set in .env -- nothing to test.")
        sys.exit(1)

    print(f"Sending a test email via {cfg.smtp_host}:{cfg.smtp_port} as {cfg.smtp_username} -> {cfg.email_to} ...")
    send_email(
        cfg.smtp_host, cfg.smtp_port, cfg.smtp_username, cfg.smtp_password,
        cfg.email_from, cfg.email_to,
        subject="canvas-ics-sync: test email",
        body="If you're reading this, SMTP is working.",
    )
    print("Sent. Check your inbox.")
