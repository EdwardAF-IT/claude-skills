// Unit tests for the fidelity gate (`verifyEdition` and its helpers) in build-magazine.mjs.
// These call the exported functions directly — no CLI build, no filesystem output — so the gate
// itself has a seam to test, which it did not have before.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { verifyEdition, extractCells, editionText, normalise } from '../scripts/build-magazine.mjs';

test('a dropped table row fails even when its words coincidentally appear in unrelated prose', () => {
  const md = [
    '| Country | Ready |',
    '| --- | --- |',
    '| Norway | Yes |',
    '| Kenya | Blocked |',
    '',
  ].join('\n');
  // The Kenya/Blocked row never made it into the table — but both words happen to appear in a
  // decoy sentence elsewhere in the edition. A whole-document substring check would miss this.
  const html = '<table><thead><tr><th>Country</th><th>Ready</th></tr></thead><tbody>' +
    '<tr><td>Norway</td><td>Yes</td></tr></tbody></table>' +
    '<p>Kenya remains blocked by new sanctions, unrelated to the table above.</p>';

  const missing = verifyEdition([{ file: 'sample.md', md }], html);
  const texts = missing.map((m) => m.text);
  assert.ok(texts.includes('Kenya'), 'dropped cell "Kenya" must be reported missing');
  assert.ok(texts.includes('Blocked'), 'dropped cell "Blocked" must be reported missing');
  // The kept row must not be flagged.
  assert.ok(!texts.includes('Norway'));
  assert.ok(!texts.includes('Yes'));
});

test('a kept table row, rendered as record cards (dt/dd + h5 card-title), is not flagged', () => {
  const md = [
    '| Name | Notes |',
    '| --- | --- |',
    '| Northgate | A long paragraph of notes about the northgate rollout. |',
    '',
  ].join('\n');
  const html = '<div class="cards-head"><span>Name</span><span>Notes</span></div>' +
    '<section class="cards"><article class="card"><h5 class="card-title">Northgate</h5>' +
    '<dl><dt>Notes</dt><dd>A long paragraph of notes about the northgate rollout.</dd></dl>' +
    '</article></section>';

  const missing = verifyEdition([{ file: 'sample.md', md }], html);
  assert.deepEqual(missing, []);
});

test('a dropped paragraph fails the fidelity check', () => {
  const md = 'This entire paragraph about widgets never makes it into the edition.\n';
  const html = '<p>Something completely different is printed instead.</p>';

  const missing = verifyEdition([{ file: 'sample.md', md }], html);
  assert.equal(missing.length, 1);
  assert.equal(missing[0].line, 1);
});

test('a paragraph reordered in the edition, but still present, is not flagged', () => {
  const md = 'Alpha paragraph text here.\n\nBeta paragraph text here.\n';
  // Beta prints before Alpha in the edition — order changed, wording did not.
  const html = '<p>Beta paragraph text here.</p><p>Alpha paragraph text here.</p>';

  const missing = verifyEdition([{ file: 'sample.md', md }], html);
  assert.deepEqual(missing, []);
});

test('extractCells pulls td/th, dt/dd and a record card title, not prose', () => {
  const html = '<table><tr><th>H</th><td>plain cell</td></tr></table>' +
    '<dl><dt>term</dt><dd>definition value</dd></dl>' +
    '<h5 class="card-title">card key</h5>' +
    '<p>this paragraph is not a cell</p>';
  const cells = extractCells(html);
  assert.deepEqual(cells.sort(), ['card key', 'definition value', 'h', 'plain cell', 'term'].sort());
});

test('editionText and normalise still collapse whitespace for ordinary substring checks', () => {
  const html = '<p>Hello   world</p>';
  assert.equal(editionText(html), 'hello world');
  assert.equal(normalise('  Hello   World  '), 'hello world');
});
