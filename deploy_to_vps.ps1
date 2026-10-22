# Update the existing human-digital checkout via GitHub and its safe deploy script.
# No API keys are passed through PowerShell arguments or SSH command history.
param (
    [string]$VpsIp = "103.20.102.229",
    [string]$SshUser = "root",
    [string]$SshKey = ""
)

$ErrorActionPreference = "Stop"
$SshArgs = @()
if ($SshKey) { $SshArgs += @("-i", $SshKey) }
$RemoteCommand = 'cd /opt/human-digital && old_commit=$(git rev-parse HEAD) && git pull --ff-only origin main && PREVIOUS_COMMIT="$old_commit" bash deploy_vps.sh'
$SshArgs += @("$SshUser@$VpsIp", $RemoteCommand)

Write-Host "Deploying only human-digital backend on $VpsIp..."
& ssh @SshArgs
if ($LASTEXITCODE -ne 0) {
    throw "Deployment stopped. Check the error above; no other VPS services were intentionally changed."
}
Write-Host "Backend deployment completed. Check the health result above."
