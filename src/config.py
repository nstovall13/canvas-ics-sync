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

        # IANA timezone name used to resolve reminder wall-clock times before converting to UTC.
        self.timezone = os.environ.get("REMINDER_TIMEZONE", "America/New_York")
