// The page's numbers have one home, assets/geometry.json. The builder derives its plate geometry
// from it; magazine.css states the same page to the browser, and this test pins the two together.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { GEOMETRY, PORTRAIT, LANDSCAPE, DEFAULT_CSS } from '../scripts/build-magazine.mjs';

const css = readFileSync(DEFAULT_CSS, 'utf8');
// The first rule for exactly this selector that sets `needs` (a selector can have several rules).
const rule = (selector, needs) => {
  const re = new RegExp(`(?:^|\\n)\\s*${selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{([^}]*)\\}`, 'g');
  const body = [...css.matchAll(re)].map((m) => m[1]).find((b) => new RegExp(`(?:^|[;\\s])${needs}\\s*:`).test(b));
  assert.ok(body, `no ${selector} rule setting ${needs} in magazine.css`);
  return body;
};
const prop = (body, name) => {
  const m = body.match(new RegExp(`(?:^|[;{\\s])${name}\\s*:\\s*([^;]+);`));
  assert.ok(m, `no ${name}`);
  return m[1].trim();
};
const inches = (list) => list.split(/\s+/).map((v) => Number(v.replace(/in$/, '')));
const p = GEOMETRY.portrait;
const l = GEOMETRY.landscape;

test('the builder derives its plate geometry from geometry.json', () => {
  assert.equal(PORTRAIT.measureIn, 7.5);
  assert.ok(Math.abs(PORTRAIT.boxIn - 9.85) < 1e-9);
  assert.ok(Math.abs(PORTRAIT.columnIn - 3.4458) < 1e-3);
  assert.ok(Math.abs(LANDSCAPE.measureIn - 10.2) < 1e-9);
  assert.ok(Math.abs(LANDSCAPE.boxIn - 7.53) < 1e-9);   // 8.5 less 0.4 top, 0.55 bottom (the folio), 0.02 safety
});

test('magazine.css states the same portrait page as geometry.json', () => {
  const page = rule('.page', 'padding');
  assert.equal(prop(page, 'width'), `${p.pageIn.width}in`);
  assert.deepEqual(inches(prop(page, 'padding')), [p.marginIn.top, p.marginIn.side, p.marginIn.bottom]);
  const print = css.match(/@page\s*\{\s*size:\s*letter;\s*margin:\s*([^;]+);/);
  assert.ok(print, 'no portrait @page rule');
  assert.deepEqual(inches(print[1]), [p.marginIn.top, p.marginIn.side, p.marginIn.bottom]);
  assert.equal(prop(rule('.columns', 'column-gap'), 'column-gap'), `${GEOMETRY.columnGapPx}px`);
});

test('magazine.css states the same landscape plate page as geometry.json', () => {
  assert.equal(prop(rule('.landscape .page', 'width'), 'width'), `${l.pageIn.width}in`);
  const plate = css.match(/@page plate\s*\{[^}]*margin:\s*([^;]+);/);
  assert.ok(plate, 'no @page plate rule');
  assert.deepEqual(inches(plate[1]),
    [GEOMETRY.plateLandscapeMarginIn, GEOMETRY.plateLandscapeMarginIn, l.marginIn.bottom]);
  const platePage = rule('.plate-page', 'width');
  const measure = l.pageIn.width - 2 * GEOMETRY.plateLandscapeMarginIn;
  assert.equal(prop(platePage, 'width'), `${measure}in`);
  assert.equal(prop(platePage, 'margin-left'), `-${measure / 2}in`);
});

// A printer cannot reach the last ~0.25in of the sheet. The folio hangs from the top of the bottom
// margin, so a 0.55in margin keeps its lower edge ~0.35in from the paper's edge; a smaller margin,
// or a folio centred in it, printed with its lower half cut off (2026-09-22).
const FOLIO_MARGIN_MIN_IN = 0.55;

test('every page leaves the folio clear of the edge a printer cannot reach', () => {
  assert.ok(p.marginIn.bottom >= FOLIO_MARGIN_MIN_IN, `portrait bottom ${p.marginIn.bottom}in`);
  assert.ok(l.marginIn.bottom >= FOLIO_MARGIN_MIN_IN, `landscape bottom ${l.marginIn.bottom}in`);
  const folio = css.match(/@bottom-right\s*\{([^}]*)\}/);
  assert.ok(folio, 'no folio margin box');
  assert.match(folio[1], /vertical-align:\s*top/, 'the folio hangs from the top of the margin');
});
