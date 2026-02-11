# YTClipper (Web)

Aplikasi web lokal (Flask) buat nge-clip video YouTube jadi format vertikal 9:16, berbasis data **Most Replayed (heatmap)**. Lo bisa auto-generate segmen dari heatmap, edit manual di UI, lalu proses jadi MP4 siap Shorts/Reels/TikTok.

Yang penting: ini jalan di PC lo sendiri, gak butuh YouTube API key, tapi butuh **FFmpeg** dan koneksi internet buat akses YouTube.

---

## Fitur

- Web UI lokal: tempel URL, preview video, dan pilih segmen
- Load heatmap “Most Replayed” buat auto-segmen
- Tambah segmen manual (start/end) + enable/disable per segmen
- Crop mode:
  - `default` (center crop)
  - `split_left` (bottom kiri buat facecam)
  - `split_right` (bottom kanan buat facecam)
- Subtitle AI (opsional) pakai Faster-Whisper:
  - Pilih model (`tiny` sampai `large-v3`)
  - Posisi subtitle: atas / tengah / bawah
- Progress + log job langsung di UI

---

## Requirement

- Python 3.8+
- FFmpeg harus ada di PATH

Python package (lihat [requirements.txt](requirements.txt)):
- `flask`
- `requests`
- `yt-dlp`
- `faster-whisper`

Catatan: subtitle AI bakal download model pertama kali (lumayan gede). Kalau PC lo kentang, pilih model `tiny`/`base`.

---

## Instalasi

1) Install dependency Python

```bash
pip install -r requirements.txt
```

2) Install FFmpeg

Windows (cara gampang):

1. Download dari https://ffmpeg.org/download.html
2. Extract ke misalnya `C:\ffmpeg`
3. Masukin `C:\ffmpeg\bin` ke PATH
4. Tutup-buka terminal lagi

3) (Opsional) cek setup

```bash
python check_setup.py
```

---

## Menjalankan

Jalanin server:

```bash
python run.py
```

Lalu buka browser:

- http://127.0.0.1:5000/

Environment variable yang kepake:

- `HOST` (default `127.0.0.1`)
- `PORT` (default `5000`)
- `FLASK_DEBUG` (set `1` buat debug)

Contoh:

```bash
set FLASK_DEBUG=1
set HOST=0.0.0.0
set PORT=5000
python run.py
```

---

## Output & Config

- Output default: `~/Videos/ClipAI` (Windows biasanya `C:\Users\<nama>\Videos\ClipAI`)
- Kalau pilih output custom di UI, hasil clip masuk ke folder itu
- Config server disimpen di file: `~/.ytclipper_web.json`

---

## Standar Durasi (Editorial)

- Maksimal durasi per klip: **02:59 (179 detik)**
- Klip **tidak boleh** mencapai 03:00 (180 detik) atau lebih
- UI bakal kasih meter durasi realtime + peringatan saat mendekati limit
- Kalau ada input/segmen kepanjangan, sistem auto-trim end ke detik ke-179 dari start (dan dicatat di log job)

---

## Troubleshooting

### FFmpeg tidak ketemu

- Pastikan `ffmpeg -version` bisa dipanggil dari terminal
- Kalau udah install tapi masih gak kebaca, cek PATH-nya (classic Windows moment)

### Heatmap kosong

- Gak semua video punya “Most Replayed”
- Pastikan URL benar (watch / shorts / youtu.be)

### Subtitle gagal

- Model pertama kali download butuh internet
- Coba model lebih kecil (`tiny`/`base`)

---

## Lisensi

MIT
