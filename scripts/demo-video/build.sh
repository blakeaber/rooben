#!/usr/bin/env bash
# build.sh — Master orchestrator for the Rooben demo video pipeline
#
# Usage: build.sh <manifest.yaml> [--gif] [--clean]
#   manifest.yaml  Path to the video manifest file
#   --gif          Also export a GIF preview after building
#   --clean        Remove build/ directory before starting
#
# Example:
#   ./build.sh manifest.example.yaml
#   ./build.sh manifest.example.yaml --gif
#   ./build.sh manifest.example.yaml --clean --gif

source "$(dirname "$0")/config.sh"

# ── Argument parsing ─────────────────────────────────────────────────────────
MANIFEST=""
OPT_GIF=0
OPT_CLEAN=0

for arg in "$@"; do
    case "$arg" in
        -h|--help)
            sed -n '2,13p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        --gif)  OPT_GIF=1 ;;
        --clean) OPT_CLEAN=1 ;;
        *)
            if [[ -z "$MANIFEST" ]]; then
                MANIFEST="$arg"
            fi
            ;;
    esac
done

[[ -n "$MANIFEST" ]] || log_error "Usage: build.sh <manifest.yaml> [--gif] [--clean]"
[[ -f "$MANIFEST" ]] || log_error "Manifest not found: $MANIFEST"
require_ffmpeg

if [[ "$OPT_CLEAN" -eq 1 ]]; then
    log_step "Cleaning build directory"
    rm -rf "$BUILD_DIR"
    ensure_build_dirs
fi

# ── Pure-bash YAML parser ────────────────────────────────────────────────────
# Parses our simplified manifest format using awk/sed.
# Handles: meta.*, music.*, segments with nested captions.

# Read a simple key: yaml_get "meta.title"
yaml_get() {
    local key="$1"
    local section="${key%%.*}"
    local field="${key#*.}"
    awk -v section="$section" -v field="$field" '
        BEGIN { in_section=0 }
        /^[a-z]/ {
            gsub(/:.*/, "", $1)
            if ($1 == section) in_section=1; else in_section=0
        }
        in_section && /^  [a-z]/ {
            gsub(/^  /, "")
            split($0, parts, ": ")
            gsub(/^ +| +$/, "", parts[1])
            if (parts[1] == field) {
                val = $0
                sub(/^[^:]*: */, "", val)
                gsub(/^ +| +$/, "", val)
                gsub(/^["'\''"]|["'\''"]$/, "", val)
                print val
                exit
            }
        }
    ' "$MANIFEST"
}

