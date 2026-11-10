const $ = (id) => document.getElementById(id);
const DEFAULT_OUTDIR = window.__YTCLIPPER_DEFAULT_OUTDIR__ || '';
const BASE_PATH = window.__YTCLIPPER_BASE__ || '';
const apiUrl = (path) => `${BASE_PATH}${path}`;
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

const formatMmSsLive = (el) => {
  if (!el) return '';
  const raw = String(el.value || '');
  const last = String(el.dataset.lastValue || '');
  const deleting = raw.length < last.length;
  const digits = raw.replace(/\D/g, '');

  let out = '';
  if (digits.length === 0) out = '';
  else if (digits.length === 1) out = digits;
  else if (digits.length === 2) out = deleting ? digits : digits + ':';
  else {
    const mm = digits.slice(0, 2);
    const ss = digits.slice(2, 4);
    out = mm + ':' + ss;
  }

  el.dataset.lastValue = out;

  if (el.value !== out) {
    const atEnd = el.selectionStart === raw.length && el.selectionEnd === raw.length;
    el.value = out;
    if (atEnd) {
      try {
        el.setSelectionRange(out.length, out.length);
      } catch {}
    }
  }
  return out;
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

const normText = (v) => {
  if (v === undefined || v === null) return '';
  return String(v);
};

const errText = (e, fallback) => {
  if (!e) return fallback || 'Terjadi error.';
  if (typeof e === 'string') return e;
  if (e && typeof e.message === 'string' && e.message.trim()) return e.message;
  try {
    const s = JSON.stringify(e);
    if (s && s !== '{}' && s !== '[]') return s;
  } catch {}
  return fallback || String(e);
};

const escapeHtml = (s) =>
  String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');

const normAlertType = (t) => {
  const x = String(t || 'info').toLowerCase();
  if (x === 'warn' || x === 'warning') return 'warning';
  if (x === 'err') return 'error';
  if (x === 'ok') return 'success';
  if (x === 'info' || x === 'success' || x === 'error' || x === 'question') return x;
  return 'info';
};

const ensureSwalToast = (() => {
  let mixin = null;
  return () => {
    const Swal = window.Swal;
    if (!Swal) return null;
    if (mixin) return mixin;
    mixin = Swal.mixin({
      toast: true,
      position: 'top-end',
      showConfirmButton: false,
      timer: 4200,
      timerProgressBar: true,
      background: '#111824',
      color: '#e8edf2',
      didOpen: (el) => {
        try {
          el.addEventListener('mouseenter', Swal.stopTimer);
          el.addEventListener('mouseleave', Swal.resumeTimer);
        } catch {}
      },
    });
    return mixin;
  };
})();

const ensureToastWrap = () => {
  let wrap = $('toastWrap');
  if (wrap) return wrap;
  wrap = document.createElement('div');
  wrap.id = 'toastWrap';
  wrap.className = 'toastWrap';
  document.body.appendChild(wrap);
  return wrap;
};

const toast = ({ type, title, message, timeout }) => {
  const t = type || 'info';
  const ttl = title ? normText(title) : t === 'error' ? 'Error' : t === 'success' ? 'Sukses' : t === 'warn' ? 'Peringatan' : 'Info';
  const msg = normText(message);
  const wrap = ensureToastWrap();

  const el = document.createElement('div');
  el.className = `toast ${t}`;
  el.setAttribute('role', 'status');
  el.setAttribute('aria-live', t === 'error' ? 'assertive' : 'polite');

  const head = document.createElement('div');
  head.className = 'toastHead';

  const h = document.createElement('div');
  h.style.minWidth = '0';
  h.style.flex = '1';

  const titleEl = document.createElement('div');
  titleEl.className = 'toastTitle';
  titleEl.textContent = ttl;

  const closeBtn = document.createElement('button');
  closeBtn.className = 'toastClose';
  closeBtn.type = 'button';
  closeBtn.textContent = '×';
  closeBtn.setAttribute('aria-label', 'Tutup');

  head.appendChild(h);
  h.appendChild(titleEl);
  head.appendChild(closeBtn);

  const msgEl = document.createElement('div');
  msgEl.className = 'toastMsg';
  msgEl.textContent = msg;

  el.appendChild(head);
  if (msg) el.appendChild(msgEl);

  const dismiss = () => {
    if (el.dataset.dismissing) return;
    el.dataset.dismissing = '1';
    el.classList.add('out');
    setTimeout(() => {
      try {
        el.remove();
      } catch {}
    }, 220);
  };

  closeBtn.addEventListener('click', dismiss);
  wrap.appendChild(el);

  const ms = timeout === undefined || timeout === null ? (t === 'error' ? 6500 : 4200) : Number(timeout);
  if (!Number.isNaN(ms) && ms > 0) setTimeout(dismiss, ms);
  return { dismiss };
};

const copyText = async (text) => {
  const t = normText(text);
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(t);
      return true;
    }
  } catch {}
  try {
    const ta = document.createElement('textarea');
    ta.value = t;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    return !!ok;
  } catch {}
  return false;
};

const ensureSysModal = () => {
  let m = $('sysModal');
  if (m) return m;
  m = document.createElement('div');
  m.id = 'sysModal';
  m.className = 'modal sys';
  m.innerHTML = `
    <div class="box">
      <div class="sysTop">
        <div class="sysIcon info" id="sysIcon">
          <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M12 16v-4"></path>
            <path d="M12 8h.01"></path>
          </svg>
        </div>
        <div style="min-width:0;flex:1">
          <h3 class="sysTitle" id="sysTitle">Info</h3>
          <div class="sysMsg" id="sysMsg"></div>
        </div>
      </div>
      <div class="row" style="justify-content:flex-end">
        <button class="btn" id="sysCopy" type="button">Copy</button>
        <button class="btn primary" id="sysOk" type="button">OK</button>
      </div>
    </div>
  `;
  document.body.appendChild(m);

  const close = () => {
    m.classList.remove('on');
  };
  const okBtn = $('sysOk');
  if (okBtn) okBtn.addEventListener('click', close);

  m.addEventListener('click', (e) => {
    if (e.target === m) close();
  });

  const copyBtn = $('sysCopy');
  if (copyBtn)
    copyBtn.addEventListener('click', async () => {
      const txt = $('sysMsg') ? $('sysMsg').textContent : '';
      const ok = await copyText(txt);
      toast({ type: ok ? 'success' : 'error', title: ok ? 'Tersalin' : 'Gagal', message: ok ? 'Teks berhasil dicopy.' : 'Clipboard tidak tersedia.' });
    });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (m.classList.contains('on')) close();
  });

  return m;
};

const alertModal = ({ type, title, message }) => {
  const t = type || 'info';
  const m = ensureSysModal();
  const icon = $('sysIcon');
  if (icon) icon.className = `sysIcon ${t}`;
  const ttl = $('sysTitle');
  if (ttl) ttl.textContent = title ? normText(title) : t === 'error' ? 'Error' : t === 'success' ? 'Sukses' : t === 'warn' ? 'Peringatan' : 'Info';
  const msg = $('sysMsg');
  if (msg) msg.textContent = normText(message);
  m.classList.add('on');
};

