from src.parser import (
    parse_assignments,
    parse_calendar_case_events,
    extract_case_citation,
)

COURSES_BY_ID = {101: {"id": 101, "course_code": "FIN1-H"}}


def make_assignment(id, name, due_at, submission_types=None, description=None):
    return {
        "id": id,
        "name": name,
        "due_at": due_at,
        "submission_types": submission_types or ["none"],
        "description": description,
        "html_url": f"https://example.instructure.com/courses/1/assignments/{id}",
    }


def test_class_session_extracts_case_title():
    assignments = {101: [make_assignment(1, "FIN1 | Class 3: Cola Wars Continue: Coke and Pepsi", "2026-09-16T19:33:00Z")]}
    items, cases = parse_assignments(COURSES_BY_ID, assignments)
    assert items == []
    assert len(cases) == 1
    assert cases[0].case_name == "Cola Wars Continue: Coke and Pepsi"
    assert cases[0].course_name == "FIN1-H"
    assert cases[0].uid_source == "assignment-1"


def test_graded_assignment_is_not_treated_as_class_session():
    assignments = {101: [make_assignment(2, "FIN1 | Tutorial | Sources and Uses", "2026-09-15T19:33:00Z", submission_types=["online_quiz"])]}
    items, cases = parse_assignments(COURSES_BY_ID, assignments)
    assert len(items) == 1
    assert cases == []
    assert items[0].name == "FIN1 | Tutorial | Sources and Uses"
    assert items[0].uid_source == "assignment-2"


def test_incidental_class_mention_is_not_misclassified():
    # "Poll - Costco Live Case (Class 12)" mentions a class number but isn't the
    # session itself -- a real false positive caught while building the Graph version.
    assignments = {101: [make_assignment(3, "Poll - Costco Live Case (Class 12)", "2026-10-13T03:59:59Z", submission_types=["online_quiz"])]}
    items, cases = parse_assignments(COURSES_BY_ID, assignments)
    assert len(items) == 1
    assert cases == []


def test_informational_only_entry_is_skipped():
    assignments = {101: [make_assignment(4, "2 | START | Day 1 | Coffee on Schwartz Common", "2026-08-25T12:33:00Z", submission_types=["not_graded"])]}
    items, cases = parse_assignments(COURSES_BY_ID, assignments)
    assert items == []
    assert cases == []


def test_missing_due_at_is_skipped():
    assignments = {101: [make_assignment(5, "FIN1 | Tutorial | No Due Date", None, submission_types=["online_quiz"])]}
    items, _ = parse_assignments(COURSES_BY_ID, assignments)
    assert items == []


def test_missing_course_name_falls_back_to_course_id():
    assignments = {202: [make_assignment(50, "X | Tutorial | Y", "2026-09-15T19:33:00Z", submission_types=["online_quiz"])]}
    items, _ = parse_assignments({}, assignments)  # course 202 not in courses_by_id
    assert items[0].course_name == "202"


def test_uid_source_is_stable_across_due_date_change():
    a1 = make_assignment(6, "FIN1 | Tutorial | X", "2026-09-15T19:33:00Z", submission_types=["online_quiz"])
    a2 = make_assignment(6, "FIN1 | Tutorial | X", "2026-09-20T19:33:00Z", submission_types=["online_quiz"])
    items1, _ = parse_assignments(COURSES_BY_ID, {101: [a1]})
    items2, _ = parse_assignments(COURSES_BY_ID, {101: [a2]})
    assert items1[0].uid_source == items2[0].uid_source == "assignment-6"
    assert items1[0].due_at != items2[0].due_at


def test_uid_source_is_stable_across_case_name_change():
    a1 = make_assignment(7, "FRC | Class 2: Old Case Name", "2026-09-16T19:33:00Z")
    a2 = make_assignment(7, "FRC | Class 2: New Case Name", "2026-09-16T19:33:00Z")
    _, cases1 = parse_assignments(COURSES_BY_ID, {101: [a1]})
    _, cases2 = parse_assignments(COURSES_BY_ID, {101: [a2]})
    assert cases1[0].uid_source == cases2[0].uid_source == "assignment-7"
    assert cases1[0].case_name != cases2[0].case_name


def test_html_description_case_citation_is_extracted():
    html = '<h3>Materials</h3> <p>Case: <a href="https://x">Mira\'s Microbrewery, Inc. (A)</a></p>'
    citation = extract_case_citation(html)
    assert citation is not None
    assert "Mira's Microbrewery" in citation


def test_no_case_citation_returns_none():
    assert extract_case_citation("<p>Just a regular description with no case mention.</p>") is None
    assert extract_case_citation(None) is None
    assert extract_case_citation("") is None


def test_calendar_event_without_case_text_is_skipped():
    events = [{"id": 900, "title": "Office Hours", "description": "", "start_at": "2026-09-01T20:00:00Z", "context_code": "course_101"}]
    cases = parse_calendar_case_events(COURSES_BY_ID, events)
    assert cases == []


def test_calendar_event_with_case_text_is_parsed():
    events = [{
        "id": 901,
        "title": "Class Session",
        "description": "Materials: Case: Grupo Coppel (Case #426-031)",
        "start_at": "2026-09-01T20:00:00Z",
        "context_code": "course_101",
    }]
    cases = parse_calendar_case_events(COURSES_BY_ID, events)
    assert len(cases) == 1
    assert "Grupo Coppel" in cases[0].case_name
    assert cases[0].uid_source == "event-901"
