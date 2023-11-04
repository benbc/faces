class Project:
    @classmethod
    def create(cls, name):
        return cls(name)

    def __init__(self, name):
        self.name = name
