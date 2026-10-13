# MedScan

An ID-based patient medical record access system. A doctor looks up a patient by ID, requests access, and sees the record once
the patient approves. Emergency access is allowed and logged. Built with Python OOP, Django (the GUI) and MySQL.

## Run it

1. **MySQL must be running** (XAMPP's MySQL is fine). MedScan needs it and will not start without it.
2. Install the packages:
   ```powershell
   python -m pip install -r requirements.txt
   ```
3. Start the site:
   ```powershell
   python manage.py runserver
   ```
   Open http://127.0.0.1:8000/. The first run creates the database `db_medscan` with all its tables and the test accounts by itself
   (from `database/schema.sql` and `database/seed.sql`).

| Test account | ID (or mobile number) | Password |
|---|---|---|
| Doctor | `2001` | `doc123` |
| Patient | `1001` or `0917 123 4567` | `pat123` |

To try both roles at once, use a normal window for one and an Incognito window for the other.

## Everyday commands

| Do this | Command |
|---|---|
| Run the tests (uses its own database `db_medscan_test`; the JavaScript checks need Windows) | `python -m unittest` |
| Console demo (uses its own database `db_medscan_demo`) | `python Main_Driver.py` |
| Wipe the MedScan tables and restore the test accounts | `python reset_database.py` |

If MedScan says the tables "come from an older version", run `python reset_database.py` once.

## Testing the screens by hand

`python -m unittest` checks the server, the database and the JavaScript logic (phone and date formatting, form rules), but it
cannot click. After changing a screen, try these in a browser. Use two windows (a normal one and an Incognito one) to be
the doctor (`2001`) and the patient (`1001`) at the same time.

**The pages**

| Role | Menu | Top bar |
|---|---|---|
| Patient | Home, My Health, Privacy | the bell |
| Doctor | Home, Patients | search box, red Emergency button, the bell |

**Doctor**

| Try | Should happen |
|---|---|
| Press `/` anywhere (not while typing in a box) | The cursor jumps to the search box |
| Type `jua` in the search box, once Juan has approved you | A list drops down with his name; arrow keys move, Enter opens his record |
| Type `0917 123 4567` and press Enter | The Patients page shows the result with Send access request |
| Click Emergency (top bar) | A pop-up asks for the patient and a reason. Cancel closes it; nothing is saved |
| Search for a patient, click Emergency access on the result | The same pop-up, already knowing the patient |
| After a patient approves | The Patients menu item gets a number; Home lists them under Ready to open; the bell notification opens the record directly |
| Patients page | A table (Patient, Allergies, Last visit) under three tabs (My patients, Waiting, Declined or ended) with counts; more than 10 in a tab adds Previous/Next |
| Click or tab into the search box | The rest of the page dims. Esc, or a click on the dimmed part, closes it |
| Home | Four equal number cards, then Ready to open, Notes this week (bars), Recently opened, Latest activity |
| Write a note | The phrases above the box (+ Labs requested) add their words to the note |

**Patient**

| Try | Should happen |
|---|---|
| Have the doctor send a request, with the patient's window just sitting there | Within about 10 seconds the bell shows a red number, Privacy gets a red count, and a message slides in. The page itself does not reload |
| Open the bell | The request has Approve and Deny buttons. Approve answers it right there; Deny asks first |
| Home, with a request waiting | A "Waiting for your answer" card at the top with Approve and Deny |
| My Health | Everything about you in one place; Edit my information opens the form (allergies as chips) |
| Privacy | Tabs: Doctors (waiting, can open, past) and Who opened my record (views and emergency uses, newest first) |
| Home, with parts of the profile still empty | A "Finish your health profile" card with a progress bar. Add now opens the edit form; the x hides it in this browser |
| Revoke access or Deny | A pop-up asks first |

**Login and sign-up**

| Try | Should happen |
|---|---|
| Tick "Remember my ID", log in, log out | The ID is filled in next time and the cursor is in the password box |
| Create account (start) | Two equal tiles, patient and doctor. Each opens a short form for that role; Back returns to the tiles |
| Create account: medical history | Patients see a closed "Add medical history now (optional)" section with allergies and surgeries |
| Create account: password | A counter (`7 / 25`); the eye shows and hides it; Caps Lock shows a warning |
| Create account: date of birth | `04042004` becomes `04/04/2004`, `4/4/2004` too, and the age appears; the calendar button works |
| Create account: mobile number | `+63 917 123 4567` or `9171234567` becomes `0917 123 4567`. It is required for patients, one per account |
| Create account: allergies | Type one and press Enter or comma: it becomes a chip with an x |
| Create account: the button | Grey until the form is valid. After creating you land on your dashboard with an ID card and a Copy ID button |
| Log in with just the mobile number | Works, same as the ID |

**Everywhere**

| Try | Should happen |
|---|---|
| Double-click a Save button | It goes grey after the first click and sends once |
| Do something that gives a message | A message slides in at the top right and fades by itself; the x closes it |
| Click a notification | It opens the page it is about and goes from unread to read; Mark all read clears the rest |
| Leave a page alone for 14 minutes | A "Still there?" pop-up counts down; Stay logged in keeps you in, otherwise you are sent to the login page |

## Database settings

The defaults suit a local XAMPP (`127.0.0.1`, port `3306`, user `root`, no password, database `db_medscan`). To change them, set
environment variables before running, for example in PowerShell:

```powershell
$env:MEDSCAN_DB_PASSWORD = "mypassword"
```

Available: `MEDSCAN_DB_HOST`, `MEDSCAN_DB_PORT`, `MEDSCAN_DB_USER`, `MEDSCAN_DB_PASSWORD`, `MEDSCAN_DB_NAME`.

## Folders

| Folder | What is in it |
|---|---|
| `models/` | The classes: `User`, `Patient`, `Doctor`, `MedicalRecord`, ... (files start with `M_`) |
| `logic/` | `MedScanSystem`: the rules (`L_`) |
| `data/` | The `Database` class and the repositories that run the SQL (`D_`) |
| `gui/` | Django views, templates, CSS and JS (`G_`) |
| `database/` | `schema.sql` and `seed.sql` |
| `tests/` | The automated tests |
| `docs/` | `DESIGN.md`: architecture, ERD, flows, bug list |
