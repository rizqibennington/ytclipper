const $ = (id) => document.getElementById(id);
const DEFAULT_OUTDIR = window.__YTCLIPPER_DEFAULT_OUTDIR__ || '';
const fmt = (sec) => {
  sec = Math.max(0, Math.floor(sec || 0));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
  return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
};

const parseTime = (raw) => {
  const s = String(raw || '').trim();
  if (!s) return null;
  if (/^\d+$/.test(s)) return parseInt(s, 10);
  const parts = s.split(':').map((x) => x.trim());
  if (parts.some((p) => p === '' || !/^\d+$/.test(p))) return null;
  if (parts.length === 2) {
    const mm = parseInt(parts[0], 10);
    const ss = parseInt(parts[1], 10);
    return mm * 60 + ss;
  }
  if (parts.length === 3) {
    const hh = parseInt(parts[0], 10);
    const mm = parseInt(parts[1], 10);
    const ss = parseInt(parts[2], 10);
    return hh * 3600 + mm * 60 + ss;
  }
  return null;
};

const syncRangeFill = (el) => {
  if (!el) return;
  const min = parseFloat(el.min || '0');
  const max = parseFloat(el.max || '0');
  const val = parseFloat(el.value || '0');
  const denom = max - min;
  const pct = denom > 0 ? ((val - min) / denom) * 100 : 0;
  el.style.setProperty('--pct', String(Math.max(0, Math.min(100, pct))) + '%');
};

let durationSec = 0;
let segments = [];
let jobId = null;
let pollTimer = null;
let player = null;
let playerReady = false;
let previewStopAt = null;
let activeSegIdx = null;
let currentVideoId = null;

let segPlayer = null;
let segStart = 0;
let segEnd = 0;

let busyCount = 0;
let busyJob = false;

let lastJobStatus = null;

let openFolderDesiredState = { visible: false, disabled: true, title: 'Buka folder output (hasil clip).' };

