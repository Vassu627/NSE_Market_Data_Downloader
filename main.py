"""Shim so `python main.py` works as in the assignment example."""

from __future__ import annotations

import sys

from nse_downloader.main import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
