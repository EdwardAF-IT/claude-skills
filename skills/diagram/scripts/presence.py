"""When a dotted identifier is still present though written shorter — the one rule the diagram
diff (audit.py) and the prose diff (edit's prose_audit.py) share, so a fact one gate keeps the
other cannot call DESTROYED. tests/presence-cases.json pins both gates to the same verdicts.

`woDetail.Installer_ID` written as `Installer_ID` is kept. `woDetail` is a local variable: the
route to the field, not something a reader can look up. The field name is what they search for,
and it survives. A reader does lose something when:
  - the qualifier is a type or namespace (`Maestro.Orchestra.Execution`, `Console.WriteLine`):
    it is part of the name, and `Execution` alone names something else;
  - the member alone says nothing (`order.Id` -> `Id`).
Both of those are DESTROYED unless the whole identifier appears.
"""
from __future__ import annotations

import re

MIN_MEMBER_LEN = 5     # a plain-word member shorter than this (Id, name, get) says nothing alone


def _code_like(word: str) -> bool:
    """A member that is unmistakably an identifier: a digit, an underscore, camelCase or an acronym."""
    return (any(c.isdigit() for c in word) or "_" in word
            or bool(re.search(r"[a-z][A-Z]", word)) or bool(re.fullmatch(r"[A-Z][A-Z0-9]{2,}", word)))


def member_stands_for(ident: str) -> str | None:
    """The member that may stand for a dotted identifier (case as written), or None when dropping
    the qualifier loses the fact."""
    if "/" in ident:
        return None          # a path or URL is matched by its segments, not as a member access
    parts = ident.split(".")
    if len(parts) < 2 or not all(parts):
        return None
    *qualifiers, member = parts
    if not all(q[0].islower() for q in qualifiers):
        return None
    if not (_code_like(member) or len(member) >= MIN_MEMBER_LEN):
        return None
    return member


def member_present(ident: str, text: str) -> bool:
    """Is a dotted identifier kept in `text` by its member alone, written as a whole word?"""
    member = member_stands_for(ident)
    return bool(member) and re.search(r"(?<!\w)" + re.escape(member) + r"(?!\w)", text) is not None
