#!/usr/bin/env python3
"""Stand-in for diagram/scripts/audit.py: exits 1 with a traceback-shaped crash, the exact
failure mode publish.py's exit-code contract is supposed to catch (finding: a crashed gate
must never be reported green)."""
import sys

print('Traceback (most recent call last):')
print('  File "audit.py", line 1, in <module>')
print("RuntimeError: boom")
sys.exit(1)