const getOpenFolderButtonState = (jobStatus, uiBusy) => {
  try {
    const fn = window.__ytclipper_computeOpenFolderButtonState;
    if (typeof fn === 'function') return fn(jobStatus, uiBusy);
  } catch {}

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

const applyOpenFolderDesiredState = () => {
  const btn = $('openFolder');
  if (!btn) return;
  btn.style.display = openFolderDesiredState.visible ? 'inline-flex' : 'none';
  btn.disabled = !!openFolderDesiredState.disabled;
  if (openFolderDesiredState.title) btn.title = String(openFolderDesiredState.title);
};

const setOpenFolderState = (patch) => {
  openFolderDesiredState = { ...openFolderDesiredState, ...(patch || {}) };
  applyOpenFolderDesiredState();
};

const syncOpenFolderButton = () => {
  const uiBusy = busyCount > 0 || !!busyJob;
  const state = getOpenFolderButtonState(lastJobStatus, uiBusy);
  setOpenFolderState(state);
  return state;
};

const getSegBulkButtonsState = (segs) => {
  try {
    const fn = window.__ytclipper_computeSegBulkButtonsState;
    if (typeof fn === 'function') return fn(segs);
  } catch {}

  const list = Array.isArray(segs) ? segs : [];
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

const syncSegBulkButtons = () => {
  const state = getSegBulkButtonsState(segments);
  const pickInfo = $('segPickInfo');
  if (pickInfo) pickInfo.textContent = state.totalCount ? `Dipilih ${state.enabledCount} / ${state.totalCount}` : '';
  const selAllBtn = $('segSelectAll');
  const deselAllBtn = $('segDeselectAll');
  if (selAllBtn) selAllBtn.disabled = state.selectAllDisabled;
  if (deselAllBtn) deselAllBtn.disabled = state.deselectAllDisabled;
  return state;
};

const setUiDisabled = (on) => {
  document.querySelectorAll('button, input, select, textarea').forEach((el) => {
    if (el.closest('#busy')) return;
    if (on) {
      if (el.dataset.prevDisabled === undefined) el.dataset.prevDisabled = el.disabled ? '1' : '0';
      el.disabled = true;
      return;
    }
    if (el.dataset.prevDisabled !== undefined) {
      el.disabled = el.dataset.prevDisabled === '1';
      delete el.dataset.prevDisabled;
    }
  });
};

const setBusyText = (title, msg) => {
  const t = $('busyTitle');
  const m = $('busyMsg');
  if (t && title) t.textContent = title;
  if (m && msg !== undefined && msg !== null) m.textContent = String(msg);
};

const updateBusyState = () => {
  const on = busyCount > 0 || !!busyJob;
  const el = $('busy');
  if (!el) return;
  if (on) el.classList.add('on');
  else el.classList.remove('on');
  setUiDisabled(on);
  if (!on) syncSegBulkButtons();
  if (!on) applyOpenFolderDesiredState();
};

const beginBusy = (title, msg) => {
  busyCount += 1;
  setBusyText(title || 'Loading', msg ?? 'Mohon tunggu...');
  updateBusyState();
};

const endBusy = () => {
  busyCount = Math.max(0, busyCount - 1);
  updateBusyState();
};

const runWithBusy = async (title, msg, fn) => {
  beginBusy(title, msg);
  try {
    return await fn();
  } finally {
    endBusy();
  }
};

const setBusyJob = (on, title, msg) => {
  busyJob = !!on;
  if (busyJob) setBusyText(title || 'Memproses...', msg ?? 'Mohon tunggu...');
  updateBusyState();
};

const setOpenFolderVisible = (on) => {
  setOpenFolderState({ visible: !!on, disabled: !on, title: 'Buka folder output (hasil clip).' });
};

const setHeatmapLoading = (on) => {
  const btn = $('loadHeatmap');
  const spin = $('heatmapSpin');
  const txt = $('heatmapText');
  if (btn) btn.disabled = !!on;
  if (spin) spin.style.display = on ? 'inline-block' : 'none';
  if (txt) txt.textContent = on ? 'Loading...' : 'Load Heatmap';
};

const qs = new URLSearchParams(window.location.search || '');
const heatmapDebug = qs.get('heatmap_debug') === '1' || localStorage.getItem('ytclipper_heatmap_debug') === '1';

const cfgKey = 'ytclipper_web_cfg_v1';
const loadLocalCfg = () => {
  try {
    return JSON.parse(localStorage.getItem(cfgKey) || '{}') || {};
  } catch {
    return {};
  }
};
const saveLocalCfg = (obj) => {
  try {
    localStorage.setItem(cfgKey, JSON.stringify(obj || {}));
  } catch {}
};

const isGeminiSuggestionsOn = () => {
  const el = $('geminiOn');
  if (!el) return false;
  const v = String(el.value || '').trim().toLowerCase();
  return v === 'yes' || v === 'ya' || v === 'on' || v === 'true' || v === '1';
};

let geminiKeyStoredOnServer = false;

const syncGeminiHint = () => {
  const hint = $('geminiKeyHint');
  if (!hint) return;

  const input = $('geminiKey');
  const hasLocalKey = !!(input && String(input.value || '').trim());
  if (hasLocalKey) {
    hint.textContent = '';
    return;
  }

  if (geminiKeyStoredOnServer) {
    hint.textContent = !isGeminiSuggestionsOn() ? 'API key tersimpan, tapi generate AI sedang OFF.' : 'API key sudah tersimpan di server. Isi lagi hanya kalau mau ganti.';
    return;
  }

  hint.textContent = '';
};

const applyCfg = (cfg) => {
  if (cfg.output_mode) document.querySelectorAll('input[name="outMode"]').forEach((r) => (r.checked = r.value === cfg.output_mode));
  if (cfg.output_dir) $('outDir').value = cfg.output_dir;
  if (cfg.crop_mode) $('crop').value = cfg.crop_mode;
  if (cfg.crop_preview !== undefined && $('cropPrev')) $('cropPrev').checked = !!cfg.crop_preview;
  if (cfg.use_subtitle !== undefined) $('subOn').checked = !!cfg.use_subtitle;
  if (cfg.use_gemini_suggestions !== undefined && $('geminiOn')) $('geminiOn').value = cfg.use_gemini_suggestions ? 'yes' : 'no';
  if (cfg.whisper_model) $('model').value = cfg.whisper_model;
  if (cfg.subtitle_language && $('subLang')) $('subLang').value = cfg.subtitle_language;
  if (cfg.subtitle_position) $('subPos').value = cfg.subtitle_position;
  if (cfg.preview_seconds) $('previewSecs').value = cfg.preview_seconds;
  geminiKeyStoredOnServer = !!cfg.has_gemini_key;
  if (cfg.has_gemini_key && $('geminiKey') && !$('geminiKey').value) {
    $('geminiKey').placeholder = 'Tersimpan di server';
  }
  syncGeminiHint();
  syncOutMode();
  syncSub();
  updateCropPreview();
};

const collectCfgLocal = () => ({
  output_mode: document.querySelector('input[name="outMode"]:checked')?.value || 'default',
  output_dir: $('outDir').value.trim(),
  crop_mode: $('crop').value,
  crop_preview: $('cropPrev') ? $('cropPrev').checked : true,
  use_subtitle: $('subOn').checked,
  use_gemini_suggestions: isGeminiSuggestionsOn(),
  whisper_model: $('model').value,
  subtitle_language: $('subLang') ? $('subLang').value : 'id',
  subtitle_position: $('subPos').value,
  preview_seconds: parseInt($('previewSecs').value || '30', 10),
});

const collectCfgServer = () => ({
  ...collectCfgLocal(),
  ...(($('geminiKey').value.trim() ? { gemini_api_key: $('geminiKey').value.trim() } : {})),
});

const persistCfg = async () => {
  const cfgLocal = collectCfgLocal();
  saveLocalCfg(cfgLocal);
  try {
    const cfgServer = collectCfgServer();
    await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cfgServer) });
  } catch {}
};

const syncOutMode = () => {
  const mode = document.querySelector('input[name="outMode"]:checked')?.value || 'default';
  $('outDir').disabled = mode === 'default';
  if (mode === 'default') $('outDir').placeholder = 'Default: ~/Videos/ClipAI';
};

const syncSub = () => {
  $('model').disabled = !$('subOn').checked;
  if ($('subLang')) $('subLang').disabled = !$('subOn').checked;
  $('subPos').disabled = !$('subOn').checked;
};

