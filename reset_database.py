"""Empty the MedScan tables and build them again from database/schema.sql, with the demo accounts from database/seed.sql.
Use it for a clean start. It asks before it deletes anything.

Run:  python reset_database.py                (asks first)
      python reset_database.py --yes          (no question)
      python reset_database.py --demo         (also adds the sample doctors, patients and history from database/demo_data.sql)
Uses the database named in MEDSCAN_DB_NAME (default db_medscan). Other databases are never touched."""
import sys

from data.D_Database import Database, DatabaseError


def main():
    """Ask for confirmation, then rebuild the tables and the demo accounts. With --demo, the sample data goes in as well."""
    db = Database.from_environment()
    if "--yes" not in sys.argv:
        answer = input(f"This deletes all MedScan data in '{db.name}' and restores the demo accounts. Type YES to go on: ")
        if answer.strip() != "YES":
            print("Nothing was changed.")
            return
    try:
        db.reset()
        if "--demo" in sys.argv:
            db.add_demo_data()
    except DatabaseError as error:
        sys.exit(str(error))
    print(f"The MedScan tables in '{db.name}' were rebuilt with the demo accounts (doctor 2001, patient 1001).")
    if "--demo" in sys.argv:
        print("The sample doctors, patients and history were added too (their password is demo123).")


if __name__ == "__main__":
    main()
