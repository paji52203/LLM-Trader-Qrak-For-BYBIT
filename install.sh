#!/bin/bash

# ==============================================================================
# LLM Trader Qrak for BYBIT - Automated Installation Script
# ==============================================================================
# This script will set up the Python virtual environment, install all
# required dependencies, and prepare the environment for running the bot.
# ==============================================================================

set -e

echo -e "\033[1;36m=============================================================\033[0m"
echo -e "\033[1;32m  Welcome to LLM Trader Qrak for BYBIT Installation\033[0m"
echo -e "\033[1;36m=============================================================\033[0m"
echo ""

# 1. System updates and required system dependencies
echo -e "\033[1;33m[1/4] Checking python system requirements...\033[0m"
if ! command -v python3 &> /dev/null; then
    echo "Python3 could not be found. Please install Python 3.10+."
    exit 1
fi
if ! command -v pip3 &> /dev/null; then
    echo "pip3 could not be found. Please install pip3."
    exit 1
fi
if ! command -v python3 -m venv &> /dev/null; then
    echo "python3-venv is required. Installing it now (requires sudo)..."
    sudo apt-get update && sudo apt-get install -y python3-venv
fi

# 2. Virtual Environment Setup
echo -e "\033[1;33m[2/4] Setting up Python Virtual Environment (.venv)...\033[0m"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "\033[0;32m Virtual environment created successfully.\033[0m"
else
    echo -e "\033[0;34m Virtual environment already exists, skipping creation.\033[0m"
fi

# 3. Installing PIP Requirements
echo -e "\033[1;33m[3/4] Installing / Upgrading PIP Dependencies...\033[0m"
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Environment Variables Setup
echo -e "\033[1;33m[4/4] Preparing Environment Configuration...\033[0m"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "\033[0;32m Created .env file from .env.example.\033[0m"
        echo -e "\033[0;31m IMPORTANT: Please edit the .env file with your specific API Keys!\033[0m"
    else
        echo -e "\033[0;31m Warning: .env.example not found. Please create a .env file manually.\033[0m"
    fi
else
    echo -e "\033[0;34m .env file already exists. Preserving your configuration.\033[0m"
fi

echo ""
echo -e "\033[1;36m=============================================================\033[0m"
echo -e "\033[1;32m Installation Complete! \033[0m"
echo -e "\033[1;36m=============================================================\033[0m"
echo -e "To start the bot manually, run:"
echo -e "   source .venv/bin/activate"
echo -e "   python start.py"
echo ""
echo -e "For background execution (Production), use PM2:"
echo -e "   pm2 start start.py --name bybit-bot --interpreter .venv/bin/python"
echo -e "\033[1;36m=============================================================\033[0m"
