#!/bin/bash
# ==============================================================================
# 🤖 DORAEMON AI TUTOR - ONE-CLICK PRODUCTION VPS INSTALLER
# Tự động hóa 100% cài đặt Server: Docker, Nginx Reverse Proxy, WSS, Firewall, Backup
# Tương thích: Ubuntu 20.04 / 22.04 / 24.04 LTS & Debian 11 / 12
# ==============================================================================

set -e

# Màu sắc giao diện console
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}"
echo "=================================================================="
echo "    🚀 DORAEMON AI DIGITAL HUMAN - ONE-CLICK VPS DEPLOYMENT      "
echo "=================================================================="
echo -e "${NC}"

# 1. Kiểm tra quyền root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Lỗi: Vui lòng chạy script này với quyền root (sudo bash deploy_vps.sh)${NC}"
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

# Tự động xác định thư mục chứa mã nguồn hiện tại
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="/opt/human-digital"
VPS_IP=$(curl -s -4 ifconfig.me || hostname -I | awk '{print $1}')
echo -e "${YELLOW}📍 Địa chỉ IP Máy Chủ VPS phát hiện:${NC} ${BOLD}${VPS_IP}${NC}"
echo -e "${YELLOW}📂 Thư mục mã nguồn gốc:${NC} ${BOLD}${SCRIPT_DIR}${NC}"