# Parse all segments into parallel arrays
parse_segments() {
    SEGMENT_COUNT=0
    local idx=-1
    local in_segments=0

    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// /}" ]] && continue

        # Detect segments section
        if [[ "$line" =~ ^segments: ]]; then
            in_segments=1
            continue
        fi

        # Stop at next top-level key
        if [[ $in_segments -eq 1 && "$line" =~ ^[a-z] && ! "$line" =~ ^segments: ]]; then
            break
        fi

        [[ $in_segments -eq 0 ]] && continue

        # New segment: "  - id: xxx"
        if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*id:[[:space:]]*(.*) ]]; then
            idx=$((idx + 1))
            SEGMENT_COUNT=$((idx + 1))
            SEG_ID[$idx]=$(echo "${BASH_REMATCH[1]}" | xargs)
            SEG_TYPE[$idx]=""
            SEG_TITLE[$idx]=""
            SEG_SUBTITLE[$idx]=""
            SEG_TAGLINE[$idx]=""
            SEG_DURATION[$idx]=""
            SEG_SOURCE[$idx]=""
            SEG_TRIM_START[$idx]=""
            SEG_TRIM_END[$idx]=""
            SEG_SPEED[$idx]=""
            SEG_FADE_IN[$idx]=""
            SEG_FADE_OUT[$idx]=""
            SEG_CAPTIONS[$idx]=""
            continue
        fi

        [[ $idx -lt 0 ]] && continue

        # Caption line: "      - text|start|end|pos|style"
        if [[ "$line" =~ ^[[:space:]]{6,}-[[:space:]]+(.*) ]]; then
            local cap="${BASH_REMATCH[1]}"
            if [[ -n "${SEG_CAPTIONS[$idx]}" ]]; then
                SEG_CAPTIONS[$idx]+=$'\n'"$cap"
            else
                SEG_CAPTIONS[$idx]="$cap"
            fi
            continue
        fi

        # Segment field: "    key: value"
        if [[ "$line" =~ ^[[:space:]]{4}([a-z_]+):[[:space:]]*(.*) ]]; then
            local key="${BASH_REMATCH[1]}"
            local val="${BASH_REMATCH[2]}"
            # Strip surrounding quotes
            val="${val#\"}"
            val="${val%\"}"
            val="${val#\'}"
            val="${val%\'}"
            val=$(echo "$val" | xargs)

            case "$key" in
                type)       SEG_TYPE[$idx]="$val" ;;
                title)      SEG_TITLE[$idx]="$val" ;;
                subtitle)   SEG_SUBTITLE[$idx]="$val" ;;
                tagline)    SEG_TAGLINE[$idx]="$val" ;;
                duration)   SEG_DURATION[$idx]="$val" ;;
                source)     SEG_SOURCE[$idx]="$val" ;;
                trim_start) SEG_TRIM_START[$idx]="$val" ;;
                trim_end)   SEG_TRIM_END[$idx]="$val" ;;
                speed)      SEG_SPEED[$idx]="$val" ;;
                fade_in)    SEG_FADE_IN[$idx]="$val" ;;
                fade_out)   SEG_FADE_OUT[$idx]="$val" ;;
            esac
        fi

    done < "$MANIFEST"
}

# ── Parse manifest ───────────────────────────────────────────────────────────
echo ""
log_step "Parsing manifest: $(basename "$MANIFEST")"

# Meta
META_TITLE=$(yaml_get "meta.title")
META_OUTPUT=$(yaml_get "meta.output")
META_OUTPUT="${META_OUTPUT:-rooben-demo-final.mp4}"

# Music
MUSIC_FILE=$(yaml_get "music.file")
MUSIC_VOLUME=$(yaml_get "music.volume")
MUSIC_VOLUME="${MUSIC_VOLUME:-0.08}"

# Segments
declare -a SEG_ID SEG_TYPE SEG_TITLE SEG_SUBTITLE SEG_TAGLINE SEG_DURATION
declare -a SEG_SOURCE SEG_TRIM_START SEG_TRIM_END SEG_SPEED SEG_FADE_IN SEG_FADE_OUT
declare -a SEG_CAPTIONS
SEGMENT_COUNT=0

parse_segments

echo "  Found $SEGMENT_COUNT segment(s)"
[[ $SEGMENT_COUNT -gt 0 ]] || log_error "No segments found in manifest"

# ── Process segments ─────────────────────────────────────────────────────────
SEGMENT_FILES=()

