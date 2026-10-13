"""Empties the MedScan tables in the database and builds them again from database/schema.sql,
with the test accounts from database/seed.sql.

Run:  python reset_database.py          (asks first)
      python reset_database.py --yes    (no question)
Uses the database named in MEDSCAN_DB_NAME (default db_medscan). Other databases are never touched."""
import sys

from data.D_Database import Database, DatabaseError


def main():
    db = Database.from_environment()
    if "--yes" not in sys.argv:
        answer = input(f"This deletes all MedScan data in '{db.name}' and restores the test accounts. Type YES to go on: ")
        if answer.strip() != "YES":
            print("Nothing was changed.")
            return
    try:
        db.reset()
    except DatabaseError as error:
        sys.exit(str(error))
    print(f"The MedScan tables in '{db.name}' were rebuilt with the test accounts (doctor 2001, patient 1001).")


if __name__ == "__main__":
    main()
