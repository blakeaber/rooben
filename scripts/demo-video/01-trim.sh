#!/usr/bin/env bash
# 01-trim.sh — Trim a raw clip to [start, end] and normalize to 1080p h264
#
# Usage: 01-trim.sh <input> <start> <end> <output>
#   input   Path to raw video file (.mov, .mp4, etc.)
#   start   Start timestamp (HH:MM:SS or seconds)
#   end     End timestamp (HH:MM:SS or seconds)
#   output  Output path (.mp4)
#
# Example:
#   ./01-trim.sh raw/cli-demo.mov 00:00:02 00:00:45 build/trimmed/cli-demo.mp4

source "$(dirname "$0")/config.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 4 ]]; then
    sed -n '2,12p' "$0" | sed 's/^# \?//'
    exit 0
fi

INPUT="$1"
START="$2"
END="$3"
OUTPUT="$4"

[[ -f "$INPUT" ]] || log_error "Input file not found: $INPUT"
require_ffmpeg

mkdir -p "$(dirname "$OUTPUT")"

log_step "Trimming $(basename "$INPUT") [$START → $END]"

# Build audio options — handle clips with no audio
if has_audio "$INPUT"; then
    ffmpeg -y -ss "$START" -to "$END" -i "$INPUT" \
        -vf "scale=${RES_W}:${RES_H}:force_original_aspect_ratio=decrease,pad=${RES_W}:${RES_H}:(ow-iw)/2:(oh-ih)/2:color=${HEX_BG_DARK}" \
        -c:v "$VIDEO_CODEC" -crf "$CRF" -preset "$PRESET" \
        -pix_fmt "$PIX_FMT" -r "$FPS" \
        -c:a "$AUDIO_CODEC" -b:a 128k \
        "$OUTPUT" 2>/dev/null
else
    ffmpeg -y -ss "$START" -to "$END" -i "$INPUT" \
        -f lavfi -i anullsrc=r=44100:cl=stereo \
        -vf "scale=${RES_W}:${RES_H}:force_original_aspect_ratio=decrease,pad=${RES_W}:${RES_H}:(ow-iw)/2:(oh-ih)/2:color=${HEX_BG_DARK}" \
        -c:v "$VIDEO_CODEC" -crf "$CRF" -preset "$PRESET" \
        -pix_fmt "$PIX_FMT" -r "$FPS" \
        -c:a "$AUDIO_CODEC" -b:a 128k \
        -shortest \
        "$OUTPUT" 2>/dev/null
fi

log_done "Trimmed → $(basename "$OUTPUT")"
