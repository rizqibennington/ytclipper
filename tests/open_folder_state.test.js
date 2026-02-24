const test = require('node:test');
const assert = require('node:assert/strict');

const { computeOpenFolderButtonState } = require('../static/open_folder_state.js');

test('no job status -> hidden and disabled', () => {
  const s = computeOpenFolderButtonState(null, false);
  assert.equal(s.visible, false);
  assert.equal(s.disabled, true);
});

test('done but UI busy -> visible but disabled', () => {
  const s = computeOpenFolderButtonState({ done: true, success_count: 1, output_dir: 'C:/x' }, true);
  assert.equal(s.visible, true);
  assert.equal(s.disabled, true);
});

test('done with error -> visible but disabled', () => {
  const s = computeOpenFolderButtonState({ done: true, error: 'boom', success_count: 1, output_dir: 'C:/x' }, false);
  assert.equal(s.visible, true);
  assert.equal(s.disabled, true);
});

test('done with zero success -> disabled', () => {
  const s = computeOpenFolderButtonState({ done: true, success_count: 0, output_dir: 'C:/x' }, false);
  assert.equal(s.visible, true);
  assert.equal(s.disabled, true);
});

test('done with missing output_dir -> disabled', () => {
  const s = computeOpenFolderButtonState({ done: true, success_count: 2, output_dir: '' }, false);
  assert.equal(s.visible, true);
  assert.equal(s.disabled, true);
});

test('done with output_dir_ok false -> disabled with reason', () => {
  const s = computeOpenFolderButtonState({ done: true, success_count: 2, output_dir: 'C:/x', output_dir_ok: false, output_dir_error: 'nope' }, false);
  assert.equal(s.visible, true);
  assert.equal(s.disabled, true);
  assert.match(String(s.title), /nope/);
});

test('done success and accessible -> enabled', () => {
  const s = computeOpenFolderButtonState({ done: true, success_count: 2, output_dir: 'C:/x', output_dir_ok: true }, false);
  assert.equal(s.visible, true);
  assert.equal(s.disabled, false);
});

