import hmac
import hashlib
import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- KONFIGURASI ---
# Ganti dengan secret yang sama di GitHub Webhook Settings
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "rahasia_super_aman_123")
PORT = 5005
# Path repo di VPS (sesuaikan dengan lokasi deploy Anda)
REPO_PATH = "/home/ubuntu/rizqibennington/ytclip"
BRANCH = "main"
SERVICE_NAME = "ytclip"  # Nama service di docker-compose.yml

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Verifikasi Signature dari GitHub
        signature = self.headers.get("X-Hub-Signature-256")
        if not signature:
            self.send_error(403, "No signature")
            return

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)

        # Hitung HMAC SHA256
        mac = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256)
        expected_signature = "sha256=" + mac.hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            print("❌ Invalid signature")
            self.send_error(403, "Invalid signature")
            return

        # 2. Respon OK ke GitHub (agar tidak timeout)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Deploy triggered")

        # 3. Jalankan Deploy
        print(f"🚀 Menerima webhook push. Memulai deploy di {REPO_PATH}...")
        try:
            # Pastikan berada di folder repo
            os.chdir(REPO_PATH)

            # Pull code terbaru
            print("⬇️ Pulling git...")
            subprocess.check_call(["git", "fetch", "origin", BRANCH])
            subprocess.check_call(["git", "reset", "--hard", f"origin/{BRANCH}"])

            # Rebuild & Restart Docker
            print("🔄 Restarting Docker container...")
            subprocess.check_call(["docker", "compose", "up", "-d", "--build", SERVICE_NAME])
            
            # Prune image lama (opsional, untuk hemat disk)
            subprocess.call(["docker", "image", "prune", "-f"])

            print("✅ Deploy sukses!")
        except Exception as e:
            print(f"❌ Deploy gagal: {e}")

if __name__ == "__main__":
    print(f"🎧 Webhook listener berjalan di port {PORT}")
    print(f"📂 Memantau repo: {REPO_PATH}")
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
