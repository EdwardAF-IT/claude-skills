// The builder reads a figure's title and caption exactly as the diagram gate does, and prints
// them with the plate: the title under the figure number, the caption beneath, each once.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { scanFences, splitLines, figureLabels, build, verifyEdition } from '../scripts/build-magazine.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const shared = path.join(here, '..', '..', 'diagram', 'tests', 'fences');
const docPath = path.join(shared, 'labels.md');
const doc = readFileSync(docPath, 'utf8');
const want = JSON.parse(readFileSync(path.join(shared, 'labels.expected.json'), 'utf8')).labels;

const edition = () => build({
  inputs: [docPath], out: 'unused.html', mermaid: 'code', accent: null, toc: null, columns: null,
  serif: null, verify: true, kind: 'brief',
}).html;

test('every figure gets the shared title and caption', () => {
  const lines = splitLines(doc);
  const got = scanFences(lines).filter((f) => f.engine).map((f) => {
    const { title, caption } = figureLabels(lines, f);
    return { title: title ? title.text : null, caption: caption ? caption.text : null };
  });
  assert.deepEqual(got, want);
});

test('a title prints under the figure number and a caption beneath the plate, once each', () => {
  const html = edition();
  for (const { title, caption } of want.filter((l) => l.title)) {
    assert.equal(html.split(`<p class="figure-title">${title}</p>`).length - 1, 1, title);
    assert.equal(html.split(`<figcaption class="figure-caption">${caption}</figcaption>`).length - 1, 1, caption);
  }
  // Consumed by the figure: never also printed as a paragraph of its own.
  assert.ok(!/<p>(?:<strong>|<em>)How a request reaches the database/.test(html));
  assert.ok(!/<p><em>A request passes through the API/.test(html));
  assert.equal((html.match(/class="figure-title"/g) || []).length, want.filter((l) => l.title).length);
});

test('bold and italic lines that are not labels stay in the prose', () => {
  const html = edition();
  assert.match(html, /not a title/);
  assert.match(html, /partly italic/);
  assert.match(html, /a list item is not a caption/);
});

test('an edition with titles and captions passes its own fidelity check', () => {
  assert.deepEqual(verifyEdition([{ file: docPath, md: doc }], edition()), []);
});
