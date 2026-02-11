HTML = r"""
<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>YTClipper</title>
  <meta name="application-name" content="YTClipper" />
  <meta name="apple-mobile-web-app-title" content="YTClipper" />
  <meta name="theme-color" content="#0b0f14" />
  <link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%2024%2024%22%3E%3Crect%20x%3D%223%22%20y%3D%225%22%20width%3D%2218%22%20height%3D%2214%22%20rx%3D%223%22%20fill%3D%22%23111824%22%20stroke%3D%22%2348d0ff%22%20stroke-width%3D%221.6%22/%3E%3Cpath%20d%3D%22M10%209v6l6-3z%22%20fill%3D%22%2348d0ff%22/%3E%3C/svg%3E" />
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; background: #0b0f14; color: #e8edf2; }
    .wrap { max-width: 920px; margin: 0 auto; padding: 18px; }
    .grid { display: flex; flex-direction: column; gap: 14px; }
    .card { background: #111824; border: 1px solid #1f2a3a; border-radius: 12px; padding: 14px; }
    .card h2 { margin: 0 0 10px 0; font-size: 16px; display: flex; align-items: center; gap: 10px; }
    label { display: block; font-size: 12px; color: #b8c6d6; margin-bottom: 6px; }
    input[type="text"], input[type="number"], select { width: 100%; box-sizing: border-box; padding: 10px 10px; border-radius: 10px; border: 1px solid #253246; background: #0b111a; color: #e8edf2; }
    .row { display: flex; gap: 10px; align-items: flex-start; flex-wrap: wrap; }
    .row > * { flex: 1 1 200px; min-width: 0; }
    .btn { padding: 10px 12px; border-radius: 10px; border: 1px solid #2a3b56; background: #132033; color: #e8edf2; cursor: pointer; transition: background 150ms ease, border-color 150ms ease, transform 150ms ease, box-shadow 150ms ease; }
    .btn:hover { background: #162844; border-color: #3a5378; }
    .btn:active { transform: translateY(1px); }
    .btn:disabled { opacity: 0.55; cursor: not-allowed; }
    .btn.primary { background: linear-gradient(90deg, #2b5cff, #48d0ff); border-color: rgba(72,208,255,0.55); box-shadow: 0 10px 26px rgba(43,92,255,0.18); }
    .btn.primary:hover { box-shadow: 0 10px 30px rgba(72,208,255,0.18); border-color: rgba(72,208,255,0.9); }
    .btn.danger { background: linear-gradient(90deg, #b4232a, #e14a52); border-color: rgba(225,74,82,0.5); box-shadow: 0 10px 26px rgba(225,74,82,0.12); }
    .btn.danger:hover { border-color: rgba(225,74,82,0.9); box-shadow: 0 10px 30px rgba(225,74,82,0.14); }
    .muted { color: #a7b7c9; font-size: 12px; }
    .btnLabel { display: inline-flex; align-items: center; justify-content: center; gap: 10px; }
    .spinner { width: 14px; height: 14px; border-radius: 999px; border: 2px solid #2a3b56; border-top-color: transparent; animation: spin 0.85s linear infinite; display: none; flex: 0 0 auto; }
    .ico { width: 16px; height: 16px; display: inline-block; flex: 0 0 auto; }
    .divider { height: 1px; background: #1f2a3a; margin: 14px 0; }
    .sectionTitle { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #cfe0f1; font-weight: 650; margin: 0 0 8px 0; }
    @keyframes spin { to { transform: rotate(360deg); } }
    input[type="range"] { width: 100%; margin: 0; -webkit-appearance: none; appearance: none; height: 14px; background: transparent; }
    input[type="range"]:focus { outline: none; }
    input[type="range"]::-webkit-slider-runnable-track { height: 14px; border-radius: 999px; background: linear-gradient(90deg, #2b5cff 0%, #2b5cff var(--pct, 0%), #0b111a var(--pct, 0%), #0b111a 100%); border: 1px solid #1f2a3a; }
    input[type="range"]::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 22px; height: 22px; margin-top: -5px; border-radius: 999px; background: #e8edf2; border: 2px solid #2b5cff; box-shadow: 0 0 0 4px rgba(43,92,255,0.18); }
    input[type="range"]::-moz-range-track { height: 14px; border-radius: 999px; background: #0b111a; border: 1px solid #1f2a3a; }
    input[type="range"]::-moz-range-progress { height: 14px; border-radius: 999px; background: #2b5cff; }
    input[type="range"]::-moz-range-thumb { width: 22px; height: 22px; border-radius: 999px; background: #e8edf2; border: 2px solid #2b5cff; box-shadow: 0 0 0 4px rgba(43,92,255,0.18); }
    .player { width: 100%; aspect-ratio: 16/9; border-radius: 12px; overflow: hidden; border: 1px solid #1f2a3a; background: #0b111a; position: relative; }
    .player iframe { width: 100%; height: 100%; border: 0; }
    .cropOverlay { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; opacity: 0; transition: opacity 120ms ease; }
    .cropOverlay.on { opacity: 1; }
    .seglist { width: 100%; border-collapse: collapse; font-size: 13px; }
    .seglist th, .seglist td { padding: 8px 6px; border-bottom: 1px solid #1f2a3a; }
    .seglist th { text-align: left; color: #b8c6d6; font-weight: 600; }
    .seglist tr.activeSeg { background: rgba(43, 92, 255, 0.12); }
    .progress { height: 18px; background: #0b111a; border: 1px solid #1f2a3a; border-radius: 999px; overflow: hidden; position: relative; }
    .bar {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #2b5cff 0%, #48d0ff 50%, #2b5cff 100%);
      background-size: 200% 100%;
      transition: width 300ms ease;
      position: relative;
    }
    .bar.active {
      animation: wave 1.5s ease-in-out infinite;
    }
    @keyframes wave {
      0% { background-position: 100% 0; }
      100% { background-position: -100% 0; }
    }
    .bar::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.2) 50%, transparent 100%);
      background-size: 50% 100%;
      animation: shimmer 1.2s ease-in-out infinite;
    }
    @keyframes shimmer {
      0% { background-position: -100% 0; }
      100% { background-position: 200% 0; }
    }
    .bar:not(.active)::after { animation: none; opacity: 0; }
    #log { margin-top: 10px; }
    #log:empty { display: none; }
    pre { white-space: pre-wrap; word-wrap: break-word; background: #0b111a; border: 1px solid #1f2a3a; border-radius: 12px; padding: 10px; height: 220px; overflow: auto; }
    .summary { background: #0b111a; border: 1px solid #1f2a3a; border-radius: 12px; padding: 12px; max-height: 320px; overflow: auto; }
    .summaryTop { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .summaryKv { background: #0f1622; border: 1px solid #1f2a3a; border-radius: 12px; padding: 10px; min-width: 0; }
    .summaryK { color: #a7b7c9; font-size: 12px; margin: 0 0 6px 0; }
    .summaryV { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; word-break: break-word; }
    .summaryH { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 12px 0 8px 0; }
    .summaryH .t { font-size: 13px; color: #cfe0f1; font-weight: 650; }
    .summaryH .s { color: #a7b7c9; font-size: 12px; }
    .summaryTable { width: 100%; border-collapse: collapse; font-size: 13px; border: 1px solid #1f2a3a; border-radius: 12px; overflow: hidden; }
    .summaryTable th, .summaryTable td { padding: 8px 8px; border-bottom: 1px solid #1f2a3a; }
    .summaryTable th { text-align: left; color: #b8c6d6; font-weight: 600; background: rgba(255,255,255,0.03); }
    .summaryTable tr:last-child td { border-bottom: 0; }
    .summaryFoot { margin-top: 10px; display: flex; gap: 10px; justify-content: space-between; flex-wrap: wrap; color: #a7b7c9; font-size: 12px; }
    .modal { position: fixed; inset: 0; display: none; align-items: flex-start; justify-content: center; padding: 16px; background: rgba(0,0,0,0.65); overflow: auto; }
    .modal.on { display: flex; }
    .modal .box { width: min(980px, 100%); background: #111824; border: 1px solid #1f2a3a; border-radius: 14px; padding: 14px; max-height: calc(100vh - 32px); overflow-y: auto; overflow-x: hidden; box-sizing: border-box; }
    .modal .box h3 { margin: 0 0 10px 0; }
    .busy { position: fixed; inset: 0; display: none; align-items: center; justify-content: center; padding: 16px; background: rgba(0,0,0,0.65); z-index: 9999; }
    .busy.on { display: flex; }
    .busy .box { width: min(520px, 100%); background: #111824; border: 1px solid #1f2a3a; border-radius: 14px; padding: 16px; box-sizing: border-box; }
    .busyTop { display: flex; align-items: center; gap: 12px; }
    .busyTitle { font-size: 14px; font-weight: 700; color: #cfe0f1; }
    .busyMsg { margin-top: 2px; font-size: 12px; color: #b8c6d6; }
    .spinner.big { width: 34px; height: 34px; border-width: 3px; display: inline-block; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
    @media (max-width: 720px) { .summaryTop { grid-template-columns: 1fr; } }
    @media (max-width: 900px) { .wrap { max-width: 100%; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="grid">
      <div class="card">
        <h2>
          <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="3" y="5" width="18" height="14" rx="2"></rect>
            <path d="M10 9l5 3-5 3V9z"></path>
          </svg>
          Video & Heatmap
        </h2>
        <div class="muted" style="margin:-6px 0 12px 0">Tempel URL, lalu ambil Most Replayed untuk auto-segmen (inti auto-clipper).</div>
        <label title="Tempel link YouTube (watch/shorts/youtu.be).">YouTube URL</label>
        <input id="url" type="text" placeholder="https://www.youtube.com/watch?v=..." />
        <div style="height:10px"></div>
        <div class="row">
          <button class="btn" id="openYT" title="Buka link di tab baru.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M14 3h7v7"></path>
                <path d="M10 14L21 3"></path>
                <path d="M21 14v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h6"></path>
              </svg>
              <span>Open</span>
            </span>
          </button>
          <button class="btn primary" id="loadHeatmap" title="Ambil segmen otomatis dari Most Replayed.">
            <span class="btnLabel">
              <span class="spinner" id="heatmapSpin"></span>
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M3 12h6l3-9 3 18 3-9h3"></path>
              </svg>
              <span id="heatmapText">Load Heatmap</span>
            </span>
          </button>
        </div>
        <div style="height:10px"></div>
        <div class="muted" id="info">Durasi: -</div>
        <div style="height:12px"></div>
        <div class="player">
          <div id="player"></div>
          <svg id="mainCropOverlay" class="cropOverlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"></svg>
        </div>
        <div style="height:10px"></div>
        <div class="row">
          <button class="btn" id="play" title="Play/Pause preview.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M8 5v14l11-7z"></path>
              </svg>
              <span>Play/Pause</span>
            </span>
          </button>
          <button class="btn" id="stop" title="Stop dan kembali ke 0.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="7" y="7" width="10" height="10" rx="2"></rect>
              </svg>
              <span>Stop</span>
            </span>
          </button>
          <input id="previewSecs" type="number" min="5" max="600" step="1" title="Preview pertama N detik." />
          <button class="btn" id="playPreview" title="Mainkan dari 0 sampai preview detik.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M22 12a10 10 0 1 1-3-7.2"></path>
                <path d="M22 4v6h-6"></path>
              </svg>
              <span>Play Preview</span>
            </span>
          </button>
        </div>
        <div style="height:10px"></div>
        <label title="Timeline untuk navigasi preview.">Timeline</label>
        <input id="timeline" type="range" min="0" max="0" value="0" />
        <div class="muted"><span id="tCur">00:00</span> / <span id="tDur">00:00</span></div>

        <div class="divider"></div>
        <div class="sectionTitle">
          <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M4 19V5"></path>
            <path d="M4 19h16"></path>
            <path d="M7 15l3-3 3 3 6-8"></path>
          </svg>
          Segmen Otomatis (Most Replayed)
        </div>
        <div class="muted" style="margin:-4px 0 10px 0">Preview/edit per segmen sebelum diproses. Tombol Preview akan membuka modal untuk adjust start/end.</div>
        <div class="row" style="margin:0 0 10px 0">
          <button class="btn" id="segSelectAll" title="Aktifkan semua segmen." disabled>
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M9 11l3 3L22 4"></path>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
              </svg>
              <span>Select All</span>
            </span>
          </button>
          <button class="btn" id="segDeselectAll" title="Nonaktifkan semua segmen." disabled>
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M18 6L6 18"></path>
                <path d="M6 6l12 12"></path>
              </svg>
              <span>Deselect All</span>
            </span>
          </button>
          <div class="muted" id="segPickInfo" style="text-align:right;flex:1"></div>
        </div>
        <table class="seglist" id="segTable">
          <thead><tr><th style="width:40px">On</th><th>Start</th><th>End</th><th>Dur</th><th style="width:64px">Score</th><th style="width:130px">Aksi</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>

      <div class="card">
        <h2>
          <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 1v2"></path>
            <path d="M12 21v2"></path>
            <path d="M4.2 4.2l1.4 1.4"></path>
            <path d="M18.4 18.4l1.4 1.4"></path>
            <path d="M1 12h2"></path>
            <path d="M21 12h2"></path>
            <path d="M4.2 19.8l1.4-1.4"></path>
            <path d="M18.4 5.6l1.4-1.4"></path>
            <circle cx="12" cy="12" r="4"></circle>
          </svg>
          Output & Subtitle
        </h2>
        <div class="muted" style="margin:-6px 0 12px 0">Atur folder output, mode crop, dan opsi subtitle.</div>
        <label title="Default: ~/Videos/ClipAI atau custom path di PC ini.">Lokasi Output</label>
        <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
          <label style="display:flex;gap:6px;align-items:center;white-space:nowrap;flex:0 0 auto;" title="Pakai default folder."><input type="radio" name="outMode" value="default" checked /> Default</label>
          <label style="display:flex;gap:6px;align-items:center;white-space:nowrap;flex:0 0 auto;" title="Tulis path folder custom."><input type="radio" name="outMode" value="custom" /> Custom</label>
          <input id="outDir" type="text" placeholder="C:\\path\\to\\folder" title="Folder output di mesin ini." style="flex:1;min-width:200px;" />
        </div>
        <div style="height:10px"></div>
        <div class="row" style="align-items:flex-end;">
          <div style="flex:0 0 160px;">
            <label title="default=middle crop, split untuk facecam bawah.">Crop Mode</label>
            <select id="crop">
              <option value="default">default</option>
              <option value="split_left">split_left</option>
              <option value="split_right">split_right</option>
            </select>
            <label style="display:flex;gap:8px;align-items:center;margin-top:10px;white-space:nowrap;" title="Tampilkan overlay perkiraan area crop di preview."><input id="cropPrev" type="checkbox" checked /> Preview crop</label>
          </div>
          <div style="flex:1;min-width:280px;">
            <label title="Aktifkan subtitle AI (butuh download model).">Subtitle</label>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
              <label style="display:flex;gap:6px;align-items:center;white-space:nowrap;"><input id="subOn" type="checkbox" /> ON</label>
              <select id="model" title="Ukuran model Faster-Whisper." style="flex:1;min-width:100px;">
                <option>tiny</option>
                <option>base</option>
                <option selected>small</option>
                <option>medium</option>
                <option>large-v3</option>
              </select>
              <select id="subPos" title="Posisi subtitle: bawah / tengah / atas." style="flex:0 0 90px;">
                <option value="bottom">Bawah</option>
                <option value="middle" selected>Tengah</option>
                <option value="top">Atas</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <h2>
          <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 5v14"></path>
            <path d="M5 12h14"></path>
          </svg>
          Tambah Segmen Manual
        </h2>
        <div class="muted" style="margin:-6px 0 12px 0">Kalau mau klip bagian tertentu, isi start/end lalu Tambah. Segmen akan muncul di tabel Segmen.</div>
        <label title="Rentang waktu klip manual (detik).">Start / End (manual)</label>
        <div class="row">
          <input id="sStart" type="number" min="0" step="1" title="Start detik." />
          <input id="sEnd" type="number" min="0" step="1" title="End detik." />
        </div>
        <div style="height:10px"></div>
        <div class="row">
          <button class="btn" id="addSeg" title="Tambah segmen manual dari input start/end.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M12 5v14"></path>
                <path d="M5 12h14"></path>
              </svg>
              <span>Tambah</span>
            </span>
          </button>
          <button class="btn danger" id="clearSeg" title="Hapus semua segmen.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M3 6h18"></path>
                <path d="M8 6V4h8v2"></path>
                <path d="M19 6l-1 14H6L5 6"></path>
                <path d="M10 11v6"></path>
                <path d="M14 11v6"></path>
              </svg>
              <span>Clear</span>
            </span>
          </button>
        </div>
      </div>

      <div class="card">
        <h2>
          <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 2l1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8L12 2z"></path>
            <path d="M19 14l.9 2.6L22 18l-2.1.7L19 21l-.9-2.3L16 18l2.1-.7L19 14z"></path>
          </svg>
          Proses
        </h2>
        <div class="muted" style="margin:-6px 0 12px 0">Review dulu ringkasan, lalu proses. Progress dan log tampil di bawah.</div>
        <div class="row">
          <button class="btn primary" id="review" title="Tampilkan ringkasan dan konfirmasi sebelum proses.">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M9 11l3 3L22 4"></path>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
              </svg>
              <span>Review & Proses</span>
            </span>
          </button>
          <button class="btn" id="openFolder" title="Buka folder output (hasil clip)." style="display:none">
            <span class="btnLabel">
              <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M3 7h6l2 2h10v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"></path>
                <path d="M3 7V5a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2"></path>
              </svg>
              <span>Lihat Folder</span>
            </span>
          </button>
        </div>
        <div style="height:12px"></div>
        <div class="progress"><div class="bar" id="bar"></div></div>
        <div class="row" style="margin-top:8px">
          <div class="muted" id="status">Idle</div>
          <div class="muted" id="eta" style="text-align:right"></div>
        </div>
        <pre id="log" class="mono"></pre>
      </div>
    </div>
  </div>

  <div class="modal" id="modal">
    <div class="box">
      <h3>Konfirmasi</h3>
      <div id="summary" class="summary"></div>
      <div class="row">
        <button class="btn" id="closeModal">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <path d="M7 10l5 5 5-5"></path>
              <path d="M12 15V3"></path>
            </svg>
            <span>Ubah Settings</span>
          </span>
        </button>
        <button class="btn primary" id="go">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M8 5v14l11-7z"></path>
            </svg>
            <span>Proses Sekarang</span>
          </span>
        </button>
      </div>
    </div>
  </div>

  <div class="modal" id="segModal">
    <div class="box">
      <h3>Preview Heatmap</h3>
      <div class="muted" id="segMeta"></div>
      <div style="height:10px"></div>
      <div class="player">
        <div id="segPlayer"></div>
        <svg id="segCropOverlay" class="cropOverlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"></svg>
      </div>
      <div style="height:10px"></div>
      <div class="row">
        <label style="display:flex;gap:8px;align-items:center;justify-content:flex-end" title="Aktif/nonaktif segmen ini untuk diproses.">
          <input id="segEnabled" type="checkbox" />
          Enable segmen
        </label>
      </div>
      <div style="height:12px"></div>
      <h3 style="margin:0 0 10px 0">Edit Segment</h3>
      <div class="row">
        <div>
          <label title="Format: detik (123) atau MM:SS atau HH:MM:SS">Start</label>
          <input id="segEditStart" type="text" placeholder="MM:SS" />
        </div>
        <div>
          <label title="Format: detik (123) atau MM:SS atau HH:MM:SS">End</label>
          <input id="segEditEnd" type="text" placeholder="MM:SS" />
        </div>
      </div>
      <div style="height:10px"></div>
      <div class="row">
        <button class="btn" id="segSetStartNow" title="Set start = posisi player saat ini.">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 8v8"></path>
              <path d="M8 12h8"></path>
              <circle cx="12" cy="12" r="10"></circle>
            </svg>
            <span>Set Start = Now</span>
          </span>
        </button>
        <button class="btn" id="segSetEndNow" title="Set end = posisi player saat ini.">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 7v10"></path>
              <path d="M8 12h8"></path>
              <path d="M12 2a10 10 0 1 1 0 20"></path>
            </svg>
            <span>Set End = Now</span>
          </span>
        </button>
        <button class="btn primary" id="segApply" title="Terapkan perubahan start/end ke segmen.">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M9 11l3 3L22 4"></path>
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
            </svg>
            <span>Apply</span>
          </span>
        </button>
      </div>
      <div style="height:12px"></div>
      <div class="row">
        <button class="btn" id="segClose">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M18 6L6 18"></path>
              <path d="M6 6l12 12"></path>
            </svg>
            <span>Tutup</span>
          </span>
        </button>
        <button class="btn primary" id="segUse" title="Pakai start/end ini ke input manual.">
          <span class="btnLabel">
            <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 5v14"></path>
              <path d="M5 12h14"></path>
            </svg>
            <span>Pakai ke Manual</span>
          </span>
        </button>
      </div>
    </div>
  </div>

  <div class="busy" id="busy">
    <div class="box">
      <div class="busyTop">
        <span class="spinner big"></span>
        <div>
          <div class="busyTitle" id="busyTitle">Loading</div>
          <div class="busyMsg" id="busyMsg">Mohon tunggu...</div>
        </div>
      </div>
    </div>
  </div>

  <script>
    const $ = (id) => document.getElementById(id);
    const DEFAULT_OUTDIR = {{ default_output_dir | tojson }};
    const fmt = (sec) => {
      sec = Math.max(0, Math.floor(sec||0));
      const h = Math.floor(sec/3600);
      const m = Math.floor((sec%3600)/60);
      const s = sec%60;
      if (h>0) return String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
      return String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
    };

    const parseTime = (raw) => {
      const s = String(raw || '').trim();
      if (!s) return null;
      if (/^\d+$/.test(s)) return parseInt(s, 10);
      const parts = s.split(':').map(x => x.trim());
      if (parts.some(p => p === '' || !/^\d+$/.test(p))) return null;
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
      const denom = (max - min);
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

    const setUiDisabled = (on) => {
      document.querySelectorAll('button, input, select, textarea').forEach((el) => {
        if (el.closest('#busy')) return;
        if (on) {
          if (el.dataset.prevDisabled === undefined) el.dataset.prevDisabled = el.disabled ? '1' : '0';
          el.disabled = true;
          return;
        }
        if (el.dataset.prevDisabled !== undefined) {
          el.disabled = (el.dataset.prevDisabled === '1');
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
      const on = (busyCount > 0) || !!busyJob;
      const el = $('busy');
      if (!el) return;
      if (on) el.classList.add('on');
      else el.classList.remove('on');
      setUiDisabled(on);
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
      const btn = $('openFolder');
      if (!btn) return;
      btn.style.display = on ? 'inline-flex' : 'none';
      btn.disabled = !on;
    };

    const setHeatmapLoading = (on) => {
      const btn = $('loadHeatmap');
      const spin = $('heatmapSpin');
      const txt = $('heatmapText');
      if (btn) btn.disabled = !!on;
      if (spin) spin.style.display = on ? 'inline-block' : 'none';
      if (txt) txt.textContent = on ? 'Loading...' : 'Load Heatmap';
    };

    const cfgKey = 'ytclipper_web_cfg_v1';
    const loadLocalCfg = () => {
      try { return JSON.parse(localStorage.getItem(cfgKey) || '{}') || {}; } catch { return {}; }
    };
    const saveLocalCfg = (obj) => {
      try { localStorage.setItem(cfgKey, JSON.stringify(obj||{})); } catch {}
    };

    const applyCfg = (cfg) => {
      if (cfg.output_mode) document.querySelectorAll('input[name="outMode"]').forEach(r => r.checked = (r.value === cfg.output_mode));
      if (cfg.output_dir) $('outDir').value = cfg.output_dir;
      if (cfg.crop_mode) $('crop').value = cfg.crop_mode;
      if (cfg.crop_preview !== undefined && $('cropPrev')) $('cropPrev').checked = !!cfg.crop_preview;
      if (cfg.use_subtitle !== undefined) $('subOn').checked = !!cfg.use_subtitle;
      if (cfg.whisper_model) $('model').value = cfg.whisper_model;
      if (cfg.subtitle_position) $('subPos').value = cfg.subtitle_position;
      if (cfg.preview_seconds) $('previewSecs').value = cfg.preview_seconds;
      syncOutMode();
      syncSub();
      updateCropPreview();
    };

    const collectCfg = () => ({
      output_mode: document.querySelector('input[name="outMode"]:checked')?.value || 'default',
      output_dir: $('outDir').value.trim(),
      crop_mode: $('crop').value,
      crop_preview: $('cropPrev') ? $('cropPrev').checked : true,
      use_subtitle: $('subOn').checked,
      whisper_model: $('model').value,
      subtitle_position: $('subPos').value,
      preview_seconds: parseInt($('previewSecs').value || '30', 10)
    });

    const persistCfg = async () => {
      const cfg = collectCfg();
      saveLocalCfg(cfg);
      try {
        await fetch('/api/config', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(cfg) });
      } catch {}
    };

    const syncOutMode = () => {
      const mode = document.querySelector('input[name="outMode"]:checked')?.value || 'default';
      $('outDir').disabled = (mode === 'default');
      if (mode === 'default') $('outDir').placeholder = 'Default: ~/Videos/ClipAI';
    };

    const syncSub = () => {
      $('model').disabled = !$('subOn').checked;
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
        const bottomX = mode === 'split_right' ? (100 - w) : 0;
        const shade = 'rgba(0,0,0,0.45)';
        const stroke = 'rgba(72,208,255,0.92)';
        const stroke2 = 'rgba(72,208,255,0.55)';
        const sw = 0.85;

        let holes = '';
        let frames = '';
        if (mode === 'split_left' || mode === 'split_right') {
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
          tag.src = "https://www.youtube.com/iframe_api";
          document.head.appendChild(tag);
          const t = setInterval(() => {
            if (window.YT && window.YT.Player) { clearInterval(t); resolve(); }
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
        const dur = Math.max(0, (s.end|0)-(s.start|0));
        const score = (s.score === undefined || s.score === null) ? '-' : Number(s.score).toFixed(2);
        tr.innerHTML = `
          <td><input type="checkbox" ${s.enabled?'checked':''} data-idx="${idx}" class="segOn" /></td>
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
      const enabledCount = segments.reduce((acc, s) => acc + (s && s.enabled ? 1 : 0), 0);
      const totalCount = segments.length;
      const pickInfo = $('segPickInfo');
      if (pickInfo) pickInfo.textContent = totalCount ? (`Dipilih ${enabledCount} / ${totalCount}`) : '';
      const selAllBtn = $('segSelectAll');
      const deselAllBtn = $('segDeselectAll');
      if (selAllBtn) selAllBtn.disabled = !totalCount || enabledCount === totalCount;
      if (deselAllBtn) deselAllBtn.disabled = !totalCount || enabledCount === 0;
      if (activeSegIdx !== null && segments[activeSegIdx] && $('segEnabled')) {
        $('segEnabled').checked = !!segments[activeSegIdx].enabled;
      }
      tbody.querySelectorAll('.segOn').forEach(cb => cb.addEventListener('change', (e) => {
        const i = parseInt(e.target.dataset.idx, 10);
        segments[i].enabled = !!e.target.checked;
        persistCfg();
      }));
      tbody.querySelectorAll('.segPrev').forEach(btn => btn.addEventListener('click', (e) => {
        const i = parseInt(e.target.dataset.idx, 10);
        openSegPreview(i);
      }));
      tbody.querySelectorAll('.segDel').forEach(btn => btn.addEventListener('click', (e) => {
        const i = parseInt(e.target.dataset.idx, 10);
        segments.splice(i, 1);
        renderSegs();
      }));
    };

    const openSegModal = () => { $('segModal').classList.add('on'); };
    const closeSegModal = () => { $('segModal').classList.remove('on'); };

    const destroySegPlayer = () => {
      try { if (segPlayer && segPlayer.destroy) segPlayer.destroy(); } catch {}
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
        $('segMeta').textContent = `Segmen #${idx+1} • ${fmt(start)} - ${fmt(end)} • Dur ${fmt(end-start)} • Score ${s.score === undefined ? '-' : Number(s.score).toFixed(2)}`;

        segStart = start;
        segEnd = end;
        $('segEditStart').value = fmt(start);
        $('segEditEnd').value = fmt(end);

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
              try { e.target.setPlaybackQuality('large'); } catch {}
              try { e.target.seekTo(start, true); } catch {}
            }
          }
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

      s.start = start;
      s.end = end;
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
      const segs = segments.filter(s => s.enabled);
      if (!segs.length) throw new Error('Minimal 1 segmen harus aktif.');
      for (const s of segs) {
        if (s.start < 0 || s.end < 0) throw new Error('Durasi tidak boleh negatif.');
        if (s.end <= s.start) throw new Error('End harus lebih besar dari Start.');
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
      for (const s of segs) totalSec += Math.max(0, (s.end|0)-(s.start|0));
      const estMB = (totalSec * 2600000 / 8) / (1024*1024);
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
      top.appendChild(mkKv('Subtitle', subOn ? ('ON • Model: ' + model) : 'OFF'));
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
        const dur = Math.max(0, (s.end|0)-(s.start|0));
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

    const setProgress = (p, status, eta, isActive = true) => {
      const pct = Math.max(0, Math.min(100, p||0));
      const bar = $('bar');
      bar.style.width = pct.toFixed(1) + '%';
      $('status').textContent = (status||'') + ' (' + pct.toFixed(0) + '%)';
      $('eta').textContent = eta ? ('ETA ~ ' + eta) : '';
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
        const isRunning = data.running && !data.done;
        setProgress(data.percent, data.status, data.eta, isRunning);
        if (busyJob && isRunning) {
          const pct = Math.max(0, Math.min(100, Number(data.percent || 0)));
          const st = (data.status || '').trim();
          setBusyText('Sedang memproses...', (st ? st + ' • ' : '') + pct.toFixed(0) + '%');
        }
        let logText = data.logs || '';
        if (data.error) {
          logText += '\\n\\n❌ ERROR: ' + data.error;
        }
        setLog(logText);
        if (data.done) {
          clearInterval(pollTimer);
          pollTimer = null;
          const canOpen = !data.error && data.success_count > 0 && !!data.output_dir;
          setOpenFolderVisible(canOpen);
          setBusyJob(false);
          if (data.error) {
            alert('❌ Proses gagal!\\n\\n' + data.error);
          } else if (data.success_count > 0) {
            alert('✅ Selesai! ' + data.success_count + ' clip berhasil dibuat.\\n\\nOutput: ' + (data.output_dir || ''));
          }
        }
      } catch {}
    };

    const startJob = async () => {
      const url = validateUrl();
      const segs = validateSegments();
      const outMode = document.querySelector('input[name="outMode"]:checked')?.value || 'default';
      const outDir = outMode === 'default' ? null : validateOutDir();
      const payload = {
        url,
        segments: segs,
        crop_mode: $('crop').value,
        use_subtitle: $('subOn').checked,
        whisper_model: $('model').value,
        subtitle_position: $('subPos').value,
        output_dir: outDir
      };
      setOpenFolderVisible(false);
      setLog('🚀 Memulai proses...');
      setProgress(0, 'Memulai...', '', true);
      setBusyJob(true, 'Memproses clip...', 'Memulai...');
      const res = await fetch('/api/start', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      const data = await res.json();
      if (!data.ok) { setBusyJob(false); throw new Error(data.error || 'Gagal start job'); }
      jobId = data.job_id;
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(poll, 700);
      await poll();
    };

    const applyVideoInfo = (data) => {
      durationSec = data.duration_seconds|0;
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
        const res = await fetch('/api/video_info', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url}) });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || 'Gagal load info');
        applyVideoInfo(data);
        persistCfg();
      });
    };

    const waitMainPlayer = async () => {
      for (let i = 0; i < 50; i++) {
        if (player && player.getCurrentTime && player.getPlayerState) return true;
        await new Promise(r => setTimeout(r, 80));
      }
      return false;
    };

    const loadHeatmap = async () => {
      const url = validateUrl();

      const infoRes = await fetch('/api/video_info', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url}) });
      const infoData = await infoRes.json();
      if (!infoData.ok) throw new Error(infoData.error || 'Gagal load info');

      const nextVideoId = infoData.video_id;
      const shouldSwitchVideo = (!currentVideoId) || (String(currentVideoId) !== String(nextVideoId));
      if (shouldSwitchVideo) {
        segments = [];
        activeSegIdx = null;
        renderSegs();
      }
      applyVideoInfo(infoData);
      persistCfg();

      let heatmapErr = null;
      try {
        const res = await fetch('/api/heatmap', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url, duration_seconds: infoData.duration_seconds}) });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || 'Gagal load heatmap');
        segments = data.segments || [];
        if (!segments.length) throw new Error('Heatmap kosong: video ini tidak punya Most Replayed, atau parsing gagal.');
        segments.sort((a, b) => ((Number(b.score ?? 0) - Number(a.score ?? 0)) || ((a.start|0) - (b.start|0)) || ((a.end|0) - (b.end|0))));
        activeSegIdx = null;
        renderSegs();
        return;
      } catch (e) {
        heatmapErr = e;
      }

      const txt = $('heatmapText');
      if (txt) txt.textContent = 'Loading (backup AI)...';

      try {
        const res = await fetch('/api/ai_segments', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({url, duration_seconds: infoData.duration_seconds, whisper_model: $('model').value, language: 'id'}) });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || 'Gagal generate AI segments');
        segments = data.segments || [];
        if (!segments.length) throw new Error('AI segments kosong: transcript tidak cukup jelas, atau analisis gagal.');
        segments.sort((a, b) => ((Number(b.score ?? 0) - Number(a.score ?? 0)) || ((a.start|0) - (b.start|0)) || ((a.end|0) - (b.end|0))));
        activeSegIdx = null;
        renderSegs();
      } catch (aiErr) {
        const hmsg = heatmapErr && heatmapErr.message ? heatmapErr.message : 'Gagal load heatmap';
        const amsg = aiErr && aiErr.message ? aiErr.message : 'Gagal backup AI';
        throw new Error(hmsg + '\n\nBackup AI juga gagal:\n' + amsg);
      }
    };

    const addSeg = () => {
      const s = parseInt(($('sStart').value||'0'), 10);
      const e = parseInt(($('sEnd').value||'0'), 10);
      if (Number.isNaN(s) || Number.isNaN(e)) throw new Error('Start/End harus angka.');
      if (s < 0 || e < 0) throw new Error('Durasi tidak boleh negatif.');
      if (e <= s) throw new Error('End harus lebih besar dari Start.');
      if (durationSec > 0 && e > durationSec) throw new Error('End melebihi durasi video.');
      segments.push({ enabled:true, start:s, end:e });
      segments.sort((a,b) => (a.start-b.start) || (a.end-b.end));
      renderSegs();
    };

    const openModal = () => { $('modal').classList.add('on'); };
    const closeModal = () => { $('modal').classList.remove('on'); };

    document.querySelectorAll('input[name="outMode"]').forEach(r => r.addEventListener('change', () => { syncOutMode(); persistCfg(); }));
    $('outDir').addEventListener('change', persistCfg);
    $('crop').addEventListener('change', () => { updateCropPreview(); persistCfg(); });
    if ($('cropPrev')) $('cropPrev').addEventListener('change', () => { updateCropPreview(); persistCfg(); });
    $('subOn').addEventListener('change', () => { syncSub(); persistCfg(); });
    $('model').addEventListener('change', persistCfg);
    $('previewSecs').addEventListener('change', persistCfg);

    $('openYT').addEventListener('click', () => window.open($('url').value.trim() || 'https://youtube.com', '_blank'));
    $('loadHeatmap').addEventListener('click', async () => {
      setHeatmapLoading(true);
      try {
        await runWithBusy('Memuat heatmap...', 'Mengambil Most Replayed / backup AI...', loadHeatmap);
      } catch(e){
        alert(e.message);
      } finally {
        setHeatmapLoading(false);
      }
    });
    $('segSelectAll').addEventListener('click', () => {
      segments.forEach(s => { if (s) s.enabled = true; });
      renderSegs();
      persistCfg();
    });
    $('segDeselectAll').addEventListener('click', () => {
      segments.forEach(s => { if (s) s.enabled = false; });
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
      } catch(e){
        alert(e.message);
      }
    });
    $('clearSeg').addEventListener('click', () => { segments = []; renderSegs(); });
    $('review').addEventListener('click', () => { try { fillSummary(); openModal(); } catch(e){ alert(e.message); } });
    $('closeModal').addEventListener('click', closeModal);
    $('go').addEventListener('click', async () => {
      try {
        closeModal();
        await startJob();
      } catch(e) {
        alert(e.message);
      }
    });
    $('openFolder').addEventListener('click', async () => {
      if (!jobId) return;
      try {
        await runWithBusy('Membuka folder...', 'Menyiapkan folder output...', async () => {
          const res = await fetch('/api/open_output/' + jobId, { method:'POST' });
          const data = await res.json();
          if (!data.ok) throw new Error(data.error || 'Gagal membuka folder output.');
        });
      } catch (e) {
        alert(e.message);
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
        const s = parseInt(($('previewSecs').value||'30'), 10);
        if (Number.isNaN(s) || s < 5 || s > 600) { alert('Preview detik harus 5-600'); return; }
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
      $('sStart').value = String(Math.max(0, parseInt(s.start||0, 10)));
      $('sEnd').value = String(Math.max(0, parseInt(s.end||0, 10)));
      closeSegModal();
      destroySegPlayer();
    });

    $('segClose').addEventListener('click', () => {
      closeSegModal();
      destroySegPlayer();
    });

    window.onYouTubeIframeAPIReady = function() {
      playerReady = true;
    };

    const loadPlayer = (videoId) => {
      ensureYTApi().then(() => {
        if (player && player.getVideoData && player.loadVideoById) {
          const curId = player.getVideoData()?.video_id;
          if (String(curId) !== String(videoId)) {
            try { player.loadVideoById(videoId); } catch {}
          }
          return;
        }

        try { if (player && player.destroy) player.destroy(); } catch {}
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
              try { e.target.setPlaybackQuality('large'); } catch {}
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
            }
          }
        });
      });
    };

    (async () => {
      const serverCfg = await fetch('/api/config').then(r=>r.json()).catch(()=>({}));
      const localCfg = loadLocalCfg();
      applyCfg(Object.assign({}, serverCfg, localCfg, { output_dir: localCfg.output_dir || serverCfg.output_dir || '{{ default_output_dir }}' }));
      if (!$('previewSecs').value) $('previewSecs').value = '30';
      $('url').value = '';
      syncRangeFill($('timeline'));
      renderSegs();
      updateBusyState();
    })();
  </script>
</body>
</html>
"""
