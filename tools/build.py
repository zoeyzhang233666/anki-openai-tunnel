"""Build only explicitly allowed addon sources; never package user_files/config state."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FILES = ('__init__.py', 'core.py', 'config.json', 'manifest.json')


def build(destination=None):
    destination = Path(destination or ROOT / 'dist' / 'anki-openai-tunnel.ankiaddon')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / 'addon' / name, name)
    return destination


if __name__ == '__main__':
    print(build())
