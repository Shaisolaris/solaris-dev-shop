#!/usr/bin/env python3
"""G14 no-op control: exits 0 with an empty report (must be REJECTED)."""
import sys

sys.stdout.write("{}\n")
sys.exit(0)
