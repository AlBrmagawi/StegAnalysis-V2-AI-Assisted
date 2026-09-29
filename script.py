"""Compatibility CLI. Creators: Mohamed Abdelgalil (AlBrmagawi) and Spooky."""

import sys

from steganalysis.cli import main

if __name__ == "__main__":
    main(["analyze", *sys.argv[1:]])
