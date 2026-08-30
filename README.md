# canvas-ics-sync

Pulls assignment due dates and case-reading info from Canvas and publishes
them as an `.ics` calendar feed that Outlook subscribes to as a separate
calendar. No Azure account, Microsoft Entra app registration, Power Automate
flow, client secret, or Graph OAuth token required anywhere in this.

- Assignment due tomorrow -> reminder at 9:00-9:15 AM the day before
- Class session tomorrow -> case-prep reminder at 6:00-6:15 PM the evening before
- A daily digest **email** listing all deadlines/exams due in the next 14
  days, plus any case prep due tomorrow
- The feed is regenerated from scratch daily via GitHub Actions and published
  via GitHub Pages; Outlook re-polls that URL on its own schedule, so
  assignment changes, new cases, and date shifts show up automatically

Requires Python 3.10+.

## How class sessions and assignments are told apart

Canvas courses can model each class session either as a calendar event whose
description contains literal `Case:` text (the approach this spec originally
assumed), or -- as is actually the case at HBS, confirmed against real data --
as an "assignment" named like `"FRC | Class 2: Mira's Microbrewery Inc. (Part 1)"`.
`src/parser.py` handles both:

- `parse_assignments()`: a name containing `| Class N:` or `| Class N |`
  right after the course code marks a class session -> case-prep reminder,
  using the text after that marker as the title. Anything else with a real
  submission type (not `none`/`not_graded`) is a graded deliverable -> due-date
  reminder. Anything else (no submission type) is skipped.
- `parse_calendar_case_events()`: the original spec's approach, kept for
  portability to Canvas instances where class sessions genuinely are
  calendar events. Verified empty at HBS (that endpoint there only returns
  things like office hours), so it costs nothing to leave in.

If a case's description also contains literal `Case: ...` text (some HBS
courses have this), that citation is appended to the event body as a bonus
detail alongside the name-derived title.

## One-time setup

### 1. Create a Canvas access token

1. Canvas -> Account -> Settings -> **New Access Token**.
2. Copy the token immediately (shown once).
3. Note your Canvas base URL too, e.g. `https://canvas.instructure.com` or
   your school's instance (e.g. `https://hbs.instructure.com`).

### 2. Run it locally first

```bash
cd canvas-ics-sync
python -m venv .venv
.venv\Scripts\activate   # or `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env     # then fill in CANVAS_BASE_URL and CANVAS_TOKEN
pytest -q                # run the test suite
python -m src.canvas_sync
```

This writes `reminders.ics` in the current directory (gitignored -- never
committed). Open it in a text editor, or double-click it to import into your
local calendar app, to sanity-check the output before publishing anywhere.

### 3. Add GitHub repository secrets

Push this repo to GitHub, then under Settings -> Secrets and variables ->
Actions, add:

| Secret | Value |
|---|---|
| `CANVAS_BASE_URL` | your Canvas instance URL |
| `CANVAS_TOKEN` | the token from step 1 |
| `SMTP_HOST` | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | e.g. `587` |
| `SMTP_USERNAME` | the sending account's address |
| `SMTP_PASSWORD` | an **app password** for that account -- never its real login password |
| `EMAIL_FROM` | usually the same as `SMTP_USERNAME` |
| `EMAIL_TO` | where you actually want the digest delivered |

No Azure client ID, tenant ID, or OAuth of any kind is needed for any of
this. See "Setting up the digest email sender" below for why the sending
account likely can't be your school email directly.

### Setting up the digest email sender

Any real email account needs a credential to prove you're authorized to
send as it -- there's no credential-free way to send mail (that's exactly
what stops spam). For a personal Gmail (or Google Workspace) account:

1. The sending account needs **2-Step Verification** turned on
   (myaccount.google.com -> Security). App Passwords only appear once this
   is enabled.
2. Go to **myaccount.google.com/apppasswords**, name one (e.g.
   `canvas-sync`), and copy the 16-character password it generates.
3. Use that as `SMTP_PASSWORD` -- **never your real account password**.
   An app password is scoped to this one purpose and independently
   revocable if it's ever exposed.

Institutional (school/work) Microsoft/Google accounts often block this
entirely -- confirmed blocked for this project's own HBS account (no SMTP
connector access via Power Automate, no app-password option visible on
the account) and for a personal outlook.com account (no app-password
option offered at all). If your sending account doesn't offer an App
Password option, the sender doesn't have to be the same account you want
the digest delivered to -- `EMAIL_FROM`/`SMTP_USERNAME` and `EMAIL_TO` can
be entirely different accounts, so a secondary Gmail used purely as a
sending relay works fine, delivering to your real inbox via `EMAIL_TO`.

### 4. Enable GitHub Pages

Settings -> Pages -> under "Build and deployment", set **Source** to
**"GitHub Actions"**. That's it -- the workflow below handles the rest.

### 5. Enable GitHub Actions and run it once

Actions tab -> if prompted, enable workflows for this repo. Then find
"Canvas to Outlook calendar sync" in the left sidebar -> **Run workflow**
(the `workflow_dispatch` trigger) to test it manually rather than waiting
for the daily schedule.

Check the run's logs -- you should see lines like:

```
Fetched 7 active course(s)
Fetched 238 assignment(s) across all courses
Fetched 14 calendar event(s)
Detected 83 case session(s) in the next 60 days
32 upcoming assignment(s) due in the next 60 days
Generated 115 reminder event(s)
Wrote reminders.ics
```

### 6. Find your calendar's subscription URL

After the workflow succeeds, go to Settings -> Pages. The URL banner there
shows your Pages site's base URL, e.g. `https://<username>.github.io/<repo>/`.
Your feed is at:

