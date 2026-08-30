"""Build the reminders.ics feed from parsed Canvas items.

Reminder times are resolved as local wall-clock times via zoneinfo (correctly
handling DST for the given calendar date) and then converted to UTC before
being written out -- so the .ics file itself only ever contains plain UTC
timestamps ("Z" suffix), which every calendar client (Outlook included)
interprets unambiguously without needing an embedded VTIMEZONE block.
"""
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event

from src.parser import AssignmentReminder, CaseReminder


def _reminder_start(event_datetime_utc: datetime, hour: int, tz_name: str) -> datetime:
    """The reminder fires at `hour` local time on the day before `event_datetime_utc`."""
    local_dt = event_datetime_utc.astimezone(ZoneInfo(tz_name))
    reminder_date = (local_dt - timedelta(days=1)).date()
    naive_start = datetime.combine(reminder_date, time(hour=hour))
    return naive_start.replace(tzinfo=ZoneInfo(tz_name))


def _make_event(uid: str, subject: str, start_local: datetime, duration_minutes: int, body: str) -> Event:
    event = Event()
    event.add("uid", uid)
    event.add("summary", subject)
    event.add("dtstart", start_local.astimezone(timezone.utc))
    event.add("dtend", (start_local + timedelta(minutes=duration_minutes)).astimezone(timezone.utc))
    event.add("dtstamp", datetime.now(timezone.utc))
    event.add("sequence", 0)
    event.add("description", body)
    event["transp"] = "TRANSPARENT"  # doesn't block the user's free/busy time
    return event


def build_assignment_event(item: AssignmentReminder, hour: int, tz_name: str, duration_minutes: int) -> Event:
    start = _reminder_start(item.due_at, hour, tz_name)
    uid = f"canvas-{item.uid_source}-reminder@canvas-sync"
    subject = f"⏰ Due Tomorrow: {item.name}"

    due_local = item.due_at.astimezone(ZoneInfo(tz_name))
    body_lines = [f"Course: {item.course_name}", f"Due: {due_local:%A, %B %d at %I:%M %p %Z}"]
    if item.canvas_url:
        body_lines.append(f"Canvas: {item.canvas_url}")

    return _make_event(uid, subject, start, duration_minutes, "\n".join(body_lines))


def build_case_event(item: CaseReminder, hour: int, tz_name: str, duration_minutes: int) -> Event:
    start = _reminder_start(item.class_date, hour, tz_name)
    uid = f"canvas-case-{item.uid_source}-reminder@canvas-sync"
    subject = f"\U0001f4da Case Prep: {item.case_name} ({item.course_name} tomorrow)"

    class_local = item.class_date.astimezone(ZoneInfo(tz_name))
    body_lines = [f"Course: {item.course_name}", f"Class: {class_local:%A, %B %d at %I:%M %p %Z}"]
    if item.case_citation and item.case_citation.lower() not in item.case_name.lower():
        body_lines.append(f"Materials: Case: {item.case_citation}")
    if item.canvas_url:
        body_lines.append(f"Canvas: {item.canvas_url}")

    return _make_event(uid, subject, start, duration_minutes, "\n".join(body_lines))


def build_calendar(events: list[Event], calendar_name: str, tz_name: str) -> Calendar:
    cal = Calendar()
    cal.add("prodid", "-//canvas-ics-sync//canvas-sync//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", calendar_name)
    cal.add("x-wr-timezone", tz_name)
    for event in events:
        cal.add_component(event)
    return cal
