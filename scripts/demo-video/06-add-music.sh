#!/usr/bin/env bash
# 06-add-music.sh — Mix background music into a video at low volume
#
# Usage: 06-add-music.sh <video> <music> <output> [volume]
#   video   Input video file (with or without existing audio)
#   music   Background music file (.mp3, .wav, etc.)
#   output  Output video file
#   volume  Music volume 0.0-1.0 (default: 0.08 = barely audible)
#
# Example:
#   ./06-add-music.sh final.mp4 bg-track.mp3 final-with-music.mp4 0.08

source "$(dirname "$0")/config.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 3 ]]; then
    sed -n '2,12p' "$0" | sed 's/^# \?//'
    exit 0
fi

VIDEO="$1"
MUSIC="$2"
OUTPUT="$3"
VOLUME="${4:-0.08}"

[[ -f "$VIDEO" ]] || log_error "Video file not found: $VIDEO"
[[ -f "$MUSIC" ]] || log_error "Music file not found: $MUSIC"
require_ffmpeg
mkdir -p "$(dirname "$OUTPUT")"

VIDEO_DURATION=$(get_duration "$VIDEO")
FADE_OUT_START=$(echo "$VIDEO_DURATION - 3" | bc)

log_step "Mixing music at ${VOLUME} volume"

ffmpeg -y -i "$VIDEO" -i "$MUSIC" \
    -filter_complex "
        [1:a]aloop=loop=-1:size=2e+09,atrim=0:${VIDEO_DURATION},
        volume=${VOLUME},
        afade=t=in:st=0:d=2,
        afade=t=out:st=${FADE_OUT_START}:d=3[music];
        [0:a][music]amix=inputs=2:duration=first:dropout_transition=3[a]
    " \
    -map 0:v -map "[a]" \
    -c:v copy \
    -c:a "$AUDIO_CODEC" -b:a 192k \
    "$OUTPUT" 2>/dev/null

log_done "Music mixed → $(basename "$OUTPUT")"
