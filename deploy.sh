#!/bin/bash
# Deployment script for FreeFits on AWS EC2

set -e  # Exit on error

echo "🚀 Starting FreeFits deployment..."

# Navigate to project directory
cd /home/ubuntu/FreeFits || exit

# Activate virtual environment
source venv/bin/activate

# Pull latest changes from GitHub
echo "📥 Pulling latest changes..."
git pull origin image-intelligence

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Restart the application service
echo "🔄 Restarting application..."
sudo systemctl restart freefits

# Check service status
echo "✅ Checking service status..."
sudo systemctl status freefits --no-pager

echo "🎉 Deployment complete!"



