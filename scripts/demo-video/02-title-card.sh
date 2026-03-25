#!/usr/bin/env bash
# 02-title-card.sh — Generate a branded title card with text
#
# Usage: 02-title-card.sh <title> <subtitle> [tagline] [duration] [output]
#   title     Main title text (displayed in teal)
#   subtitle  Subtitle text (displayed in white)
#   tagline   Optional tagline (displayed in muted gray)
#   duration  Duration in seconds (default: 4)
#   output    Output path (default: build/titled/title-card.mp4)
#
# Example:
#   ./02-title-card.sh "Rooben" "Autonomous Agent Orchestration" "Your taste is the product." 4

source "$(dirname "$0")/config.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 2 ]]; then
    sed -n '2,13p' "$0" | sed 's/^# \?//'
    exit 0
fi

TITLE="$1"
SUBTITLE="$2"
TAGLINE="${3:-}"
DURATION="${4:-$DEFAULT_TITLE_DURATION}"
OUTPUT="${5:-$BUILD_DIR/titled/title-card.mp4}"

require_ffmpeg
mkdir -p "$(dirname "$OUTPUT")"

[[ -z "$FONT_BOLD" ]] && log_error "No fonts found. Install dejavu-sans or set FONT_BOLD."

log_step "Generating title card: \"$TITLE\""

# Build the drawtext filter chain with staggered fade-in
FILTER="color=c=${HEX_BG_DARK}:s=${RESOLUTION}:d=${DURATION}:r=${FPS}[bg];"
FILTER+="[bg]"

# Thin teal horizontal rule (centered, above subtitle area)
FILTER+="drawbox=x=(iw/2)-120:y=(ih/2)-30:w=240:h=2:color=${HEX_TEAL}@0.6:t=fill,"

# Title — large teal text, centered above the rule
FILTER+="drawtext=fontfile='${FONT_BOLD}':"
FILTER+="text='${TITLE//\'/\\\'}':"
FILTER+="fontcolor=${HEX_TEAL}:fontsize=72:"
FILTER+="x=(w-text_w)/2:y=(h/2)-100:"
FILTER+="alpha='if(lt(t\,0.8)\,t/0.8\,1)',"

# Subtitle — white, below the rule
FILTER+="drawtext=fontfile='${FONT_PRIMARY}':"
FILTER+="text='${SUBTITLE//\'/\\\'}':"
FILTER+="fontcolor=${HEX_TEXT_PRIMARY}:fontsize=36:"
FILTER+="x=(w-text_w)/2:y=(h/2)+20:"
FILTER+="alpha='if(lt(t\,1.0)\,(t-0.2)/0.8\,if(lt(t\,0.2)\,0\,1))',"

# Tagline — muted gray, smallest
if [[ -n "$TAGLINE" ]]; then
    FILTER+="drawtext=fontfile='${FONT_PRIMARY}':"
    FILTER+="text='${TAGLINE//\'/\\\'}':"
    FILTER+="fontcolor=${HEX_TEXT_SECONDARY}:fontsize=24:"
    FILTER+="x=(w-text_w)/2:y=(h/2)+80:"
    FILTER+="alpha='if(lt(t\,1.2)\,(t-0.4)/0.8\,if(lt(t\,0.4)\,0\,1))',"
fi

# Fade in/out on the whole card
FADE_OUT_START=$(echo "$DURATION - $DEFAULT_FADE_OUT" | bc)
FILTER+="fade=t=in:st=0:d=${DEFAULT_FADE_IN},"
FILTER+="fade=t=out:st=${FADE_OUT_START}:d=${DEFAULT_FADE_OUT}"
FILTER+="[v]"

ffmpeg -y \
    -f lavfi -i "color=c=${HEX_BG_DARK}:s=${RESOLUTION}:d=${DURATION}:r=${FPS}" \
    -f lavfi -i "anullsrc=r=44100:cl=stereo" \
    -filter_complex "$FILTER" \
    -map "[v]" -map 1:a \
    -c:v "$VIDEO_CODEC" -crf "$CRF" -preset "$PRESET" -pix_fmt "$PIX_FMT" \
    -c:a "$AUDIO_CODEC" -b:a 128k \
    -shortest \
    "$OUTPUT" 2>/dev/null

log_done "Title card → $(basename "$OUTPUT") (${DURATION}s)"
