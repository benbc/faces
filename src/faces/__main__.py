from pathlib import Path

from .application import Web

if __name__ == '__main__':
    root_dir = Path(__file__).parent.parent
    Web.create(root_dir).run()
