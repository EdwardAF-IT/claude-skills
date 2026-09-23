// Unit tests for the extracted `renderSub` helper (the nested sub-list expression that used to be
// duplicated three times across renderItems/renderRunInItem/renderRunIn).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderSub, renderList } from '../scripts/build-magazine.mjs';

test('renderSub returns an empty string for a leaf item (no sub-items)', () => {
  const item = { text: 'leaf', sub: [], task: null };
  assert.equal(renderSub(item), '');
});

test('renderSub renders an unordered nested list', () => {
  const item = {
    text: 'parent',
    sub: [
      { text: 'child one', sub: [], task: null, ordered: false },
      { text: 'child two', sub: [], task: null, ordered: false },
    ],
  };
  assert.equal(renderSub(item), renderList(item.sub, false));
  assert.match(renderSub(item), /^<ul>.*child one.*child two.*<\/ul>$/s);
});

test('renderSub renders an ordered nested list, taking its ordered flag from the first sub-item', () => {
  const item = {
    text: 'parent',
    sub: [
      { text: 'step one', sub: [], task: null, ordered: true },
      { text: 'step two', sub: [], task: null, ordered: true },
    ],
  };
  const html = renderSub(item);
  assert.match(html, /^<ol>/);
  assert.match(html, /<\/ol>$/);
});
