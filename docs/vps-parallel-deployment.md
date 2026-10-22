# Chạy song song human-digital và havsAI trên VPS 103.20.102.229

Tài liệu này ghi lại cấu hình đang chạy thực tế ngày 2026-10-22 và cách vận hành
để hai project không ghi đè lên nhau.

## 1. Kiến trúc hiện tại

| Project | Thư mục | Runtime | Cổng nội bộ | Cổng công khai | URL chính |
| --- | --- | --- | --- | --- | --- |
| human-digital (Doraemon) | `/opt/human-digital` | Docker Compose service `backend` | `8000` | `8000`, `80` | `http://103.20.102.229/` |
| havsAI | `/opt/havs-ai` | systemd `havs-ai` (Node) | `3000` | `8080`, `443` | `https://103-20-102-229.sslip.io/` |

- human-digital dùng Docker volume `human-digital_app_data` cho `/app/data`.
- havsAI dùng SQLite tại `/opt/havs-ai/fullstack/data/havs.db`.
- Android Doraemon mặc định gọi `ws://103.20.102.229/ws/live` (port 80), nên
  **Nginx port 80 phải tiếp tục trỏ về human-digital**.
- TWA havsAI dùng `https://103-20-102-229.sslip.io`; assetlinks được phục vụ tại
  `/.well-known/assetlinks.json`.

## 2. Phân chia Nginx

Mỗi project có file riêng trong `/etc/nginx/sites-available/`:

| File | Listen | Server name | Proxy tới |
| --- | --- | --- | --- |
| `digital-human.conf` | `80` | `103.20.102.229 _` | `127.0.0.1:8000` |
| `havs-ai` | `8080` | `_` | `127.0.0.1:3000` |
| `havs-ai-ssl` | `80` | `103-20-102-229.sslip.io` | ACME challenge + redirect HTTPS |
| `havs-ai-ssl` | `443` | `103-20-102-229.sslip.io` | `127.0.0.1:3000` |

Quy tắc:

1. Chỉ `digital-human.conf` được làm catch-all (`_`) trên port 80. Không thêm
   một `server_name _` khác trên 80/443.
2. Không xoá hoặc ghi đè file Nginx của project khác khi cài project mới.
3. Certbot dùng webroot `/var/www/certbot`, không dùng `--nginx` để tránh Nginx
   bị tự sửa cấu hình.
4. Sau mọi thay đổi: `nginx -t && systemctl reload nginx`.

## 3. Deploy human-digital

Từ Windows:

```powershell
cd D:\Agentic-AI\Doing\human-digital
.\deploy_to_vps.ps1 -SshKey "$env:USERPROFILE\.ssh\human_digital_vps"
```

Trên VPS:

```bash
cd /opt/human-digital
old_commit=$(git rev-parse HEAD)
git pull --ff-only origin main
PREVIOUS_COMMIT="$old_commit" bash deploy_vps.sh
```

Script chỉ:

- kiểm tra đang ở branch `main`, remote đúng `MiERP/human-digital`;
- backup data vào `/opt/backups/human-digital/<timestamp>/`;
- backup online SQLite bằng Python trong container;
- rebuild **duy nhất** service `backend` với `--no-deps`;
- kiểm tra `/health` và `/api/companions`.

Script **không** sửa Nginx, firewall, `.env`, volume, hay service havsAI.

Rollback nhanh về image trước đó:

```bash
cd /opt/human-digital
docker tag human-digital-backend:rollback-<timestamp> human-digital-backend:latest
docker compose up -d --no-deps --force-recreate --no-build backend
```

Hoặc checkout commit cũ rồi chạy lại `deploy_vps.sh`.

## 4. Deploy havsAI

```bash
sudo bash /opt/havs-ai/deploy/deploy.sh
```

Script backup DB vào `/var/backups/havs-ai/`, pull `main`, `npm ci --omit=dev`,
chạy test, restart systemd `havs-ai`, rồi health-check
`http://127.0.0.1:3000/api/health`. Script không đụng tới human-digital hay Nginx.

Nếu lỗi:

```bash
journalctl -u havs-ai -n 100 --no-pager
systemctl status havs-ai
```

## 5. Kiểm tra nhanh

```bash
curl -fsS http://103.20.102.229/health
curl -fsS http://103.20.102.229:8000/health
curl -fsS https://103-20-102-229.sslip.io/api/health
curl -fsS http://103.20.102.229:8080/api/health

systemctl is-active havs-ai
cd /opt/human-digital && docker compose ps && git status --porcelain
```

Kiểm tra cổng:

```bash
ss -lntp | grep -E ':(80|443|8000|8080|3000) '
```

Kiểm tra certificate/renewal:

```bash
certbot certificates
certbot renew --dry-run --no-random-sleep-on-renew
```

## 6. Quy tắc không phá cấu hình

1. Không chạy `docker compose down` cho human-digital; chỉ dùng
   `docker compose up -d --no-deps --build backend`.
2. Không xoá volume `human-digital_app_data`.
3. Không regenerate `/root/.ssh/id_ed25519`. Key này đang được GitHub chấp nhận
   cho cả `MiERP/human-digital` và `MiERP/havsAI`. Nếu đổi key, phải cập nhật
   deploy key trên cả hai repo.
4. Giữ `.env` riêng, không commit:
   - `/opt/human-digital/.env`
   - `/opt/havs-ai/fullstack/.env`
5. Không đổi port nội bộ `8000`/`3000` nếu chưa sửa đồng thời compose/systemd và
   Nginx.
6. Android Doraemon hardcode URL backend. Nếu đổi domain/port, phải sửa
   `android/.../MainActivity.kt` và build lại APK, hoặc đổi URL trong màn hình
   Setup của app.

## 7. Thêm project thứ ba

1. Tạo thư mục riêng, service/systemd hoặc compose riêng, database riêng.
2. Chọn cổng nội bộ riêng (ví dụ `4000`) và cổng công khai/subdomain riêng.
3. Tạo file Nginx riêng với `server_name` cụ thể; không dùng `_` trên 80/443.
4. Nếu dùng HTTPS, thêm location ACME vào server block port 80 của host đó:

   ```nginx
   location /.well-known/acme-challenge/ {
       root /var/www/certbot;
   }
   ```

5. Xin cert bằng webroot, reload Nginx, rồi kiểm tra `nginx -t`.
6. Không sửa/xoá file Nginx của human-digital hoặc havsAI.

## 8. Trạng thái sau lần cấu hình 2026-10-22

- `/opt/human-digital` đã là git checkout sạch tại commit `4a713b9`, remote
  `git@github.com:MiERP/human-digital.git`.
- Source cũ được giữ tại `/opt/human-digital.old-20261022T073643Z`.
- Backup trước khi chuyển: `/opt/backups/human-digital/20261022T073643Z/`
  (source, volume, Nginx config, image ID).
- Image rollback: `human-digital-backend:rollback-20261022T073643Z`.
- `.env` của human-digital có `ENABLE_PROACTIVE_AUDIO=false` vì model
  `gemini-2.5-flash-native-audio-latest` từ chối field `proactivity`.
- Cert `103-20-102-229.sslip.io` hết hạn 2027-01-19; renewal dry-run đã pass.
- SSH key `~/.ssh/human_digital_vps` đã được thêm vào
  `/root/.ssh/authorized_keys` để phục vụ cấu hình; có thể gỡ khi không cần.