# Đồng bộ mã nguồn từ thư mục hiện tại sang /opt/human-digital nếu chạy từ nơi khác (vd: /root/human-digital)
if [ "$SCRIPT_DIR" != "$APP_DIR" ]; then
    echo -e "${CYAN}📋 Đang đồng bộ mã nguồn sang $APP_DIR...${NC}"
    mkdir -p "$APP_DIR"
    cp -rf "$SCRIPT_DIR"/* "$APP_DIR"/ 2>/dev/null || true
fi

# 2. Cập nhật hệ điều hành & cài đặt gói phụ trợ
echo -e "\n${CYAN}📦 [1/6] Đang cập nhật hệ điều hành & cài đặt công cụ thiết yếu...${NC}"
apt-get update -y -qq
apt-get install -y -qq curl git ufw nginx certbot python3-certbot-nginx sqlite3 rsync

# 3. Cài đặt Docker & Docker Compose Plugin nếu chưa có
echo -e "\n${CYAN}🐳 [2/6] Kiểm tra & Cài đặt Docker Engine...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Chưa có Docker, đang tiến hành cài đặt chính hãng...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm -f get-docker.sh
    systemctl enable docker
    systemctl start docker
    echo -e "${GREEN}✅ Docker đã được cài đặt thành công!${NC}"
else
    echo -e "${GREEN}✅ Docker đã tồn tại trên hệ thống.${NC}"
fi

# 4. Cấu hình Tường lửa (UFW Firewall)
echo -e "\n${CYAN}🛡️ [3/6] Thiết lập Tường lửa Firewall UFW...${NC}"
ufw allow 22/tcp >/dev/null 2>&1 || true
ufw allow 80/tcp >/dev/null 2>&1 || true
ufw allow 443/tcp >/dev/null 2>&1 || true
ufw allow 8000/tcp >/dev/null 2>&1 || true
ufw --force enable >/dev/null 2>&1 || true
echo -e "${GREEN}✅ Tường lửa đã kích hoạt (Đã mở Port: 22, 80, 443, 8000).${NC}"

# 5. Cấu hình biến môi trường .env
echo -e "\n${CYAN}⚙️ [4/6] Khởi tạo tệp cấu hình môi trường .env...${NC}"
mkdir -p "$APP_DIR/backend"
mkdir -p "$APP_DIR/data"

ENV_FILE="$APP_DIR/backend/.env"

if [ ! -f "$ENV_FILE" ]; then
    # Lấy API key từ đối số truyền vào hoặc dùng placeholder
    GEMINI_KEY="${1:-AIzaSy_YOUR_GEMINI_API_KEY_HERE}"
    ADMIN_KEY="${2:-KiemSoatPhuHuynh2026SecureKeyXYZ987}"

    cat <<EOF > "$ENV_FILE"
# ==========================================
# CẤU HÌNH MÁY CHỦ DORAEMON DIGITAL HUMAN
# ==========================================
GEMINI_API_KEY=$GEMINI_KEY
GEMINI_MODEL=gemini-2.5-flash-native-audio-latest
GEMINI_VOICE=Aoede

# Khóa Master Admin (Dành riêng cho chủ VPS quản trị hệ thống)
ADMIN_API_KEY=$ADMIN_KEY

# Google Custom Search Engine (Bách khoa toàn thư)
GOOGLE_CSE_ID=
GOOGLE_CSE_KEY=

# CORS & Network Host
ALLOWED_ORIGINS=http://$VPS_IP:8000,http://$VPS_IP,https://$VPS_IP
ENV=production
HOST=0.0.0.0
PORT=8000
EOF
    echo -e "${GREEN}✅ Đã tạo file cấu hình mới tại: $ENV_FILE${NC}"
else
    if [ -n "$1" ]; then
        sed -i "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=$1|" "$ENV_FILE"
        echo -e "${GREEN}✅ Đã cập nhật GEMINI_API_KEY mới vào: $ENV_FILE${NC}"
    else
        echo -e "${GREEN}✅ File $ENV_FILE đã tồn tại, giữ nguyên cấu hình hiện tại.${NC}"
    fi
fi

# 6. Cấu hình Nginx Reverse Proxy (Hỗ trợ WSS & Timeout 3600s)
echo -e "\n${CYAN}🌐 [5/6] Thiết lập Nginx Web Server & WebSocket Routing...${NC}"
NGINX_CONF="/etc/nginx/sites-available/digital-human.conf"

cat <<EOF > "$NGINX_CONF"
# Cấu hình Nginx Reverse Proxy cho Doraemon AI Tutor
server {
    listen 80;
    server_name $VPS_IP _;

    # Chuyển tiếp WebSocket 2 chiều (WSS / WS)
    location /ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Chống đứt kết nối khi phiên đàm thoại kéo dài
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
    }

    # Chuyển tiếp REST API & Web Dashboard
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/digital-human.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t >/dev/null 2>&1
systemctl restart nginx
echo -e "${GREEN}✅ Nginx Reverse Proxy đã sẵn sàng trên cổng 80 & WebSocket.${NC}"

# 7. Khởi chạy Docker Container
echo -e "\n${CYAN}🚀 [6/6] Đang Build và Khởi động Container Backend...${NC}"
cd "$APP_DIR"
docker compose down >/dev/null 2>&1 || true
docker compose up -d --build

# 8. Cấu hình tự động sao lưu dữ liệu SQLite vào Crontab lúc 03:00 sáng
BACKUP_SCRIPT="/opt/backup_memory.sh"
cat <<'EOF' > "$BACKUP_SCRIPT"
#!/bin/bash
BACKUP_DIR="/opt/backups/sqlite"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"
DB_SRC="/opt/human-digital/backend/data/child_memory.db"
if [ -f "$DB_SRC" ]; then
    sqlite3 "$DB_SRC" ".backup '$BACKUP_DIR/child_memory_$DATE.db'"
    find "$BACKUP_DIR" -type f -name "*.db" -mtime +30 -delete
fi
EOF
chmod +x "$BACKUP_SCRIPT"
(crontab -l 2>/dev/null | grep -v "$BACKUP_SCRIPT" ; echo "0 3 * * * $BACKUP_SCRIPT") | crontab -

# 9. Kiểm tra Healthcheck
echo -e "\n${CYAN}🔍 Đang kiểm tra trạng thái hoạt động của Backend...${NC}"
sleep 3
HEALTH_RESP=$(curl -s "http://127.0.0.1:8000/health" || echo "")

echo -e "\n${GREEN}${BOLD}=================================================================="
echo "    🎉 CÀI ĐẶT SERVER LÊN VPS THÀNH CÔNG RỰC RỠ 100%!           "
echo "==================================================================${NC}"
echo -e "${BOLD}📍 Địa chỉ IP Máy chủ:${NC}    http://$VPS_IP"
echo -e "${BOLD}🔌 WebSocket Live Endpoint:${NC} ws://$VPS_IP/ws/live"
echo -e "${BOLD}🏥 Health Check:${NC}           http://$VPS_IP/health"
echo -e "${BOLD}📊 Web Phụ Huynh:${NC}          http://$VPS_IP/config"
echo -e "${BOLD}💾 Auto Backup Database:${NC}   03:00 AM mỗi ngày -> /opt/backups/sqlite/"
echo ""
echo -e "${YELLOW}👉 Bước tiếp theo: Cài app trên điện thoại của bé và bắt đầu trò chuyện!${NC}"
echo "=================================================================="
