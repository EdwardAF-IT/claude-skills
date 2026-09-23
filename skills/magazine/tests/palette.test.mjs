// The edition's palette has one home, the stylesheet's :root; the plates take their colors from
// it, and --accent recolors the plates as well as the page.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { paletteOf, mermaidConfig, actorHues, parseArgs, DEFAULT_CSS, MERMAID_THEME } from '../scripts/build-magazine.mjs';

const css = readFileSync(DEFAULT_CSS, 'utf8');
const colors = (o) => JSON.stringify(o).match(/#[0-9a-fA-F]{3,8}\b/g) || [];

test('mermaid-theme.json names every color from the palette and holds no hex of its own', () => {
  assert.deepEqual(colors(JSON.parse(readFileSync(MERMAID_THEME, 'utf8'))), []);
});

test('every color a plate is drawn with is a :root value', () => {
  const palette = paletteOf(css);
  const root = new Set(Object.values(palette).map((v) => v.toLowerCase()));
  const config = mermaidConfig(palette);
  assert.ok(!JSON.stringify(config).includes('var('));
  for (const c of colors(config)) assert.ok(root.has(c.toLowerCase()), c);
  const { hues, rest } = actorHues({ palette, hues: null });
  for (const h of [...hues, rest]) for (const c of [h.fill, h.stroke]) assert.ok(root.has(c.toLowerCase()), c);
});

test('the blue tint is one value: the plates use the stylesheet\'s own', () => {
  const palette = paletteOf(css);
  const config = mermaidConfig(palette);
  assert.equal(config.themeVariables.primaryColor, palette['accent-bg']);
  assert.equal(actorHues({ palette, hues: null }).hues[0].fill, palette['blue-bg']);
});

test('--accent reaches the plates: node and actor borders follow it, data hues do not', () => {
  const config = mermaidConfig(paletteOf(css, '#aa3300'));
  const v = config.themeVariables;
  for (const k of ['primaryBorderColor', 'nodeBorder', 'actorBorder', 'activationBorderColor']) assert.equal(v[k], '#aa3300', k);
  assert.equal(v.primaryColor, '#f5e6e0');   // the accent at 1f over paper, opaque
  assert.equal(v.pie1, paletteOf(css).blue);
});

test('--accent must be a #rrggbb color', () => {
  assert.throws(() => parseArgs(['--out', 'x.html', '--accent', 'red', 'doc.md']), /#rrggbb/);
});

test('a stylesheet missing a color the plates use fails loudly, never draws undefined', () => {
  const palette = paletteOf(':root { --ink: #000000; }');
  assert.throws(() => mermaidConfig(palette), /--accent-bg/);
});

test('reading text is true black; display type keeps the ink', () => {
  assert.equal(paletteOf(css).text, '#000000');
  assert.match(css, /\nbody \{[^}]*\bcolor: var\(--text\);/);
  assert.match(css, /\na \{ color: inherit;/);
  assert.notEqual(paletteOf(css).ink, '#000000');
});