const updateCropPreview = () => {
  const mode = ($('crop')?.value || 'default').trim();
  const on = $('cropPrev') ? !!$('cropPrev').checked : true;

  const els = [$('mainCropOverlay'), $('segCropOverlay')].filter(Boolean);
  els.forEach((el) => {
    el.classList.toggle('on', on);
    if (!on) return;
    const w = 31.640625;
    const xC = (100 - w) / 2;
    const topH = 75;
    const bottomY = topH;
    const bottomH = 25;
    const bottomX = mode === 'split_right' ? 100 - w : 0;
    const shade = 'rgba(0,0,0,0.45)';
    const stroke = 'rgba(72,208,255,0.92)';
    const stroke2 = 'rgba(72,208,255,0.55)';
    const sw = 0.85;

    let holes = '';
    let frames = '';
    if (mode === 'fit') {
      holes = 'M0 0H100V100H0Z';
      frames = `<rect x="0" y="0" width="100" height="100" fill="none" stroke="${stroke}" stroke-width="${sw}" />`;
    } else if (mode === 'split_left' || mode === 'split_right') {
      holes = `M${xC} 0H${xC + w}V${topH}H${xC}Z M${bottomX} ${bottomY}H${bottomX + w}V100H${bottomX}Z`;
      frames = `
            <rect x="${xC}" y="0" width="${w}" height="${topH}" fill="none" stroke="${stroke}" stroke-width="${sw}" />
            <rect x="${bottomX}" y="${bottomY}" width="${w}" height="${bottomH}" fill="none" stroke="${stroke}" stroke-width="${sw}" />
            <line x1="0" y1="${bottomY}" x2="100" y2="${bottomY}" stroke="${stroke2}" stroke-width="${sw}" stroke-dasharray="3 2" />
          `;
    } else {
      holes = `M${xC} 0H${xC + w}V100H${xC}Z`;
      frames = `<rect x="${xC}" y="0" width="${w}" height="100" fill="none" stroke="${stroke}" stroke-width="${sw}" />`;
    }

    el.innerHTML = `
          <path d="M0 0H100V100H0Z ${holes}" fill="${shade}" fill-rule="evenodd" />
          ${frames}
        `;
  });
};

const ensureYTApi = (() => {
  let p = null;
  return () => {
    if (window.YT && window.YT.Player) return Promise.resolve();
    if (p) return p;
    p = new Promise((resolve) => {
      const tag = document.createElement('script');
      tag.src = 'https://www.youtube.com/iframe_api';
      document.head.appendChild(tag);
      const t = setInterval(() => {
        if (window.YT && window.YT.Player) {
          clearInterval(t);
          resolve();
        }
      }, 80);
    });
    return p;
  };
})();

const renderSegs = () => {
  const tbody = $('segTable').querySelector('tbody');
  tbody.innerHTML = '';
  segments.forEach((s, idx) => {
    const tr = document.createElement('tr');
    if (activeSegIdx === idx) tr.classList.add('activeSeg');
    const dur = Math.max(0, (s.end | 0) - (s.start | 0));
    const score = s.score === undefined || s.score === null ? '-' : Number(s.score).toFixed(2);
    tr.innerHTML = `
          <td><input type="checkbox" ${s.enabled ? 'checked' : ''} data-idx="${idx}" class="segOn" /></td>
          <td>${fmt(s.start)}</td>
          <td>${fmt(s.end)}</td>
          <td>${fmt(dur)}</td>
          <td>${score}</td>
          <td>
            <button class="btn segPrev" data-idx="${idx}" title="Preview segmen (modal).">Preview</button>
            <button class="btn danger segDel" data-idx="${idx}" title="Hapus segmen ini.">Del</button>
          </td>
        `;
    tbody.appendChild(tr);
  });
  syncSegBulkButtons();
  if (activeSegIdx !== null && segments[activeSegIdx] && $('segEnabled')) {
    $('segEnabled').checked = !!segments[activeSegIdx].enabled;
  }
  tbody.querySelectorAll('.segOn').forEach((cb) =>
    cb.addEventListener('change', (e) => {
      const i = parseInt(e.target.dataset.idx, 10);
      segments[i].enabled = !!e.target.checked;
      syncSegBulkButtons();
      persistCfg();
    }),
  );
  tbody.querySelectorAll('.segPrev').forEach((btn) =>
    btn.addEventListener('click', (e) => {
      const i = parseInt(e.target.dataset.idx, 10);
      openSegPreview(i);
    }),
  );
  tbody.querySelectorAll('.segDel').forEach((btn) =>
    btn.addEventListener('click', (e) => {
      const i = parseInt(e.target.dataset.idx, 10);
      segments.splice(i, 1);
      renderSegs();
    }),
  );
};

const openSegModal = () => {
  $('segModal').classList.add('on');
};
const closeSegModal = () => {
  $('segModal').classList.remove('on');
};

const destroySegPlayer = () => {
  try {
    if (segPlayer && segPlayer.destroy) segPlayer.destroy();
  } catch {}
  segPlayer = null;
  const holder = $('segPlayer');
  if (holder) holder.innerHTML = '';
  segStart = 0;
  segEnd = 0;
};

const openSegPreview = async (idx) => {
  const s = segments[idx];
  if (!s) return;
  await runWithBusy('Menyiapkan preview...', 'Memuat player segmen...', async () => {
    if (!currentVideoId) {
      try {
        await loadInfo();
      } catch (e) {
        alert(e.message);
        return;
      }
    }

    const start = Math.max(0, parseInt(s.start || 0, 10));
    const end = Math.max(0, parseInt(s.end || 0, 10));
    if (end <= start) {
      alert('Segmen tidak valid (end <= start).');
      return;
    }

    activeSegIdx = idx;
    renderSegs();

    $('segEnabled').checked = !!s.enabled;
    $('segMeta').textContent = `Segmen #${idx + 1} • ${fmt(start)} - ${fmt(end)} • Dur ${fmt(end - start)} • Score ${s.score === undefined ? '-' : Number(s.score).toFixed(2)}`;

    segStart = start;
    segEnd = end;
    $('segEditStart').value = fmt(start);
    $('segEditEnd').value = fmt(end);
    setDurMeter($('durMeterSeg'), start, end);

    destroySegPlayer();
    openSegModal();

    await ensureYTApi();
    segPlayer = new YT.Player('segPlayer', {
      height: '100%',
      width: '100%',
      videoId: currentVideoId,
      playerVars: { controls: 1, rel: 0, modestbranding: 1, fs: 1, start: start, end: end },
      events: {
        onReady: (e) => {
          try {
            e.target.setPlaybackQuality('large');
          } catch {}
          try {
            e.target.seekTo(start, true);
          } catch {}
        },
      },
    });
  });
};

