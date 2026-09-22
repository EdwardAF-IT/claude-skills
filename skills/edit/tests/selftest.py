#!/usr/bin/env python3
"""One case per check in prose_audit.py. Each fixture fails without the check it guards; a gate
suite that cannot go red is decoration. Run: python tests/selftest.py — expect N/N."""
from __future__ import annotations

import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prose_audit as pa  # noqa: E402

BEFORE = """# Doc

## 1. Section

The `ExecutionBroker` places a job through `SubmitAsync` and records provenance in
`execution.db`. It uses ProjectVerificationCache.ComputeKey for the hash. The lease TTL is
30 s and the fleet has 5 boxes; see §7.3 and [the broker](execution-broker.md). Item #1337
is the worked example. The flag is `--label-cap`.

| Id | Meaning |
|---|---|
| P-01 | The loop is invisible |

```mermaid
flowchart TD
    A --> B
```
"""


def run(argv) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            code = pa.main(argv)
        except SystemExit as e:  # argparse
            code = int(e.code or 0)
    return code, buf.getvalue()


def diff(before: str, after: str, *extra) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as d:
        b = Path(d) / 'b.md'
        a = Path(d) / 'a.md'
        b.write_text(before, encoding='utf-8')
        a.write_text(after, encoding='utf-8')
        return run(['diff', str(b), str(a), *extra])


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case('an unchanged document is KEPT (exit 0)')
def _():
    code, out = diff(BEFORE, BEFORE)
    assert code == 0 and 'KEPT' in out, out


@case('a rewrite that keeps every fact is KEPT even when every sentence changed')
def _():
    after = BEFORE.replace('The `ExecutionBroker` places a job through `SubmitAsync` and records provenance in\n`execution.db`. It uses ProjectVerificationCache.ComputeKey for the hash.',
                           'A job enters through `SubmitAsync`; the `ExecutionBroker` places it and writes provenance to `execution.db`. The hash comes from ProjectVerificationCache.ComputeKey.')
    code, out = diff(BEFORE, after)
    assert code == 0, out


@case('a dropped code span is DESTROYED (exit 2)')
def _():
    code, out = diff(BEFORE, BEFORE.replace(' and records provenance in\n`execution.db`', ''))
    assert code == 2 and 'execution.db' in out, out


@case('a dropped identifier is DESTROYED')
def _():
    code, out = diff(BEFORE, BEFORE.replace('It uses ProjectVerificationCache.ComputeKey for the hash. ', ''))
    assert code == 2 and 'ProjectVerificationCache.ComputeKey' in out, out


@case('an identifier written with spaces is kept, not lost')
def _():
    b = "The InternalAPI is called.\n"
    a = "The internal API is called.\n"
    code, out = diff(b, a)
    assert code == 0, out


@case('a dropped number with its unit is DESTROYED')
def _():
    code, out = diff(BEFORE, BEFORE.replace('The lease TTL is\n30 s and the fleet has 5 boxes', 'The lease TTL is set and the fleet has 5 boxes'))
    assert code == 2 and "'30 s'" in out and 'TTL' not in out.split('facts checked')[1], out


@case('a dropped example number of 4+ digits is a warning, not a blocker')
def _():
    code, out = diff(BEFORE, BEFORE.replace(' Item #1337\nis the worked example.', ''))
    assert code == 0 and 'dropped example' in out and '1337' in out, out


@case('a dropped section reference is DESTROYED')
def _():
    code, out = diff(BEFORE, BEFORE.replace('see §7.3 and', 'see'))
    assert code == 2 and '§7.3' in out, out


@case('a dropped link target is DESTROYED')
def _():
    code, out = diff(BEFORE, BEFORE.replace('[the broker](execution-broker.md)', 'the broker'))
    assert code == 2 and 'execution-broker.md' in out, out


@case('a dropped CLI flag is DESTROYED')
def _():
    code, out = diff(BEFORE, BEFORE.replace(' The flag is `--label-cap`.', ''))
    assert code == 2 and '--label-cap' in out, out


@case('a changed fenced block is DESTROYED: the edit skill never touches a diagram')
def _():
    code, out = diff(BEFORE, BEFORE.replace('A --> B', 'A --> C'))
    assert code == 2 and 'fence' in out, out


@case('a removed table cell is CHANGED (exit 1), and declared it passes')
def _():
    after = BEFORE.replace('| P-01 | The loop is invisible |', '| P-01 | The loop cannot be seen |')
    code, out = diff(BEFORE, after)
    assert code == 1 and 'changed' in out, out
    code, out = diff(BEFORE, after, '--declare', 'cell reworded on purpose')
    assert code == 0, out


@case('a reworded heading is CHANGED, never silently accepted')
def _():
    code, out = diff(BEFORE, BEFORE.replace('## 1. Section', '## 1. The section'))
    assert code == 1 and 'heading' in out, out


@case('a fact moved to another paragraph is kept (relocation is allowed)')
def _():
    after = BEFORE.replace(' The flag is `--label-cap`.', '') + '\nThe flag is `--label-cap`.\n'
    code, out = diff(BEFORE, after)
    assert code == 0, out


@case('check finds a wall of 300+ words with no entry point')
def _():
    sentence = 'The loop runs a pass on a short interval and drains the durable queue before it dispatches anything at all. '
    md = '# D\n\n## 1. S\n\n' + '\n\n'.join([sentence * 4] * 5) + '\n'
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'w.md'
        p.write_text(md, encoding='utf-8')
        code, out = run(['check', str(p)])
    assert '[wall]' in out and 'walls 1' in out, out


