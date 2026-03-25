#!/usr/bin/env bash
# 08-gif.sh — Export a high-quality GIF from a video (two-pass palette)
#
# Usage: 08-gif.sh <input> [output] [width] [fps] [max_duration]
#   input         Input video file
#   output        Output GIF path (default: build/<input-name>.gif)
#   width         GIF width in pixels (default: 640)
#   fps           GIF frame rate (default: 12)
#   max_duration  Maximum duration in seconds (default: 15)
#
# Example:
#   ./08-gif.sh build/rooben-demo-final.mp4
#   ./08-gif.sh build/rooben-demo-final.mp4 build/rooben-demo.gif 640 12 15

source "$(dirname "$0")/config.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 1 ]]; then
    sed -n '2,13p' "$0" | sed 's/^# \?//'
    exit 0
fi

INPUT="$1"
BASENAME=$(basename "${INPUT%.*}")
OUTPUT="${2:-$BUILD_DIR/${BASENAME}.gif}"
WIDTH="${3:-$GIF_WIDTH}"
GIF_FRAMERATE="${4:-$GIF_FPS}"
MAX_DUR="${5:-$GIF_MAX_DURATION}"

[[ -f "$INPUT" ]] || log_error "Input file not found: $INPUT"
require_ffmpeg
mkdir -p "$(dirname "$OUTPUT")"

PALETTE="$BUILD_DIR/palette-${BASENAME}.png"

log_step "Generating GIF (${WIDTH}px, ${GIF_FRAMERATE}fps, max ${MAX_DUR}s)"

# Pass 1: Generate optimized palette
ffmpeg -y -ss 0 -t "$MAX_DUR" -i "$INPUT" \
    -vf "fps=${GIF_FRAMERATE},scale=${WIDTH}:-1:flags=lanczos,palettegen=stats_mode=diff" \
    "$PALETTE" 2>/dev/null

# Pass 2: Render GIF using palette
ffmpeg -y -ss 0 -t "$MAX_DUR" -i "$INPUT" -i "$PALETTE" \
    -lavfi "fps=${GIF_FRAMERATE},scale=${WIDTH}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
    "$OUTPUT" 2>/dev/null

rm -f "$PALETTE"

GIF_SIZE=$(du -h "$OUTPUT" | cut -f1)
log_done "GIF → $(basename "$OUTPUT") (${GIF_SIZE})"
