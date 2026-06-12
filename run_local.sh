#!/bin/bash
# Local dev runner — loads .env.local instead of .env
# Usage: ./run_local.sh

if [ ! -f .env.local ]; then
  echo "❌ .env.local not found"
  echo "   Copy .env.local.example → .env.local and fill in your test bot token"
  exit 1
fi

echo "🤖 Starting bot in LOCAL mode (polling)..."
echo "   Loaded: .env.local"
export $(grep -v '^#' .env.local | grep -v '^$' | xargs)
python main.py
