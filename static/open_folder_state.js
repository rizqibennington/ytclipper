(function (root) {
  const computeOpenFolderButtonState = (jobStatus, uiBusy) => {
    const js = jobStatus || null;
    const busy = !!uiBusy;

    if (!js || !js.done) {
      return { visible: false, disabled: true, title: 'Buka folder output (hasil clip).' };
    }

    if (busy) {
      return { visible: true, disabled: true, title: 'Tunggu sebentar, masih ada proses yang berjalan.' };
    }

    if (js.error) {
      return { visible: true, disabled: true, title: 'Proses gagal, tidak ada folder output yang bisa dibuka.' };
    }

    if (!js.success_count || js.success_count <= 0) {
      return { visible: true, disabled: true, title: 'Tidak ada clip yang berhasil dibuat.' };
    }

    if (!js.output_dir) {
      return { visible: true, disabled: true, title: 'Output folder tidak tersedia.' };
    }

    if (js.output_dir_ok === false) {
      return { visible: true, disabled: true, title: js.output_dir_error ? String(js.output_dir_error) : 'Folder output tidak bisa diakses.' };
    }

    return { visible: true, disabled: false, title: 'Buka folder output (hasil clip).' };
  };

  try {
    root.__ytclipper_computeOpenFolderButtonState = computeOpenFolderButtonState;
  } catch {}

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { computeOpenFolderButtonState };
  }
})(typeof window !== 'undefined' ? window : globalThis);

