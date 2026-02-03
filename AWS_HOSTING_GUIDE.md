# AWS Hosting Guide for FreeFits

This guide covers two free/cheap hosting options for your Flask application on AWS:

1. **AWS EC2 Free Tier** - Truly FREE for 12 months (Recommended for capstone)
2. **AWS Elastic Beanstalk** - FREE tier, easier deployment
3. **AWS Lightsail** - $3.50/month (simplest, but not free)

---

## Option 1: AWS EC2 Free Tier (FREE - Recommended)

### Prerequisites
- AWS account (free tier eligible)
- EC2 t2.micro instance (750 hours/month free for 12 months)
- Domain name (optional) or use EC2 public IP

### Step 1: Launch EC2 Instance

1. **Go to AWS Console → EC2 → Launch Instance**
   - Name: `freefits-production`
   - AMI: **Ubuntu Server 22.04 LTS** (free tier eligible)
   - Instance type: **t2.micro** (free tier eligible)
   - Key pair: Create new or use existing (download `.pem` file)
   - Network settings: 
     - Allow HTTP (port 80)
     - Allow HTTPS (port 443) - optional
     - Allow SSH (port 22) from your IP
   - Storage: 8GB gp3 (free tier: 30GB)

2. **Launch Instance**

### Step 2: Connect to EC2 Instance

**Important:** These commands should be run on your **LOCAL Windows machine**, NOT on the EC2 instance.

**Windows (PowerShell) - Run on YOUR computer:**
```powershell
# Navigate to folder with your .pem file (on your Windows machine)
cd C:\Users\tibaa\Downloads

# Set permissions (if needed)
# $env:USERNAME automatically uses your current Windows username
icacls.exe host-free-fits.pem /inheritance:r
icacls.exe host-free-fits.pem /grant:r "$($env:USERNAME):(R)"

# Alternative: If the above doesn't work, use your actual username explicitly
# icacls.exe host-free-fits.pem /grant:r "tibaa:(R)"

# Connect to EC2 (replace with your actual EC2 public IP)
ssh -i host-free-fits.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

**Mac/Linux - Run on YOUR computer:**
```bash
# Navigate to folder with your .pem file
cd ~/Downloads

# Set permissions
chmod 400 host-free-fits.pem

# Connect to EC2
ssh -i host-free-fits.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

**Note:** If you're already connected to EC2 (you see `ubuntu@ip-172-31-76-99:~$`), you can skip this step and proceed directly to **Step 3: Setup Server**.

### Step 3: Setup Server

Once connected to EC2, run these commands:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.12 and pip
sudo apt install -y python3.12 python3.12-venv python3-pip git nginx

# Install MongoDB (or use MongoDB Atlas - recommended)
# Option A: MongoDB Atlas (Cloud - FREE tier available)
# Go to https://www.mongodb.com/cloud/atlas and create free cluster
# Update MONGO_URI in .env file

# Option B: Install MongoDB locally (not recommended for production)
# sudo apt install -y mongodb

# Clone your repository
cd /home/ubuntu

# Option A: Use Personal Access Token (recommended)
# First, create a token at: https://github.com/settings/tokens
# Then use it as the password when prompted:
git clone https://github.com/tibatuba/FreeFits.git
# When prompted:
#   Username: tibatuba
#   Password: <paste your Personal Access Token here>

# Option B: Use SSH (if you have SSH keys set up)
# git clone git@github.com:tibatuba/FreeFits.git

# Option C: Make repository public temporarily (easiest for capstone)
# If you make the repo public, you can clone without authentication:
# git clone https://github.com/tibatuba/FreeFits.git

cd FreeFits
git checkout image-intelligence

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn  # Production WSGI server

# Create .env file
nano .env
```

### Step 4: Configure Environment Variables

Add all your environment variables to `.env`:

```env
SECRET_KEY=your-secret-key-here-generate-with-openssl-rand-hex-32
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/freefits?retryWrites=true&w=majority
GOOGLE_PLACES_API_KEY=your-google-places-api-key
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
AWS_S3_BUCKET_NAME=your-s3-bucket-name
AWS_S3_REGION=us-east-1
IMAGE_VALIDATION_API=rekognition
PORT=8000
LOG_LEVEL=info
```

**Generate SECRET_KEY:**
```bash
openssl rand -hex 32
```

### Step 5: Setup Gunicorn and Nginx

```bash
# Copy nginx configuration
sudo cp nginx_freefits.conf /etc/nginx/sites-available/freefits
sudo ln -s /etc/nginx/sites-available/freefits /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove default site

# Test nginx configuration
sudo nginx -t

# Copy systemd service file
sudo cp freefits.service /etc/systemd/system/

# Make deploy script executable
chmod +x deploy.sh

