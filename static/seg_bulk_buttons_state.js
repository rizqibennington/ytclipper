(function (root) {
  const computeSegBulkButtonsState = (segments) => {
    const list = Array.isArray(segments) ? segments : [];
    const totalCount = list.length;
    let enabledCount = 0;
    for (let i = 0; i < list.length; i += 1) {
      const s = list[i];
      if (s && s.enabled) enabledCount += 1;
    }

    return {
      totalCount,
      enabledCount,
      selectAllDisabled: totalCount === 0 || enabledCount === totalCount,
      deselectAllDisabled: totalCount === 0 || enabledCount === 0,
    };
  };

  try {
    root.__ytclipper_computeSegBulkButtonsState = computeSegBulkButtonsState;
  } catch {}

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { computeSegBulkButtonsState };
  }
})(typeof window !== 'undefined' ? window : globalThis);

