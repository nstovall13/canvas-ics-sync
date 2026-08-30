"""Build and send the daily 'upcoming deadlines' digest as a plain email
(instead of a calendar event) via generic SMTP -- works with any provider;
which one is a config/secrets choice, not a code choice.
"""
import smtplib
from datetime import datetime
from email.message import EmailMessage
from zoneinfo import ZoneInfo

from src.parser import AssignmentReminder, CaseReminder


def build_digest_email(
    items: list[AssignmentReminder],
    window_days: int,
    tz_name: str,
    cases_tomorrow: list[CaseReminder] | None = None,
) -> tuple[str, str]:
    """Returns (subject, plain-text body). Pure function -- no network/IO."""
    cases_tomorrow = cases_tomorrow or []
    sorted_items = sorted(items, key=lambda i: i.due_at)
    sorted_cases = sorted(cases_tomorrow, key=lambda c: c.class_date)

    subject = f"Upcoming deadlines: {len(sorted_items)} in the next {window_days} days"

    if sorted_items:
        deadline_blocks = [
            f"{n}. {i.course_name}: {i.name}\n   Due: {i.due_at.astimezone(ZoneInfo(tz_name)):%a %b %d, %I:%M %p}"
            for n, i in enumerate(sorted_items, start=1)
        ]
        deadlines_section = f"Upcoming Deadlines (next {window_days} days)\n\n" + "\n\n".join(deadline_blocks)
    else:
        deadlines_section = f"Upcoming Deadlines (next {window_days} days)\n\nNo deadlines due in the next {window_days} days."

    if sorted_cases:
        case_blocks = [
            f"{n}. {c.course_name}: {c.case_name}\n   Class: {c.class_date.astimezone(ZoneInfo(tz_name)):%a %b %d, %I:%M %p}"
            for n, c in enumerate(sorted_cases, start=1)
        ]
        cases_section = "Case Prep for Tomorrow\n\n" + "\n\n".join(case_blocks)
    else:
        cases_section = "Case Prep for Tomorrow\n\nNo case prep due tomorrow."

    body = deadlines_section + "\n\n\n" + cases_section

    return subject, body


def send_email(smtp_host: str, smtp_port: int, username: str, password: str, from_addr: str, to_addr: str, subject: str, body: str):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(msg)
