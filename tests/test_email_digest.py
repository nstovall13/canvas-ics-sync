from datetime import datetime, timezone

from src.email_digest import build_digest_email
from src.parser import AssignmentReminder, CaseReminder


def test_digest_email_lists_items_sorted_by_due_date():
    later = AssignmentReminder(uid_source="assignment-2", course_name="TOM-H", name="Later Exam", due_at=datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc))
    earlier = AssignmentReminder(uid_source="assignment-1", course_name="FIN1-H", name="Earlier Quiz", due_at=datetime(2026, 9, 5, 15, 0, tzinfo=timezone.utc))

    subject, body = build_digest_email([later, earlier], window_days=14, tz_name="America/New_York")

    assert "2 in the next 14 days" in subject
    assert body.index("Earlier Quiz") < body.index("Later Exam")


def test_digest_email_with_no_upcoming_items_is_still_reassuring():
    subject, body = build_digest_email([], window_days=14, tz_name="America/New_York")
    assert "0 in the next 14 days" in subject
    assert "No deadlines" in body


def test_digest_email_includes_cases_due_tomorrow():
    case = CaseReminder(uid_source="assignment-1", course_name="FRC-H", case_name="Mira's Microbrewery", class_date=datetime(2026, 9, 3, 19, 33, tzinfo=timezone.utc))

    _, body = build_digest_email([], window_days=14, tz_name="America/New_York", cases_tomorrow=[case])

    assert "Case Prep for Tomorrow" in body
    assert "FRC-H: Mira's Microbrewery" in body


def test_digest_email_with_no_cases_tomorrow_still_shows_section():
    _, body = build_digest_email([], window_days=14, tz_name="America/New_York", cases_tomorrow=[])
    assert "Case Prep for Tomorrow" in body
    assert "No case prep due tomorrow" in body


def test_digest_email_cases_tomorrow_sorted_by_class_date():
    later = CaseReminder(uid_source="assignment-2", course_name="TOM-H", case_name="Later Case", class_date=datetime(2026, 9, 3, 23, 0, tzinfo=timezone.utc))
    earlier = CaseReminder(uid_source="assignment-1", course_name="FIN1-H", case_name="Earlier Case", class_date=datetime(2026, 9, 3, 13, 0, tzinfo=timezone.utc))

    _, body = build_digest_email([], window_days=14, tz_name="America/New_York", cases_tomorrow=[later, earlier])

    assert body.index("Earlier Case") < body.index("Later Case")
