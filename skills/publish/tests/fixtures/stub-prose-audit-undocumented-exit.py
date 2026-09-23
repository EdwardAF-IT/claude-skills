#!/usr/bin/env python3
"""Stand-in for edit/scripts/prose_audit.py `check`: exits with a code outside its documented
contract ({0}), with no traceback text. publish.py must still call this red — the contract is
the exit code, not the presence of the word "Traceback"."""
import sys

print('some odd partial output')
sys.exit(9)
