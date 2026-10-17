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
| Patient | Home, My Record, Access, Profile | Show my QR code (a sheet) | the bell |
| Doctor | Home, Patients, Profile (phone: Search tab too) | Scan QR code | search box, the bell |

Log out is only on Profile. Emergency is only on a locked patient's page.

**Patient**

| Try | Should happen |
|---|---|
| Have the doctor send a request, with the patient's window just sitting there | Within about 10 seconds the bell and the Access item get a red mark, and a message slides in. The page does not reload |
| Open the bell | Rows are only pointers ("Opens Access, Requests"). Clicking one opens that page and marks it read; Mark all as read clears the rest |
| Home, with a request waiting | "Needs your answer" with Deny and Review. Review opens a sheet saying what the doctor would see, with Deny and Approve. Deny asks first |
| Show my QR code | A sheet with the code and "Works once, 4:59 left" counting down. Make a new code replaces it at once. After 5 minutes it gets a new code by itself |
| Access, tabs Requests / Doctors / History | Requests: who is waiting. Doctors: who can open the record (Remove access asks first; "approved by QR scan" when it was). History: every view, scan and emergency, with chips All / QR scan / Approved / Emergency |
| My Record | Notes, then allergies, medications, surgeries and basic info (phone: Notes / Medical / Info tabs). Edit my information opens a sheet |
| Profile | Details, the password date, Edit contact info (a sheet), and Log out, which asks in a modal |

**Doctor**

| Try | Should happen |
|---|---|
| Press `/` anywhere (not while typing in a box) | The cursor jumps to the search box |
| Type `jua` in the search box, once Juan is yours | A list drops down; arrow keys move, Enter opens his page |
| Type `0917 123 4567` and press Enter | The Search page shows him with a Locked pill; clicking opens his locked page |
| A locked patient's page | Scan his QR code, Send access request (or Request again / "Request sent"), and Emergency access at the bottom |
| Emergency access | A sheet asks for a reason and a tick that it is a medical emergency. Cancel saves nothing. The patient is told at once |
| Scan QR code, with the patient's sheet open on a phone | The camera starts by itself. A live code lands on the open record with "Approved by QR scan" and a "Scan successful" message. The same code a second time says it was already used |
| Scan a plain ID code (an old printout) | The locked patient page: a plain ID never approves anyone |
| Patients | One list with chips All, With access, Waiting, Emergency, Denied (counts on each); more than 10 adds Previous/Next |
| An open record | Allergy alert under the name; tabs Notes, Medical, Info; the phrases above the note box add their words |
| After a patient approves | The Patients menu item gets a number; Home lists them first under Recent patients |

**Login and sign-up**

| Try | Should happen |
|---|---|
| Tick "Remember me", log in, log out | The ID is filled in next time and the cursor is in the password box |
| Create account | One form with a Patient / Doctor switch. A doctor's contact number is optional |
| Create account: medical history | Patients see a closed "Add medical history now (optional)" section with allergies and surgeries |
| Create account: password | A counter (`7 / 25`); the eye shows and hides it; Caps Lock shows a warning |
| Create account: date of birth | `04042004` becomes `04/04/2004`, and the age appears; the calendar button works |
| Create account: mobile number | `+63 917 123 4567` or `9171234567` becomes `0917 123 4567`. Required for patients, one per account |
| Create account: the button | Grey until the form is valid. After creating you land on Home with a welcome card and a Copy ID button |
| Log in with just the mobile number | Works, same as the ID |

**Everywhere**

| Try | Should happen |
|---|---|
| Double-click a Save button | It goes grey after the first click and sends once |
| Do something that gives a message | A message slides in at the top right and fades by itself; the x closes it |
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
| `design/` | The target screens (HTML mockups and screenshots) |
| (root) | `manage.py` starts the site and runs the tests, `reset_database.py` rebuilds the tables, `Main_Driver.py` is the console demo |

## Where the OOP ideas are

| Idea | Where |
|---|---|
| Encapsulation | `User` keeps the password private (`__password`) and exposes only `login()`; `QRToken` and `QRCode` keep their secret and text private and read-only; `Notification`, `PatientLink` and `ScanResult` keep their fields private and give read-only properties |
| Inheritance | `Patient` and `Doctor` extend `User` and reuse its login and ID handling |
| Polymorphism | Each subclass replaces `ID_PREFIX` (`PT`, `DR`), so `display_id` works the same way for either kind of account, and the pages treat both as a `User` |
| Abstraction | `MedScanSystem` hides the SQL and the repositories behind questions like `access_status()` and `scan_qr()`; `ScanResult` and `PatientLink` give the page one simple answer instead of the rules behind it |
