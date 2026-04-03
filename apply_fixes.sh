#!/bin/bash
# Apply fixes to the main bot directory

TARGET_DIR=\$1

if [ -z "\$TARGET_DIR" ]; then echo "Usage: ./apply_fixes.sh /path/to/bot"; exit 1; fi
if [ ! -d "\$TARGET_DIR" ]; then echo "Error: \$TARGET_DIR not found"; exit 1; fi

BACKUP_DIR="backup_bybit_fix_\$(date +%Y%m%d_%H%M%S)"
mkdir -p "\$BACKUP_DIR"

echo "📦 Backing up files to \$BACKUP_DIR..."
cp "\$TARGET_DIR/src/platforms/exchange_manager.py" "\$BACKUP_DIR/" 2>/dev/null
cp "\$TARGET_DIR/src/trading/trading_strategy.py" "\$BACKUP_DIR/" 2>/dev/null
cp "\$TARGET_DIR/start.py" "\$BACKUP_DIR/" 2>/dev/null

echo "🚀 Applying fixes..."
cp -rv src/ "\$TARGET_DIR/"
cp -v start.py "\$TARGET_DIR/"

echo "✅ Fixes applied successfully!"
echo "You can now run your bot with ./run.sh"