# Reload systemd and start services
sudo systemctl daemon-reload
sudo systemctl enable freefits
sudo systemctl start freefits
sudo systemctl enable nginx
sudo systemctl start nginx

# Check status
sudo systemctl status freefits
sudo systemctl status nginx
```

### Step 6: Update Security Group

1. Go to **EC2 → Security Groups → Select your instance's security group**
2. **Edit inbound rules:**
   - Type: HTTP, Port: 80, Source: 0.0.0.0/0
   - Type: HTTPS, Port: 443, Source: 0.0.0.0/0 (if using SSL)

### Step 7: Test Your Application

Visit: `http://YOUR_EC2_PUBLIC_IP`

### Step 8: Future Deployments

```bash
# SSH into your server
ssh -i freefits-key.pem ubuntu@YOUR_EC2_PUBLIC_IP

# Run deployment script
cd /home/ubuntu/FreeFits
./deploy.sh
```

### Monitoring and Logs

```bash
# View application logs
sudo journalctl -u freefits -f

# View nginx logs
sudo tail -f /var/log/nginx/freefits_access.log
sudo tail -f /var/log/nginx/freefits_error.log

# Restart application
sudo systemctl restart freefits

# Restart nginx
sudo systemctl restart nginx
```

---

## Option 2: AWS Elastic Beanstalk (FREE Tier - Easier)

### Prerequisites
- AWS account
- AWS CLI installed locally
- EB CLI installed

### Step 1: Install EB CLI

**Windows:**
```powershell
pip install awsebcli
```

**Mac/Linux:**
```bash
pip install awsebcli
```

### Step 2: Initialize Elastic Beanstalk

```bash
# In your project directory
cd C:\Users\tibaa\OneDrive\Documents\GitHub\FreeFits

# Initialize EB
eb init -p python-3.12 freefits-app --region us-east-1

# Create environment
eb create freefits-env --instance-type t3.micro

# This will:
# - Create EC2 instance (free tier eligible)
# - Setup load balancer
# - Configure nginx
# - Deploy your application
```

### Step 3: Configure Environment Variables

```bash
# Set environment variables
eb setenv SECRET_KEY=your-secret-key \
          MONGO_URI=your-mongo-uri \
          AWS_ACCESS_KEY_ID=your-key \
          AWS_SECRET_ACCESS_KEY=your-secret \
          AWS_S3_BUCKET_NAME=your-bucket \
          IMAGE_VALIDATION_API=rekognition
```

### Step 4: Deploy

```bash
# Deploy your application
eb deploy

# Open in browser
eb open
```

### Step 5: Future Deployments

```bash
# Make changes, then:
eb deploy
```

---

## Option 3: AWS Lightsail ($3.50/month)

### Step 1: Create Lightsail Instance

1. Go to **AWS Lightsail → Create instance**
2. Choose **Ubuntu 22.04**
3. Choose **$3.50/month** plan
4. Create instance

### Step 2: Connect and Setup

Follow the same steps as EC2 (Step 2-5 from Option 1).

---

## Cost Comparison

| Option | Cost | Difficulty | Best For |
|--------|------|------------|----------|
| EC2 Free Tier | **FREE** (12 months) | Medium | Capstone projects |
| Elastic Beanstalk | **FREE** (12 months) | Easy | Quick deployment |
| Lightsail | $3.50/month | Easy | Long-term projects |

---

## Important Notes

1. **MongoDB**: Use MongoDB Atlas (free tier) instead of installing locally
2. **SSL/HTTPS**: Use Let's Encrypt (free) for SSL certificates
3. **Domain**: Point your domain to EC2 public IP using Route 53 or your DNS provider
4. **Backups**: Setup automated backups for your database
5. **Monitoring**: Use CloudWatch (free tier) for basic monitoring

---

## Troubleshooting

### Application not starting
```bash
sudo journalctl -u freefits -n 50
```

### Nginx 502 Bad Gateway
- Check if gunicorn is running: `sudo systemctl status freefits`
- Check gunicorn logs: `sudo journalctl -u freefits -f`

### Can't connect via SSH
- Check security group allows SSH from your IP
- Verify key pair is correct

### Environment variables not loading
- Ensure `.env` file exists and has correct permissions
- Check `EnvironmentFile` in systemd service file

---

## Next Steps

1. Setup SSL certificate with Let's Encrypt
2. Configure custom domain
3. Setup automated backups
4. Configure CloudWatch monitoring
5. Setup CI/CD pipeline (optional)

---

## Support

For issues, check:
- Application logs: `sudo journalctl -u freefits -f`
- Nginx logs: `sudo tail -f /var/log/nginx/freefits_error.log`
- EC2 system logs: AWS Console → EC2 → Instance → Actions → Monitor and troubleshoot → Get system log