const applySegEdit = async () => {
  if (activeSegIdx === null) return;
  const s = segments[activeSegIdx];
  if (!s) return;

  const rawStart = $('segEditStart').value;
  const rawEnd = $('segEditEnd').value;
  const start = parseTime(rawStart);
  const end = parseTime(rawEnd);

  if (start === null || end === null) {
    alert('Format Start/End tidak valid. Pakai detik (123) atau MM:SS atau HH:MM:SS.');
    return;
  }
  if (start < 0 || end < 0) {
    alert('Durasi tidak boleh negatif.');
    return;
  }
  if (durationSec > 0 && (start > durationSec || end > durationSec)) {
    alert('Start/End melebihi durasi video.');
    return;
  }
  if (end <= start) {
    alert('End harus lebih besar dari Start.');
    return;
  }

  const capped = enforceMaxDur(start, end, 'edit segmen');
  const end2 = capped.changed ? capped.end : end;
  if (capped.changed) {
    $('segEditEnd').value = fmt(end2);
    alert('Durasi klip dibatasi maksimal 02:59. End otomatis dipotong di 179 detik dari start.');
  }

  s.start = start;
  s.end = end2;
  segments[activeSegIdx] = s;
  renderSegs();
  persistCfg();
  try {
    await openSegPreview(activeSegIdx);
  } catch (e) {
    alert(e && e.message ? e.message : 'Gagal menerapkan perubahan segmen.');
  }
};

const validateUrl = () => {
  const u = $('url').value.trim();
  if (!u) throw new Error('YouTube URL wajib diisi.');
  return u;
};

const validateOutDir = () => {
  const mode = document.querySelector('input[name="outMode"]:checked')?.value || 'default';
  if (mode === 'default') return null;
  const p = $('outDir').value.trim();
  if (!p) throw new Error('Output folder custom tidak boleh kosong.');
  return p;
};

const validateSegments = () => {
  const segs = segments.filter((s) => s.enabled);
  if (!segs.length) throw new Error('Minimal 1 segmen harus aktif.');
  for (const s of segs) {
    if (s.start < 0 || s.end < 0) throw new Error('Durasi tidak boleh negatif.');
    if (s.end <= s.start) throw new Error('End harus lebih besar dari Start.');
    if (s.end - s.start > MAX_CLIP_S) throw new Error('Durasi klip maksimal 02:59 (179 detik).');
  }
  return segs;
};