const uiAlert = (message, opts) => {
  const msg = normText(message);
  const o = opts || {};
  const type = normAlertType(o.type || 'info');
  const title = o.title ? normText(o.title) : type === 'error' ? 'Error' : type === 'success' ? 'Sukses' : type === 'warning' ? 'Peringatan' : 'Info';
  const modal = !!o.modal || msg.includes('\n') || msg.length >= 120;

  const Swal = window.Swal;
  if (Swal && typeof Swal.fire === 'function') {
    if (modal) {
      Swal.fire({
        icon: type,
        title,
        html: `<pre style="white-space:pre-wrap;margin:0;text-align:left">${escapeHtml(msg)}</pre>`,
        background: '#111824',
        color: '#e8edf2',
        confirmButtonColor: '#2b5cff',
      });
      return;
    }
    const t = ensureSwalToast();
    if (t && typeof t.fire === 'function') {
      t.fire({
        icon: type,
        title,
        text: msg,
      });
      return;
    }
    Swal.fire({
      icon: type,
      title,
      text: msg,
      background: '#111824',
      color: '#e8edf2',
      confirmButtonColor: '#2b5cff',
    });
    return;
  }

  if (modal) alertModal({ type, title, message: msg });
  else toast({ type, title, message: msg });
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

const syncDownloadButtons = () => {
  const btn = $('btnShowResult');
  const container = $('downloadContainer'); // legacy container, we hide it now
  if (container) container.style.display = 'none';
  if (!btn) return;

  const js = lastJobStatus || null;
  const uiBusy = busyCount > 0 || !!busyJob;
  
  if (!js || !js.done || !js.files || js.files.length === 0 || uiBusy) {
    btn.style.display = 'none';
    return;
  }
  btn.style.display = 'inline-flex';
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

const setBusyProgress = (pct) => {
  const track = $('busyProgressTrack');
  const bar = $('busyProgressBar');
  const pctEl = $('busyPct');
  if (pct === null || pct === undefined || isNaN(pct) || pct < 0) {
    if (track) track.style.display = 'none';
    if (pctEl) pctEl.textContent = '';
    return;
  }
  const clamped = Math.max(0, Math.min(100, Math.round(pct)));
  if (track) track.style.display = 'block';
  if (bar) bar.style.width = clamped + '%';
  if (pctEl) pctEl.textContent = clamped + '%';
};

const setBusyText = (title, msg, pct) => {
  const t = $('busyTitle');
  const m = $('busyMsg');
  if (t && title) t.textContent = title;
  if (m && msg !== undefined && msg !== null) m.textContent = String(msg);
  if (pct !== undefined) setBusyProgress(pct);
};

const updateBusyState = () => {
  const on = busyCount > 0 || !!busyJob;
  const el = $('busy');
  if (!el) return;
  if (on) el.classList.add('on');
  else el.classList.remove('on');
  setUiDisabled(on);
  if (!on) syncSegBulkButtons();
  if (!on) syncDownloadButtons();
};

const beginBusy = (title, msg, pct) => {
  busyCount += 1;
  setBusyProgress(pct !== undefined ? pct : null);
  setBusyText(title || 'Loading', msg ?? 'Mohon tunggu...', pct);
  updateBusyState();
};

const endBusy = () => {
  busyCount = Math.max(0, busyCount - 1);
  if (busyCount === 0) setBusyProgress(null);
  updateBusyState();
};

const runWithBusy = async (title, msg, fn, pct) => {
  beginBusy(title, msg, pct);
  try {
    return await fn();
  } finally {
    endBusy();
  }
};

const setBusyJob = (on, title, msg, pct) => {
  busyJob = !!on;
  if (busyJob) {
    setBusyText(title || 'Memproses...', msg ?? 'Mohon tunggu...', pct);
  } else {
    setBusyProgress(null);
  }
  updateBusyState();
  const btnCancel = $('btnCancelJob');
  if (btnCancel) btnCancel.style.display = busyJob ? 'inline-block' : 'none';
};

const setOpenFolderVisible = (on) => {
  // deprecated
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

const SUB_SAMPLE_TEXTS = [
  '🔥 RAHASIA VIRAL SHORTS TERBONGKAR!',
  'Ternyata plot twist endingnya gak nyangka...',
  'Jangan lupa like & subscribe ya guys!',
  'Tips penting buat pemula yang wajib dicoba!',
  'Buset parah banget hasilnya kayak gini?!'
];
let subSampleIndex = 0;

const updateSubtitlePreview = () => {
  const isSubOn = $('subOn') ? $('subOn').checked : false;
  const fontName = $('subFont') ? $('subFont').value : 'Arial Black';
  const fontSize = $('subFontSize') ? parseInt($('subFontSize').value || '22', 10) : 22;
  const fontColor = $('subFontColor') ? $('subFontColor').value : '#FFFFFF';
  const pos = $('subPos') ? $('subPos').value : 'middle';
  const customText = $('subCustomText') ? $('subCustomText').value : SUB_SAMPLE_TEXTS[0];

  const fontSizeVal = $('subFontSizeVal');
  if (fontSizeVal) fontSizeVal.textContent = fontSize + 'px';

  // Update active pill styling
  document.querySelectorAll('.sub-color-pill').forEach((btn) => {
    const col = btn.dataset.color;
    btn.classList.toggle('active', col && col.toLowerCase() === fontColor.toLowerCase());
  });

  // Update size preset buttons
  document.querySelectorAll('.sub-size-preset').forEach((btn) => {
    const sz = parseInt(btn.dataset.size, 10);
    btn.classList.toggle('active', sz === fontSize);
  });

  const updateEl = (el, scaleFactor = 1.0) => {
    if (!el) return;
    if (isSubOn) {
      el.style.display = 'block';
      el.textContent = customText || SUB_SAMPLE_TEXTS[0];
      el.style.fontFamily = `"${fontName}", sans-serif`;
      const scaledSize = Math.max(12, Math.round(fontSize * scaleFactor));
      el.style.fontSize = scaledSize + 'px';
      el.style.color = fontColor;
      el.className = `sub-overlay-text pos-${pos}`;
    } else {
      el.style.display = 'none';
    }
  };

  // Update Unified Main Player overlays
  updateEl($('mainShortsSubOverlay'), 1.0);
  updateEl($('mainFullSubOverlay'), 0.95);

  // Update Segment Modal overlay
  updateEl($('segModalSubOverlay'), 1.05);

  // Fallback for legacy mockup if present
  updateEl($('subOverlayText'), 0.72);
};

const applyCfg = (cfg) => {
  if (cfg.crop_mode) $('crop').value = cfg.crop_mode;
  if (cfg.crop_preview !== undefined && $('cropPrev')) $('cropPrev').checked = !!cfg.crop_preview;
  if (cfg.use_subtitle !== undefined) $('subOn').checked = !!cfg.use_subtitle;
  if (cfg.use_gemini_suggestions !== undefined && $('geminiOn')) $('geminiOn').value = cfg.use_gemini_suggestions ? 'yes' : 'no';
  if (cfg.whisper_model) $('model').value = cfg.whisper_model;
  if (cfg.subtitle_language && $('subLang')) $('subLang').value = cfg.subtitle_language;
  if (cfg.subtitle_position) $('subPos').value = cfg.subtitle_position;
  if (cfg.subtitle_font_name && $('subFont')) $('subFont').value = cfg.subtitle_font_name;
  if (cfg.subtitle_font_size && $('subFontSize')) $('subFontSize').value = cfg.subtitle_font_size;
  if (cfg.subtitle_font_color && $('subFontColor')) $('subFontColor').value = cfg.subtitle_font_color;
  if (cfg.preview_seconds) $('previewSecs').value = cfg.preview_seconds;
  geminiKeyStoredOnServer = !!cfg.has_gemini_key;
  if (cfg.has_gemini_key && $('geminiKey') && !$('geminiKey').value) {
    $('geminiKey').placeholder = 'Tersimpan di server';
  }
  syncGeminiHint();
  syncSub();
  updateCropPreview();
  updateSubtitlePreview();
};

const collectCfgLocal = () => ({
  crop_mode: $('crop').value,
  crop_preview: $('cropPrev') ? $('cropPrev').checked : true,
  use_subtitle: $('subOn').checked,
  use_gemini_suggestions: isGeminiSuggestionsOn(),
  whisper_model: $('model').value,
  subtitle_language: $('subLang') ? $('subLang').value : 'id',
  subtitle_position: $('subPos').value,
  subtitle_font_name: $('subFont') ? $('subFont').value : 'Arial Black',
  subtitle_font_size: $('subFontSize') ? parseInt($('subFontSize').value || '22', 10) : 22,
  subtitle_font_color: $('subFontColor') ? $('subFontColor').value : '#FFFFFF',
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
    await fetch(apiUrl('/api/config'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cfgServer) });
  } catch {}
};

const syncSub = () => {
  const on = $('subOn').checked;
  $('reviewSubtitles').disabled = !on;
  $('model').disabled = !on;
  if ($('subLang')) $('subLang').disabled = !on;
  $('subPos').disabled = !on;
  if ($('subFont')) $('subFont').disabled = !on;
  if ($('subFontSize')) $('subFontSize').disabled = !on;
  if ($('subFontColor')) $('subFontColor').disabled = !on;
  if ($('subCustomText')) $('subCustomText').disabled = !on;
  const panel = $('subConfigPanel');
  if (panel) {
    panel.style.opacity = on ? '1' : '0.45';
  }
  updateSubtitlePreview();
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
    const shade = 'rgba(0,0,0,0.80)'; // Much darker to highlight the crop area
    const stroke = 'rgba(6, 182, 212, 0.9)'; // Neon cyan
    const stroke2 = 'rgba(139, 92, 246, 0.6)'; // Neon purple for split line
    const sw = 0.5; // Thinner, more elegant line

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
            <line x1="0" y1="${bottomY}" x2="100" y2="${bottomY}" stroke="${stroke2}" stroke-width="${sw}" stroke-dasharray="2 1" />
          `;
    } else if (mode === 'split_podcast') {
      const wPod = 63.28;
      const rightX = 100 - wPod;
      holes = `M0 0H${wPod}V100H0Z M${rightX} 0H100V100H${rightX}Z`;
      frames = `
            <rect x="0" y="0" width="${wPod}" height="100" fill="none" stroke="${stroke}" stroke-width="${sw}" />
            <rect x="${rightX}" y="0" width="${wPod}" height="100" fill="none" stroke="rgba(244, 63, 94, 0.9)" stroke-width="${sw}" />
            <line x1="${rightX}" y1="0" x2="${rightX}" y2="100" stroke="${stroke2}" stroke-width="${sw}" stroke-dasharray="2 1" />
            <line x1="${wPod}" y1="0" x2="${wPod}" y2="100" stroke="${stroke2}" stroke-width="${sw}" stroke-dasharray="2 1" />
          `;
    } else if (mode === 'podcast_speaker') {
      const wSpk = 31.64;
      const leftSpkX = 4;
      const rightSpkX = 100 - wSpk - 4;
      holes = `M${leftSpkX} 0H${leftSpkX + wSpk}V100H${leftSpkX}Z M${rightSpkX} 0H${rightSpkX + wSpk}V100H${rightSpkX}Z`;
      frames = `
            <rect x="${leftSpkX}" y="0" width="${wSpk}" height="100" fill="none" stroke="${stroke}" stroke-width="${sw}" stroke-dasharray="2 1" />
            <rect x="${rightSpkX}" y="0" width="${wSpk}" height="100" fill="none" stroke="rgba(244, 63, 94, 0.9)" stroke-width="${sw}" stroke-dasharray="2 1" />
          `;
    } else {
      holes = `M${xC} 0H${xC + w}V100H${xC}Z`;
      frames = `<rect x="${xC}" y="0" width="${w}" height="100" fill="none" stroke="${stroke}" stroke-width="${sw}" />`;
    }

    el.innerHTML = `
          <defs>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="0.5" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>
          <path d="M0 0H100V100H0Z ${holes}" fill="${shade}" fill-rule="evenodd" />
          <g filter="url(#glow)">
            ${frames}
          </g>
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

let currentSortCol = 'score'; // 'score' | 'start' | 'end' | 'dur'
let currentSortDir = 'desc'; // 'asc' | 'desc'

const applySorting = () => {
  segments.sort((a, b) => {
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

  updateSortUI();
};

const updateSortUI = () => {
  const sel = $('segSortSelect');
  if (sel) {
    const val = `${currentSortCol}_${currentSortDir}`;
    if (sel.value !== val) sel.value = val;
  }

  const btnDir = $('btnToggleSortDir');
  if (btnDir) {
    btnDir.title = `Arah urutan saat ini: ${currentSortDir.toUpperCase()} (klik untuk membalik)`;
    btnDir.textContent = currentSortDir === 'asc' ? '▲ Asc' : '▼ Desc';
    btnDir.style.color = currentSortDir === 'asc' ? '#38bdf8' : '#a78bfa';
  }

  document.querySelectorAll('.th-sortable').forEach((th) => {
    const col = th.dataset.col;
    const ind = $('sortInd_' + col);
    if (col === currentSortCol) {
      th.classList.add('active-sort');
      if (ind) ind.textContent = currentSortDir === 'asc' ? '▲' : '▼';
    } else {
      th.classList.remove('active-sort');
      if (ind) ind.textContent = '';
    }
  });
};

const handleHeaderSort = (col) => {
  if (currentSortCol === col) {
    currentSortDir = currentSortDir === 'asc' ? 'desc' : 'asc';
  } else {
    currentSortCol = col;
    currentSortDir = col === 'start' || col === 'end' ? 'asc' : 'desc';
  }
  applySorting();
  renderSegs();
};

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
            <div style="display:flex; gap:8px;">
              <button class="btn segPrev" data-idx="${idx}" title="Preview segmen (modal).">Preview</button>
              <button class="btn danger segDel" data-idx="${idx}" title="Hapus segmen ini.">Del</button>
            </div>
          </td>
        `;
    tbody.appendChild(tr);
  });
  updateSortUI();
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

let segViewMode = 'shorts'; // 'shorts' | 'full'
let segShortsPlayers = [];
let segShortsTimer = null;
let segShortsPlaying = true;

const openSegModal = () => {
  $('segModal').classList.add('on');
  updateSubtitlePreview();
};

const updateSegShortsPlayBtn = (playing) => {
  const btn = $('btnSegShortsPlayToggle');
  if (btn) btn.textContent = playing ? '⏸' : '▶';
};

const updateSegShortsTimeDisplay = (currSec) => {
  const el = $('segShortsTimeDisplay');
  if (!el) return;
  const c = Math.max(0, Math.floor(currSec));
  const tot = Math.max(0, segEnd - segStart);
  const prog = Math.max(0, c - segStart);
  el.textContent = `${fmt(c)} (${fmt(prog)}/${fmt(tot)})`;
};

const destroySegShortsPlayers = () => {
  if (segShortsTimer) {
    clearInterval(segShortsTimer);
    segShortsTimer = null;
  }
  segShortsPlayers.forEach((p) => {
    try { if (p && p.destroy) p.destroy(); } catch {}
  });
  segShortsPlayers = [];
  const c = $('segShortsContainer');
  if (c) c.innerHTML = '';
};

const destroySegPlayer = () => {
  try {
    if (segPlayer && segPlayer.destroy) segPlayer.destroy();
  } catch {}
  segPlayer = null;
  const holder = $('segPlayer');
  if (holder) holder.innerHTML = '';
};

const closeSegModal = () => {
  $('segModal').classList.remove('on');
  destroySegPlayer();
  destroySegShortsPlayers();
  segStart = 0;
  segEnd = 0;
};

const getSegCurrentTime = () => {
  if (segViewMode === 'full') {
    if (segPlayer && segPlayer.getCurrentTime) {
      try { return Math.floor(segPlayer.getCurrentTime() || 0); } catch {}
    }
  } else {
    if (segShortsPlayers.length > 0 && segShortsPlayers[0]?.getCurrentTime) {
      try { return Math.floor(segShortsPlayers[0].getCurrentTime() || 0); } catch {}
    }
  }
  return segStart;
};

const initSegShortsPlayer = async (startTime) => {
  destroySegShortsPlayers();
  if (!currentVideoId) return;
  await ensureYTApi();

  const c = $('segShortsContainer');
  if (!c) return;
  c.innerHTML = '';

  const mode = ($('crop')?.value || 'default').trim();
  const startAt = startTime !== undefined ? startTime : segStart;
  segShortsPlaying = true;
  updateSegShortsPlayBtn(true);

  const createPlayer = (boxClass, ifClass, isMuted) => {
    const box = document.createElement('div');
    box.className = `shorts-crop-box ${boxClass}`;
    
    const ifHolder = document.createElement('div');
    ifHolder.className = `shorts-iframe ${ifClass}`;
    box.appendChild(ifHolder);
    c.appendChild(box);
    
    const p = new YT.Player(ifHolder, {
      videoId: currentVideoId,
      playerVars: { 
        autoplay: 1, 
        controls: 0, 
        rel: 0, 
        modestbranding: 1, 
        fs: 0, 
        disablekb: 1, 
        start: Math.floor(startAt), 
        mute: 1 
      },
      events: {
        onReady: (e) => {
          const iframe = e.target.getIframe();
          if (iframe) iframe.className = `shorts-iframe ${ifClass}`;
          try { e.target.seekTo(startAt, true); } catch {}
          try { e.target.playVideo(); } catch {}
          if (!isMuted) {
            try { e.target.unMute(); } catch {}
          }
        },
        onStateChange: (e) => {
          if (e.data === YT.PlayerState.ENDED) {
            segShortsPlayers.forEach((pl) => {
              try { pl.seekTo(segStart, true); pl.playVideo(); } catch {}
            });
          }
        }
      }
    });
    segShortsPlayers.push(p);
    return p;
  };

  if (mode === 'split_left' || mode === 'split_right') {
    createPlayer('shorts-box-top', 'shorts-if-top', false);
    createPlayer('shorts-box-bottom', mode === 'split_left' ? 'shorts-if-bottom-left' : 'shorts-if-bottom-right', true);
  } else if (mode === 'split_podcast') {
    createPlayer('shorts-box-podcast-top', 'shorts-if-podcast-top', false);
    createPlayer('shorts-box-podcast-bottom', 'shorts-if-podcast-bottom', true);
  } else if (mode === 'podcast_speaker') {
    createPlayer('shorts-box-podcast-speaker', 'shorts-if-podcast-speaker', false);
  } else if (mode === 'fit') {
    createPlayer('shorts-box-fit', 'shorts-if-fit', false);
  } else {
    createPlayer('shorts-box-default', 'shorts-if-default', false);
  }

  const slider = $('segShortsSlider');
  if (slider) {
    slider.min = String(segStart);
    slider.max = String(Math.max(segStart + 1, segEnd));
    slider.value = String(startAt);
  }
  updateSegShortsTimeDisplay(startAt);

  segShortsTimer = setInterval(() => {
    if (segShortsPlayers.length === 0) return;
    const p0 = segShortsPlayers[0];
    if (!p0 || !p0.getCurrentTime) return;
    try {
      const ct = p0.getCurrentTime();
      if (ct >= segEnd && segEnd > segStart) {
        segShortsPlayers.forEach((pl) => {
          try { pl.seekTo(segStart, true); } catch {}
        });
        updateSegShortsTimeDisplay(segStart);
        if (slider) slider.value = String(segStart);
      } else {
        updateSegShortsTimeDisplay(ct);
        if (slider && !slider.matches(':active')) {
          slider.value = String(Math.floor(ct));
        }
      }
    } catch {}
  }, 250);
};

const initSegFullPlayer = async (startTime) => {
  destroySegPlayer();
  if (!currentVideoId) return;
  await ensureYTApi();

  const startAt = startTime !== undefined ? startTime : segStart;

  segPlayer = new YT.Player('segPlayer', {
    height: '100%',
    width: '100%',
    videoId: currentVideoId,
    playerVars: { controls: 1, rel: 0, modestbranding: 1, fs: 1, start: Math.floor(startAt), end: segEnd },
    events: {
      onReady: (e) => {
        try {
          e.target.setPlaybackQuality('large');
        } catch {}
        try {
          e.target.seekTo(startAt, true);
        } catch {}
      },
    },
  });
  updateCropPreview();
};

const setSegViewMode = async (mode) => {
  if (mode === segViewMode) return;
  const currentCt = getSegCurrentTime();
  segViewMode = mode;

  const btnShorts = $('btnSegViewShorts');
  const btnFull = $('btnSegViewFull');
  const viewShorts = $('segShortsView');
  const viewFull = $('segFullView');
  const hint = $('segViewHint');

  if (mode === 'shorts') {
    if (btnShorts) btnShorts.classList.add('active');
    if (btnFull) btnFull.classList.remove('active');
    if (viewShorts) viewShorts.style.display = 'flex';
    if (viewFull) viewFull.style.display = 'none';
    if (hint) hint.textContent = 'Simulasi vertikal 9:16';
    destroySegPlayer();
    await initSegShortsPlayer(currentCt);
  } else {
    if (btnShorts) btnShorts.classList.remove('active');
    if (btnFull) btnFull.classList.add('active');
    if (viewShorts) viewShorts.style.display = 'none';
    if (viewFull) viewFull.style.display = 'block';
    if (hint) hint.textContent = 'Video penuh 16:9 + batas crop';
    destroySegShortsPlayers();
    await initSegFullPlayer(currentCt);
  }
};

const openSegPreview = async (idx) => {
  const s = segments[idx];
  if (!s) return;
  await runWithBusy('Menyiapkan preview...', 'Memuat player segmen...', async () => {
    if (!currentVideoId) {
      try {
        await loadInfo();
      } catch (e) {
        uiAlert(errText(e, 'Gagal memuat info video.'), { type: 'error' });
        return;
      }
    }

    const start = Math.max(0, parseInt(s.start || 0, 10));
    const end = Math.max(0, parseInt(s.end || 0, 10));
    if (end <= start) {
      uiAlert('Segmen tidak valid (end <= start).', { type: 'warn' });
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

    const cropSelect = $('segCropModeSelect');
    if (cropSelect) {
      const mode = ($('crop')?.value || 'default').trim();
      cropSelect.value = mode;
    }

    destroySegPlayer();
    destroySegShortsPlayers();
    openSegModal();

    if (segViewMode === 'shorts') {
      if ($('segShortsView')) $('segShortsView').style.display = 'flex';
      if ($('segFullView')) $('segFullView').style.display = 'none';
      if ($('btnSegViewShorts')) $('btnSegViewShorts').classList.add('active');
      if ($('btnSegViewFull')) $('btnSegViewFull').classList.remove('active');
      if ($('segViewHint')) $('segViewHint').textContent = 'Simulasi vertikal 9:16';
      await initSegShortsPlayer(start);
    } else {
      if ($('segShortsView')) $('segShortsView').style.display = 'none';
      if ($('segFullView')) $('segFullView').style.display = 'block';
      if ($('btnSegViewShorts')) $('btnSegViewShorts').classList.remove('active');
      if ($('btnSegViewFull')) $('btnSegViewFull').classList.add('active');
      if ($('segViewHint')) $('segViewHint').textContent = 'Video penuh 16:9 + batas crop';
      await initSegFullPlayer(start);
    }
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
    uiAlert('Format Start/End tidak valid. Pakai MM:SS.', { type: 'warn' });
    return;
  }
  if (start < 0 || end < 0) {
    uiAlert('Durasi tidak boleh negatif.', { type: 'warn' });
    return;
  }
  if (durationSec > 0 && (start > durationSec || end > durationSec)) {
    uiAlert('Start/End melebihi durasi video.', { type: 'warn' });
    return;
  }
  if (end <= start) {
    uiAlert('End harus lebih besar dari Start.', { type: 'warn' });
    return;
  }

  const capped = enforceMaxDur(start, end, 'edit segmen');
  const end2 = capped.changed ? capped.end : end;
  if (capped.changed) {
    $('segEditEnd').value = fmt(end2);
    uiAlert('Durasi klip dibatasi maksimal 03:00. End otomatis dipotong di 180 detik dari start.', { type: 'warn', title: 'Durasi dibatasi' });
  }

  s.start = start;
  s.end = end2;
  segments[activeSegIdx] = s;
  renderSegs();
  persistCfg();
  try {
    await openSegPreview(activeSegIdx);
  } catch (e) {
    uiAlert(errText(e, 'Gagal menerapkan perubahan segmen.'), { type: 'error' });
  }
};

const validateUrl = () => {
  const u = $('url').value.trim();
  if (!u) throw new Error('YouTube URL wajib diisi.');
  return u;
};



const validateSegments = () => {
  const segs = segments.filter((s) => s.enabled);
  if (!segs.length) throw new Error('Minimal 1 segmen harus aktif.');
  for (const s of segs) {
    if (s.start < 0 || s.end < 0) throw new Error('Durasi tidak boleh negatif.');
    if (s.end <= s.start) throw new Error('End harus lebih besar dari Start.');
    if (s.end - s.start > MAX_CLIP_S) throw new Error('Durasi klip maksimal 03:00 (180 detik).');
  }
  return segs;
};

const fillSummary = () => {
  const segs = validateSegments();
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


  const fontName = $('subFont') ? $('subFont').value : 'Arial Black';
  const fontSize = $('subFontSize') ? $('subFontSize').value : '22';
  top.appendChild(mkKv('Crop mode', crop || '-'));
  const reviewNote = $('reviewSubtitles').checked ? ' • Tinjau sebelum render' : '';
  top.appendChild(mkKv('Subtitle', subOn ? `ON • Model: ${model} • Font: ${fontName} (${fontSize}px)${reviewNote}` : 'OFF'));
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

const MAX_CLIP_S = 180;
const DUR_NEAR_S = 170;
const DUR_WARN_S = 175;
const DUR_MAX_S = 180;

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
    el.textContent = 'Durasi: - / 03:00';
    return;
  }
  const dur = Math.max(0, Math.floor(end - start));
  const pct = Math.max(0, Math.min(100, (dur / MAX_CLIP_S) * 100));
  el.style.setProperty('--pct', pct.toFixed(1) + '%');
  el.textContent = `Durasi: ${fmt(dur)} / 03:00`;
  if (dur > MAX_CLIP_S) el.classList.add('max');
  else if (dur >= DUR_WARN_S) el.classList.add('warn');
  else if (dur >= DUR_NEAR_S) el.classList.add('near');
};

const enforceMaxDur = (start, end, label) => {
  if (start === null || end === null) return { start, end, changed: false };
  if (end <= start) return { start, end, changed: false };
  const dur = end - start;
  if (dur <= MAX_CLIP_S) return { start, end, changed: false };
  const newEnd = start + MAX_CLIP_S;
  appendLog(`[durasi] ${label || 'segmen'} melebihi 03:00, auto-trim end ke ${fmt(newEnd)}`);
  beep();
  return { start, end: newEnd, changed: true };
};

const MIN_SHORTS_DUR = 15; // Batas minimal durasi resmi YouTube Shorts (15 detik)

const enforceAllSegments = (label) => {
  let changed = 0;
  for (const s of segments || []) {
    if (!s) continue;
    let st = Number(s.start || 0);
    let en = Number(s.end || 0);
    if (!Number.isFinite(st) || !Number.isFinite(en)) continue;

    // Jika durasi terlalu pendek (< 15 detik, misalnya cuma 1 detik), otomatis ekspansi ke standar Shorts (30 detik)
    if (en - st < MIN_SHORTS_DUR) {
      const targetDur = 30;
      let newEnd = st + targetDur;
      if (durationSec > 0 && newEnd > durationSec) {
        newEnd = durationSec;
        if (durationSec >= MIN_SHORTS_DUR) {
          st = Math.max(0, newEnd - targetDur);
          s.start = st;
        }
      }
      s.end = newEnd;
      appendLog(`[durasi] ${label || 'segmen'} durasi terlalu pendek (< 15s), auto-expand ke durasi Shorts standar ${fmt(newEnd - s.start)}`);
      changed++;
    }

    const capped = enforceMaxDur(s.start, s.end, label || 'segmen');
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

const captionReviewDialog = $('captionReviewDialog');
const captionReviewVideo = $('captionReviewVideo');
const captionReviewSrt = $('captionReviewSrt');
const captionTrack = captionReviewVideo.addTextTrack('captions', 'Caption');
captionTrack.mode = 'showing';
let activeCaptionReview = null;
let submittedReviewId = null;
let pollPending = false;

const updateCaptionReviewTrack = () => {
  for (const cue of Array.from(captionTrack.cues || [])) captionTrack.removeCue(cue);
  if (typeof VTTCue !== 'function') return;
  const toSeconds = (timestamp) => {
    const [h, m, s] = timestamp.replace(',', '.').split(':').map(Number);
    return h * 3600 + m * 60 + s;
  };
  const timingPattern = /^(\d{2}:[0-5]\d:[0-5]\d,\d{3})\s+-->\s+(\d{2}:[0-5]\d:[0-5]\d,\d{3})$/;
  for (const block of captionReviewSrt.value.trim().split(/\n(?:[ \t]*\n)+/)) {
    const [, timing, ...lines] = block.split('\n');
    const match = timing?.trim().match(timingPattern);
    if (!match || lines.length === 0) continue;
    const start = toSeconds(match[1]);
    const end = toSeconds(match[2]);
    if (end <= start) continue;
    const text = lines.join('\n').replaceAll('&', '&amp;').replaceAll('<', '&lt;');
    captionTrack.addCue(new VTTCue(start, end, text));
  }
};

const stopCaptionReviewVideo = () => {
  captionReviewVideo.pause();
  captionReviewVideo.removeAttribute('src');
  captionReviewVideo.load();
};

const closeCaptionReview = () => {
  if (!activeCaptionReview) return;
  activeCaptionReview = null;
  stopCaptionReviewVideo();
  captionReviewSrt.value = '';
  updateCaptionReviewTrack();
  captionReviewDialog.close();
};

const showCaptionReview = (review, currentJob) => {
  if (review.review_id === submittedReviewId || review.review_id === activeCaptionReview?.reviewId) return;
  closeCaptionReview();
  const base = '/api/subtitle-review/' + encodeURIComponent(currentJob);
  const videoUrl = apiUrl(base + '/' + encodeURIComponent(review.review_id) + '/video');
  activeCaptionReview = { reviewId: review.review_id, base, videoUrl };
  $('captionReviewTitle').textContent = 'Tinjau caption Clip #' + review.clip_index;
  $('captionReviewError').textContent = '';
  $('saveCaptionReview').disabled = false;
  $('cancelCaptionReview').disabled = false;
  captionReviewSrt.value = review.srt;
  captionReviewVideo.src = videoUrl;
  updateCaptionReviewTrack();
  captionReviewDialog.showModal();
};

captionReviewSrt.addEventListener('input', updateCaptionReviewTrack);
captionReviewDialog.addEventListener('cancel', (event) => event.preventDefault());
$('cancelCaptionReview').addEventListener('click', () => $('btnCancelJob').click());
$('saveCaptionReview').addEventListener('click', async () => {
  const review = activeCaptionReview;
  if (!review) return;
  const button = $('saveCaptionReview');
  const cancel = $('cancelCaptionReview');
  button.disabled = true;
  cancel.disabled = true;
  $('captionReviewError').textContent = '';
  const time = captionReviewVideo.currentTime;
  stopCaptionReviewVideo();
  try {
    const response = await fetch(apiUrl(review.base), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ review_id: review.reviewId, srt: captionReviewSrt.value }),
    });
    const data = await response.json();
    if (review !== activeCaptionReview) return;
    if (!data.ok) throw new Error(data.error || 'Gagal menyimpan caption.');
    submittedReviewId = review.reviewId;
    closeCaptionReview();
    void poll();
  } catch (error) {
    if (review !== activeCaptionReview) return;
    $('captionReviewError').textContent = errText(error);
    captionReviewVideo.src = review.videoUrl;
    captionReviewVideo.currentTime = time;
  } finally {
    if (review === activeCaptionReview) {
      button.disabled = false;
      cancel.disabled = false;
    }
  }
});

const poll = async () => {
  if (!jobId || pollPending) return;
  const currentJob = jobId;
  pollPending = true;
  try {
    const res = await fetch(apiUrl('/api/status/') + currentJob, { cache: 'no-store' });
    const data = await res.json();
    if (!data.ok || jobId !== currentJob) return;
    if (data.subtitle_review) showCaptionReview(data.subtitle_review, currentJob);
    else closeCaptionReview();
    lastJobStatus = data;
    const isRunning = data.running && !data.done;
    setProgress(data.percent, data.status, data.eta, isRunning);
    if (busyJob && isRunning) {
      const pct = Math.max(0, Math.min(100, Number(data.percent || 0)));
      const st = (data.status || '').trim();
      const etaStr = data.eta ? ` • ETA: ${data.eta}` : '';
      setBusyText('Sedang memproses...', (st ? st : 'Memproses klip video...') + etaStr, pct);
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
    syncDownloadButtons();
    if (data.done) {
      clearInterval(pollTimer);
      pollTimer = null;
      setBusyJob(false);
      syncDownloadButtons();
      if (data.error) {
        uiAlert('❌ Proses gagal!\n\n' + normText(data.error), { type: 'error', title: 'Proses gagal', modal: true });
      } else if (data.success_count > 0) {
        showResultModal(data);
      }
    }
  } catch {} finally {
    pollPending = false;
  }
};

const startJob = async () => {
  const url = validateUrl();
  const segs = validateSegments();
  const useGemini = isGeminiSuggestionsOn();
  const payload = {
    url,
    segments: segs,
    crop_mode: $('crop').value,
    use_subtitle: $('subOn').checked,
    review_subtitles: $('subOn').checked && $('reviewSubtitles').checked,
    whisper_model: $('model').value,
    subtitle_language: $('subLang') ? $('subLang').value : 'id',
    subtitle_position: $('subPos').value,
    subtitle_font_name: $('subFont') ? $('subFont').value : 'Arial Black',
    subtitle_font_size: $('subFontSize') ? parseInt($('subFontSize').value || '22', 10) : 22,
    subtitle_font_color: $('subFontColor') ? $('subFontColor').value : '#FFFFFF',
    output_dir: null,
    use_gemini_suggestions: useGemini,
    gemini_api_key: useGemini ? $('geminiKey').value.trim() : null,
  };
  lastJobStatus = null;
  syncDownloadButtons();
  setLog('🚀 Memulai proses...');
  setProgress(0, 'Memulai...', '', true);
  setBusyJob(true, 'Memproses clip...', 'Memulai...');
  const res = await fetch(apiUrl('/api/start'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
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
    const res = await fetch(apiUrl('/api/video_info'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || 'Gagal load info');
    applyVideoInfo(data);
    persistCfg();
  });
};

const waitMainPlayer = async () => {
  for (let i = 0; i < 50; i++) {
    if (mainViewMode === 'shorts') {
      if (mainShortsPlayers.length > 0 && mainShortsPlayers[0]?.getCurrentTime) return true;
    } else {
      if (player && player.getCurrentTime && player.getPlayerState) return true;
    }
    await new Promise((r) => setTimeout(r, 80));
  }
  return false;
};

const loadHeatmap = async () => {
  const url = validateUrl();
  setBusyText('Memeriksa video...', 'Mengambil informasi durasi & metadata video...', 10);

  const tAll0 = performance.now();

  const tInfo0 = performance.now();
  const infoRes = await fetch(apiUrl('/api/video_info'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) });
  
  let infoData;
  const infoText = await infoRes.text();
  try {
    infoData = JSON.parse(infoText);
  } catch (e) {
    throw new Error(`Server error (${infoRes.status}): Gagal mem-parsing response video_info.`);
  }
  
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

  setBusyText('Memindai Heatmap...', 'Mencari titik puncak penonton (Most Replayed)...', 35);

  let heatmapErr = null;
  try {
    const tHm0 = performance.now();
    setBusyText('Memindai Heatmap...', 'Menganalisis kurva Most Replayed dari YouTube...', 50);
    const res = await fetch(apiUrl('/api/heatmap'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, duration_seconds: infoData.duration_seconds, debug: heatmapDebug }),
    });
    
    let data;
    const text = await res.text();
    try {
      data = JSON.parse(text);
    } catch (e) {
      throw new Error(`Server error (${res.status}): Gagal mem-parsing response heatmap.`);
    }
    
    const tHmMs = performance.now() - tHm0;
    if (!data.ok) throw new Error(data.error || 'Gagal load heatmap');
    segments = data.segments || [];
    enforceAllSegments('heatmap');
    if (!segments.length) throw new Error('Heatmap kosong: video ini tidak punya Most Replayed, atau parsing gagal.');
    setBusyText('Menyusun segmen...', 'Menerapkan batas durasi Shorts & sorting...', 90);
    applySorting();
    activeSegIdx = null;
    const tRender0 = performance.now();
    renderSegs();
    setBusyText('Selesai!', 'Segmen berhasil dimuat.', 100);
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
  setBusyText('Backup AI...', 'Memulai analisis transkrip cadangan...', 15);

  try {
    const res = await fetch(apiUrl('/api/ai_segments'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, duration_seconds: infoData.duration_seconds, whisper_model: $('model').value, language: ($('subLang') ? $('subLang').value : 'id') }),
    });
    
    let data;
    const text = await res.text();
    try {
      data = JSON.parse(text);
    } catch (e) {
      throw new Error(`Server error (${res.status}): Gagal mem-parsing response AI segments.`);
    }
    
    if (!data.ok) throw new Error(data.error || 'Gagal memulai job AI segments');
    
    const aiJobId = data.job_id;
    let aiJobDone = false;
    let aiSegments = [];
    
    while (!aiJobDone) {
      await new Promise(r => setTimeout(r, 600));
      const sRes = await fetch(apiUrl('/api/status/') + aiJobId);
      const sData = await sRes.json();
      if (!sData.ok) continue;
      
      const pct = typeof sData.percent === 'number' && sData.percent > 0 ? sData.percent : 20;
      const statusText = sData.status || 'Menganalisis konten video...';
      setBusyText('Backup AI...', statusText, pct);
      
      if (sData.done) {
        aiJobDone = true;
        if (sData.error) throw new Error(sData.error);
        aiSegments = sData.segments || [];
        setBusyText('Backup AI...', 'Menyusun segmen selesai!', 100);
      }
    }
    
    segments = aiSegments;
    enforceAllSegments('AI');
    if (!segments.length) throw new Error('AI segments kosong: transcript tidak cukup jelas, atau analisis gagal.');
    applySorting();
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
    uiAlert('Durasi klip dibatasi maksimal 03:00. End otomatis dipotong di 180 detik dari start.', { type: 'warn', title: 'Durasi dibatasi' });
  }

  segments.push({ enabled: true, start: s, end: end2 });
  applySorting();
  renderSegs();
};

const openModal = () => {
  $('modal').classList.add('on');
};
const closeModal = () => {
  $('modal').classList.remove('on');
};


$('crop').addEventListener('change', () => {
  updateCropPreview();
  if (mainViewMode === 'shorts' && currentVideoId) {
    const ct = getMainCurrentTime();
    initMainShortsPlayer(ct);
  }
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
if ($('subLang')) $('subLang').addEventListener('change', persistCfg);
if ($('subPos')) {
  $('subPos').addEventListener('change', () => {
    updateSubtitlePreview();
    persistCfg();
  });
}
if ($('subFont')) {
  $('subFont').addEventListener('change', () => {
    updateSubtitlePreview();
    persistCfg();
  });
}
if ($('subFontSize')) {
  $('subFontSize').addEventListener('input', () => {
    updateSubtitlePreview();
  });
  $('subFontSize').addEventListener('change', () => {
    updateSubtitlePreview();
    persistCfg();
  });
}
if ($('subFontColor')) {
  $('subFontColor').addEventListener('input', () => {
    updateSubtitlePreview();
  });
  $('subFontColor').addEventListener('change', () => {
    updateSubtitlePreview();
    persistCfg();
  });
}
if ($('subCustomText')) {
  $('subCustomText').addEventListener('input', () => {
    updateSubtitlePreview();
  });
}
if ($('btnCycleSubSample')) {
  $('btnCycleSubSample').addEventListener('click', () => {
    subSampleIndex = (subSampleIndex + 1) % SUB_SAMPLE_TEXTS.length;
    if ($('subCustomText')) $('subCustomText').value = SUB_SAMPLE_TEXTS[subSampleIndex];
    updateSubtitlePreview();
  });
}
document.querySelectorAll('.sub-color-pill').forEach((btn) => {
  btn.addEventListener('click', () => {
    const col = btn.dataset.color;
    if (col && $('subFontColor')) {
      $('subFontColor').value = col;
      updateSubtitlePreview();
      persistCfg();
    }
  });
});
document.querySelectorAll('.sub-size-preset').forEach((btn) => {
  btn.addEventListener('click', () => {
    const sz = btn.dataset.size;
    if (sz && $('subFontSize')) {
      $('subFontSize').value = sz;
      updateSubtitlePreview();
      persistCfg();
    }
  });
});
$('model').addEventListener('change', persistCfg);
$('previewSecs').addEventListener('change', persistCfg);
$('geminiKey').addEventListener('change', () => {
  syncGeminiHint();
  persistCfg();
});
if ($('geminiOn')) {
  $('geminiOn').addEventListener('change', () => {
    syncGeminiHint();
    persistCfg();
  });
}

const showResultModal = (data) => {
  const modal = $('resultModal');
  if (!modal) return;
  
  const subtext = $('resultModalSubtext');
  const grid = $('resultGrid');
  grid.innerHTML = '';
  
  const files = data.files || [];
  if (files.length === 0) {
    uiAlert('Proses selesai tapi tidak ada file hasil.', { type: 'warn' });
    return;
  }
  
  const btnDownloadAll = $('resultBtnDownloadAll');
  if (btnDownloadAll) {
    btnDownloadAll.style.display = files.length > 1 ? 'inline-flex' : 'none';
  }
  
  const aiMap = data.ai_metadata || {};
  const hasAnyAi = Object.keys(aiMap).length > 0;
  
  subtext.textContent = 'Berhasil memproses ' + data.success_count + ' klip. ' + (hasAnyAi ? 'Saran judul clickbait, caption & hashtag dari AI siap disalin!' : 'Anda bisa melihat preview atau mengunduh video di bawah.');
  
  files.forEach((filename, idx) => {
    const url = apiUrl('/api/download/' + jobId + '/' + encodeURIComponent(filename));
    const meta = aiMap[filename];
    
    const card = document.createElement('div');
    card.className = 'result-card';
    
    // Left column: Video preview & download button
    const videoCol = document.createElement('div');
    videoCol.className = 'result-video-col';
    
    const titleEl = document.createElement('div');
    titleEl.className = 'result-item-title';
    titleEl.textContent = 'Clip #' + (idx + 1) + ': ' + filename;
    
    const vid = document.createElement('video');
    vid.controls = true;
    vid.preload = 'metadata';
    vid.src = url;
    
    const btnDl = document.createElement('a');
    btnDl.className = 'btn primary';
    btnDl.href = url;
    btnDl.download = filename;
    btnDl.target = '_blank';
    btnDl.textContent = '⬇ Unduh Klip (MP4)';
    btnDl.style.textAlign = 'center';
    btnDl.style.display = 'block';
    btnDl.style.fontSize = '12px';
    btnDl.style.padding = '8px';
    
    videoCol.appendChild(titleEl);
    videoCol.appendChild(vid);
    videoCol.appendChild(btnDl);
    card.appendChild(videoCol);
    
    // Right column: AI Content (Titles, Caption, Hashtags)
    const metaCol = document.createElement('div');
    metaCol.className = 'result-meta-col';
    
    if (meta && (meta.titles?.length || meta.caption || meta.hashtags?.length)) {
      // Titles block
      if (meta.titles && meta.titles.length) {
        const titleBlock = document.createElement('div');
        titleBlock.className = 'meta-block';
        titleBlock.innerHTML = '<div class="meta-label">💡 Rekomendasi Judul Shorts:</div>';
        
        meta.titles.forEach((t) => {
          const row = document.createElement('div');
          row.className = 'meta-copy-row';
          row.innerHTML = '<span class="meta-text">' + escapeHtml(t) + '</span><button class="btn-copy" type="button">📋 Salin</button>';
          row.querySelector('.btn-copy').addEventListener('click', (e) => {
            navigator.clipboard.writeText(t);
            e.target.textContent = '✅ Disalin!';
            e.target.classList.add('copied');
            setTimeout(() => {
              e.target.textContent = '📋 Salin';
              e.target.classList.remove('copied');
            }, 2000);
          });
          titleBlock.appendChild(row);
        });
        metaCol.appendChild(titleBlock);
      }
      
      // Caption block
      if (meta.caption) {
        const capBlock = document.createElement('div');
        capBlock.className = 'meta-block';
        capBlock.innerHTML = 
          '<div class="meta-header-row">' +
            '<span class="meta-label">📝 Caption Video:</span>' +
            '<button class="btn-copy" type="button">📋 Salin Caption</button>' +
          '</div>' +
          '<div class="meta-box-text">' + escapeHtml(meta.caption) + '</div>';
        
        capBlock.querySelector('.btn-copy').addEventListener('click', (e) => {
          navigator.clipboard.writeText(meta.caption);
          e.target.textContent = '✅ Disalin!';
          e.target.classList.add('copied');
          setTimeout(() => {
            e.target.textContent = '📋 Salin Caption';
            e.target.classList.remove('copied');
          }, 2000);
        });
        metaCol.appendChild(capBlock);
      }
      
      // Hashtags block
      if (meta.hashtags && meta.hashtags.length) {
        const tagStr = meta.hashtags.join(' ');
        const tagBlock = document.createElement('div');
        tagBlock.className = 'meta-block';
        tagBlock.innerHTML = 
          '<div class="meta-header-row">' +
            '<span class="meta-label">🏷️ Hashtags Viral:</span>' +
            '<button class="btn-copy" type="button">📋 Salin Tags</button>' +
          '</div>' +
          '<div class="meta-box-text">' + escapeHtml(tagStr) + '</div>';
        
        tagBlock.querySelector('.btn-copy').addEventListener('click', (e) => {
          navigator.clipboard.writeText(tagStr);
          e.target.textContent = '✅ Disalin!';
          e.target.classList.add('copied');
          setTimeout(() => {
            e.target.textContent = '📋 Salin Tags';
            e.target.classList.remove('copied');
          }, 2000);
        });
        metaCol.appendChild(tagBlock);
      }
    } else {
      const placeholder = document.createElement('div');
      placeholder.className = 'meta-block';
      placeholder.innerHTML = 
        '<div class="meta-label" style="color:var(--muted)">ℹ️ Info AI Metadata:</div>' +
        '<div class="meta-box-text" style="color:var(--muted)">Saran judul clickbait dan caption otomatis tidak diaktifkan pada proses ini. Untuk mengaktifkannya, masukkan Gemini API Key dan pilih opsi "Ya" pada kartu Output & Subtitle sebelum memproses.</div>';
      metaCol.appendChild(placeholder);
    }
    
    card.appendChild(metaCol);
    grid.appendChild(card);
  });
  
  modal.classList.add('on');
};

$('btnShowResult')?.addEventListener('click', () => {
  if (lastJobStatus) showResultModal(lastJobStatus);
});

$('closeResultModal')?.addEventListener('click', () => {
  $('resultModal').classList.remove('on');
  // Stop all videos playing
  $('resultGrid').querySelectorAll('video').forEach(v => { try { v.pause(); } catch {} });
});

$('resultBtnNew')?.addEventListener('click', () => {
  $('resultModal').classList.remove('on');
  $('resultGrid').querySelectorAll('video').forEach(v => { try { v.pause(); } catch {} });
  $('url').value = '';
  segments = [];
  activeSegIdx = null;
  lastJobStatus = null;
  jobId = null;
  setLog('');
  $('bar').style.width = '0%';
  $('status').textContent = 'Idle';
  $('eta').textContent = '';
  syncDownloadButtons();
  renderSegs();
});

$('resultBtnDownloadAll')?.addEventListener('click', () => {
  if (!jobId) return;
  window.location.href = apiUrl('/api/download-zip/' + encodeURIComponent(jobId));
});

$('btnCancelJob')?.addEventListener('click', async () => {
  if (!jobId) return;
  if (!confirm('Yakin ingin membatalkan proses klip yang sedang berjalan?')) return;
  const review = activeCaptionReview;
  const cancelReview = $('cancelCaptionReview');
  const saveReview = $('saveCaptionReview');
  if (review) {
    cancelReview.disabled = true;
    saveReview.disabled = true;
    stopCaptionReviewVideo();
  }
  try {
    $('status').textContent = 'Membatalkan proses...';
    const btnCancel = $('btnCancelJob');
    if (btnCancel) btnCancel.disabled = true;
    const res = await fetch(apiUrl('/api/cancel/' + encodeURIComponent(jobId)), { method: 'POST' });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || 'Gagal membatalkan job.');
    if (review) submittedReviewId = review.reviewId;
    closeCaptionReview();
    uiAlert('Job berhasil dibatalkan.', { type: 'info' });
    void poll();
  } catch (e) {
    if (review && review === activeCaptionReview) {
      captionReviewVideo.src = review.videoUrl;
      $('captionReviewError').textContent = 'Gagal membatalkan job: ' + errText(e);
      cancelReview.disabled = false;
      saveReview.disabled = false;
    } else {
      uiAlert('Gagal membatalkan job: ' + errText(e), { type: 'error' });
    }
  } finally {
    const btnCancel = $('btnCancelJob');
    if (btnCancel) btnCancel.disabled = false;
  }
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
  const over = start !== null && end !== null && end > start && end - start > MAX_CLIP_S;
  $('sStart').classList.toggle('timeInvalid', over);
  $('sEnd').classList.toggle('timeInvalid', over);
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
  const over = start !== null && end !== null && end > start && end - start > MAX_CLIP_S;
  $('segEditStart').classList.toggle('timeInvalid', over);
  $('segEditEnd').classList.toggle('timeInvalid', over);
  if (start !== null && end !== null && end > start) {
    const dur = Math.floor(end - start);
    if (dur >= DUR_WARN_S && dur < DUR_MAX_S) beep();
  }
};

$('sStart').addEventListener('input', () => updateManualDur(false));
$('sEnd').addEventListener('input', () => updateManualDur(false));
$('sStart').addEventListener('change', () => updateManualDur(false));
$('sEnd').addEventListener('change', () => updateManualDur(false));

$('segEditStart').addEventListener('input', (e) => {
  formatMmSsLive(e.target);
  updateSegEditDur(false);
});
$('segEditEnd').addEventListener('input', (e) => {
  formatMmSsLive(e.target);
  updateSegEditDur(false);
});
$('segEditStart').addEventListener('change', (e) => {
  formatMmSsLive(e.target);
  updateSegEditDur(false);
});
$('segEditEnd').addEventListener('change', (e) => {
  formatMmSsLive(e.target);
  updateSegEditDur(false);
});

updateManualDur(false);

$('openYT').addEventListener('click', () => window.open($('url').value.trim() || 'https://youtube.com', '_blank'));
$('loadHeatmap').addEventListener('click', async () => {
  setHeatmapLoading(true);
  try {
    await runWithBusy('Memuat heatmap...', 'Mengambil Most Replayed / backup AI...', loadHeatmap);
  } catch (e) {
    uiAlert(errText(e), { type: 'error' });
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

$('segSortSelect')?.addEventListener('change', (e) => {
  const parts = e.target.value.split('_');
  if (parts.length === 2) {
    currentSortCol = parts[0];
    currentSortDir = parts[1];
    applySorting();
    renderSegs();
  }
});

$('btnToggleSortDir')?.addEventListener('click', () => {
  currentSortDir = currentSortDir === 'asc' ? 'desc' : 'asc';
  applySorting();
  renderSegs();
});

document.querySelectorAll('.th-sortable').forEach((th) => {
  th.addEventListener('click', () => {
    const col = th.dataset.col;
    if (col) handleHeaderSort(col);
  });
});
$('addSeg').addEventListener('click', async () => {
  try {
    await runWithBusy('Menambah segmen...', 'Menyiapkan data video...', async () => {
      if (!durationSec) await loadInfo();
      addSeg();
    });
  } catch (e) {
    uiAlert(errText(e), { type: 'error' });
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
    uiAlert(errText(e), { type: 'error' });
  }
});
$('closeModal').addEventListener('click', closeModal);
$('go').addEventListener('click', async () => {
  try {
    closeModal();
    await startJob();
  } catch (e) {
    uiAlert(errText(e), { type: 'error' });
  }
});

// Removed openFolder event listener

$('timeline').addEventListener('input', () => {
  const v = parseInt($('timeline').value || '0', 10);
  $('tCur').textContent = fmt(v);
  syncRangeFill($('timeline'));
  if (mainViewMode === 'shorts') {
    mainShortsPlayers.forEach((p) => {
      try { p.seekTo(v, true); } catch {}
    });
  } else {
    if (playerReady && player) player.seekTo(v, true);
  }
});

$('play').addEventListener('click', async () => {
  try {
    if (!currentVideoId) await loadInfo();
    if (mainViewMode === 'shorts') {
      if (mainShortsPlayers.length === 0) {
        await initMainShortsPlayer(getMainCurrentTime());
      }
      mainShortsPlaying = !mainShortsPlaying;
      mainShortsPlayers.forEach((p) => {
        try {
          if (mainShortsPlaying) p.playVideo();
          else p.pauseVideo();
        } catch {}
      });
    } else {
      if (!(await waitMainPlayer())) return;
      const st = player.getPlayerState();
      if (st === 1) {
        player.pauseVideo();
        mainShortsPlaying = false;
      } else {
        player.playVideo();
        mainShortsPlaying = true;
      }
    }
  } catch (e) {
    uiAlert(errText(e), { type: 'error' });
  }
});

$('stop').addEventListener('click', async () => {
  try {
    if (!currentVideoId) await loadInfo();
    previewStopAt = null;
    mainShortsPlaying = false;
    if (mainViewMode === 'shorts') {
      mainShortsPlayers.forEach((p) => {
        try {
          p.pauseVideo();
          p.seekTo(0, true);
        } catch {}
      });
    } else {
      if (!(await waitMainPlayer())) return;
      player.pauseVideo();
      player.seekTo(0, true);
    }
    if ($('timeline')) $('timeline').value = '0';
    if ($('tCur')) $('tCur').textContent = '00:00';
    syncRangeFill($('timeline'));
  } catch (e) {
    uiAlert(errText(e), { type: 'error' });
  }
});

$('playPreview').addEventListener('click', async () => {
  try {
    if (!currentVideoId) await loadInfo();
    const s = parseInt(($('previewSecs').value || '30'), 10);
    if (Number.isNaN(s) || s < 5 || s > 600) {
      uiAlert('Preview detik harus 5-600', { type: 'warn' });
      return;
    }
    previewStopAt = s;
    mainShortsPlaying = true;
    if (mainViewMode === 'shorts') {
      if (mainShortsPlayers.length === 0) {
        await initMainShortsPlayer(0);
      } else {
        mainShortsPlayers.forEach((p) => {
          try {
            p.seekTo(0, true);
            p.playVideo();
          } catch {}
        });
      }
    } else {
      if (!(await waitMainPlayer())) return;
      player.seekTo(0, true);
      player.playVideo();
    }
  } catch (e) {
    uiAlert(errText(e), { type: 'error' });
  }
});

$('btnMainViewShorts')?.addEventListener('click', () => setMainViewMode('shorts'));
$('btnMainViewFull')?.addEventListener('click', () => setMainViewMode('full'));
$('btnSimulateShorts')?.addEventListener('click', () => setMainViewMode('shorts'));

$('segEnabled').addEventListener('change', () => {
  if (activeSegIdx === null) return;
  if (!segments[activeSegIdx]) return;
  segments[activeSegIdx].enabled = !!$('segEnabled').checked;
  renderSegs();
  persistCfg();
});

$('btnSegViewShorts')?.addEventListener('click', () => setSegViewMode('shorts'));
$('btnSegViewFull')?.addEventListener('click', () => setSegViewMode('full'));
$('segCloseTop')?.addEventListener('click', () => closeSegModal());

$('segCropModeSelect')?.addEventListener('change', async (e) => {
  const newMode = e.target.value;
  if ($('crop')) $('crop').value = newMode;
  persistCfg();
  updateCropPreview();

  if (segViewMode === 'shorts') {
    const ct = getSegCurrentTime();
    await initSegShortsPlayer(ct);
  }
});

$('btnSegShortsPlayToggle')?.addEventListener('click', () => {
  if (segShortsPlayers.length === 0) return;
  segShortsPlaying = !segShortsPlaying;
  updateSegShortsPlayBtn(segShortsPlaying);
  segShortsPlayers.forEach((p) => {
    try {
      if (segShortsPlaying) p.playVideo();
      else p.pauseVideo();
    } catch {}
  });
});

$('segShortsSlider')?.addEventListener('input', (e) => {
  const val = Number(e.target.value);
  updateSegShortsTimeDisplay(val);
  segShortsPlayers.forEach((p) => {
    try { p.seekTo(val, true); } catch {}
  });
});

$('btnSegShortsReplay')?.addEventListener('click', () => {
  segShortsPlayers.forEach((p) => {
    try { p.seekTo(segStart, true); p.playVideo(); } catch {}
  });
  segShortsPlaying = true;
  updateSegShortsPlayBtn(true);
  updateSegShortsTimeDisplay(segStart);
  if ($('segShortsSlider')) $('segShortsSlider').value = String(segStart);
});

$('segSetStartNow')?.addEventListener('click', () => {
  const ct = getSegCurrentTime();
  $('segEditStart').value = fmt(ct);
  setDurMeter($('durMeterSeg'), ct, parseTime($('segEditEnd').value) || segEnd);
});

$('segSetEndNow')?.addEventListener('click', () => {
  const ct = getSegCurrentTime();
  $('segEditEnd').value = fmt(ct);
  setDurMeter($('durMeterSeg'), parseTime($('segEditStart').value) || segStart, ct);
});

$('segApply')?.addEventListener('click', applySegEdit);

$('segUse')?.addEventListener('click', () => {
  if (activeSegIdx === null) return;
  const s = segments[activeSegIdx];
  if (!s) return;
  $('sStart').value = String(Math.max(0, parseInt(s.start || 0, 10)));
  $('sEnd').value = String(Math.max(0, parseInt(s.end || 0, 10)));
  closeSegModal();
});

$('segClose')?.addEventListener('click', () => {
  closeSegModal();
});

// ==================== UNIFIED MAIN PLAYER ARCHITECTURE ====================
let mainViewMode = 'shorts'; // 'shorts' | 'full'
let mainShortsPlayers = [];
let mainShortsTimer = null;
let mainShortsPlaying = false;

const destroyMainShortsPlayers = () => {
  if (mainShortsTimer) {
    clearInterval(mainShortsTimer);
    mainShortsTimer = null;
  }
  mainShortsPlayers.forEach((p) => {
    try { if (p && p.destroy) p.destroy(); } catch {}
  });
  mainShortsPlayers = [];
  const c = $('mainShortsContainer');
  if (c) c.innerHTML = '';
};

const destroyMainFullPlayer = () => {
  try {
    if (player && player.destroy) player.destroy();
  } catch {}
  player = null;
  playerReady = false;
  const holder = $('player');
  if (holder) holder.innerHTML = '';
};

const getMainCurrentTime = () => {
  if (mainViewMode === 'full') {
    if (player && player.getCurrentTime) {
      try { return Math.floor(player.getCurrentTime() || 0); } catch {}
    }
  } else {
    if (mainShortsPlayers.length > 0 && mainShortsPlayers[0]?.getCurrentTime) {
      try { return Math.floor(mainShortsPlayers[0].getCurrentTime() || 0); } catch {}
    }
  }
  const tl = $('timeline');
  return tl ? parseInt(tl.value || '0', 10) : 0;
};

const initMainShortsPlayer = async (startTime) => {
  destroyMainShortsPlayers();
  if (!currentVideoId) return;
  await ensureYTApi();

  const c = $('mainShortsContainer');
  if (!c) return;
  c.innerHTML = '';

  const mode = ($('crop')?.value || 'default').trim();
  const startAt = startTime !== undefined ? Math.floor(startTime) : (parseInt($('timeline')?.value || '0', 10) || 0);

  const createPlayer = (boxClass, ifClass, isMuted) => {
    const box = document.createElement('div');
    box.className = `shorts-crop-box ${boxClass}`;

    const ifHolder = document.createElement('div');
    ifHolder.className = `shorts-iframe ${ifClass}`;
    box.appendChild(ifHolder);
    c.appendChild(box);

    const p = new YT.Player(ifHolder, {
      videoId: currentVideoId,
      playerVars: {
        autoplay: mainShortsPlaying ? 1 : 0,
        controls: 0,
        rel: 0,
        modestbranding: 1,
        fs: 0,
        disablekb: 1,
        start: startAt,
        mute: isMuted ? 1 : 0
      },
      events: {
        onReady: (e) => {
          const iframe = e.target.getIframe();
          if (iframe) iframe.className = `shorts-iframe ${ifClass}`;
          try { e.target.seekTo(startAt, true); } catch {}
          if (mainShortsPlaying) {
            try { e.target.playVideo(); } catch {}
          }
          if (!isMuted) {
            try { e.target.unMute(); } catch {}
          }
        },
        onStateChange: (e) => {
          if (e.data === YT.PlayerState.PLAYING) {
            mainShortsPlaying = true;
          } else if (e.data === YT.PlayerState.PAUSED) {
            mainShortsPlaying = false;
          } else if (e.data === YT.PlayerState.ENDED) {
            mainShortsPlaying = false;
            mainShortsPlayers.forEach((pl) => {
              try { pl.seekTo(0, true); pl.pauseVideo(); } catch {}
            });
            if ($('timeline')) $('timeline').value = '0';
            if ($('tCur')) $('tCur').textContent = '00:00';
            syncRangeFill($('timeline'));
          }
        }
      }
    });
    mainShortsPlayers.push(p);
    return p;
  };

  if (mode === 'split_left' || mode === 'split_right') {
    createPlayer('shorts-box-top', 'shorts-if-top', false);
    createPlayer('shorts-box-bottom', mode === 'split_left' ? 'shorts-if-bottom-left' : 'shorts-if-bottom-right', true);
  } else if (mode === 'split_podcast') {
    createPlayer('shorts-box-podcast-top', 'shorts-if-podcast-top', false);
    createPlayer('shorts-box-podcast-bottom', 'shorts-if-podcast-bottom', true);
  } else if (mode === 'podcast_speaker') {
    createPlayer('shorts-box-podcast-speaker', 'shorts-if-podcast-speaker', false);
  } else if (mode === 'fit') {
    createPlayer('shorts-box-fit', 'shorts-if-fit', false);
  } else {
    createPlayer('shorts-box-default', 'shorts-if-default', false);
  }

  if (mainShortsTimer) clearInterval(mainShortsTimer);
  mainShortsTimer = setInterval(() => {
    if (mainShortsPlayers.length === 0) return;
    const p0 = mainShortsPlayers[0];
    if (!p0 || !p0.getCurrentTime) return;
    try {
      const ct = p0.getCurrentTime();
      const tl = $('timeline');
      if (tl && !tl.matches(':active')) {
        tl.value = String(Math.floor(ct));
        syncRangeFill(tl);
        if ($('tCur')) $('tCur').textContent = fmt(ct);
      }
      if (previewStopAt !== null && ct >= previewStopAt) {
        mainShortsPlayers.forEach((pl) => { try { pl.pauseVideo(); } catch {} });
        mainShortsPlaying = false;
        previewStopAt = null;
      }
    } catch {}
  }, 200);

  updateSubtitlePreview();
};

const initMainFullPlayer = async (startTime) => {
  destroyMainFullPlayer();
  if (!currentVideoId) return;
  await ensureYTApi();

  const startAt = startTime !== undefined ? Math.floor(startTime) : (parseInt($('timeline')?.value || '0', 10) || 0);

  player = new YT.Player('player', {
    height: '100%',
    width: '100%',
    videoId: currentVideoId,
    playerVars: { controls: 1, rel: 0, modestbranding: 1, fs: 1, start: startAt },
    events: {
      onReady: (e) => {
        playerReady = true;
        try { e.target.setPlaybackQuality('large'); } catch {}
        try { e.target.seekTo(startAt, true); } catch {}
        if (mainShortsPlaying) {
          try { e.target.playVideo(); } catch {}
        }
        const tick = () => {
          try {
            if (!player || mainViewMode !== 'full') return;
            const ct = player.getCurrentTime ? player.getCurrentTime() : 0;
            const tl = $('timeline');
            if (tl && !tl.matches(':active')) {
              tl.value = String(Math.floor(ct));
              syncRangeFill(tl);
              if ($('tCur')) $('tCur').textContent = fmt(ct);
            }
            if (previewStopAt !== null && ct >= previewStopAt) {
              player.pauseVideo();
              previewStopAt = null;
            }
          } catch {}
          if (mainViewMode === 'full') requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      },
      onStateChange: (e) => {
        if (e.data === YT.PlayerState.PLAYING) {
          mainShortsPlaying = true;
        } else if (e.data === YT.PlayerState.PAUSED) {
          mainShortsPlaying = false;
        }
      }
    },
  });

  updateCropPreview();
  updateSubtitlePreview();
};

const setMainViewMode = async (mode) => {
  if (mode === mainViewMode) return;
  const currentCt = getMainCurrentTime();
  mainViewMode = mode;

  const btnShorts = $('btnMainViewShorts');
  const btnFull = $('btnMainViewFull');
  const viewShorts = $('mainShortsView');
  const viewFull = $('mainFullView');

  if (btnShorts) btnShorts.classList.toggle('active', mode === 'shorts');
  if (btnFull) btnFull.classList.toggle('active', mode === 'full');

  if (mode === 'shorts') {
    if (viewShorts) viewShorts.style.display = 'flex';
    if (viewFull) viewFull.style.display = 'none';
    destroyMainFullPlayer();
    await initMainShortsPlayer(currentCt);
  } else {
    if (viewShorts) viewShorts.style.display = 'none';
    if (viewFull) viewFull.style.display = 'block';
    destroyMainShortsPlayers();
    await initMainFullPlayer(currentCt);
  }
  updateSubtitlePreview();
};

window.onYouTubeIframeAPIReady = function () {
  playerReady = true;
};

const loadPlayer = (videoId, startTime = 0) => {
  currentVideoId = videoId;
  ensureYTApi().then(() => {
    if (mainViewMode === 'shorts') {
      initMainShortsPlayer(startTime);
    } else {
      initMainFullPlayer(startTime);
    }
  });
};


async function refreshCookiesStatus() {
  const badge = $('cookieBadge');
  const msg = $('cookieStatusMsg');
  const delBtn = $('deleteCookieBtn');
  if (!badge) return;

  try {
    const res = await fetch(apiUrl('/api/cookies'));
    const data = await res.json();
    if (!data.ok || !data.status) throw new Error('Status tidak valid');
    const st = data.status;

    if (st.installed) {
      badge.textContent = `✅ Terpasang (${st.line_count} cookies)`;
      badge.style.background = 'rgba(34, 197, 94, 0.2)';
      badge.style.color = '#4ade80';
      badge.style.border = '1px solid rgba(34, 197, 94, 0.4)';
      if (msg) {
        const kb = (st.size_bytes / 1024).toFixed(1);
        msg.textContent = `File: ${st.path} (${kb} KB, ${st.line_count} baris). Siap digunakan untuk download di server.`;
      }
      if (delBtn) delBtn.style.display = 'inline-block';
    } else {
      badge.textContent = '⚠️ Belum Terpasang';
      badge.style.background = 'rgba(245, 158, 11, 0.2)';
      badge.style.color = '#fbbf24';
      badge.style.border = '1px solid rgba(245, 158, 11, 0.4)';
      if (msg) {
        msg.textContent = 'Belum ada cookies.txt. Server VPS/Docker butuh cookies agar download YouTube tidak diblokir bot check.';
      }
      if (delBtn) delBtn.style.display = 'none';
    }
  } catch (err) {
    badge.textContent = '❓ Gagal Cek';
    badge.style.background = 'rgba(239, 68, 68, 0.2)';
    badge.style.color = '#f87171';
    if (msg) msg.textContent = 'Gagal memuat status cookies: ' + err.message;
    if (delBtn) delBtn.style.display = 'none';
  }
}

async function saveCookiesToServer(content) {
  try {
    const res = await fetch(apiUrl('/api/cookies'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cookies: content }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || data.detail || 'Gagal menyimpan cookies');
    uiAlert(data.message || 'Cookies berhasil disimpan!', { type: 'success' });
    await refreshCookiesStatus();
  } catch (err) {
    uiAlert('Gagal simpan cookies: ' + err.message, { type: 'error' });
  }
}

function initCookiesManager() {
  const uploadBtn = $('uploadCookieBtn');
  const fileInput = $('cookieFileInput');
  const pasteBtn = $('pasteCookieBtn');
  const deleteBtn = $('deleteCookieBtn');
  const helpBtn = $('cookieHelpBtn');

  if (uploadBtn && fileInput) {
    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async (evt) => {
        const text = evt.target.result;
        await saveCookiesToServer(text);
        fileInput.value = '';
      };
      reader.readAsText(file);
    });
  }

  if (pasteBtn) {
    pasteBtn.addEventListener('click', async () => {
      const Swal = window.Swal;
      if (!Swal) {
        const text = prompt('Paste teks Netscape cookies.txt di sini:');
        if (text) await saveCookiesToServer(text);
        return;
      }
      const { value: text } = await Swal.fire({
        title: 'Paste Isi cookies.txt',
        input: 'textarea',
        inputLabel: 'Paste teks cookies format Netscape (dimulai dari # Netscape HTTP Cookie File atau baris domain):',
        inputPlaceholder: '# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t...',
        showCancelButton: true,
        confirmButtonText: 'Simpan Cookies',
        cancelButtonText: 'Batal',
        confirmButtonColor: '#8b5cf6',
        background: '#111824',
        color: '#e8edf2',
      });
      if (text) {
        await saveCookiesToServer(text);
      }
    });
  }

  if (deleteBtn) {
    deleteBtn.addEventListener('click', async () => {
      const Swal = window.Swal;
      let confirmed = false;
      if (Swal) {
        const res = await Swal.fire({
          title: 'Hapus cookies.txt?',
          text: 'Setelah dihapus, server production mungkin akan diblokir oleh YouTube dengan bot check.',
          icon: 'warning',
          showCancelButton: true,
          confirmButtonText: 'Ya, Hapus',
          cancelButtonText: 'Batal',
          confirmButtonColor: '#ef4444',
          background: '#111824',
          color: '#e8edf2',
        });
        confirmed = res.isConfirmed;
      } else {
        confirmed = confirm('Yakin ingin menghapus cookies.txt?');
      }

      if (!confirmed) return;

      try {
        const res = await fetch(apiUrl('/api/cookies'), { method: 'DELETE' });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || 'Gagal menghapus cookies');
        uiAlert('Cookies YouTube berhasil dihapus', { type: 'success' });
        await refreshCookiesStatus();
      } catch (err) {
        uiAlert('Gagal menghapus cookies: ' + err.message, { type: 'error' });
      }
    });
  }

  if (helpBtn) {
    helpBtn.addEventListener('click', () => {
      const Swal = window.Swal;
      const htmlContent = `
        <div style="text-align:left; font-size:13px; line-height:1.6; color:#e4e4e7;">
          <p><strong>Kenapa butuh cookies?</strong><br>
          YouTube memblokir IP server Datacenter (VPS) dengan pesan <em>"Sign in to confirm you're not a bot"</em>. Cookies membuktikan bahwa request berasal dari akun terverifikasi.</p>
          <hr style="border-color:rgba(255,255,255,0.1); margin:10px 0;">
          <p><strong>Langkah mendapatkan cookies.txt:</strong></p>
          <ol style="padding-left:18px; margin:0 0 10px 0;">
            <li>Pasang ekstensi browser di Chrome / Firefox:
              <br>• <strong>Get cookies.txt LOCALLY</strong> atau <strong>Cookie-Editor</strong>
            </li>
            <li>Buka <a href="https://www.youtube.com" target="_blank" style="color:#a78bfa;">youtube.com</a> (pastikan sudah login akun YouTube).</li>
            <li>Klik icon ekstensi tersebut, lalu pilih <strong>Export</strong> (format Netscape HTTP Cookie File).</li>
            <li>Upload file <code>cookies.txt</code> tersebut menggunakan tombol <strong>Upload cookies.txt</strong> atau <strong>Paste Teks</strong> di sini.</li>
          </ol>
          <p style="font-size:12px; color:#94a3b8; margin:0;">💡 <em>Tips:</em> Gunakan akun YouTube sekunder/cadangan jika tidak ingin menggunakan akun utama.</p>
        </div>
      `;
      if (Swal) {
        Swal.fire({
          title: '🍪 Panduan YouTube Cookies',
          html: htmlContent,
          confirmButtonText: 'Mengerti',
          confirmButtonColor: '#8b5cf6',
          background: '#111824',
          color: '#e8edf2',
          width: 520,
        });
      } else {
        alert("Panduan cookies:\n1. Buka youtube.com di browser dan login\n2. Gunakan ekstensi 'Get cookies.txt LOCALLY' untuk export cookies.txt\n3. Upload file cookies.txt ke sini.");
      }
    });
  }

  refreshCookiesStatus();
}

(async () => {
  const serverCfg = await fetch(apiUrl('/api/config')).then((r) => r.json()).catch(() => ({}));
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
  
  // Clean up old output files
  fetch(apiUrl('/api/clean'), { method: 'POST' }).catch(() => {});
  initCookiesManager();
})();
