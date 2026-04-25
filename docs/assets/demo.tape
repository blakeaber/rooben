# vhs tape script for the canonical `rooben demo` recording.
#
# Regenerate the demo GIF with:
#   vhs docs/assets/demo.tape
#
# Cost: $0 (mock providers, no API key required).
# Duration: ~30s real time -> ~15s after PlaybackSpeed 2.0.

Output docs/assets/demo-cli.gif

Set FontSize 13
Set Width 1000
Set Height 720
Set Theme "Dracula"
Set TypingSpeed 60ms
Set PlaybackSpeed 2.0
Set Padding 18
Set Shell "zsh"

Hide
Type "clear"
Enter
Show

Sleep 500ms

Type "rooben demo"
Sleep 800ms
Enter

# `rooben demo` runs a full mock orchestration in ~30s. 35s gives headroom
# for the final summary banner; PlaybackSpeed 2.0 compresses to ~17s in the GIF.
Sleep 35s
