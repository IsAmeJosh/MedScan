# MedScan

A patient medical record system where a doctor opens a record only with the patient's consent: the patient approves a request, or
shows a one-time QR code in person for the doctor to scan. Emergency access is allowed and always logged. Built with Python OOP,
Django (the GUI) and MySQL. The screens follow the design in `design/`.

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
| Run the tests (uses its own database `db_medscan_test`; the JavaScript checks need Windows) | `python manage.py test` |
| Console demo (uses its own database `db_medscan_demo`) | `python Main_Driver.py` |
| Wipe the MedScan tables and restore the demo accounts | `python reset_database.py` |
| The same, and also add sample doctors, patients and history (good for a demo or a screen recording; password `demo123`) | `python reset_database.py --demo` |

Old databases are not upgraded. If MedScan says the tables "come from an older version", run `python reset_database.py` once: it
removes the old tables and builds the current ones (this empties the data in `db_medscan`).

## Testing the screens by hand

`python manage.py test` checks the server, the database and the JavaScript logic (phone and date formatting, form rules), but it
cannot click or use a camera. After changing a screen, try these in a browser. Use two windows (a normal one and an Incognito
one) to be the doctor (`2001`) and the patient (`1001`) at the same time. Narrow the window below 760 px to see the phone layout.

**The pages**

| Role | Menu (sidebar, or the bottom tabs on a phone) | Main action | Top bar |
|---|---|---|---|
| Patient | Home, My Record, Access, Profile, Settings | Show my QR code (a sheet) | the bell |
| Doctor | Home, Patients, Profile, Settings (phone: Search tab too, and Settings is the gear in the top bar) | Scan QR code | search box, the bell |

Log out is only in Settings. Emergency is only on a locked patient's page.

**Patient**

