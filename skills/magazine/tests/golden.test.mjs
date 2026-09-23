// Golden test: the structure() decomposition, the run-in helper, the px->pt constant and the
// fidelity-gate rewrite must not change a single byte of a built edition, other than the masthead
// date. `tests/fixtures/golden-before.html` and `golden2-before.html` were captured from the
// UNMODIFIED build-magazine.mjs (via `git show HEAD:...` before any of this pass's edits) so this
// test proves the refactor against the real pre-change output, not a re-derived expectation.
// Regenerated 2026-09-22 on purpose when the palette moved to :root: the only change is the
// inlined stylesheet's :root gaining --ink-faint, --teal/--teal-bg, the pie second shades and a
// comment. Rendered content is byte-identical.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const script = path.join(here, '..', 'scripts', 'build-magazine.mjs');

// The masthead's "Printed <date>" line is expected to change (that is finding 6's own fix); every
// other line must be identical to the pre-refactor build.
const stripDate = (html) => html.replace(/Printed \d{4}-\d{2}-\d{2}/, 'Printed <date>');

function buildFixture(name) {
  const dir = mkdtempSync(path.join(tmpdir(), 'magazine-golden-'));
  const out = path.join(dir, 'out.html');
  try {
    execFileSync('node', [script, '--out', out, '--kind', 'brief', path.join(here, 'fixtures', name)], {
      encoding: 'utf8',
    });
    return readFileSync(out, 'utf8');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test('sample.md builds byte-identical to the pre-refactor golden, except the date', () => {
  const golden = readFileSync(path.join(here, 'fixtures', 'golden-before.html'), 'utf8');
  const rebuilt = buildFixture('sample.md');
  assert.equal(stripDate(rebuilt), stripDate(golden));
});

test('sample2.md (ladder, fielded list, card grid, deflist, record cards, quote) builds byte-identical to the pre-refactor golden, except the date', () => {
  const golden = readFileSync(path.join(here, 'fixtures', 'golden2-before.html'), 'utf8');
  const rebuilt = buildFixture('sample2.md');
  assert.equal(stripDate(rebuilt), stripDate(golden));
});
