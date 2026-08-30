"""Turn raw Canvas API payloads into the two reminder types we care about.

Two independent sources feed into "case-prep" items, per the spec:

1. Assignment names. At HBS (and likely other schools using this Canvas theme),
   each class session is modeled as an "assignment" named like
   "FRC | Class 2: Mira's Microbrewery Inc. (Part 1)" rather than as a calendar
   event. A "Class N" marker right after the course-code "|" identifies these;
   the text after the marker is the case/topic title. This is the primary,
   verified-against-real-data source -- see parse_assignments().

2. Calendar event descriptions containing literal "Case: ..." text, per the
   original spec. Confirmed empty at HBS (the /calendar_events endpoint there
   only returns things like office hours), but implemented for spec compliance
   and portability to schools where class sessions genuinely are modeled as
   calendar events -- see parse_calendar_case_events().

Anything else with a real submission type (not "none"/"not_graded") is a
graded deliverable -> due-date reminder. Purely informational assignment
entries (e.g. orientation schedule items) have no submission type and are
skipped entirely.
"""
import html
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.canvas_client import parse_canvas_datetime

HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")

# Anchored on the "|" right before "Class N" so an incidental mention elsewhere
# (e.g. a poll named "Poll - Costco Live Case (Class 12)") isn't mistaken for
# the class session itself.
CLASS_SESSION_PATTERN = re.compile(r"\|\s*class\s*\d+\s*[:|]", re.IGNORECASE)
CLASS_TITLE_PATTERN = re.compile(r"\|\s*class\s*\d+\s*[:|]\s*(.+)$", re.IGNORECASE)

# Best-effort supplementary extraction of an explicit "Case: ..." citation.
CASE_LINE_PATTERN = re.compile(r"case:\s*([^\n]{1,150})", re.IGNORECASE)

NON_DELIVERABLE_SUBMISSION_TYPES = {"none", "not_graded"}


def clean_html(text: Optional[str]) -> str:
    if not text:
        return ""
    stripped = HTML_TAG_RE.sub(" ", text)
    unescaped = html.unescape(stripped)
    return WHITESPACE_RE.sub(" ", unescaped).strip()


def _trim_to_word_boundary(text: str) -> str:
    """The capture group is capped at 150 chars for safety; avoid cutting mid-word
    by dropping back to the last preceding space when the cap landed inside one."""
    if len(text) < 150:
        return text
    last_space = text.rfind(" ")
    return text[:last_space] if last_space > 0 else text


def extract_case_citation(text: Optional[str]) -> Optional[str]:
    """Best-effort: pull an explicit "Case: ..." line out of text, if present."""
    if not text:
        return None
    cleaned = clean_html(text)
    match = CASE_LINE_PATTERN.search(cleaned)
    if not match:
        return None
    citation = _trim_to_word_boundary(match.group(1).strip()).rstrip(".")
    return citation or None


@dataclass
class AssignmentReminder:
    uid_source: str  # e.g. "assignment-1171815" -- stable across due-date changes
    course_name: str
    name: str
    due_at: datetime
    canvas_url: str = ""


@dataclass
class CaseReminder:
    uid_source: str  # e.g. "assignment-1171815" or "event-9001"
    course_name: str
    case_name: str
    class_date: datetime
    canvas_url: str = ""
    case_citation: Optional[str] = None  # supplementary "Case: ..." text, if found


def _extract_class_title(name: str) -> Optional[str]:
    match = CLASS_TITLE_PATTERN.search(name)
    if not match:
        return None
    title = match.group(1).strip()
    return title or None


def parse_assignments(
    courses_by_id: dict[int, dict],
    assignments_by_course: dict[int, list[dict]],
) -> tuple[list[AssignmentReminder], list[CaseReminder]]:
    assignments: list[AssignmentReminder] = []
    cases: list[CaseReminder] = []

    for course_id, items in assignments_by_course.items():
        course = courses_by_id.get(course_id, {})
        course_name = course.get("course_code") or course.get("name") or str(course_id)

        for a in items:
            due_at = parse_canvas_datetime(a.get("due_at"))
            if due_at is None:
                continue  # missing/unparseable due_at -- nothing to schedule against

            name = a.get("name")
            if not name:
                continue  # missing name -- can't build a useful reminder

            if CLASS_SESSION_PATTERN.search(name):
                case_name = _extract_class_title(name) or name
                cases.append(
                    CaseReminder(
                        uid_source=f"assignment-{a['id']}",
                        course_name=course_name,
                        case_name=case_name,
                        class_date=due_at,
                        canvas_url=a.get("html_url", ""),
                        case_citation=extract_case_citation(a.get("description")),
                    )
                )
                continue

            submission_types = set(a.get("submission_types") or [])
            if submission_types <= NON_DELIVERABLE_SUBMISSION_TYPES:
                continue  # informational-only entry (e.g. orientation schedule item)

            assignments.append(
                AssignmentReminder(
                    uid_source=f"assignment-{a['id']}",
                    course_name=course_name,
                    name=name,
                    due_at=due_at,
                    canvas_url=a.get("html_url", ""),
                )
            )

    return assignments, cases


def parse_calendar_case_events(
    courses_by_id: dict[int, dict],
    calendar_events: list[dict],
) -> list[CaseReminder]:
    """Supplementary source per the original spec: class sessions modeled as Canvas
    calendar events whose description contains an explicit "Case:" mention. Verified
    empty at HBS (class sessions are modeled as assignments there instead -- see
    parse_assignments), kept for portability to other Canvas instances.
    """
    cases: list[CaseReminder] = []
    for event in calendar_events:
        citation = extract_case_citation(event.get("description")) or extract_case_citation(event.get("title"))
        if not citation:
            continue  # no case info in this event -- skip

        class_date = parse_canvas_datetime(event.get("start_at"))
        if class_date is None:
            continue

        context_code = event.get("context_code", "")
        course_id = context_code[len("course_"):] if context_code.startswith("course_") else None
        course = courses_by_id.get(int(course_id)) if course_id and course_id.isdigit() else {}
        course_name = course.get("course_code") or course.get("name") or context_code or "Unknown course"

        cases.append(
            CaseReminder(
                uid_source=f"event-{event['id']}",
                course_name=course_name,
                case_name=citation,
                class_date=class_date,
                canvas_url=event.get("html_url", ""),
            )
        )
    return cases
