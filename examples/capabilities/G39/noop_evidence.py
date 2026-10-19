#!/usr/bin/env python3
"""No-op control: runs nothing, records nothing, always answers GO. Must fail the G39 oracle."""
import sys
if __name__ == "__main__":
    if sys.argv[1:2] == ["verify"]:
        print("delivery verdict: GO")
    sys.exit(0)
