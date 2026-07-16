#!/bin/bash
set -e

# ฟังก์ชันแสดงปุ่มยืนยันเพื่อกด Next
press_enter_to_continue() {
    echo
    read -r -p "Press [Enter] to continue..."
    clear
}

clear
echo "==================================================="
echo "       MMS SYSTEM OFFLINE INSTALLATION WIZARD       "
echo "==================================================="
echo
echo "This wizard will guide you through the offline installation."
echo

# Step 1: Check Docker
echo "[Step 1 of 4] Checking Prerequisites"
echo "---------------------------------------------------"
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker command not found. Please install Docker first."
    exit 1
fi
echo "[OK] Docker is installed and running."
press_enter_to_continue

# Step 2: Load Images
echo "==================================================="
echo "[Step 2 of 4] Loading Docker Images (.tar)"
echo "---------------------------------------------------"
echo "This step will load the packaged offline images."
echo "It may take a few minutes depending on your disk speed."
echo
read -r -p "Ready to load images? [Y/n]: " load_confirm
if [[ "$load_confirm" =~ ^[Nn]$ ]]; then
    echo "[INFO] Skip loading images."
else
    if [ ! -d "images" ]; then
        echo "[ERROR] 'images' folder not found."
        exit 1
    fi
    for f in images/*.tar; do
        if [ -f "$f" ]; then
            echo "Loading: $f..."
            docker load -i "$f"
        fi
    done
    echo
    echo "[OK] All images loaded successfully."
fi
press_enter_to_continue

# Step 3: Network Check
echo "==================================================="
echo "[Step 3 of 4] Checking Network Configuration"
echo "---------------------------------------------------"
echo "Checking if Docker network 'mms-network' exists..."
if ! docker network inspect mms-network &> /dev/null; then
    echo "Network 'mms-network' not found. Creating it now..."
    docker network create mms-network
    echo "[OK] Created network 'mms-network'."
else
    echo "[OK] Network 'mms-network' already exists."
fi
press_enter_to_continue

# Step 4: Run Containers
echo "==================================================="
echo "[Step 4 of 4] Deploying Applications"
echo "---------------------------------------------------"
echo "Ready to launch MMS containers using docker-compose."
echo
read -r -p "Start deployment now? [Y/n]: " deploy_confirm
if [[ "$deploy_confirm" =~ ^[Nn]$ ]]; then
    echo "[INFO] Installation paused. You can start it later by running 'docker compose up -d'."
else
    if [ -f "docker-compose.yml" ]; then
        echo "Deploying containers..."
        docker compose up -d
        echo
        echo "==================================================="
        echo "     MMS Application Deployed Successfully!"
        echo "==================================================="
    else
        echo "[ERROR] docker-compose.yml not found."
        exit 1
    fi
fi
echo
