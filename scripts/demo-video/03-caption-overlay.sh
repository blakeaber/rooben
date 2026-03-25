#!/usr/bin/env bash
# 03-caption-overlay.sh — Add text captions to a video clip
#
# Usage: 03-caption-overlay.sh <input> <output> <caption_spec> [caption_spec...]
#   input         Input video file
#   output        Output video file
#   caption_spec  Pipe-delimited: "text|start|end|position|style"
#                 position: bottom (default), top, center
#                 style: default (white sans-serif), code (green monospace)
#
# Example:
#   ./03-caption-overlay.sh clip.mp4 out.mp4 "Hello world|0.5|4.5|bottom|default"
#   ./03-caption-overlay.sh clip.mp4 out.mp4 "First caption|0|3|bottom|default" "Second|3.5|7|top|code"

source "$(dirname "$0")/config.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 3 ]]; then
    sed -n '2,14p' "$0" | sed 's/^# \?//'
    exit 0
fi

INPUT="$1"
OUTPUT="$2"
shift 2

[[ -f "$INPUT" ]] || log_error "Input file not found: $INPUT"
require_ffmpeg
mkdir -p "$(dirname "$OUTPUT")"

# Build compound drawtext filter from all caption specs
FILTER=""
for spec in "$@"; do
    TEXT=$(echo "$spec" | cut -d'|' -f1)
    START=$(echo "$spec" | cut -d'|' -f2)
    END=$(echo "$spec" | cut -d'|' -f3)
    POSITION=$(echo "$spec" | cut -d'|' -f4)
    STYLE=$(echo "$spec" | cut -d'|' -f5)

    POSITION="${POSITION:-bottom}"
    STYLE="${STYLE:-default}"

    # Compute y position
    case "$POSITION" in
        top)    Y_EXPR="y=60" ;;
        center) Y_EXPR="y=(h-text_h)/2" ;;
        *)      Y_EXPR="y=h-text_h-60" ;;  # bottom
    esac

    # Escape single quotes in text for FFmpeg
    TEXT="${TEXT//\'/\\\'}"
    # Escape colons in text
    TEXT="${TEXT//:/\\:}"

    # Style-specific options
    if [[ "$STYLE" == "code" ]]; then
        FONT="$FONT_MONO"
        FONTCOLOR="${HEX_EMERALD}"
        FONTSIZE=28
        BOXCOLOR="black@0.8"
        BOXBORDER=16
    else
        FONT="$FONT_PRIMARY"
        FONTCOLOR="white"
        FONTSIZE=32
        BOXCOLOR="black@0.6"
        BOXBORDER=12
    fi

    [[ -n "$FILTER" ]] && FILTER+=","

    FILTER+="drawtext=fontfile='${FONT}':"
    FILTER+="text='${TEXT}':"
    FILTER+="fontcolor=${FONTCOLOR}:fontsize=${FONTSIZE}:"
    FILTER+="x=(w-text_w)/2:${Y_EXPR}:"
    FILTER+="box=1:boxcolor=${BOXCOLOR}:boxborderw=${BOXBORDER}:"
    FILTER+="enable='between(t\\,${START}\\,${END})'"
done

log_step "Adding $(echo "$@" | wc -w | tr -d ' ') caption(s) to $(basename "$INPUT")"

ffmpeg -y -i "$INPUT" \
    -vf "$FILTER" \
    -c:v "$VIDEO_CODEC" -crf "$CRF" -preset "$PRESET" -pix_fmt "$PIX_FMT" \
    -c:a copy \
    "$OUTPUT" 2>/dev/null

log_done "Captioned → $(basename "$OUTPUT")"
