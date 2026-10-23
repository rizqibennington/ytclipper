# YTClipper (Web)

Aplikasi web lokal (Flask/FastAPI) buat nge-clip video YouTube jadi format vertikal 9:16, berbasis data **Most Replayed (heatmap)**. Lo bisa auto-generate segmen dari heatmap, edit manual di UI, lalu proses jadi MP4 siap Shorts/Reels/TikTok.

Yang penting: ini jalan di PC lo sendiri atau server VPS/Docker, gak butuh YouTube API key, tapi butuh **FFmpeg** dan koneksi internet buat akses YouTube.

---

## Fitur

- Web UI: tempel URL, preview video, dan pilih segmen
- Load heatmap “Most Replayed” buat auto-segmen
- Fallback AI (Gemini / Subtitle) saat video tidak memiliki heatmap
- Manajemen YouTube Cookies (Upload / Paste langsung dari UI) untuk bypass bot detection di server production
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

- Python 3.10+
- FFmpeg harus ada di PATH
- Node.js (direkomendasikan untuk JS runtime yt-dlp)

Python package (lihat [requirements.txt](requirements.txt)):
- `requests`
- `yt-dlp`
- `fastapi`
- `uvicorn`
- `faster-whisper`
- `google-genai`

---

## Instalasi & Menjalankan

### Cara 1: Menggunakan Docker (Production / VPS)

```bash
docker-compose up -d --build
```
Akses di browser: `http://<ip-server>:5000`

### Cara 2: Manual / Lokal

1) Install dependencies:
```bash
pip install -r requirements.txt
```

2) Jalankan aplikasi:
```bash
python run.py
```
Akses di browser: `http://127.0.0.1:5000`

---

## Standar Durasi (Editorial)

- Maksimal durasi per klip: **03:00 (180 detik)**
- Klip **tidak boleh** lebih dari 03:00 (180 detik)
- UI bakal kasih meter durasi realtime + peringatan saat mendekati limit
- Kalau ada input/segmen kepanjangan, sistem auto-trim end ke detik ke-180 dari start (dan dicatat di log job)

---

## Troubleshooting

### Error: "Sign in to confirm you're not a bot" di Production / VPS

Penyebab: YouTube memblokir IP Datacenter/VPS (Cloudflare, DigitalOcean, Hetzner, AWS, Tencent, dll.) yang melakukan download otomatis tanpa login.

**Solusi (Sangat Mudah):**
1. Di browser laptop/PC Anda, pasang ekstensi:
   - **Get cookies.txt LOCALLY** (Chrome Web Store) atau **Cookie-Editor**.
2. Buka [youtube.com](https://www.youtube.com) (pastikan dalam keadaan login akun Google/YouTube biasa).
3. Klik ekstensi tersebut, lalu klik **Export** (format Netscape HTTP Cookie File).
4. Di UI YTClipper, masuk ke bagian **🍪 YouTube Cookies**:
   - Klik **📁 Upload cookies.txt** lalu pilih file yang baru diekspor tadi, ATAU klik **📋 Paste Teks**.
   - Status akan langsung berubah menjadi `✅ Terpasang`.
5. *(Alternatif CLI/Docker)*: Letakkan file tersebut di `./data/cookies.txt` pada folder server host Anda, lalu restart container: `docker-compose restart`.

### Heatmap kosong: "video ini tidak punya Most Replayed, atau parsing gagal"

- Tidak semua video YouTube memiliki grafik Most Replayed (misal video baru, views rendah, atau video tertentu).
- Ketika heatmap kosong, sistem akan otomatis beralih ke **Backup AI** (mengambil audio dan transkrip untuk auto-generate segmen highlight).

### FFmpeg tidak ketemu

- Pastikan `ffmpeg -version` bisa dipanggil dari terminal
- Kalau sudah install tapi masih gak kebaca, cek PATH sistem Anda.

---

## Lisensi

MIT
