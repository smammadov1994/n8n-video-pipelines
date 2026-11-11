#!/bin/sh
# join.sh <clip> <clip> ...  ->  final.mp4 (1920x1080, 24 fps), clips in the order given
cd "$(dirname "$0")"
ins=""; f=""; m=""; i=0
for c in "$@"; do
  ins="$ins -i $c"
  f="$f[$i:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps=24[v$i];[$i:a]aresample=48000,aformat=channel_layouts=stereo[a$i];"
  m="$m[v$i][a$i]"; i=$((i+1))
done
ffmpeg -v error -y $ins -filter_complex "${f}${m}concat=n=$i:v=1:a=1[v][a]" -map "[v]" -map "[a]" \
  -c:v libx264 -crf 17 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart "${OUT:-final.mp4}"
