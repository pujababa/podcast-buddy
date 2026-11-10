#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -e

echo "=== [1/2] Installing Python production dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== [2/2] Checking FFmpeg installation for audio processing ==="
if command -v ffmpeg &> /dev/null; then
    echo "FFmpeg is already installed in system PATH: $(command -v ffmpeg)"
else
    echo "FFmpeg not found in system PATH. Installing static Linux x64 FFmpeg binary..."
    mkdir -p bin
    if [ ! -f bin/ffmpeg ]; then
        curl -s -L https://github.com/eugeneware/ffmpeg-static/releases/download/b4.4/ffmpeg-linux-x64 -o bin/ffmpeg
        chmod +x bin/ffmpeg
        echo "Static FFmpeg successfully installed to bin/ffmpeg"
    else
        echo "Static FFmpeg already exists in bin/ffmpeg"
    fi
fi

echo "=== Build completed successfully! ==="

