// Unit tests for parseArgs, including that `--label-cap` returns through `opts` instead of
// reaching past it to mutate the module-level PAGE constant as a side effect of parsing.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseArgs } from '../scripts/build-magazine.mjs';

test('parseArgs is a pure argv -> opts function for the required flags', () => {
  const opts = parseArgs(['--out', 'edition.html', 'doc.md']);
  assert.equal(opts.out, 'edition.html');
  assert.deepEqual(opts.inputs, ['doc.md']);
});

test('--label-cap is returned on opts, not applied as a side effect of parsing', () => {
  const opts = parseArgs(['--out', 'edition.html', '--label-cap', '9', 'doc.md']);
  assert.equal(opts.labelCap, 9);
});

test('parseArgs without --label-cap leaves opts.labelCap unset', () => {
  const opts = parseArgs(['--out', 'edition.html', 'doc.md']);
  assert.equal(opts.labelCap, undefined);
});

test('parseArgs rejects an unknown flag', () => {
  assert.throws(() => parseArgs(['--out', 'edition.html', '--bogus', 'doc.md']), /unknown option/);
});

test('parseArgs requires --out and at least one input', () => {
  assert.throws(() => parseArgs(['doc.md']), /--out/);
  assert.throws(() => parseArgs(['--out', 'edition.html']), /at least one markdown file/);
});
