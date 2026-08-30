"""Environment-driven configuration. No secrets are hardcoded here."""
import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class Config:
    def __init__(self):
        self.canvas_base_url = _require("CANVAS_BASE_URL").rstrip("/")
        self.canvas_token = _require("CANVAS_TOKEN")

        self.ics_output_path = os.environ.get("ICS_OUTPUT_PATH", "reminders.ics")
        self.calendar_name = os.environ.get("CALENDAR_NAME", "HBS Prep & Deadlines")

        # How far ahead to look for assignments/case sessions when generating reminders.
        self.lookahead_days = int(os.environ.get("LOOKAHEAD_DAYS", "60"))

        self.assignment_reminder_hour = int(os.environ.get("ASSIGNMENT_REMINDER_HOUR", "9"))
        self.case_reminder_hour = int(os.environ.get("CASE_REMINDER_HOUR", "18"))
        self.reminder_duration_minutes = int(os.environ.get("REMINDER_DURATION_MINUTES", "15"))

        # Daily "upcoming deadlines" digest email: assignments/exams due within
        # the next N days, sent once per run.
        self.digest_window_days = int(os.environ.get("DIGEST_WINDOW_DAYS", "14"))

        # IANA timezone name used to resolve reminder wall-clock times before converting to UTC.
        self.timezone = os.environ.get("REMINDER_TIMEZONE", "America/New_York")

        # SMTP settings for the digest email. Optional -- if SMTP_USERNAME isn't
        # set, the digest email is skipped (logged, not an error) so the .ics
        # side of this project keeps working standalone while email is being set up.
        self.smtp_host = os.environ.get("SMTP_HOST", "")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_username = os.environ.get("SMTP_USERNAME", "")
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")
        self.email_from = os.environ.get("EMAIL_FROM") or self.smtp_username
        self.email_to = os.environ.get("EMAIL_TO") or self.smtp_username