| Try | Should happen |
|---|---|
| Have the doctor send a request, with the patient's window just sitting there | Within about 10 seconds the bell and the Access item get a red mark, and a message slides in. The page does not reload |
| Open the bell | Rows are only pointers ("Opens Access, Requests"). Clicking one opens that page and marks it read; Mark all as read clears the rest |
| Home, with a request waiting | Row one: the ID card (allergies; what you take, last vaccine, last visit, surgery) and "Needs your answer" with Decline and Allow, which look the same. Allow opens a sheet saying what the doctor would see. Decline asks first. After you answer, a teal message says "Allowed. Dr. X can now see your record." (its Undo link is a placeholder) and the card says "You're all caught up". Row two: Your care team and Recent activity, each in its own panel |
| Show my QR code | A pop-up over a dimmed, blurred page with the code and "Works once, 4:59 left" counting down. Make a new code replaces it at once. After 5 minutes the code is blurred and the pop-up says "This code has expired", with a Make a new code button on it |
| Access, tabs Requests / Doctors / History | Requests: who is waiting, and what a doctor can see if you allow. Doctors: who can open the record (Remove asks first; "allowed by QR scan" when it was) and what emergency access means. History: every view, scan, emergency and request you declined, with chips All / QR scan / Allowed / Emergency |
| My Record | Tabs Notes / Care history / Medical / Info on every screen size. On the Info tab, Edit (Basic info) opens the edit sheet. Care history, vaccinations, conditions, allergy severity, "Prescribed in these notes", height, weight and the emergency contact are sample data for now: only demo patient 1001 shows them, everyone else reads "Not recorded". "Written by" counts the real notes per doctor |
| Profile | Patient: the page of reference 30 (personal details, emergency contact, health at a glance, recent care). Edit on Personal details opens the mobile number sheet. The emergency contact, conditions and last vaccine are sample data shown only for demo patient 1001 (others read "Not recorded"). Doctor: details and Edit contact info (a sheet) |
| Settings | Switches, Text size and Language are sample data for now and do not save. Download my MedScan ID is a printable page for patients and doctors (save it as PDF from the browser's Print dialog). Log out asks in a modal |

**Doctor**

| Try | Should happen |
|---|---|
| Press `/` anywhere (not while typing in a box) | The cursor jumps to the search box |
| Type `jua` in the search box, once Juan is yours | A list drops down; arrow keys move, Enter opens his page |
| Type `0917 123 4567` and press Enter | The Search page shows him with a Locked pill; clicking opens his locked page |
| A locked patient's page | One panel: the text on the left ("his" or "her" follows the sex on file), Scan QR code and Send access request (or Request again / "Request sent") on the right, and Emergency access underneath |
| Emergency access | A sheet asks for a reason and a tick "This is a medical emergency". Cancel saves nothing. The patient is told at once |
| Scan QR code, with the patient's sheet open on a phone | The camera starts by itself, and Recent scans lists your last scans. A live code lands on the open record with "Allowed by QR scan" and a "Scan successful" message. The same code a second time says it was already used |
| Scan a plain ID code (an old printout) | The locked patient page: a plain ID never approves anyone |
| Home | Today (requests waiting, patients who allowed you, records you opened lately) and Recent notes (your latest notes) |
| Patients | One list with chips All, Can see, Waiting, Emergency, Declined (counts on each); more than 10 adds Previous/Next |
| An open record | Allergy banner under the name; tabs Notes, Care history, Medical, Info; Seen elsewhere is sample data for patient 1001 only |
| Profile | Work details (the licence number is a sample for demo doctor 2001) and This month: real counts of patients seen, notes, scans and emergency openings |
| After a patient approves | The Patients menu item gets a number; Home lists them under Today |

**Login and sign-up**

| Try | Should happen |
|---|---|
| Create account | One form with a Patient / Doctor switch. A doctor's mobile number is optional |
| Create account: medical history | Patients see a closed "Add medical history now (optional)" section with allergies and surgeries |
| Create account: password | Show / Hide reveals it; Caps Lock shows a warning. At least 6 characters |
| Create account: date of birth | `04042004` becomes `04/04/2004`, and the age appears; the calendar button works |
| Create account: mobile number | `+63 917 123 4567` or `9171234567` becomes `0917 123 4567`. Required for patients, one per account |
| Create account: the button | Grey until the form is valid. After creating you see "Your MedScan ID is ready" with Download as PDF, a tick box, and Continue to MedScan. The password is never shown or printed |
| Log in with just the mobile number | Works, same as the ID |

**Everywhere**

| Try | Should happen |
|---|---|
| Double-click a Save button | It goes grey after the first click and sends once |
| Do something that gives a message | A message slides in at the bottom centre and fades by itself: teal for good news, red or amber (with an x) for errors and warnings |
| Leave a page alone for 14 minutes | A "Still there?" pop-up counts down; Stay logged in keeps you in, otherwise you are sent to the login page |
| Resize below 760 px | The sidebar becomes bottom tabs with the main action raised in the middle; sheets rise from the bottom |

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
| `database/` | `schema.sql` (the tables, all named `tb_...`), `seed.sql` (the two demo accounts) and `demo_data.sql` (optional sample data, added with `--demo`) |
| `tests/` | The automated tests |
| `design/` | The target screens: the design's HTML pages (`design/html`) and screenshots |
| (root) | `manage.py` starts the site and runs the tests, `reset_database.py` rebuilds the tables, `Main_Driver.py` is the console demo |

## Where the OOP ideas are

| Idea | Where |
|---|---|
| Encapsulation | `User` keeps the password private (`__password`) and exposes only `login()`; `QRToken` and `QRCode` keep their secret and text private and read-only; `Notification`, `PatientLink` and `ScanResult` keep their fields private and give read-only properties |
| Inheritance | `Patient` and `Doctor` extend `User` and reuse its login and ID handling |
| Polymorphism | Each subclass replaces `ID_PREFIX` (`PT`, `DR`), so `display_id` works the same way for either kind of account, and the pages treat both as a `User` |
| Abstraction | `MedScanSystem` hides the SQL and the repositories behind questions like `access_status()` and `scan_qr()`; `ScanResult` and `PatientLink` give the page one simple answer instead of the rules behind it |
