"""What a fenced block is, read from fences.json beside this file — the one definition the diagram
gate, the edit gate and the publish board share. The magazine builder reads the same JSON and
mirrors `fence_at` below; tests/fences/ pins every tool to the same answer on every fence shape.

Other skills load this module by path (importlib), never by `import fences`, so it works however
the caller was started.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_SPEC = json.loads(Path(__file__).with_name("fences.json").read_text(encoding="utf-8"))
MIN_LENGTH: int = _SPEC["minLength"]
# language as written in the info string (lower-case) -> the engine that draws it
DIAGRAM_LANGS: dict[str, str] = {k.lower(): v for k, v in _SPEC["diagramLanguages"].items()}
_ANY_LANGUAGE: dict[str, bool] = {m["char"]: m["anyLanguage"] for m in _SPEC["markers"]}
_OPENER = re.compile(
    r"^[ \t]*(?P<run>(?P<ch>[" + re.escape("".join(_ANY_LANGUAGE)) + r"])(?P=ch){"
    + str(MIN_LENGTH - 1) + r",})[ \t]*(?P<info>.*?)[ \t]*$")


@dataclass(frozen=True)
class Fence:
    start: int            # 0-based line of the opener
    end: int              # 0-based line of the closer; len(lines) when unterminated
    run: str              # the opening marker run, e.g. ``` or ::::
    lang: str             # the info string's first word, as written ('' for none)
    engine: str | None    # mermaid | graphviz for a diagram fence, else None

    @property
    def diagram(self) -> bool:
        return self.engine is not None


def split_lines(text: str) -> list[str]:
    """Lines exactly as the builder splits them, so a line number means the same in every tool."""
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def opener(line: str) -> tuple[str, str] | None:
    """(marker run, language) when `line` opens a fence, else None."""
    m = _OPENER.match(line)
    if not m:
        return None
    run, info = m.group("run"), m.group("info")
    if run[0] == "`" and "`" in info:
        return None          # a backtick fence's info string may not hold a backtick: that is inline code
    lang = info.split()[0] if info else ""
    if not _ANY_LANGUAGE[run[0]] and lang.lower() not in DIAGRAM_LANGS:
        return None
    return run, lang


def is_closer(line: str, run: str) -> bool:
    s = line.strip()
    return len(s) >= len(run) and set(s) == {run[0]}


def fence_at(lines: list[str], i: int) -> Fence | None:
    """The fence that opens on line `i`, running to its closer or the end of the document."""
    o = opener(lines[i])
    if not o:
        return None
    run, lang = o
    j = i + 1
    while j < len(lines) and not is_closer(lines[j], run):
        j += 1
    return Fence(i, j, run, lang, DIAGRAM_LANGS.get(lang.lower()))


def scan(text: str) -> list[Fence]:
    """Every fence in a document, in order."""
    lines = split_lines(text)
    out: list[Fence] = []
    i = 0
    while i < len(lines):
        f = fence_at(lines, i)
        if f:
            out.append(f)
            i = f.end + 1
        else:
            i += 1
    return out
