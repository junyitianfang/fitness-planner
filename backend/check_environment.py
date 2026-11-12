"""Environment checks used by the PowerShell launcher, without shell quoting."""
import importlib
import sys


def main():
    for name in ('fastapi', 'uvicorn', 'multipart', 'pydantic'):
        importlib.import_module(name)
    print('Backend dependencies ready.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
