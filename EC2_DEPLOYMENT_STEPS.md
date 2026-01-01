# Complete EC2 Free Tier Deployment Guide

## 🎯 Overview
This guide will help you deploy FreeFits to AWS EC2 free tier (completely FREE for 12 months).

---

## PART 1: AWS Console Setup (Do this in your web browser)

### Step 1: Launch EC2 Instance

1. **Go to AWS Console**: https://console.aws.amazon.com
2. **Search for "EC2"** in the top search bar
3. **Click "Launch Instance"** button

4. **Configure Instance**:
   - **Name**: `freefits-production`
   - **AMI (Operating System)**: Select **"Ubuntu Server 22.04 LTS"** (free tier eligible)
   - **Instance type**: Select **"t2.micro"** (free tier eligible)
   - **Key pair**: 
     - Click "Create new key pair"
     - Name: `freefits-key`
     - Key pair type: RSA
     - File format: .pem
     - Click "Create key pair" - **DOWNLOAD THE FILE** (save it to `C:\Users\tibaa\Downloads\`)
   
5. **Network settings** (Click "Edit" to expand):
   - **Security group name**: `freefits-sg`
   - **VPC**: Keep default (or create new if needed)
   - **Subnet**: Keep default (auto-assign public IP)
   - **Auto-assign public IP**: Enable (required for internet access)
   
   **Inbound security group rules** (add these):
   - **SSH (22)**: 
     - Type: SSH
     - Port: 22
     - Source: My IP (recommended) OR Anywhere (0.0.0.0/0) for testing
     - Description: "Allow SSH from my computer"
   
   - **HTTP (80)**:
     - Type: HTTP
     - Port: 80
     - Source: Anywhere (0.0.0.0/0)
     - Description: "Allow HTTP web traffic"
   
   - **HTTPS (443)** (optional, for SSL later):
     - Type: HTTPS
     - Port: 443
     - Source: Anywhere (0.0.0.0/0)
     - Description: "Allow HTTPS web traffic"
   
   - **Custom TCP (8000)** (optional, for direct Flask access):
     - Type: Custom TCP
     - Port: 8000
     - Source: My IP (for testing only)
     - Description: "Direct Flask access for testing"
   
   **Outbound rules**: Keep default (All traffic allowed)
   
   **Note**: You can always add/edit security group rules later in EC2 → Security Groups
   
   **Advanced Network Settings** (usually not needed for basic setup):
   - **VPC**: Default VPC is fine (Virtual Private Cloud)
   - **Subnet**: Default subnet is fine (auto-assigns public IP)
   - **Elastic IP**: Not needed initially (IP changes on restart). Can add later if you want a permanent IP
   - **Load Balancer**: Not needed for single instance (only if you scale to multiple instances)

6. **Storage**: Keep default (8GB is fine, free tier includes 30GB)

7. **Click "Launch Instance"**

8. **Wait for instance to start** (takes 1-2 minutes)
   - Click "View all instances"
   - Wait until "Instance state" shows "Running"
   - **Copy the "Public IPv4 address"** (you'll need this!)

---

## PART 2: Connect to EC2 (Do this on your Windows computer)

### Step 2: Connect via SSH

**Open PowerShell on your Windows machine** (NOT in AWS console):

```powershell
# 1. Navigate to where you saved the .pem file
cd C:\Users\tibaa\Downloads

# 2. Set permissions on the key file
icacls.exe freefits-key.pem /inheritance:r
icacls.exe freefits-key.pem /grant:r "$($env:USERNAME):(R)"

# 3. Connect to EC2 (replace YOUR_EC2_PUBLIC_IP with the IP you copied)
ssh -i freefits-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

**Example** (if your IP is 3.229.118.71):
```powershell
ssh -i freefits-key.pem ubuntu@3.229.118.71
```

**First time connection**: Type `yes` when asked "Are you sure you want to continue connecting?"

**You should now see**: `ubuntu@ip-172-31-xx-xx:~$` - This means you're connected to EC2!

---

## PART 3: Setup Server (Do this on EC2 - you're now connected)

### Step 3: Install Required Software

Run these commands **one by one** on the EC2 instance:

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python, Git, and Nginx
sudo apt install -y python3.12 python3.12-venv python3-pip git nginx

# Navigate to home directory
cd /home/ubuntu

# Clone your repository (now that it's public)
git clone https://github.com/tibatuba/FreeFits.git

# Navigate into project
cd FreeFits

# Switch to your branch
git checkout image-intelligence

# Create virtual environment
python3.12 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### Step 4: Create .env File

```bash
# Generate a secret key
openssl rand -hex 32
# Copy the output (you'll need it)

# Create .env file
nano .env
```

**In the nano editor**, paste this (replace with YOUR actual values):

```env
SECRET_KEY=<paste the secret key from openssl command>
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/freefits?retryWrites=true&w=majority
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
AWS_S3_BUCKET_NAME=your-s3-bucket-name
AWS_S3_REGION=us-east-1
IMAGE_VALIDATION_API=rekognition
PORT=8000
LOG_LEVEL=info
```

**Note:** Google Places API is not used - the app uses Nominatim (OpenStreetMap) which is free and requires no API key.

**To save in nano**:
- Press `Ctrl+X`
- Press `Y`
- Press `Enter`

### Step 5: Setup Gunicorn and Nginx

```bash
# Make sure you're in the project directory
cd /home/ubuntu/FreeFits

# Copy nginx configuration
sudo cp nginx_freefits.conf /etc/nginx/sites-available/freefits

# Enable the site
sudo ln -s /etc/nginx/sites-available/freefits /etc/nginx/sites-enabled/

# Remove default nginx site
sudo rm /etc/nginx/sites-enabled/default

# Test nginx configuration
sudo nginx -t
# Should say "syntax is ok" and "test is successful"

# Copy systemd service file
sudo cp freefits.service /etc/systemd/system/

# Make deploy script executable
chmod +x deploy.sh

# Reload systemd
sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable freefits
sudo systemctl start freefits
sudo systemctl enable nginx
sudo systemctl start nginx

# Check if services are running
sudo systemctl status freefits
sudo systemctl status nginx
```

**If you see errors**, check logs:
```bash
sudo journalctl -u freefits -n 50
```

---

## PART 4: Final Steps (Back in AWS Console)

### Step 6: Verify Security Group

1. Go back to **AWS Console → EC2 → Instances**
2. Select your instance
3. Click **"Security"** tab
4. Click the **security group name** (e.g., `sg-xxxxx`)
5. Click **"Edit inbound rules"**
6. Make sure you have:
   - **SSH** (port 22) - from your IP or anywhere
   - **HTTP** (port 80) - from anywhere (0.0.0.0/0)
7. Click **"Save rules"**

---

## PART 5: Test Your Application

### Step 7: Visit Your Site

Open your browser and go to:
```
http://YOUR_EC2_PUBLIC_IP
```

**Example**: `http://3.229.118.71`

You should see your FreeFits application!

---

## 🔧 Troubleshooting

### If the site doesn't load:

1. **Check if services are running** (on EC2):
   ```bash
   sudo systemctl status freefits
   sudo systemctl status nginx
   ```

2. **Check application logs**:
   ```bash
   sudo journalctl -u freefits -n 50
   ```

3. **Check nginx logs**:
   ```bash
   sudo tail -f /var/log/nginx/freefits_error.log
   ```

4. **Restart services**:
   ```bash
   sudo systemctl restart freefits
   sudo systemctl restart nginx
   ```

5. **Verify security group** allows HTTP (port 80) from anywhere

### Common Issues:

- **502 Bad Gateway**: Gunicorn not running → `sudo systemctl restart freefits`
- **Connection refused**: Security group not allowing HTTP traffic
- **Environment variables not working**: Check `.env` file exists and has correct values

---

## 💻 Development Workflow (IMPORTANT!)

### Can I still develop my app after launching EC2?

**YES!** You can continue developing on your local machine. You **DO NOT** need to create new EC2 instances for development.

### Recommended Workflow:

**1. Develop Locally (Your Windows Computer)**
   - Edit code in your IDE (VS Code, etc.)
   - Test locally: `python run.py` (runs on `http://localhost:5000`)
   - Make changes, test, iterate

**2. Deploy to EC2 (Production Server)**
   - Push changes to GitHub
   - Pull changes on EC2
   - Restart services

### Typical Development Cycle:

```
┌─────────────────────────────────────┐
│ 1. Develop on Local Machine        │
│    - Edit code                      │
│    - Test with: python run.py      │
│    - Fix bugs                       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 2. Commit & Push to GitHub          │
│    git add .                        │
│    git commit -m "Added feature X"  │
│    git push origin image-intelligence│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 3. Deploy to EC2 (Production)       │
│    ssh into EC2                     │
│    cd /home/ubuntu/FreeFits          │
│    git pull origin image-intelligence│
│    ./deploy.sh                      │
└─────────────────────────────────────┘
```

### Quick Deploy Script (After Code Changes):

**On your local machine** (after pushing to GitHub):
```powershell
# Connect to EC2
ssh -i C:\Users\tibaa\Downloads\freefits-key.pem ubuntu@YOUR_EC2_IP

# Once connected, run:
cd /home/ubuntu/FreeFits
git pull origin image-intelligence
./deploy.sh
exit
```

### When to Use EC2 vs Local:

| Task | Where to Do It |
|------|----------------|
| **Writing code** | Local machine (faster, easier) |
| **Testing features** | Local machine first, then EC2 |
| **Production deployment** | EC2 (after testing locally) |
| **Database changes** | Test locally first, then apply to production |
| **API testing** | Both (local for dev, EC2 for production) |

### Pro Tips:

1. **Keep EC2 for production only** - Don't develop directly on EC2
2. **Test locally first** - Catch bugs before deploying
3. **Use Git branches** - Create feature branches, merge when ready
4. **One EC2 instance is enough** - No need for multiple instances unless you need staging/dev environments

---

## 📝 Future Updates

When you make changes to your code:

1. **On your local machine**: 
   ```powershell
   # Make your changes, then:
   git add .
   git commit -m "Your commit message"
   git push origin image-intelligence
   ```

2. **On EC2**:
   ```bash
   cd /home/ubuntu/FreeFits
   git pull origin image-intelligence
   ./deploy.sh
   ```

---

## ✅ Checklist

- [ ] EC2 instance launched and running
- [ ] Connected via SSH
- [ ] Software installed (Python, Git, Nginx)
- [ ] Repository cloned
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] .env file created with all credentials
- [ ] Gunicorn and Nginx configured
- [ ] Services started and running
- [ ] Security group allows HTTP traffic
- [ ] Application accessible via browser

---

## 🎉 You're Done!

Your application should now be live at: `http://YOUR_EC2_PUBLIC_IP`

**Note**: The IP address will change if you stop/start the instance. For a permanent URL, consider:
- Using an Elastic IP (free if instance is running)
- Setting up a domain name
- Using AWS Route 53 for DNS

