#!/usr/bin/env bash
# 04-speed-ramp.sh — Change playback speed of a video clip
#
# Usage: 04-speed-ramp.sh <input> <output> <speed>
#   input   Input video file
#   output  Output video file
#   speed   Speed multiplier (>1 = faster, <1 = slower)
#           e.g., 1.5 = 1.5x faster, 0.5 = half speed
#
# Example:
#   ./04-speed-ramp.sh clip.mp4 fast-clip.mp4 2.0

source "$(dirname "$0")/config.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 3 ]]; then
    sed -n '2,12p' "$0" | sed 's/^# \?//'
    exit 0
fi

INPUT="$1"
OUTPUT="$2"
SPEED="$3"

[[ -f "$INPUT" ]] || log_error "Input file not found: $INPUT"
require_ffmpeg
mkdir -p "$(dirname "$OUTPUT")"

# Compute PTS factor: 1/speed (faster = smaller PTS)
PTS_FACTOR=$(echo "scale=6; 1.0 / $SPEED" | bc)

# Build atempo chain — atempo only accepts 0.5-2.0 range
# For values outside this, chain multiple atempo filters
build_atempo_chain() {
    local speed="$1"
    local chain=""

    # Handle speeds > 2.0: chain atempo=2.0 repeatedly
    while (( $(echo "$speed > 2.0" | bc -l) )); do
        [[ -n "$chain" ]] && chain+=","
        chain+="atempo=2.0"
        speed=$(echo "scale=6; $speed / 2.0" | bc)
    done

    # Handle speeds < 0.5: chain atempo=0.5 repeatedly
    while (( $(echo "$speed < 0.5" | bc -l) )); do
        [[ -n "$chain" ]] && chain+=","
        chain+="atempo=0.5"
        speed=$(echo "scale=6; $speed / 0.5" | bc)
    done

    # Final atempo for remaining speed
    [[ -n "$chain" ]] && chain+=","
    chain+="atempo=${speed}"

    echo "$chain"
}

ATEMPO_CHAIN=$(build_atempo_chain "$SPEED")

log_step "Speed ${SPEED}x on $(basename "$INPUT")"

if has_audio "$INPUT"; then
    ffmpeg -y -i "$INPUT" \
        -filter_complex "[0:v]setpts=${PTS_FACTOR}*PTS[v];[0:a]${ATEMPO_CHAIN}[a]" \
        -map "[v]" -map "[a]" \
        -c:v "$VIDEO_CODEC" -crf "$CRF" -preset "$PRESET" -pix_fmt "$PIX_FMT" \
        -c:a "$AUDIO_CODEC" -b:a 128k \
        "$OUTPUT" 2>/dev/null
else
    ffmpeg -y -i "$INPUT" \
        -filter_complex "[0:v]setpts=${PTS_FACTOR}*PTS[v]" \
        -map "[v]" \
        -c:v "$VIDEO_CODEC" -crf "$CRF" -preset "$PRESET" -pix_fmt "$PIX_FMT" \
        "$OUTPUT" 2>/dev/null
fi

log_done "Speed ${SPEED}x → $(basename "$OUTPUT")"
