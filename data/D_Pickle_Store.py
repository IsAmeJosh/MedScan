import os
import pickle

from data.D_Store import Store

# the pickle file lives in the project root (this file is one folder deeper, in data/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(ROOT_DIR, "medscan_data.pkl")


class PickleStore(Store):
    """Keeps the whole system in one pickle file. Simple, and works without any database running."""

    def __init__(self, path=DEFAULT_PATH):
        self.path = path

    def load(self):
        """Read the pickle file, or return None if it does not exist yet."""
        if not os.path.exists(self.path):
            return None
        with open(self.path, "rb") as f:
            return pickle.load(f)

    def save(self, system):
        """Write to a temporary file first, so a crash cannot leave a half-written save."""
        temp_path = self.path + ".tmp"
        with open(temp_path, "wb") as f:
            pickle.dump(system, f)
        os.replace(temp_path, self.path)
