#!/bin/bash

echo "================================================"
echo "  🤖 Tokocrypto AI Trading Bot - INSTALLER"
echo "================================================"

# Cek Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 tidak ditemukan! Install dulu:"
    echo "   sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PYTHON_VERSION" -lt 10 ]; then
    echo "❌ Python 3.10+ dibutuhkan. Versi Anda: 3.$PYTHON_VERSION"
    exit 1
fi

echo "✅ Python3 ditemukan"

# Install system deps jika belum ada
echo "📦 Mengecek dependensi sistem..."
sudo apt-get install -y python3-venv python3-dev build-essential 2>/dev/null | tail -1

# Buat virtual environment
echo "🔧 Membuat Virtual Environment..."
python3 -m venv venv

# Aktifkan dan install packages
echo "📥 Menginstall library Python (butuh beberapa menit)..."
source venv/bin/activate
pip3 install --upgrade pip -q
pip3 install -r requirements.txt

echo ""
echo "================================================"
echo "  ✅ INSTALASI SELESAI!"
echo "================================================"
echo ""

# Cek apakah keys.env sudah diisi
if grep -q "YOUR_KEY_HERE" keys.env 2>/dev/null || ! grep -q "TOKOCRYPTO_API_KEY" keys.env 2>/dev/null; then
    echo "⚠️  WAJIB: Isi API Keys di file keys.env sebelum jalan!"
    echo "   nano keys.env"
    echo ""
    echo "   Yang harus diisi:"
    echo "   - TOKOCRYPTO_API_KEY"
    echo "   - TOKOCRYPTO_API_SECRET"
    echo "   - GOOGLE_STUDIO_API_KEY"
    echo ""
else
    echo "✅ keys.env sudah terisi"
fi

echo "🚀 Untuk menjalankan bot:"
echo "   ./run.sh"
echo ""