@case('check names a sentence over 30 words and counts the long share')
def _():
    long = 'This sentence goes on and on with clause after clause and a parenthetical (which is the point) and a dash - and more - until it passes thirty words easily and then keeps going for a while longer.'
    md = f'# D\n\n## 1. S\n\nShort one. {long} Another short one.\n'
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'l.md'
        p.write_text(md, encoding='utf-8')
        code, out = run(['check', str(p)])
    assert '[long]' in out and 'long 33%' in out, out


@case('list items are measured as prose, and the list still breaks a wall')
def _():
    item = '1. **A question.** This item runs on for a long while with clause after clause and a parenthetical (as they do) and a dash - and more - until it is well past thirty words, which is the point of the fixture.'
    md = '# D\n\n## 1. S\n\nShort.\n\n' + '\n'.join(item.replace('1.', f'{k}.') for k in range(1, 4)) + '\n'
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'i.md'
        p.write_text(md, encoding='utf-8')
        code, out = run(['check', str(p)])
    assert '[long]' in out and 'walls 0' in out and '118 words' in out and 'This item runs on' in out, out


@case('a heading that carries a link keeps the link text as its words')
def _():
    b = '# D\n\n## See [the broker](x.md) now\n\nText.\n'
    a = '# D\n\n## See the broker now\n\nText, in [the broker](x.md).\n'
    code, out = diff(b, a)
    assert code == 0, out


@case('a heading or cell that carries a code span matches itself (the self-diff is KEPT)')
def _():
    b = '# D\n\n## 5.1 Registry - `executors.json`\n\n| Id | Meaning |\n|---|---|\n| `P-01` | The `loop` |\n\nText.\n'
    code, out = diff(b, b)
    assert code == 0 and 'KEPT' in out, out


@case('every sentence over 45 words is named, even five of them in one section')
def _():
    big = 'This sentence is built to run past forty-five words by stacking clause after clause after clause, with a parenthetical (as these do) and a dash - and another - and it keeps going until the count is safely past the line that the tool draws for a very long sentence indeed.'
    md = '# D\n\n## 1. S\n\n' + '\n\n'.join([big] * 5) + '\n'
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'v.md'
        p.write_text(md, encoding='utf-8')
        code, out = run(['check', str(p)])
    assert out.count('[long]') == 5, out


@case('a consequence cut from its "so" and left as a bare assertion is CAUSAL (exit 1)')
def _():
    b = '# D\n\n## 1. S\n\nThe phase now has a command form, so any repo fits the manifest and the script is a legacy alias read once.\n'
    a = '# D\n\n## 1. S\n\nThe phase now has a command form, so any repo fits the manifest. The script is a legacy alias read once.\n'
    code, out = diff(b, a)
    assert code == 1 and '[causal]' in out and 'the script is a legacy' in out, out


@case('"if so" is not a cause, and a cause that follows its consequence still counts')
def _():
    b = '# D\n\n## 1. S\n\nIf so: the landing is not blocked by it, but the corpus is red. The filing rule, since filing a row is outward-facing but not destructive.\n'
    a = '# D\n\n## 1. S\n\nIf so: the landing is not blocked by it, but the corpus is red. Filing a row is outward-facing but not destructive, so it gets a rule.\n'
    code, out = diff(b, a)
    assert '[causal]' not in out, out


@case('a split that keeps every consequence on its cause is KEPT')
def _():
    b = '# D\n\n## 1. S\n\nThe phase now has a command form, so any repo fits the manifest and the script is a legacy alias read once.\n'
    a = '# D\n\n## 1. S\n\nThe phase now has a command form. So any repo fits the manifest, and so the script is a legacy alias read once.\n'
    code, out = diff(b, a)
    assert code == 0 and '[causal]' not in out, out


@case('a section reference like §7.3 does not split a sentence')
def _():
    s = pa.sentences('See §7.3 for the window. The next one.')
    assert len(s) == 2, s


@case('audit ranks the costlier section first')
def _():
    dense = ('The pipeline, which is invoked by the pass that is fired by the interval or by an operator command that was written to the durable queue by Podium or by the CLI, is executed before anything is dispatched because every dispatch is based on the master that the landing has just moved. ' * 6)
    light = 'The loop runs all the time. A pass fires on a short interval. It also fires on a command. An idle pass costs nothing. ' * 8
    md = f'# D\n\n## 1. Dense\n\n{dense}\n\n## 2. Light\n\n{light}\n'
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'r.md'
        p.write_text(md, encoding='utf-8')
        code, out = run(['audit', str(p)])
    lines = [l for l in out.splitlines() if '## ' in l]
    assert lines and 'Dense' in lines[0] and 'Light' in lines[1], out


@case('a rewrite that raises the reading cost is warned about')
def _():
    b = '# D\n\n## 1. S\n\nThe loop runs. A pass fires. It drains the queue. ' * 3 + '\n'
    a = '# D\n\n## 1. S\n\n' + 'The loop, which runs, fires a pass, which, being fired, drains the queue that it was given by the operator who wrote it, and then it continues with the next thing that it was going to do anyway. ' * 3 + '\n'
    code, out = diff(b, a)
    assert 'reading cost rose' in out, out


def main() -> int:
    passed = 0
    for name, fn in CASES:
        try:
            fn()
            passed += 1
            print(f'  ok   {name}')
        except AssertionError as e:
            print(f'  FAIL {name}\n       {str(e)[:400]}')
        except Exception as e:  # noqa: BLE001
            print(f'  FAIL {name}\n       {type(e).__name__}: {e}')
    print(f'{passed}/{len(CASES)}')
    return 0 if passed == len(CASES) else 1


if __name__ == '__main__':
    sys.exit(main())
