#!/usr/bin/env bash
# 05-transitions.sh — Add fade-in and fade-out transitions to a video clip
#
# Usage: 05-transitions.sh <input> <output> [fade_in] [fade_out]
#   input     Input video file
#   output    Output video file
#   fade_in   Fade-in duration in seconds (default: 0.5)
#   fade_out  Fade-out duration in seconds (default: 0.5)
#
# Example:
#   ./05-transitions.sh clip.mp4 faded-clip.mp4 0.5 0.3

source "$(dirname "$0")/config.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 2 ]]; then
    sed -n '2,12p' "$0" | sed 's/^# \?//'
    exit 0
fi

INPUT="$1"
OUTPUT="$2"
FADE_IN="${3:-$DEFAULT_FADE_IN}"
FADE_OUT="${4:-$DEFAULT_FADE_OUT}"

[[ -f "$INPUT" ]] || log_error "Input file not found: $INPUT"
require_ffmpeg
mkdir -p "$(dirname "$OUTPUT")"

DURATION=$(get_duration "$INPUT")
FADE_OUT_START=$(echo "$DURATION - $FADE_OUT" | bc)

log_step "Fading $(basename "$INPUT") [in:${FADE_IN}s out:${FADE_OUT}s]"

VIDEO_FILTER="fade=t=in:st=0:d=${FADE_IN},fade=t=out:st=${FADE_OUT_START}:d=${FADE_OUT}"

if has_audio "$INPUT"; then
    AUDIO_FILTER="afade=t=in:st=0:d=${FADE_IN},afade=t=out:st=${FADE_OUT_START}:d=${FADE_OUT}"
    ffmpeg -y -i "$INPUT" \
        -vf "$VIDEO_FILTER" \
        -af "$AUDIO_FILTER" \
        -c:v "$VIDEO_CODEC" -crf "$CRF" -preset "$PRESET" -pix_fmt "$PIX_FMT" \
        -c:a "$AUDIO_CODEC" -b:a 128k \
        "$OUTPUT" 2>/dev/null
else
    ffmpeg -y -i "$INPUT" \
        -vf "$VIDEO_FILTER" \
        -c:v "$VIDEO_CODEC" -crf "$CRF" -preset "$PRESET" -pix_fmt "$PIX_FMT" \
        "$OUTPUT" 2>/dev/null
fi

log_done "Faded → $(basename "$OUTPUT")"
