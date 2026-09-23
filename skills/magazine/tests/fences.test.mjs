// The builder reads fences exactly as the diagram gate, the edit gate and the publish board do:
// the diagram skill's shared fixture (every fence shape) must get the shared answer here too.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { scanFences, splitLines, parseBlocks, build, verifyEdition } from '../scripts/build-magazine.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const shared = path.join(here, '..', '..', 'diagram', 'tests', 'fences');
const docPath = path.join(shared, 'every-fence.md');
const doc = readFileSync(docPath, 'utf8');
const want = JSON.parse(readFileSync(path.join(shared, 'every-fence.expected.json'), 'utf8')).fences;

test('every fence shape gets the shared answer', () => {
  const lines = splitLines(doc);
  const got = scanFences(lines).map((f) => ({
    open: f.start + 1, close: f.end < lines.length ? f.end + 1 : null, lang: f.lang, engine: f.engine,
  }));
  assert.deepEqual(got, want);
});

test('every diagram fence becomes a figure, in order, and nothing else does', () => {
  const blocks = parseBlocks(doc, { h1: null, seenSection: false });
  const figures = blocks.filter((b) => b.k === 'figure').map((b) => b.engine);
  const lists = blocks.filter((b) => b.k === 'list');
  assert.deepEqual(figures, want.filter((f) => f.engine).map((f) => f.engine));
  // the fence directly beneath a list item is a figure, not text folded into the item
  assert.ok(lists.every((l) => !l.items.some((it) => /flowchart/.test(it.text))));
});

test('an edition of every fence shape passes its own fidelity check', () => {
  const { html } = build({
    inputs: [docPath], out: 'unused.html', mermaid: 'code', accent: null, toc: null, columns: null, serif: null, verify: true, kind: 'brief',
  });
  assert.deepEqual(verifyEdition([{ file: docPath, md: doc }], html), []);
  assert.equal((html.match(/class="figure-label">Figure \d+/g) || []).length, want.filter((f) => f.engine).length);
});