const fillSummary = () => {
  const segs = validateSegments();
  const outMode = document.querySelector('input[name="outMode"]:checked')?.value || 'default';
  const outDir = outMode === 'default' ? DEFAULT_OUTDIR : $('outDir').value.trim();
  const crop = $('crop').value;
  const subOn = $('subOn').checked;
  const model = $('model').value;
  let totalSec = 0;
  for (const s of segs) totalSec += Math.max(0, (s.end | 0) - (s.start | 0));
  const estMB = (totalSec * 2600000 / 8) / (1024 * 1024);
  const root = $('summary');
  while (root.firstChild) root.removeChild(root.firstChild);

  const top = document.createElement('div');
  top.className = 'summaryTop';

  const mkKv = (k, v) => {
    const box = document.createElement('div');
    box.className = 'summaryKv';
    const kk = document.createElement('div');
    kk.className = 'summaryK';
    kk.textContent = k;
    const vv = document.createElement('div');
    vv.className = 'summaryV';
    vv.textContent = v;
    box.appendChild(kk);
    box.appendChild(vv);
    return box;
  };

  top.appendChild(mkKv('Lokasi output', outDir || '-'));
  top.appendChild(mkKv('Crop mode', crop || '-'));
  top.appendChild(mkKv('Subtitle', subOn ? 'ON • Model: ' + model : 'OFF'));
  top.appendChild(mkKv('Total', segs.length + ' klip • ' + fmt(totalSec)));
  root.appendChild(top);

  const h = document.createElement('div');
  h.className = 'summaryH';
  const ht = document.createElement('div');
  ht.className = 't';
  ht.textContent = 'Daftar klip';
  const hs = document.createElement('div');
  hs.className = 's';
  hs.textContent = 'Format: Start–End (Durasi)';
  h.appendChild(ht);
  h.appendChild(hs);
  root.appendChild(h);

  const table = document.createElement('table');
  table.className = 'summaryTable';
  const thead = document.createElement('thead');
  const hr = document.createElement('tr');
  ['#', 'Start', 'End', 'Durasi'].forEach((txt) => {
    const th = document.createElement('th');
    th.textContent = txt;
    hr.appendChild(th);
  });
  thead.appendChild(hr);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  segs.forEach((s, i) => {
    const tr = document.createElement('tr');
    const dur = Math.max(0, (s.end | 0) - (s.start | 0));
    const cells = [String(i + 1), fmt(s.start), fmt(s.end), fmt(dur)];
    cells.forEach((txt) => {
      const td = document.createElement('td');
      td.textContent = txt;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  root.appendChild(table);

  const foot = document.createElement('div');
  foot.className = 'summaryFoot';
  const left = document.createElement('div');
  left.textContent = 'Estimasi ukuran total (kasar)';
  const right = document.createElement('div');
  right.className = 'summaryV';
  right.textContent = estMB.toFixed(1) + ' MB';
  foot.appendChild(left);
  foot.appendChild(right);
  root.appendChild(foot);
};

const setLog = (text) => {
  $('log').textContent = text || '';
  $('log').scrollTop = $('log').scrollHeight;
};

const appendLog = (line) => {
  if (!line) return;
  const el = $('log');
  if (!el) return;
  el.textContent = (el.textContent ? el.textContent + '\n' : '') + String(line);
  el.scrollTop = el.scrollHeight;
};

const MAX_CLIP_S = 179;
const DUR_NEAR_S = 170;
const DUR_WARN_S = 175;
const DUR_MAX_S = 179;

let _beepCtx = null;
let _lastBeepTs = 0;
const beep = async () => {
  const now = Date.now();
  if (now - _lastBeepTs < 1200) return;
  _lastBeepTs = now;
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    if (!_beepCtx) _beepCtx = new AC();
    try {
      if (_beepCtx.state === 'suspended') await _beepCtx.resume();
    } catch {}

    const o = _beepCtx.createOscillator();
    const g = _beepCtx.createGain();
    o.type = 'sine';
    o.frequency.value = 880;
    g.gain.value = 0.0001;
    o.connect(g);
    g.connect(_beepCtx.destination);

    const t0 = _beepCtx.currentTime;
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(0.12, t0 + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.12);
    o.start(t0);
    o.stop(t0 + 0.14);
  } catch {}
};

const setDurMeter = (el, start, end) => {
  if (!el) return;
  el.classList.remove('near', 'warn', 'max');
  if (start === null || end === null || end <= start) {
    el.style.setProperty('--pct', '0%');
    el.textContent = 'Durasi: - / 02:59';
    return;
  }
  const dur = Math.max(0, Math.floor(end - start));
  const pct = Math.max(0, Math.min(100, (dur / MAX_CLIP_S) * 100));
  el.style.setProperty('--pct', pct.toFixed(1) + '%');
  el.textContent = `Durasi: ${fmt(dur)} / 02:59`;
  if (dur >= DUR_MAX_S) el.classList.add('max');
  else if (dur >= DUR_WARN_S) el.classList.add('warn');
  else if (dur >= DUR_NEAR_S) el.classList.add('near');
};

const enforceMaxDur = (start, end, label) => {
  if (start === null || end === null) return { start, end, changed: false };
  if (end <= start) return { start, end, changed: false };
  const dur = end - start;
  if (dur <= MAX_CLIP_S) return { start, end, changed: false };
  const newEnd = start + MAX_CLIP_S;
  appendLog(`[durasi] ${label || 'segmen'} melebihi 02:59, auto-trim end ke ${fmt(newEnd)}`);
  beep();
  return { start, end: newEnd, changed: true };
};

const enforceAllSegments = (label) => {
  let changed = 0;
  for (const s of segments || []) {
    if (!s || !s.enabled) continue;
    const st = Number(s.start);
    const en = Number(s.end);
    if (!Number.isFinite(st) || !Number.isFinite(en)) continue;
    if (en <= st) continue;
    const capped = enforceMaxDur(st, en, label || 'segmen');
    if (capped.changed) {
      s.end = capped.end;
      changed++;
    }
  }
  return changed;
};

const setProgress = (p, status, eta, isActive = true) => {
  const pct = Math.max(0, Math.min(100, p || 0));
  const bar = $('bar');
  bar.style.width = pct.toFixed(1) + '%';
  $('status').textContent = (status || '') + ' (' + pct.toFixed(0) + '%)';
  $('eta').textContent = eta ? 'ETA ~ ' + eta : '';
  if (isActive && pct < 100) {
    bar.classList.add('active');
  } else {
    bar.classList.remove('active');
  }
};

const poll = async () => {
  if (!jobId) return;
  try {
    const res = await fetch('/api/status/' + jobId);
    const data = await res.json();
    if (!data.ok) return;
    lastJobStatus = data;
    const isRunning = data.running && !data.done;
    setProgress(data.percent, data.status, data.eta, isRunning);
    if (busyJob && isRunning) {
      const pct = Math.max(0, Math.min(100, Number(data.percent || 0)));
      const st = (data.status || '').trim();
      setBusyText('Sedang memproses...', (st ? st + ' • ' : '') + pct.toFixed(0) + '%');
    }
    let logText = data.logs || '';
    if (data.error) {
      logText += '\n\n❌ ERROR: ' + data.error;
    }

    if (logText && logText.includes('__AI_JSON__')) {
      const parts = logText.split('__AI_JSON__');
      let cleanLog = parts[0];
      for (let i = 1; i < parts.length; i++) {
        try {
          const lineEnd = parts[i].indexOf('\n');
          const jsonStr = lineEnd === -1 ? parts[i] : parts[i].substring(0, lineEnd);
          const rest = lineEnd === -1 ? '' : parts[i].substring(lineEnd);

          const meta = JSON.parse(jsonStr);
          const titles = (meta.titles || []).map((t) => '• ' + t).join('\n');
          const tags = (meta.hashtags || []).join(' ');

          cleanLog +=
            '\n\n✨ AI SUGGESTION:\n' +
            '----------------------------------------\n' +
            'JUDUL:\n' +
            titles +
            '\n\n' +
            'CAPTION:\n' +
            (meta.caption || '-') +
            '\n\n' +
            'HASHTAGS:\n' +
            tags +
            '\n' +
            '----------------------------------------\n';
          cleanLog += rest;
        } catch (e) {
          cleanLog += parts[i];
        }
      }
      logText = cleanLog;
    }

    setLog(logText);
    syncOpenFolderButton();
    if (data.done) {
      clearInterval(pollTimer);
      pollTimer = null;
      setBusyJob(false);
      syncOpenFolderButton();
      if (data.error) {
        alert('❌ Proses gagal!\n\n' + data.error);
      } else if (data.success_count > 0) {
        alert('✅ Selesai! ' + data.success_count + ' clip berhasil dibuat.\n\nOutput: ' + (data.output_dir || ''));
      }
    }
  } catch {}
};

const startJob = async () => {
  const url = validateUrl();
  const segs = validateSegments();
  const outMode = document.querySelector('input[name="outMode"]:checked')?.value || 'default';
  const outDir = outMode === 'default' ? null : validateOutDir();
  const useGemini = isGeminiSuggestionsOn();
  const payload = {
    url,
    segments: segs,
    crop_mode: $('crop').value,
    use_subtitle: $('subOn').checked,
    whisper_model: $('model').value,
    subtitle_language: $('subLang') ? $('subLang').value : 'id',
    subtitle_position: $('subPos').value,
    output_dir: outDir,
    use_gemini_suggestions: useGemini,
    gemini_api_key: useGemini ? $('geminiKey').value.trim() : null,
  };
  lastJobStatus = null;
  setOpenFolderState({ visible: false, disabled: true, title: 'Tombol ini aktif setelah proses selesai.' });
  setLog('🚀 Memulai proses...');
  setProgress(0, 'Memulai...', '', true);
  setBusyJob(true, 'Memproses clip...', 'Memulai...');
  const res = await fetch('/api/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const data = await res.json();
  if (!data.ok) {
    setBusyJob(false);
    throw new Error(data.error || 'Gagal start job');
  }
  jobId = data.job_id;
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(poll, 700);
  await poll();
};

const applyVideoInfo = (data) => {
  durationSec = data.duration_seconds | 0;
  currentVideoId = data.video_id;
  $('timeline').max = String(durationSec);
  $('tDur').textContent = fmt(durationSec);
  $('info').textContent = 'Durasi: ' + fmt(durationSec);
  $('sStart').value = '0';
  $('sEnd').value = String(Math.min(30, durationSec));
  loadPlayer(data.video_id);
  syncRangeFill($('timeline'));
};

const loadInfo = async () => {
  return await runWithBusy('Memuat info video...', 'Mengambil durasi & video ID...', async () => {
    const url = validateUrl();
    const res = await fetch('/api/video_info', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || 'Gagal load info');
    applyVideoInfo(data);
    persistCfg();
  });
};

const waitMainPlayer = async () => {
  for (let i = 0; i < 50; i++) {
    if (player && player.getCurrentTime && player.getPlayerState) return true;
    await new Promise((r) => setTimeout(r, 80));
  }
  return false;
};

const loadHeatmap = async () => {
  const url = validateUrl();

  const tAll0 = performance.now();

  const tInfo0 = performance.now();
  const infoRes = await fetch('/api/video_info', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) });
  const infoData = await infoRes.json();
  if (!infoData.ok) throw new Error(infoData.error || 'Gagal load info');
  const tInfoMs = performance.now() - tInfo0;

  const nextVideoId = infoData.video_id;
  const shouldSwitchVideo = !currentVideoId || String(currentVideoId) !== String(nextVideoId);
  if (shouldSwitchVideo) {
    segments = [];
    activeSegIdx = null;
    renderSegs();
  }
  applyVideoInfo(infoData);
  persistCfg();

  let heatmapErr = null;
  try {
    const tHm0 = performance.now();
    const res = await fetch('/api/heatmap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, duration_seconds: infoData.duration_seconds, debug: heatmapDebug }),
    });
    const data = await res.json();
    const tHmMs = performance.now() - tHm0;
    if (!data.ok) throw new Error(data.error || 'Gagal load heatmap');
    segments = data.segments || [];
    enforceAllSegments('heatmap');
    if (!segments.length) throw new Error('Heatmap kosong: video ini tidak punya Most Replayed, atau parsing gagal.');
    segments.sort((a, b) => Number(b.score ?? 0) - Number(a.score ?? 0) || (a.start | 0) - (b.start | 0) || (a.end | 0) - (b.end | 0));
    activeSegIdx = null;
    const tRender0 = performance.now();
    renderSegs();
    const tRenderMs = performance.now() - tRender0;
    if (heatmapDebug) {
      appendLog(`[heatmap] video_info ${tInfoMs.toFixed(0)}ms`);
      appendLog(`[heatmap] /api/heatmap ${tHmMs.toFixed(0)}ms • render ${tRenderMs.toFixed(0)}ms • seg ${segments.length}`);
      if (data._meta) appendLog(`[heatmap] meta ${JSON.stringify(data._meta)}`);
      appendLog(`[heatmap] total ${(performance.now() - tAll0).toFixed(0)}ms`);
    }
    return;
  } catch (e) {
    heatmapErr = e;
  }

  const txt = $('heatmapText');
  if (txt) txt.textContent = 'Loading (backup AI)...';

  try {
    const res = await fetch('/api/ai_segments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, duration_seconds: infoData.duration_seconds, whisper_model: $('model').value, language: ($('subLang') ? $('subLang').value : 'id') }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || 'Gagal generate AI segments');
    segments = data.segments || [];
    enforceAllSegments('AI');
    if (!segments.length) throw new Error('AI segments kosong: transcript tidak cukup jelas, atau analisis gagal.');
    segments.sort((a, b) => Number(b.score ?? 0) - Number(a.score ?? 0) || (a.start | 0) - (b.start | 0) || (a.end | 0) - (b.end | 0));
    activeSegIdx = null;
    renderSegs();
  } catch (aiErr) {
    const hmsg = heatmapErr && heatmapErr.message ? heatmapErr.message : 'Gagal load heatmap';
    const amsg = aiErr && aiErr.message ? aiErr.message : 'Gagal backup AI';
    throw new Error(hmsg + '\n\nBackup AI juga gagal:\n' + amsg);
  }
};

const addSeg = () => {
  const s = parseInt(($('sStart').value || '0'), 10);
  const e = parseInt(($('sEnd').value || '0'), 10);
  if (Number.isNaN(s) || Number.isNaN(e)) throw new Error('Start/End harus angka.');
  if (s < 0 || e < 0) throw new Error('Durasi tidak boleh negatif.');
  if (e <= s) throw new Error('End harus lebih besar dari Start.');
  if (durationSec > 0 && e > durationSec) throw new Error('End melebihi durasi video.');

  const capped = enforceMaxDur(s, e, 'manual');
  const end2 = capped.changed ? capped.end : e;
  if (capped.changed) {
    $('sEnd').value = String(end2);
    alert('Durasi klip dibatasi maksimal 02:59. End otomatis dipotong di 179 detik dari start.');
  }

  segments.push({ enabled: true, start: s, end: end2 });
  segments.sort((a, b) => a.start - b.start || a.end - b.end);
  renderSegs();
};

const openModal = () => {
  $('modal').classList.add('on');
};
const closeModal = () => {
  $('modal').classList.remove('on');
};

document.querySelectorAll('input[name="outMode"]').forEach((r) => r.addEventListener('change', () => {
  syncOutMode();
  persistCfg();
}));
$('outDir').addEventListener('change', persistCfg);
$('crop').addEventListener('change', () => {
  updateCropPreview();
  persistCfg();
});
if ($('cropPrev')) $('cropPrev').addEventListener('change', () => {
  updateCropPreview();
  persistCfg();
});
$('subOn').addEventListener('change', () => {
  syncSub();
  persistCfg();
});
$('model').addEventListener('change', persistCfg);
$('previewSecs').addEventListener('change', persistCfg);
$('geminiKey').addEventListener('change', () => {
  syncGeminiHint();
  persistCfg();
});
if ($('geminiOn'))
  $('geminiOn').addEventListener('change', () => {
    syncGeminiHint();
    persistCfg();
  });

const updateManualDur = (clamp = false) => {
  const st = parseInt(($('sStart').value || '').trim(), 10);
  const en = parseInt(($('sEnd').value || '').trim(), 10);
  const start = Number.isFinite(st) ? st : null;
  const end0 = Number.isFinite(en) ? en : null;
  let end = end0;
  if (clamp && start !== null && end !== null && end > start) {
    const capped = enforceMaxDur(start, end, 'manual');
    if (capped.changed) {
      end = capped.end;
      $('sEnd').value = String(end);
    }
  }
  setDurMeter($('durMeterManual'), start, end);
  if (start !== null && end !== null && end > start) {
    const dur = Math.floor(end - start);
    if (dur >= DUR_WARN_S && dur < DUR_MAX_S) beep();
  }
};

const updateSegEditDur = (clamp = false) => {
  const start0 = parseTime($('segEditStart').value);
  const end0 = parseTime($('segEditEnd').value);
  let start = start0;
  let end = end0;
  if (clamp && start !== null && end !== null && end > start) {
    const capped = enforceMaxDur(start, end, 'edit segmen');
    if (capped.changed) {
      end = capped.end;
      $('segEditEnd').value = fmt(end);
    }
  }
  setDurMeter($('durMeterSeg'), start, end);
  if (start !== null && end !== null && end > start) {
    const dur = Math.floor(end - start);
    if (dur >= DUR_WARN_S && dur < DUR_MAX_S) beep();
  }
};

$('sStart').addEventListener('input', () => updateManualDur(true));
$('sEnd').addEventListener('input', () => updateManualDur(true));
$('sStart').addEventListener('change', () => updateManualDur(true));
$('sEnd').addEventListener('change', () => updateManualDur(true));

$('segEditStart').addEventListener('input', () => updateSegEditDur(true));
$('segEditEnd').addEventListener('input', () => updateSegEditDur(true));
$('segEditStart').addEventListener('change', () => updateSegEditDur(true));
$('segEditEnd').addEventListener('change', () => updateSegEditDur(true));

updateManualDur(false);

$('openYT').addEventListener('click', () => window.open($('url').value.trim() || 'https://youtube.com', '_blank'));
$('loadHeatmap').addEventListener('click', async () => {
  setHeatmapLoading(true);
  try {
    await runWithBusy('Memuat heatmap...', 'Mengambil Most Replayed / backup AI...', loadHeatmap);
  } catch (e) {
    alert(e.message);
  } finally {
    setHeatmapLoading(false);
  }
});

$('segSelectAll').addEventListener('click', () => {
  segments.forEach((s) => {
    if (s) s.enabled = true;
  });
  renderSegs();
  persistCfg();
});
$('segDeselectAll').addEventListener('click', () => {
  segments.forEach((s) => {
    if (s) s.enabled = false;
  });
  activeSegIdx = null;
  renderSegs();
  persistCfg();
});
$('addSeg').addEventListener('click', async () => {
  try {
    await runWithBusy('Menambah segmen...', 'Menyiapkan data video...', async () => {
      if (!durationSec) await loadInfo();
      addSeg();
    });
  } catch (e) {
    alert(e.message);
  }
});
$('clearSeg').addEventListener('click', () => {
  segments = [];
  activeSegIdx = null;
  renderSegs();
  persistCfg();
});
$('review').addEventListener('click', () => {
  try {
    fillSummary();
    openModal();
  } catch (e) {
    alert(e.message);
  }
});
$('closeModal').addEventListener('click', closeModal);
$('go').addEventListener('click', async () => {
  try {
    closeModal();
    await startJob();
  } catch (e) {
    alert(e.message);
  }
});

const _openFolderBtn = $('openFolder');
if (_openFolderBtn)
  _openFolderBtn.addEventListener('click', async (ev) => {
  try {
    ev.preventDefault();
  } catch {}
  if (!jobId) {
    const msg = 'Job belum ada. Tombol ini aktif setelah proses selesai.';
    appendLog('[openFolder] ' + msg);
    try {
      console.warn(msg);
    } catch {}
    alert(msg);
    return;
  }
  try {
    await runWithBusy('Membuka folder...', 'Menyiapkan folder output...', async () => {
      appendLog('[openFolder] Request /api/open_output/' + jobId);
      const res = await fetch('/api/open_output/' + jobId, { method: 'POST', headers: { Accept: 'application/json' }, cache: 'no-store' });
      let data = null;
      try {
        data = await res.json();
      } catch {
        const t = await res.text().catch(() => '');
        throw new Error('Response tidak valid (bukan JSON). ' + (t ? '\n' + t.slice(0, 200) : ''));
      }
      if (!data || !data.ok) throw new Error(data && data.error ? data.error : 'Gagal membuka folder output.');
      appendLog('[openFolder] OK ' + (data.output_dir ? '→ ' + data.output_dir : ''));
      try {
        console.log('openFolder OK', data);
      } catch {}
    });
  } catch (e) {
    const msg = e && e.message ? e.message : String(e);
    appendLog('[openFolder] ERROR ' + msg);
    try {
      console.error(e);
    } catch {}
    alert(msg);
  }
  });

$('timeline').addEventListener('input', () => {
  const v = parseInt($('timeline').value || '0', 10);
  $('tCur').textContent = fmt(v);
  syncRangeFill($('timeline'));
  if (playerReady && player) player.seekTo(v, true);
});

$('play').addEventListener('click', async () => {
  try {
    if (!currentVideoId) await loadInfo();
    if (!(await waitMainPlayer())) return;
    const st = player.getPlayerState();
    if (st === 1) player.pauseVideo();
    else player.playVideo();
  } catch (e) {
    alert(e.message);
  }
});
$('stop').addEventListener('click', async () => {
  try {
    if (!currentVideoId) await loadInfo();
    if (!(await waitMainPlayer())) return;
    previewStopAt = null;
    player.pauseVideo();
    player.seekTo(0, true);
  } catch (e) {
    alert(e.message);
  }
});
$('playPreview').addEventListener('click', async () => {
  try {
    if (!currentVideoId) await loadInfo();
    if (!(await waitMainPlayer())) return;
    const s = parseInt(($('previewSecs').value || '30'), 10);
    if (Number.isNaN(s) || s < 5 || s > 600) {
      alert('Preview detik harus 5-600');
      return;
    }
    previewStopAt = s;
    player.seekTo(0, true);
    player.playVideo();
  } catch (e) {
    alert(e.message);
  }
});

$('segEnabled').addEventListener('change', () => {
  if (activeSegIdx === null) return;
  if (!segments[activeSegIdx]) return;
  segments[activeSegIdx].enabled = !!$('segEnabled').checked;
  renderSegs();
  persistCfg();
});

$('segSetStartNow').addEventListener('click', () => {
  if (!segPlayer || !segPlayer.getCurrentTime) return;
  try {
    const ct = Math.floor(segPlayer.getCurrentTime() || 0);
    $('segEditStart').value = fmt(ct);
  } catch {}
});

$('segSetEndNow').addEventListener('click', () => {
  if (!segPlayer || !segPlayer.getCurrentTime) return;
  try {
    const ct = Math.floor(segPlayer.getCurrentTime() || 0);
    $('segEditEnd').value = fmt(ct);
  } catch {}
});

$('segApply').addEventListener('click', applySegEdit);

$('segUse').addEventListener('click', () => {
  if (activeSegIdx === null) return;
  const s = segments[activeSegIdx];
  if (!s) return;
  $('sStart').value = String(Math.max(0, parseInt(s.start || 0, 10)));
  $('sEnd').value = String(Math.max(0, parseInt(s.end || 0, 10)));
  closeSegModal();
  destroySegPlayer();
});

$('segClose').addEventListener('click', () => {
  closeSegModal();
  destroySegPlayer();
});

window.onYouTubeIframeAPIReady = function () {
  playerReady = true;
};

const loadPlayer = (videoId) => {
  ensureYTApi().then(() => {
    if (player && player.getVideoData && player.loadVideoById) {
      const curId = player.getVideoData()?.video_id;
      if (String(curId) !== String(videoId)) {
        try {
          player.loadVideoById(videoId);
        } catch {}
      }
      return;
    }

    try {
      if (player && player.destroy) player.destroy();
    } catch {}
    const holder = $('player');
    if (holder) holder.innerHTML = '';

    player = new YT.Player('player', {
      height: '100%',
      width: '100%',
      videoId: videoId,
      playerVars: { controls: 1, rel: 0, modestbranding: 1, fs: 1 },
      events: {
        onReady: (e) => {
          playerReady = true;
          try {
            e.target.setPlaybackQuality('large');
          } catch {}
          const tick = () => {
            try {
              if (!player) return;
              const ct = player.getCurrentTime ? player.getCurrentTime() : 0;
              $('timeline').value = String(Math.floor(ct));
              syncRangeFill($('timeline'));
              $('tCur').textContent = fmt(ct);
              if (previewStopAt !== null && ct >= previewStopAt) {
                player.pauseVideo();
                previewStopAt = null;
              }
            } catch {}
            requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        },
      },
    });
  });
};

(async () => {
  const serverCfg = await fetch('/api/config').then((r) => r.json()).catch(() => ({}));
  const localCfg = loadLocalCfg();
  if (localCfg && localCfg.gemini_api_key) {
    try {
      delete localCfg.gemini_api_key;
      saveLocalCfg(localCfg);
    } catch {}
  }
  applyCfg(Object.assign({}, serverCfg, localCfg, { output_dir: localCfg.output_dir || serverCfg.output_dir || DEFAULT_OUTDIR }));
  if (!$('previewSecs').value) $('previewSecs').value = '30';
  $('url').value = '';
  syncRangeFill($('timeline'));
  renderSegs();
  updateBusyState();
})();
