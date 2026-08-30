from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.ics_builder import build_assignment_event, build_case_event, build_calendar
from src.parser import AssignmentReminder, CaseReminder

ET = ZoneInfo("America/New_York")


def test_assignment_due_tuesday_reminds_monday_9am():
    # Tuesday 2026-09-15, 4:00 PM ET due date.
    item = AssignmentReminder(
        uid_source="assignment-1",
        course_name="FIN1-H",
        name="Quantitative Exercise",
        due_at=datetime(2026, 9, 15, 20, 0, tzinfo=timezone.utc),
    )
    event = build_assignment_event(item, hour=9, tz_name="America/New_York", duration_minutes=15)

    start_local = event["dtstart"].dt.astimezone(ET)
    end_local = event["dtend"].dt.astimezone(ET)
    assert start_local.date().isoformat() == "2026-09-14"  # Monday
    assert start_local.hour == 9 and start_local.minute == 0
    assert (end_local - start_local).total_seconds() == 15 * 60
    assert str(event["summary"]) == "⏰ Due Tomorrow: Quantitative Exercise"


def test_monday_class_reminds_sunday_6pm():
    # Monday 2026-09-14, 9:00 AM ET class.
    item = CaseReminder(
        uid_source="assignment-2",
        course_name="MKT-H",
        case_name="IKEA",
        class_date=datetime(2026, 9, 14, 13, 0, tzinfo=timezone.utc),
    )
    event = build_case_event(item, hour=18, tz_name="America/New_York", duration_minutes=15)

    start_local = event["dtstart"].dt.astimezone(ET)
    assert start_local.date().isoformat() == "2026-09-13"  # Sunday
    assert start_local.hour == 18
    assert str(event["summary"]) == "📚 Case Prep: IKEA (MKT-H tomorrow)"


def test_assignment_uid_format():
    item = AssignmentReminder(uid_source="assignment-1171815", course_name="FIN1-H", name="X", due_at=datetime(2026, 9, 15, 19, 33, tzinfo=timezone.utc))
    event = build_assignment_event(item, 9, "America/New_York", 15)
    assert str(event["uid"]) == "canvas-assignment-1171815-reminder@canvas-sync"


def test_case_uid_format():
    item = CaseReminder(uid_source="assignment-1171815", course_name="FIN1-H", case_name="X", class_date=datetime(2026, 9, 15, 19, 33, tzinfo=timezone.utc))
    event = build_case_event(item, 18, "America/New_York", 15)
    assert str(event["uid"]) == "canvas-case-assignment-1171815-reminder@canvas-sync"


def test_dst_transition_produces_correct_utc_offset():
    # EDT (UTC-4) is active through early Nov; EST (UTC-5) resumes after.
    # 9am ET the day before should differ in UTC hour by exactly 1 across the boundary.
    summer_item = AssignmentReminder(uid_source="assignment-10", course_name="X", name="Y", due_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc))
    winter_item = AssignmentReminder(uid_source="assignment-11", course_name="X", name="Y", due_at=datetime(2026, 12, 2, 12, 0, tzinfo=timezone.utc))

    summer_event = build_assignment_event(summer_item, 9, "America/New_York", 15)
    winter_event = build_assignment_event(winter_item, 9, "America/New_York", 15)

    assert summer_event["dtstart"].dt.hour == 13  # 9am EDT = 13:00 UTC
    assert winter_event["dtstart"].dt.hour == 14  # 9am EST = 14:00 UTC

    # And both still read as exactly 9am when viewed back in America/New_York.
    assert summer_event["dtstart"].dt.astimezone(ET).hour == 9
    assert winter_event["dtstart"].dt.astimezone(ET).hour == 9


def test_duplicate_uid_collapses_to_single_event():
    item_a = AssignmentReminder(uid_source="assignment-99", course_name="X", name="First version", due_at=datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc))
    item_b = AssignmentReminder(uid_source="assignment-99", course_name="X", name="Updated version", due_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc))

    events_by_uid = {}
    for item in (item_a, item_b):
        event = build_assignment_event(item, 9, "America/New_York", 15)
        events_by_uid[str(event["uid"])] = event

    assert len(events_by_uid) == 1

    cal = build_calendar(list(events_by_uid.values()), "Test Calendar", "America/New_York")
    ics_text = cal.to_ical().decode("utf-8")
    assert ics_text.count("BEGIN:VEVENT") == 1


def test_calendar_round_trips_through_icalendar_parser():
    from icalendar import Calendar as ICalendar

    item = AssignmentReminder(uid_source="assignment-1", course_name="X", name="Y", due_at=datetime(2026, 9, 15, 19, 33, tzinfo=timezone.utc))
    event = build_assignment_event(item, 9, "America/New_York", 15)
    cal = build_calendar([event], "HBS Prep & Deadlines", "America/New_York")

    raw = cal.to_ical()
    reparsed = ICalendar.from_ical(raw)
    events = [c for c in reparsed.walk() if c.name == "VEVENT"]
    assert len(events) == 1
    assert str(events[0]["uid"]) == "canvas-assignment-1-reminder@canvas-sync"
