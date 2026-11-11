// One swapped product video with captions and an end card added by raea, instead of by hand in CapCut.
// The clip and its words come from cuts.ts / words.json (`raea cut` wrote both, timings from the speech itself).
import { AbsoluteFill, Composition, Easing, Sequence, Series, Video, interpolate, registerRoot, useCurrentFrame, useWords, type TimelineWord } from "raea";
import { cuts, edit, frames, total } from "./cuts";

const C = { ground: "#0B0B0A", ink: "#F2F1EE", muted: "#A9A7A0", accent: "#F25A2B", accentText: "#FF7F52", onAccent: "#160A05" };
const SANS = "Geist, 'Helvetica Neue', Helvetica, Arial, sans-serif";
const MONO = "'Geist Mono', 'SF Mono', Menlo, monospace";
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const OUT = Easing.out(Easing.cubic);
const END = 84;                                   // end card length in frames (2.8 s)
const PRODUCT = "__PRODUCT__";            // short product name, filled in per clip by caption_job.py

/** Groups of up to 3 words, broken at punctuation and at pauses over 8 frames (raea's caption rule). */
function group(words: TimelineWord[]): TimelineWord[][] {
  const groups: TimelineWord[][] = [];
  for (const w of words) {
    const g = groups[groups.length - 1];
    const prev = g?.[g.length - 1];
    if (!g || g.length >= 3 || /[.,?!]$/.test(prev!.text) || w.from - prev!.to > 8) groups.push([w]);
    else g.push(w);
  }
  return groups;
}

/** Word-by-word captions on a dark plate, the spoken word in the accent. Sits above the app's bottom buttons. */
function Captions() {
  const f = useCurrentFrame();
  const groups = group(useWords());
  const i = groups.findIndex((g, n) => f >= g[0].from && f < (groups[n + 1]?.[0].from ?? g[g.length - 1].to + 8));
  if (i < 0) return null;
  const g = groups[i];
  const local = f - g[0].from;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", padding: "0 150px 470px 70px" }}>
      <div style={{ background: "rgba(11,11,10,0.94)", borderRadius: 22, padding: "22px 34px",
        fontFamily: SANS, fontWeight: 700, fontSize: 78, lineHeight: 1.05, letterSpacing: "-0.02em", textAlign: "center",
        transform: `translateY(${interpolate(local, [0, 5], [14, 0], { ...clamp, easing: OUT })}px)` }}>
        {g.map((w, j) => (
          <span key={j} style={{ color: f >= w.from && f < Math.max(w.to, w.from + 4) ? C.accentText : C.ink }}>
            {w.text + (j < g.length - 1 ? " " : "")}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
}

/** The product name, landing with her first word and leaving a few seconds later. */
function ProductTag() {
  const f = useCurrentFrame();
  const at = useWords()[0]?.from ?? 0;          // lands with her first word
  const t = interpolate(f, [at, at + 10], [0, 1], { ...clamp, easing: OUT }) * interpolate(f, [at + 110, at + 122], [1, 0], clamp);
  if (t <= 0) return null;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "flex-start", padding: "250px 150px 0 70px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18, opacity: t, transform: `translateX(${(1 - t) * 30}px)`,
        background: "rgba(11,11,10,0.82)", border: "2px solid #383835", borderRadius: 18, padding: "20px 30px",
        fontFamily: MONO, fontSize: 42, letterSpacing: "0.03em", color: C.ink }}>
        <div style={{ width: 18, height: 18, borderRadius: 18, background: C.accent }} />{PRODUCT}
      </div>
    </AbsoluteFill>
  );
}

/** End card: the product and where to get it. */
function EndCard() {
  const f = useCurrentFrame();
  const on = (at: number) => interpolate(f, [at, at + 12], [0, 1], { ...clamp, easing: OUT });
  return (
    <AbsoluteFill style={{ background: C.ground, justifyContent: "center", padding: "0 150px 0 90px", opacity: on(0) }}>
      <div style={{ fontFamily: MONO, fontSize: 44, letterSpacing: "0.04em", color: C.muted, textTransform: "uppercase", opacity: on(4) }}>Shown in this video</div>
      <div style={{ fontFamily: SANS, fontWeight: 700, fontSize: 112, lineHeight: 1.04, letterSpacing: "-0.03em", color: C.ink, marginTop: 26,
        opacity: on(8), transform: `translateY(${(1 - on(8)) * 40}px)` }}>{PRODUCT}</div>
      <div style={{ marginTop: 64, alignSelf: "flex-start", background: C.accent, color: C.onAccent, borderRadius: 20, padding: "30px 46px",
        fontFamily: SANS, fontWeight: 700, fontSize: 66, opacity: on(22), transform: `scale(${0.92 + 0.08 * on(22)})`, transformOrigin: "left center" }}>
        Link below
      </div>
    </AbsoluteFill>
  );
}

function Edit() {
  return (
    <AbsoluteFill style={{ background: C.ground }}>
      <Series>
        {cuts.map((c, i) => (
          <Series.Sequence key={i} durationInFrames={frames(c)}>
            <Video src={c.src} startFrom={Math.round(c.from * edit.fps)} endAt={Math.round(c.to * edit.fps)} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          </Series.Sequence>
        ))}
      </Series>
      <Sequence from={0} durationInFrames={total}><ProductTag /><Captions /></Sequence>
      <Sequence from={total} durationInFrames={END}><EndCard /></Sequence>
    </AbsoluteFill>
  );
}

registerRoot(() => <Composition id="edit" component={Edit} width={edit.width} height={edit.height} fps={edit.fps} durationInFrames={total + END} />);
