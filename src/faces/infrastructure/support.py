class OutputTracker:
    def __init__(self):
        self._current_batch = []
        self._batches = []

    def end_batch(self):
        self._batches.append(self._current_batch)
        self._current_batch = []

    def add(self, data):
        self._current_batch.append(data)

    def last_output(self):
        return self.all_outputs()[-1]

    def all_outputs(self):
        return sum(self._batches, []) + self._current_batch

    def last_batch(self):
        return self._batches[-1]
