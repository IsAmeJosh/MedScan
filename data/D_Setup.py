"""Decides which store MedScan uses when the website starts."""
import os

from data.D_Memory_Store import MemoryStore
from data.D_Pickle_Store import PickleStore


def choose_store():
    """MySQL if it is running, otherwise the pickle file (with a clear message).
    Set MEDSCAN_STORE=pickle or MEDSCAN_STORE=memory to force one of the others."""
    wanted = os.environ.get("MEDSCAN_STORE", "mysql").lower()
    if wanted == "memory":
        return MemoryStore()
    if wanted == "pickle":
        print("MedScan: saving to the pickle file.")
        return PickleStore()
    try:
        from data.D_MySQL_Store import MySQLStore
        store = MySQLStore.from_environment()
        store.check()
        print(f"MedScan: saving to the MySQL database '{store.database}'.")
        return store
    except Exception as error:  # MySQL stopped, wrong password, PyMySQL missing, ...
        print("=" * 70)
        print(f"MedScan: could not use MySQL ({error}).")
        print("Start MySQL in the XAMPP Control Panel. For now MedScan saves to the pickle file instead.")
        print("=" * 70)
        return PickleStore()
