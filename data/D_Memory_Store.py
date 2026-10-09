from data.D_Store import Store


class MemoryStore(Store):
    """Saves nothing. Used by the tests so they never touch real data."""

    def load(self):
        """Nothing is ever saved, so there is nothing to load."""
        return None

    def save(self, system):
        """Do nothing."""
