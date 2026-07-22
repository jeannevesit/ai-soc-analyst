#!/bin/bash
# NevesSec VPS Bootstrap Script
# Automatically deploys the AI SOC stack on a fresh Debian/Ubuntu server

echo "=========================================="
echo "🚀 Starting NevesSec AI SOC Stack Deployment"
echo "=========================================="

# 1. Update system package repository
echo "🔄 Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# 2. Install Docker, Docker Compose, Git, and utilities
echo "📦 Installing Docker, Git, and dependencies..."
sudo apt-get install -y docker.io docker-compose git curl grep

# Start and enable Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Add current user to docker group so sudo isn't needed for docker commands
sudo usermod -aG docker $USER

# 3. Clone Repository
echo "📥 Cloning project repository from GitHub..."
rm -rf ai-soc-analyst
git clone https://github.com/jr7020-pixel/ai-soc-analyst.git
cd ai-soc-analyst

# 4. Start Docker Stack
echo "🐳 Launching Docker Compose containers..."
sudo docker-compose -f agentic-n8n/docker-compose.yml up --build -d

# 5. Set up Cloudflare Tunnels
echo "☁️ Fetching Cloudflare Tunnel agent..."
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared

echo "🔗 Establishing secure tunnels (this takes ~10 seconds)..."
# Start tunnel for SIEM (port 8000)
./cloudflared tunnel --url http://localhost:8000 > siem.log 2>&1 &
# Start tunnel for n8n (port 5678)
./cloudflared tunnel --url http://localhost:5678 > n8n.log 2>&1 &

# Wait for tunnels to initialize and register subdomains
sleep 10

# Extract URLs from logs
SIEM_URL=$(grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' siem.log | head -n 1)
N8N_URL=$(grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' n8n.log | head -n 1)

echo "=========================================="
echo "🎉 DEPLOYMENT COMPLETE!"
echo "=========================================="
echo "Your cloud services are live:"
echo ""
echo "🖥️  Enterprise SIEM Console:"
echo "    $SIEM_URL"
echo ""
echo "🤖  n8n Automation Console:"
echo "    $N8N_URL"
echo "=========================================="
echo "Note: Copy these URLs! You can now access them from any device."
echo "Keep this SSH session open to maintain the active tunnels."