for i in $(seq 0 $((SEGMENT_COUNT - 1))); do
    local_id="${SEG_ID[$i]}"
    local_type="${SEG_TYPE[$i]}"
    padded_idx=$(printf "%02d" "$i")
    segment_output="$BUILD_DIR/segments/${padded_idx}-${local_id}.mp4"

    echo ""
    log_step "[$((i+1))/$SEGMENT_COUNT] Segment: $local_id ($local_type)"

    if [[ "$local_type" == "title-card" ]]; then
        # ── Title card ───────────────────────────────────────────────
        local_title="${SEG_TITLE[$i]:-$META_TITLE}"
        local_subtitle="${SEG_SUBTITLE[$i]:-}"
        local_tagline="${SEG_TAGLINE[$i]:-}"
        local_duration="${SEG_DURATION[$i]:-$DEFAULT_TITLE_DURATION}"

        bash "$SCRIPT_DIR/02-title-card.sh" \
            "$local_title" "$local_subtitle" "$local_tagline" \
            "$local_duration" "$segment_output"

    elif [[ "$local_type" == "clip" ]]; then
        # ── Video clip: trim → caption → speed → fade ────────────────
        local_source="${SEG_SOURCE[$i]}"
        local_trim_start="${SEG_TRIM_START[$i]:-00:00:00}"
        local_trim_end="${SEG_TRIM_END[$i]}"
        local_speed="${SEG_SPEED[$i]:-1.0}"
        local_fade_in="${SEG_FADE_IN[$i]:-$DEFAULT_FADE_IN}"
        local_fade_out="${SEG_FADE_OUT[$i]:-$DEFAULT_FADE_OUT}"
        local_captions="${SEG_CAPTIONS[$i]:-}"

        [[ -f "$local_source" ]] || log_error "Source not found: $local_source (segment: $local_id)"

        # Step 1: Trim
        trimmed="$BUILD_DIR/trimmed/${padded_idx}-${local_id}.mp4"
        bash "$SCRIPT_DIR/01-trim.sh" "$local_source" "$local_trim_start" "$local_trim_end" "$trimmed"
        current="$trimmed"

        # Step 2: Captions
        if [[ -n "$local_captions" ]]; then
            captioned="$BUILD_DIR/captioned/${padded_idx}-${local_id}.mp4"
            caption_args=()
            while IFS= read -r cap_line; do
                [[ -n "$cap_line" ]] && caption_args+=("$cap_line")
            done <<< "$local_captions"

            if [[ ${#caption_args[@]} -gt 0 ]]; then
                bash "$SCRIPT_DIR/03-caption-overlay.sh" "$current" "$captioned" "${caption_args[@]}"
                current="$captioned"
            fi
        fi

        # Step 3: Speed (skip if 1.0)
        if [[ "$local_speed" != "1.0" && "$local_speed" != "1" ]]; then
            sped="$BUILD_DIR/sped/${padded_idx}-${local_id}.mp4"
            bash "$SCRIPT_DIR/04-speed-ramp.sh" "$current" "$sped" "$local_speed"
            current="$sped"
        fi

        # Step 4: Transitions
        bash "$SCRIPT_DIR/05-transitions.sh" "$current" "$segment_output" "$local_fade_in" "$local_fade_out"

    else
        log_error "Unknown segment type: $local_type (segment: $local_id)"
    fi

    SEGMENT_FILES+=("$segment_output")
done

# ── Concatenate ──────────────────────────────────────────────────────────────
echo ""
log_step "Concatenating ${#SEGMENT_FILES[@]} segments"

CONCAT_OUTPUT="$BUILD_DIR/concat-raw.mp4"
bash "$SCRIPT_DIR/07-concat.sh" "$CONCAT_OUTPUT" "${SEGMENT_FILES[@]}"

# ── Music mix ────────────────────────────────────────────────────────────────
FINAL_OUTPUT="$BUILD_DIR/$META_OUTPUT"

if [[ -n "$MUSIC_FILE" && -f "$MUSIC_FILE" ]]; then
    log_step "Adding background music"
    bash "$SCRIPT_DIR/06-add-music.sh" "$CONCAT_OUTPUT" "$MUSIC_FILE" "$FINAL_OUTPUT" "$MUSIC_VOLUME"
else
    cp "$CONCAT_OUTPUT" "$FINAL_OUTPUT"
fi

# ── GIF export ───────────────────────────────────────────────────────────────
if [[ "$OPT_GIF" -eq 1 ]]; then
    echo ""
    GIF_OUTPUT="$BUILD_DIR/${META_OUTPUT%.mp4}.gif"
    bash "$SCRIPT_DIR/08-gif.sh" "$FINAL_OUTPUT" "$GIF_OUTPUT"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
FINAL_SIZE=$(du -h "$FINAL_OUTPUT" | cut -f1)
FINAL_DURATION=$(get_duration "$FINAL_OUTPUT")
log_done "Build complete!"
echo "  Output:   $FINAL_OUTPUT"
echo "  Size:     $FINAL_SIZE"
echo "  Duration: ${FINAL_DURATION}s"
echo "  Segments: ${#SEGMENT_FILES[@]}"
