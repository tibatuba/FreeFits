# Deploy FreeFits to EC2 from your Windows machine
# Usage: Run this script after you've pushed your changes to GitHub.
#        Edit the variables below if your key path or EC2 IP changes.

$KeyPath = "$env:USERPROFILE\Downloads\host-free-fits.pem"
$EC2_IP = "3.229.118.71"
$RemoteUser = "ubuntu"

Write-Host "Deploying FreeFits to EC2..." -ForegroundColor Cyan
Write-Host "  Key: $KeyPath" -ForegroundColor Gray
Write-Host "  Host: $RemoteUser@$EC2_IP" -ForegroundColor Gray
Write-Host ""

if (-not (Test-Path $KeyPath)) {
    Write-Host "ERROR: Key file not found at $KeyPath" -ForegroundColor Red
    Write-Host "Edit this script and set `$KeyPath to your .pem file location." -ForegroundColor Yellow
    exit 1
}

# SSH in and run the deploy script on the server
ssh -i $KeyPath -o StrictHostKeyChecking=no "${RemoteUser}@${EC2_IP}" "cd /home/ubuntu/FreeFits && ./deploy.sh"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Deploy finished. Check your site: https://free-fits.com" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Deploy may have failed. Check the output above." -ForegroundColor Red
    exit $LASTEXITCODE
}
