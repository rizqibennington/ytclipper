const test = require('node:test');
const assert = require('node:assert/strict');

const sortSegments = (segments, currentSortCol, currentSortDir) => {
  const list = [...segments];
  list.sort((a, b) => {
    let valA, valB;
    if (currentSortCol === 'start') {
      valA = a.start | 0;
      valB = b.start | 0;
    } else if (currentSortCol === 'end') {
      valA = a.end | 0;
      valB = b.end | 0;
    } else if (currentSortCol === 'dur') {
      valA = Math.max(0, (a.end | 0) - (a.start | 0));
      valB = Math.max(0, (b.end | 0) - (b.start | 0));
    } else {
      valA = Number(a.score ?? 0);
      valB = Number(b.score ?? 0);
    }

    if (valA === valB) {
      return (a.start | 0) - (b.start | 0);
    }

    return currentSortDir === 'asc' ? valA - valB : valB - valA;
  });
  return list;
};

test('sorts by score desc and asc', () => {
  const sample = [
    { start: 10, end: 20, score: 0.8 },
    { start: 30, end: 40, score: 0.95 },
    { start: 5, end: 15, score: 0.9 },
  ];

  const desc = sortSegments(sample, 'score', 'desc');
  assert.equal(desc[0].score, 0.95);
  assert.equal(desc[1].score, 0.9);
  assert.equal(desc[2].score, 0.8);

  const asc = sortSegments(sample, 'score', 'asc');
  assert.equal(asc[0].score, 0.8);
  assert.equal(asc[1].score, 0.9);
  assert.equal(asc[2].score, 0.95);
});

test('sorts by start time asc and desc', () => {
  const sample = [
    { start: 120, end: 180, score: 0.9 },
    { start: 15, end: 45, score: 0.95 },
    { start: 60, end: 100, score: 0.8 },
  ];

  const asc = sortSegments(sample, 'start', 'asc');
  assert.equal(asc[0].start, 15);
  assert.equal(asc[1].start, 60);
  assert.equal(asc[2].start, 120);

  const desc = sortSegments(sample, 'start', 'desc');
  assert.equal(desc[0].start, 120);
  assert.equal(desc[1].start, 60);
  assert.equal(desc[2].start, 15);
});

test('sorts by duration asc and desc', () => {
  const sample = [
    { start: 0, end: 50, score: 0.9 }, // 50s
    { start: 100, end: 120, score: 0.95 }, // 20s
    { start: 200, end: 290, score: 0.8 }, // 90s
  ];

  const asc = sortSegments(sample, 'dur', 'asc');
  assert.equal(asc[0].end - asc[0].start, 20);
  assert.equal(asc[1].end - asc[1].start, 50);
  assert.equal(asc[2].end - asc[2].start, 90);

  const desc = sortSegments(sample, 'dur', 'desc');
  assert.equal(desc[0].end - desc[0].start, 90);
  assert.equal(desc[1].end - desc[1].start, 50);
  assert.equal(desc[2].end - desc[2].start, 20);
});

