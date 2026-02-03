#!/bin/bash
# Quick setup script for EC2 instance
# Run this after connecting to your EC2 instance for the first time

set -e

echo "🚀 Setting up FreeFits on EC2..."

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install dependencies
echo "📦 Installing Python, Git, and Nginx..."
sudo apt install -y python3.12 python3.12-venv python3-pip git nginx

# Clone repository (update with your GitHub URL)
echo "📥 Cloning repository..."
cd /home/ubuntu
if [ ! -d "FreeFits" ]; then
    git clone https://github.com/YOUR_USERNAME/FreeFits.git
    cd FreeFits
    git checkout image-intelligence
else
    echo "Repository already exists, skipping clone..."
    cd FreeFits
fi

# Create virtual environment
echo "🐍 Creating virtual environment..."
python3.12 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Setup nginx
echo "🌐 Configuring Nginx..."
sudo cp nginx_freefits.conf /etc/nginx/sites-available/freefits
sudo ln -sf /etc/nginx/sites-available/freefits /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t

# Setup systemd service
echo "⚙️ Configuring systemd service..."
sudo cp freefits.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable freefits
sudo systemctl enable nginx

# Make deploy script executable
chmod +x deploy.sh

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Create .env file with your environment variables:"
echo "   nano .env"
echo ""
echo "2. Start the services:"
echo "   sudo systemctl start freefits"
echo "   sudo systemctl start nginx"
echo ""
echo "3. Check status:"
echo "   sudo systemctl status freefits"
echo "   sudo systemctl status nginx"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u freefits -f"



