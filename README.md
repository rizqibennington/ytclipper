# YTClipper (Web)

Aplikasi web lokal (FastAPI) buat nge-clip video YouTube jadi format vertikal 9:16 untuk kebutuhan **YouTube Shorts, Instagram Reels, dan TikTok**, berbasis data **Most Replayed (heatmap)** dan **AI Video Highlight Analysis**.

Jalan di PC lokal atau server VPS/Docker. Bebas kuota API YouTube karena menggunakan ekstraksi langsung, didukung **FFmpeg** dan **Faster-Whisper** untuk transkrip offline & **Google Gemini** untuk rekomendasi judul clickbait, caption, dan hashtag.

---

## Fitur Utama

- **Web UI Modern**: Tempel URL, preview interaktif, dan simulasi tampilan Shorts di layar HP.
- **Auto-Segment Heatmap**: Mengambil momen puncak "Most Replayed" secara presisi.
- **Fallback AI Multi-Highlight**:
  - Jika video tidak memiliki heatmap, AI otomatis menganalisis transkrip/audio untuk mengekstrak **3-5 klip highlight viral** berdurasi 30-60 detik dengan algoritma Non-Maximum Suppression (anti-tumpang tindih).
- **Asisten Konten AI (1-Click Copy)**:
  - Rekomendasi 3 judul clickbait dengan hook tinggi.
  - Caption interaktif untuk memancing engagement penonton.
  - Hashtags viral & trending yang siap disalin langsung dari UI.
- **Format & Crop Mode 9:16 Siap Medsos**:
  - `default`: Center crop 9:16 standar.
  - `fit`: **Blurred Background (Canvas Blur)** profesional tanpa bar hitam kaku (gaya Opus Clip / CapCut).
  - `split_left` & `split_right`: Layout split untuk video gaming/reaksi dengan facecam.
- **Audio Normalization**:
  - Dilengkapi filter `-af loudnorm` standar Shorts/TikTok (-14 LUFS) agar suara vokal selalu kencang, jernih, dan tidak tenggelam.
- **Subtitle AI Otomatis (Faster-Whisper)**:
  - Tipografi bergaya tegas (Arial Black, bold outline, shadow kontras tinggi).
  - Pilihan model (`tiny` sampai `large-v3`), multi-bahasa (ID, EN, Auto), dan posisi (Bawah, Tengah, Atas).
- **Ekspor & Manajemen Job**:
  - **Unduh Semua (ZIP)**: Download seluruh video hasil klip beserta file saran judul & caption dalam satu paket ZIP.
  - **Tombol Batal**: Batalkan job yang sedang berjalan kapan saja langsung dari UI.
  - **Manajemen YouTube Cookies**: Upload atau paste Netscape `cookies.txt` langsung dari UI untuk bypass bot detection di server VPS/Docker.

---

## Requirement

- Python 3.10+
- FFmpeg terinstall di PATH sistem
- Node.js (direkomendasikan untuk JS runtime yt-dlp)

Python package (lihat [requirements.txt](requirements.txt)):
- `requests`
- `yt-dlp`
- `fastapi`
- `uvicorn`
- `faster-whisper`
- `google-genai`
- `python-dotenv`

---

## Instalasi & Menjalankan

### Cara 1: Menggunakan Docker (Production / VPS)

```bash
docker-compose up -d --build
```
Akses di browser: `http://<ip-server>:5000`

### Cara 2: Manual / Lokal

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Jalankan aplikasi:
```bash
python run.py
```
Akses di browser: `http://127.0.0.1:5000`

---

## Standar Durasi (Editorial)

- Maksimal durasi per klip: **03:00 (180 detik)**.
- Standar rekomendasi durasi YouTube Shorts ideal: **30-60 detik**.
- UI menyediakan meter durasi realtime + peringatan saat mendekati limit.
- Jika ada input/segmen melebihi batas, sistem otomatis melakukan auto-trim end ke detik ke-180 dari start.

---

## Troubleshooting

### Error: "Sign in to confirm you're not a bot" di Production / VPS
Penyebab: YouTube memblokir IP Datacenter/VPS yang mengunduh tanpa autentikasi.
**Solusi:**
1. Ekspor cookies dari browser Anda menggunakan ekstensi *Get cookies.txt LOCALLY* atau *Cookie-Editor*.
2. Buka menu **🍪 YouTube Cookies** di pojok kanan YTClipper.
3. Klik **📁 Upload cookies.txt** atau **📋 Paste Teks**. Status akan berubah menjadi `✅ Terpasang`.

---

## Lisensi

MIT
