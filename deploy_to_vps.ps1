# ==============================================================================
# 🤖 DORAEMON AI TUTOR - ONE-CLICK DEPLOYMENT FROM WINDOWS TO VPS
# Tự động đẩy code lên VPS và kích hoạt bộ cài đặt chỉ với 1 cú click!
# ==============================================================================

param (
    [string]$VpsIp = "103.20.102.229",
    [string]$SshUser = "root",
    [string]$GeminiApiKey = ""
)

Clear-Host
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "    🚀 ONE-CLICK DEPLOY TO VPS: $VpsIp" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Nhập Gemini API Key nếu chưa có
if ([string]::IsNullOrWhiteSpace($GeminiApiKey)) {
    $GeminiApiKey = Read-Host "🔑 Nhập Google Gemini API Key của bạn (hoặc nhấn Enter để cấu hình sau)"
}

Write-Host "`n📦 [1/3] Đang tải mã nguồn lên VPS ($SshUser@$VpsIp)..." -ForegroundColor Yellow

$RemoteDir = "/opt/human-digital"

# Tạo thư mục từ xa
ssh "$SshUser@$VpsIp" "mkdir -p $RemoteDir/backend"

# Upload mã nguồn backend, docker files, và script installer
scp -r backend "$SshUser@$VpsIp`:$RemoteDir/"
scp docker-compose.yml Dockerfile deploy_vps.sh "$SshUser@$VpsIp`:$RemoteDir/"

Write-Host "`n⚙️ [2/3] Cấp quyền thực thi cho bộ cài đặt..." -ForegroundColor Yellow
ssh "$SshUser@$VpsIp" "chmod +x $RemoteDir/deploy_vps.sh"

Write-Host "`n🚀 [3/3] Đang kích hoạt tiến trình cài đặt tự động trên VPS..." -ForegroundColor Green

if (![string]::IsNullOrWhiteSpace($GeminiApiKey)) {
    ssh "$SshUser@$VpsIp" "cd $RemoteDir && bash deploy_vps.sh '$GeminiApiKey'"
} else {
    ssh "$SshUser@$VpsIp" "cd $RemoteDir && bash deploy_vps.sh"
}

Write-Host "`n🎉 QUÁ TRÌNH TRIỂN KHAI HOÀN TẤT!" -ForegroundColor Cyan
Write-Host "👉 Bạn có thể kiểm tra trực tiếp tại: http://$VpsIp/health" -ForegroundColor Yellow
