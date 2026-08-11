#!/bin/bash
# Assemble Diazites marketing video: Seedance clip + voiceover + branding
# Run AFTER seedance video completes at /root/voice-agent-manager/static/diazites_demo_seedance.mp4

set -e
VIDEO="/root/voice-agent-manager/static/diazites_demo_seedance.mp4"
VO="/root/voice-agent-manager/static/diazites_vo_short.mp3"
OUT="/root/voice-agent-manager/static/diazites_marketing_final.mp4"

echo "⏳ Waiting for video..."
while [ ! -f "$VIDEO" ]; do sleep 3; done
echo "✅ Video found!"

# Get durations
VID_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO")
VO_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VO")
echo "Video: ${VID_DUR}s | Voiceover: ${VO_DUR}s"

# Loop video to match voiceover + 1s padding for CTA
LOOPS=$(python3 -c "import math; print(max(1, math.ceil(($VO_DUR + 1.5) / $VID_DUR) - 1))")
echo "Looping video ${LOOPS}x..."

# Create loop concat file
> /tmp/loop_concat.txt
for i in $(seq 1 $((LOOPS + 1))); do
    echo "file '$VIDEO'" >> /tmp/loop_concat.txt
done

TOTAL_VID_DUR=$(python3 -c "print(($LOOPS + 1) * $VID_DUR)")

# Generate background music (subtle ambient)
ffmpeg -y -f lavfi -i "anoisesrc=d=$TOTAL_VID_DUR:c=pink:a=0.08" \
       -f lavfi -i "sine=f=174:d=$TOTAL_VID_DUR" \
       -filter_complex "[0:a][1:a]amix=inputs=2:duration=first,afade=t=out:st=$(python3 -c "print($TOTAL_VID_DUR - 1)"):d=1" \
       -ar 44100 -ac 1 /tmp/ambient_bg.mp3 2>/dev/null

# Main assembly: loop video + voiceover + ambient + text overlay
ffmpeg -y \
  -f concat -safe 0 -i /tmp/loop_concat.txt \
  -i "$VO" \
  -i /tmp/ambient_bg.mp3 \
  -filter_complex "
    [1:a]volume=1.8[vo];
    [2:a]volume=0.6[bg];
    [vo][bg]amix=inputs=2:duration=first[aout];
    [0:v]drawtext=text='Diazites AI':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.4:boxborderw=8:x=(w-text_w)/2:y=h-th-120:enable='between(t,0.5,3)',
         drawtext=text='diazites.online':fontcolor=#a855f7:fontsize=32:box=1:boxcolor=black@0.5:boxborderw=8:x=(w-text_w)/2:y=h-th-50:enable='gte(t,${VO_DUR})'[vout]
  " \
  -map "[vout]" -map "[aout]" \
  -c:v libx264 -crf 20 -preset fast \
  -c:a aac -b:a 128k \
  -t $(python3 -c "print($VO_DUR + 2)") \
  -pix_fmt yuv420p \
  "$OUT" 2>/dev/null

echo ""
echo "🎬 DONE!"
echo "FILE: $OUT"
ffprobe -v error -show_entries format=duration,size -of csv=p=0 "$OUT" | awk -F, '{printf "Duration: %.1fs | Size: %.1fMB\n", $1, $2/1024/1024}'
echo ""
echo "MEDIA:$OUT"
