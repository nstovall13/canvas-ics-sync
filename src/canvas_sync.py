"""Daily entrypoint: Canvas -> parse -> reminders.ics (regenerated from scratch each run)."""
import sys
from datetime import datetime, timedelta, timezone

# Windows consoles often default to cp1252, which can't print the emoji used
# in reminder subjects; force UTF-8 for stdout so logging never crashes.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.canvas_client import CanvasClient
from src.config import Config
from src.ics_builder import build_assignment_event, build_case_event, build_calendar
from src.parser import parse_assignments, parse_calendar_case_events


def main():
    cfg = Config()
    now_utc = datetime.now(timezone.utc)
    horizon = now_utc + timedelta(days=cfg.lookahead_days)

    canvas = CanvasClient(cfg.canvas_base_url, cfg.canvas_token)

    courses = canvas.get_active_courses()
    courses_by_id = {c["id"]: c for c in courses}
    print(f"Fetched {len(courses)} active course(s)")

    assignments_by_course = {}
    total_assignments = 0
    for c in courses:
        items = canvas.get_assignments(c["id"])
        assignments_by_course[c["id"]] = items
        total_assignments += len(items)
    print(f"Fetched {total_assignments} assignment(s) across all courses")

    calendar_events = canvas.get_calendar_events(courses_by_id.keys())
    print(f"Fetched {len(calendar_events)} calendar event(s)")

    assignments, cases_from_assignments = parse_assignments(courses_by_id, assignments_by_course)
    cases_from_events = parse_calendar_case_events(courses_by_id, calendar_events)
    cases = cases_from_assignments + cases_from_events

    assignments = [a for a in assignments if now_utc <= a.due_at <= horizon]
    cases = [c for c in cases if now_utc <= c.class_date <= horizon]
    print(f"Detected {len(cases)} case session(s) in the next {cfg.lookahead_days} days")
    print(f"{len(assignments)} upcoming assignment(s) due in the next {cfg.lookahead_days} days")

    events_by_uid = {}

    for item in assignments:
        event = build_assignment_event(item, cfg.assignment_reminder_hour, cfg.timezone, cfg.reminder_duration_minutes)
        uid = str(event["uid"])
        if uid in events_by_uid:
            print(f"  [warning] duplicate UID {uid} in source data -- keeping one copy")
        events_by_uid[uid] = event

    for item in cases:
        event = build_case_event(item, cfg.case_reminder_hour, cfg.timezone, cfg.reminder_duration_minutes)
        uid = str(event["uid"])
        if uid in events_by_uid:
            print(f"  [warning] duplicate UID {uid} in source data -- keeping one copy")
        events_by_uid[uid] = event

    calendar = build_calendar(list(events_by_uid.values()), cfg.calendar_name, cfg.timezone)

    with open(cfg.ics_output_path, "wb") as f:
        f.write(calendar.to_ical())

    print(f"Generated {len(events_by_uid)} reminder event(s)")
    print(f"Wrote {cfg.ics_output_path}")


if __name__ == "__main__":
    main()
