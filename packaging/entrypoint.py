"""PyInstaller entry point.

The package ``__main__.py`` uses a relative import and cannot be used as a
top-level script. This module uses absolute imports and is the frozen app
entry point.
"""

from autotube.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
