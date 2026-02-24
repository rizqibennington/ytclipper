const test = require('node:test');
const assert = require('node:assert/strict');

const { computeSegBulkButtonsState } = require('../static/seg_bulk_buttons_state.js');

test('no segments -> both disabled', () => {
  const s = computeSegBulkButtonsState([]);
  assert.equal(s.totalCount, 0);
  assert.equal(s.enabledCount, 0);
  assert.equal(s.selectAllDisabled, true);
  assert.equal(s.deselectAllDisabled, true);
});

test('all selected -> select disabled, deselect enabled', () => {
  const s = computeSegBulkButtonsState([{ enabled: true }, { enabled: true }]);
  assert.equal(s.totalCount, 2);
  assert.equal(s.enabledCount, 2);
  assert.equal(s.selectAllDisabled, true);
  assert.equal(s.deselectAllDisabled, false);
});

test('none selected -> select enabled, deselect disabled', () => {
  const s = computeSegBulkButtonsState([{ enabled: false }, { enabled: false }, { enabled: false }]);
  assert.equal(s.totalCount, 3);
  assert.equal(s.enabledCount, 0);
  assert.equal(s.selectAllDisabled, false);
  assert.equal(s.deselectAllDisabled, true);
});

test('partial selected -> both enabled', () => {
  const s = computeSegBulkButtonsState([{ enabled: true }, { enabled: false }, { enabled: false }]);
  assert.equal(s.totalCount, 3);
  assert.equal(s.enabledCount, 1);
  assert.equal(s.selectAllDisabled, false);
  assert.equal(s.deselectAllDisabled, false);
});

test('null entries and missing enabled are treated as not selected', () => {
  const s = computeSegBulkButtonsState([null, {}, { enabled: true }]);
  assert.equal(s.totalCount, 3);
  assert.equal(s.enabledCount, 1);
  assert.equal(s.selectAllDisabled, false);
  assert.equal(s.deselectAllDisabled, false);
});

