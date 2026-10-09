class Store:
    """What every store must do (abstraction). MedScanSystem only ever calls these two methods,
    so it does not care whether the data lives in MySQL, a pickle file or memory (polymorphism)."""

    def load(self):
        """Return the saved MedScanSystem, or None if nothing has been saved yet."""
        raise NotImplementedError

    def save(self, system):
        """Save the whole MedScanSystem."""
        raise NotImplementedError
