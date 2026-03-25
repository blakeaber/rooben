#!/usr/bin/env bash
# 07-concat.sh — Concatenate multiple video segments into one video
#
# Usage: 07-concat.sh <output> <segment1> <segment2> ...
#   output     Output video file
#   segment*   Input video segments (in order)
#
# Example:
#   ./07-concat.sh final.mp4 intro.mp4 demo.mp4 cta.mp4
#   ./07-concat.sh final.mp4 build/segments/*.mp4

source "$(dirname "$0")/config.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 3 ]]; then
    sed -n '2,12p' "$0" | sed 's/^# \?//'
    exit 0
fi

OUTPUT="$1"
shift
SEGMENTS=("$@")

require_ffmpeg
mkdir -p "$(dirname "$OUTPUT")"

# Validate all segments exist
for seg in "${SEGMENTS[@]}"; do
    [[ -f "$seg" ]] || log_error "Segment not found: $seg"
done

log_step "Concatenating ${#SEGMENTS[@]} segments"

# Build concat list file
CONCAT_LIST="$BUILD_DIR/concat-list.txt"
> "$CONCAT_LIST"
for seg in "${SEGMENTS[@]}"; do
    echo "file '$(realpath "$seg")'" >> "$CONCAT_LIST"
done

ffmpeg -y -f concat -safe 0 -i "$CONCAT_LIST" \
    -c:v "$VIDEO_CODEC" -crf "$CRF" -preset "$PRESET" -pix_fmt "$PIX_FMT" \
    -c:a "$AUDIO_CODEC" -b:a 128k \
    "$OUTPUT" 2>/dev/null

rm -f "$CONCAT_LIST"

log_done "Concatenated → $(basename "$OUTPUT") (${#SEGMENTS[@]} segments)"
