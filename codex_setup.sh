#!/bin/bash
set -e

pip install yt-dlp

# 可選（建議）
apt-get update
apt-get install -y ffmpeg jq
