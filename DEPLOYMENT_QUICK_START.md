# Quick Start: Deploy FreeFits to AWS EC2 (FREE)

## Prerequisites
- AWS account (free tier eligible)
- GitHub repository URL
- MongoDB Atlas account (free tier) or MongoDB connection string
- AWS credentials (for S3 and Rekognition)

## Edit locally, deploy easily (recommended workflow)

1. **Edit code in Cursor** on your Windows machine (this repo: `C:\Users\tibaa\OneDrive\Documents\GitHub\FreeFits`).
2. **Commit and push** to GitHub (same branch your EC2 uses, e.g. `main` or `image-intelligence`).
3. **Deploy in one command** from PowerShell in this project folder:
   ```powershell
   .\deploy-from-windows.ps1
   ```
   This SSHs to EC2, runs `git pull`, installs deps, and restarts the app. No need to open files on the server.

**First-time setup:** Ensure EC2 has your repo cloned and `deploy.sh` is executable. If your branch or key path differ, edit the variables at the top of `deploy-from-windows.ps1`.

---

## 5-Minute Setup

### 1. Launch EC2 Instance (2 minutes)
1. AWS Console → EC2 → Launch Instance
2. **Ubuntu 22.04 LTS**, **t2.micro**, create key pair
3. Security Group: Allow HTTP (80), HTTPS (443), SSH (22)
4. Launch

### 2. Connect to EC2 (1 minute)
```powershell
# Windows PowerShell
ssh -i your-key.pem ubuntu@YOUR_EC2_IP
```

### 3. Run Setup Script (2 minutes)
```bash
# On EC2 instance
wget https://raw.githubusercontent.com/YOUR_USERNAME/FreeFits/image-intelligence/setup_ec2.sh
chmod +x setup_ec2.sh
./setup_ec2.sh
```

**OR manually:**
```bash
# Update system
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.12 python3.12-venv python3-pip git nginx

# Clone repo
cd /home/ubuntu
git clone https://github.com/YOUR_USERNAME/FreeFits.git
cd FreeFits
git checkout image-intelligence

# Setup Python
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup Nginx
sudo cp nginx_freefits.conf /etc/nginx/sites-available/freefits
sudo ln -s /etc/nginx/sites-available/freefits /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t

# Setup systemd
sudo cp freefits.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable freefits nginx
```

### 4. Configure Environment Variables
```bash
nano .env
```

Add:
```env
SECRET_KEY=$(openssl rand -hex 32)
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/freefits
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_S3_BUCKET_NAME=your-bucket
AWS_REGION=us-east-1
IMAGE_VALIDATION_API=rekognition
```

### 5. Start Services
```bash
sudo systemctl start freefits
sudo systemctl start nginx
```

### 6. Test
Visit: `http://YOUR_EC2_IP`

---

## Common Commands

```bash
# View logs
sudo journalctl -u freefits -f

# Restart app
sudo systemctl restart freefits

# Deploy updates
./deploy.sh

# Check status
sudo systemctl status freefits
sudo systemctl status nginx
```

---

## Troubleshooting

**502 Bad Gateway:**
```bash
sudo systemctl restart freefits
sudo journalctl -u freefits -n 50
```

**Can't connect:**
- Check security group allows HTTP (port 80)
- Check if services are running: `sudo systemctl status freefits nginx`

**Environment variables not working:**
- Check `.env` file exists and has correct format
- Restart service: `sudo systemctl restart freefits`

---

## Cost: $0/month (Free Tier - 12 months)

After 12 months: ~$8-10/month for t2.micro instance