```
https://<username>.github.io/<repo>/reminders.ics
```

This URL is stable across every future run -- only the file's contents change.

### 7. Subscribe in Outlook

In Outlook (web or desktop):

1. **Add calendar** -> **Subscribe from web**
2. Paste the URL from step 6
3. Name it **`HBS Prep & Deadlines`**
4. Save

The feed will appear as its own calendar, separate from your primary one.
Outlook re-polls subscribed internet calendars on its own schedule (typically
every several hours, not instantly) -- so same-day changes to Canvas may take
a while to show up; this is an Outlook-side limitation of the "subscribe from
web" feature, not something this script controls.

## Reliability notes / known limitations

- **Deleted or cancelled Canvas items**: the feed is regenerated from scratch
  every run based on current Canvas data, so a removed assignment or
  cancelled class simply won't appear in the next `reminders.ics`. Some
  calendar clients don't reliably delete a previously-seen event whose UID
  has vanished from a refreshed feed (this is a general quirk of subscribed
  `.ics` feeds, not specific to this script) -- worst case, you might briefly
  see a stale reminder for something that's been removed, until Outlook's
  next full refresh. Given the spec's instruction to avoid an external
  dedup/state log unless technically required, this tradeoff is accepted
  rather than solved with added infrastructure.
- **DST**: reminder times are computed as local wall-clock times via
  `zoneinfo`, which resolves the correct UTC offset for the actual calendar
  date -- covered by `tests/test_ics_builder.py::test_dst_transition_produces_correct_utc_offset`.
- **Cron timing**: GitHub Actions' `schedule` trigger has no timezone
  support. The workflow runs at 12:00 UTC daily, which is 8:00 AM ET during
  EDT and 7:00 AM ET during EST -- a one-hour drift twice a year that doesn't
  matter here, since it only affects when the feed is *regenerated*, not the
  correctness of the reminder times themselves.

## Troubleshooting

**Workflow fails with "CANVAS_TOKEN is expired, revoked, or invalid"**
Generate a new token (Canvas -> Account -> Settings -> New Access Token) and
update the `CANVAS_TOKEN` secret.

**Workflow fails with a network/timeout error**
Canvas may be temporarily unreachable, or rate-limiting requests -- the
script already retries once on a detected rate limit. Re-run the workflow;
if it persists, check Canvas's status page.

**"Generated 0 reminder events"**
Check `LOOKAHEAD_DAYS` (default 60) -- if all your upcoming due dates/classes
fall further out than that, nothing will show up yet. Also confirm
`CANVAS_BASE_URL` matches your actual institution's Canvas domain exactly
(no trailing slash needed, it's stripped automatically).

**Case-prep reminders aren't appearing for a specific course**
Your school's Canvas may name class sessions differently than the
`"COURSE | Class N: Title"` pattern this script looks for. Check a few
assignment names in that course via
`GET /api/v1/courses/:course_id/assignments` and adjust `CLASS_SESSION_PATTERN`
/ `CLASS_TITLE_PATTERN` in `src/parser.py` accordingly.

**Outlook shows the calendar but events aren't updating**
Outlook controls its own refresh cadence for subscribed internet calendars;
there's no way to force an immediate refresh from this side. Confirm the
workflow itself is succeeding (Actions tab) before assuming it's a script
issue.

**The subscribed calendar disappeared or shows old data after I renamed the
GitHub repo**
The Pages URL is tied to the repo name; renaming the repo changes the URL.
Re-subscribe in Outlook with the new URL if this happens.

**"SMTP not configured (SMTP_USERNAME unset) -- skipping digest email"**
This is expected, not an error, until you've added the SMTP secrets from
step 3 -- the `.ics` calendar side works independently of the email digest.

**Digest email fails with an authentication error**
Almost always means `SMTP_PASSWORD` is a real account password instead of
an app password, or the sending account doesn't have App Passwords enabled
at all (common for institutional accounts). Use
`scripts/send_test_email.py` locally to iterate on this without waiting for
the full daily workflow.

## Project layout

```
src/
  config.py         env-var driven settings
  canvas_client.py  Canvas REST calls (read-only, with 401/rate-limit handling)
  parser.py         raw Canvas JSON -> AssignmentReminder / CaseReminder
  ics_builder.py    builds the .ics VEVENTs with stable UIDs and DST-safe UTC times
  email_digest.py   builds and sends the daily "upcoming deadlines" digest email
  canvas_sync.py    daily entrypoint, wires everything together
scripts/
  send_test_email.py   one-off local SMTP connectivity/credential test
tests/
  test_parser.py       classification and extraction logic, mocked Canvas data
  test_ics_builder.py  reminder timing, UID stability, DST, dedup
  test_email_digest.py digest email content, mocked data (no real send)
.github/workflows/
  canvas-sync.yml   daily cron -> generate .ics + send digest -> publish to GitHub Pages
```

## Optional: LLM-assisted summaries

Not part of the core pipeline, and not implemented. If wanted later, this
would call the Anthropic API (`api.anthropic.com/v1/messages`) with case/
assignment text as input to produce a short summary or a prioritized daily
digest -- bolted onto `src/canvas_sync.py` without touching the Canvas
fetching or `.ics` generation.
