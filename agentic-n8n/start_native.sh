#!/bin/bash

# Native Startup Script for AI SOC Analyst (No Docker Required)
# Binds:
# - Mock SIEM to http://localhost:8000
# - MCP Server to http://localhost:8500 (SSE)
# - n8n to http://localhost:5678

# Terminate background processes on exit
trap 'kill $(jobs -p)' EXIT

echo "===================================================="
echo "      Starting Local AI SOC Analyst Natively        "
echo "===================================================="

# 1. Check Prereqs
echo "[*] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "[!] Error: python3 is not installed. Please install Python 3."
    exit 1
fi

echo "[*] Checking Node.js / npm..."
if ! command -v npm &> /dev/null; then
    echo "[!] Warning: npm/node not found. You can still run the SIEM and MCP, but npx n8n will fail."
    echo "[!] Please install Node.js (https://nodejs.org) to run n8n natively."
fi

# 2. Setup and run Mock SIEM
echo "[*] Starting Mock SIEM on http://localhost:8000..."
cd mock-siem
python3 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 &
SIEM_PID=$!
deactivate
cd ..

# 3. Setup and run MCP Server
echo "[*] Starting MCP Server on http://localhost:8500..."
cd mcp-server
python3 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
python server.py --sse --host 127.0.0.1 --port 8500 &
MCP_PID=$!
deactivate
cd ..

# 4. Start n8n
if command -v npx &> /dev/null; then
    echo "[*] Starting n8n on http://localhost:5678..."
    echo "[*] Setting environment variables for n8n..."
    export N8N_PORT=5678
    export N8N_ENCRYPTION_KEY=soc_analyst_secret_key_999
    # Run n8n in background
    npx n8n start &
    N8N_PID=$!
else
    echo "[!] Skipped starting n8n (npm/npx not found)."
fi

echo ""
echo "===================================================="
echo "   All services are launching in the background!    "
echo "   - Mock SIEM: http://localhost:8000"
echo "   - MCP Server: http://localhost:8500"
echo "   - n8n Console: http://localhost:5678"
echo "===================================================="
echo "Press Ctrl+C to stop all services."
echo ""

# Keep script running to maintain background jobs
wait
