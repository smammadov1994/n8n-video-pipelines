#!/bin/zsh
# collect.sh : move downloaded director clips (<prefix>_<n>_00001_.mp4 in ~/Downloads) into ads/<folder>/clips/<prefix>_<n>.mp4
cd ${0:A:h}
for f in ~/Downloads/*_[0-9]_0000[0-9]_.mp4(N); do
  b=${f:t}; pre=${b%%_*}; n=${${b#*_}%%_*}
  d=$(dirname $(ls ads/*/spec.json | xargs grep -l "\"name\": \"$pre\"" | head -1))
  [ -n "$d" ] || continue
  mkdir -p $d/clips && mv "$f" $d/clips/${pre}_$n.mp4 && echo "$d/clips/${pre}_$n.mp4"
done
