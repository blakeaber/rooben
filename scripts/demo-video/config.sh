#!/usr/bin/env bash
# config.sh — Central configuration for the Rooben demo video pipeline
# Source this file from other scripts: source "$(dirname "$0")/config.sh"

set -euo pipefail

# ── Directories ───────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
RAW_DIR="${SCRIPT_DIR}/raw"
ASSETS_DIR="${PROJECT_ROOT}/docs/assets"

# ── Brand Colors (FFmpeg hex format) ──────────────────────────────────────────
COLOR_TEAL="0x0d9488"
COLOR_EMERALD="0x16a34a"
COLOR_RED="0xdc2626"
COLOR_VIOLET="0x7c3aed"
COLOR_BG_DARK="0x0f172a"           # Slate-900 — dark card background
COLOR_TEXT_PRIMARY="0xf8fafc"       # Slate-50  — bright white text
COLOR_TEXT_SECONDARY="0x94a3b8"     # Slate-400 — muted secondary text

# Hex versions for drawtext (# prefix)
HEX_TEAL="#0d9488"
HEX_EMERALD="#16a34a"
HEX_BG_DARK="#0f172a"
HEX_TEXT_PRIMARY="#f8fafc"
HEX_TEXT_SECONDARY="#94a3b8"

# ── Video Defaults ────────────────────────────────────────────────────────────
RESOLUTION="1920x1080"
RES_W=1920
RES_H=1080
FPS=30
VIDEO_CODEC="libx264"
AUDIO_CODEC="aac"
CRF=18                              # Visually lossless
PRESET="slow"                       # Quality over speed
PIX_FMT="yuv420p"                   # Universal player compatibility

# ── Font Configuration ────────────────────────────────────────────────────────
# Try common Linux paths first, then macOS
FONT_PRIMARY=""
FONT_BOLD=""
FONT_MONO=""

font_candidates_primary=(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    "/usr/share/fonts/TTF/DejaVuSans.ttf"
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"
    "/System/Library/Fonts/Helvetica.ttc"
    "/System/Library/Fonts/SFNSText.ttf"
)
font_candidates_bold=(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf"
    "/System/Library/Fonts/Helvetica.ttc"
    "/System/Library/Fonts/SFNSText-Bold.ttf"
)
font_candidates_mono=(
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf"
    "/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf"
    "/System/Library/Fonts/SFNSMono.ttf"
    "/System/Library/Fonts/Menlo.ttc"
)

for f in "${font_candidates_primary[@]}"; do
    [[ -f "$f" ]] && FONT_PRIMARY="$f" && break
done
for f in "${font_candidates_bold[@]}"; do
    [[ -f "$f" ]] && FONT_BOLD="$f" && break
done
for f in "${font_candidates_mono[@]}"; do
    [[ -f "$f" ]] && FONT_MONO="$f" && break
done

# Fall back to whatever is available
if [[ -z "$FONT_PRIMARY" ]]; then
    FONT_PRIMARY=$(fc-list : file | head -1 | cut -d: -f1 2>/dev/null || echo "")
    FONT_BOLD="$FONT_PRIMARY"
    FONT_MONO="$FONT_PRIMARY"
fi

# ── Default Durations (seconds) ──────────────────────────────────────────────
DEFAULT_FADE_IN=0.5
DEFAULT_FADE_OUT=0.5
DEFAULT_TITLE_DURATION=4

# ── GIF Settings ─────────────────────────────────────────────────────────────
GIF_WIDTH=640
GIF_FPS=12
GIF_MAX_DURATION=15

# ── Helper Functions ─────────────────────────────────────────────────────────

# Print a step indicator
log_step() {
    echo -e "\033[36m▶\033[0m $1"
}

# Print success
log_done() {
    echo -e "\033[32m✓\033[0m $1"
}

# Print error and exit
log_error() {
    echo -e "\033[31m✗\033[0m $1" >&2
    exit 1
}

# Check that ffmpeg is available
require_ffmpeg() {
    command -v ffmpeg &>/dev/null || log_error "ffmpeg not found. Install: brew install ffmpeg / apt install ffmpeg"
    command -v ffprobe &>/dev/null || log_error "ffprobe not found. Install: brew install ffmpeg / apt install ffmpeg"
}

# Get video duration in seconds
get_duration() {
    ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"
}

# Check if file has an audio stream
has_audio() {
    ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 "$1" 2>/dev/null | grep -q audio
}

# Ensure build directories exist
ensure_build_dirs() {
    mkdir -p "$BUILD_DIR"/{trimmed,titled,captioned,sped,segments}
}

# ── Initialize ───────────────────────────────────────────────────────────────
ensure_build_dirs
