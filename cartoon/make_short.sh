#!/bin/sh
# make_short.sh <wide video> <out>  ->  1080x1920 vertical: middle three quarters of the picture, full width,
# on a soft blurred copy of itself. Nothing important is cut: all props sit inside the middle three quarters.
ffmpeg -v error -y -i "$1" -filter_complex \
"[0:v]split[a][b];[a]scale=3414:1920,crop=1080:1920,gblur=sigma=40,eq=brightness=-0.03[bg];\
[b]crop=1440:1080,scale=1080:810[fg];[bg][fg]overlay=0:(H-h)/2,setsar=1[v]" \
-map "[v]" -map 0:a -c:v libx264 -crf 22 -preset slow -pix_fmt yuv420p -c:a copy -movflags +faststart "$2"
