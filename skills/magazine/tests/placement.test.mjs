// Unit tests for placementFor, the query the diagram skill's magazine target measures with: it
// must answer with the same placement a build makes, and leave no state behind.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { placementFor, parseArgs } from '../scripts/build-magazine.mjs';

const TALL = '101x2536';   // tests/fixtures of the diagram skill: forty steps, one column wide
const WIDE = '571x425';

test('a tall figure is shrunk by the page height, not only the width', () => {
  const p = placementFor(TALL);
  assert.ok(p.scale < 0.5, `scale ${p.scale}`);
  assert.ok(p.labelPt < 7, `labels ${p.labelPt}pt`);
  // Height-bound: the plate fills the page box, far narrower than any column.
  assert.ok(p.hIn > 9 && p.wIn < 1, `${p.wIn}x${p.hIn}in`);
});

test('an ordinary figure prints at the label cap, not blown up to fill the room', () => {
  const p = placementFor(WIDE);
  assert.equal(p.labelPt, 10);
});

test('the kind changes the placement choices', () => {
  assert.equal(placementFor(TALL, 'feature').cls, 'diagram tall');
  assert.equal(placementFor(TALL, 'brief').cls, 'diagram full plate');
});

test('--label-cap applies to the query and is restored after it', () => {
  assert.equal(placementFor(WIDE, 'feature', 8).labelPt, 8);
  assert.equal(placementFor(WIDE).labelPt, 10);
});

test('a malformed size or unknown kind is refused, never guessed', () => {
  assert.throws(() => placementFor('0x5'), /--place takes/);
  assert.throws(() => placementFor('wide'), /--place takes/);
  assert.throws(() => placementFor(WIDE, 'poster'), /--kind must be one of/);
});

test('--place parses without --out or inputs, and still validates --kind', () => {
  assert.equal(parseArgs(['--place', WIDE]).place, WIDE);
  assert.throws(() => parseArgs(['--place', WIDE, '--kind', 'poster']), /--kind must be one of/);
});
