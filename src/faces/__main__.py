from pathlib import Path

from .application import App

if __name__ == '__main__':
    root_dir = Path(__file__).parent.parent
    App(root_dir).run()
