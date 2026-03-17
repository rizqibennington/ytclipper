# Panduan Auto Deploy Gratis (Tanpa GitHub Actions)

Karena GitHub Actions berbayar (setelah kuota habis), kita bisa menggunakan metode **Webhook** yang berjalan di VPS Anda sendiri. Gratis selamanya!

## Cara Kerja
1. GitHub mengirim sinyal (Webhook) ke VPS setiap ada commit baru.
2. Script Python (`deploy_webhook.py`) di VPS menerima sinyal tersebut.
3. Script menjalankan `git pull` dan `docker compose up` secara otomatis.

---

## 1. Persiapan di VPS
Masuk ke VPS via SSH, lalu ikuti langkah ini:

### A. Clone Repo (Jika belum)
Sebelumnya deploy pakai SCP (copy file), sekarang kita ubah jadi `git pull`.
```bash
# Masuk ke folder user
cd /home/ubuntu/rizqibennington

# Hapus folder lama (backup dulu jika perlu)
mv ytclip ytclip_backup

# Clone repo (gunakan HTTPS dan masukkan token, atau SSH key)
git clone https://github.com/USERNAME/REPO_NAME.git ytclip

# Masuk folder
cd ytclip
```

### B. Siapkan Script Webhook
Script `deploy_webhook.py` sudah ada di dalam repo. Pastikan konfigurasinya sesuai:
- `WEBHOOK_SECRET`: Ganti dengan password rahasia (misal: `kuncirahasia123`).
- `REPO_PATH`: Pastikan path-nya benar (`/home/ubuntu/rizqibennington/ytclip`).

### C. Jalankan Listener
Jalankan script ini di background agar terus menyala meski SSH ditutup.
```bash
# Install supervisor (opsional tapi disarankan) agar auto-restart kalau crash/reboot
sudo apt update && sudo apt install supervisor -y

# Buat config supervisor
sudo nano /etc/supervisor/conf.d/ytclip-deploy.conf
```

Isi file tersebut dengan:
```ini
[program:ytclip-deploy]
command=python3 /home/ubuntu/rizqibennington/ytclip/deploy_webhook.py
directory=/home/ubuntu/rizqibennington/ytclip
autostart=true
autorestart=true
stderr_logfile=/var/log/ytclip-deploy.err.log
stdout_logfile=/var/log/ytclip-deploy.out.log
environment=WEBHOOK_SECRET="kuncirahasia123"
```

Simpan (Ctrl+X, Y, Enter), lalu jalankan:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status
```
Pastikan statusnya `RUNNING`.

---

## 2. Setting di GitHub
1. Buka Repo GitHub > **Settings** > **Webhooks**.
2. Klik **Add webhook**.
3. **Payload URL**: `http://ALAMAT_IP_VPS:5005`
   - Pastikan port 5005 dibuka di firewall VPS (`sudo ufw allow 5005`).
4. **Content type**: `application/json` (PENTING!).
5. **Secret**: Masukkan password rahasia tadi (`kuncirahasia123`).
6. **SSL verification**: Disable (kecuali Anda sudah setup HTTPS untuk IP tersebut).
7. Klik **Add webhook**.

---

## 3. Tes Deploy
Coba edit file di laptop, commit, dan push ke GitHub.
```bash
git add .
git commit -m "Tes auto deploy gratis"
git push origin main
```
Tunggu beberapa detik. Cek log di VPS:
```bash
tail -f /var/log/ytclip-deploy.out.log
```
Jika sukses, Anda akan melihat:
```
🚀 Menerima webhook push...
⬇️ Pulling git...
🔄 Restarting Docker container...
✅ Deploy sukses!
```
