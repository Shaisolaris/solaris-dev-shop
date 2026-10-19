#!/usr/bin/env python3
"""Negative control: a no-op activation that only echoes its arguments and exits 0.
It creates nothing. activation_oracle.py must reject it."""
import sys

print(" ".join(sys.argv[1:]))
sys.exit(0)
