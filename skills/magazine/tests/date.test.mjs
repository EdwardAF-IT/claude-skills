// Unit test for the masthead "Printed" date: it must be the reader's local calendar day, not
// UTC, so an edition built in the evening does not print tomorrow's date.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { printedDate } from '../scripts/build-magazine.mjs';

test('printedDate uses the given local time zone, not UTC', () => {
  // 21:30 the previous evening in Chicago is already past midnight UTC.
  const evening = new Date('2026-09-23T02:30:00Z');
  assert.equal(printedDate(evening, 'America/Chicago'), '2026-09-22');
  assert.equal(printedDate(evening, 'UTC'), '2026-09-23');
});

test('printedDate formats as YYYY-MM-DD', () => {
  const noon = new Date('2026-01-05T12:00:00Z');
  assert.equal(printedDate(noon, 'UTC'), '2026-01-05');
});
