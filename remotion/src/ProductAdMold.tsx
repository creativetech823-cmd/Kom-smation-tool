import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  Loop,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { sceneDurationInFrames, type CameraMotion, type ProductAdProps, type VideoScene } from "./types";

const TRANSITION_FRAMES = 15;
const ASSUMED_MOTION_CLIP_SECONDS = 2.5;
const FONT = "Arial, sans-serif";
const ACCENT = "#E8A33D";

type TextToken = { word: string; emphasized: boolean };

/** Script generation marks 2-5 key words per line with **double asterisks**
 * (see scene_plan_service._extract_emphasis on the Python side, which reads
 * the same markdown to populate scene.emphasis) — this tokenizer strips the
 * markers for display while remembering which words to highlight. */
function tokenize(text: string): TextToken[] {
  const tokens: TextToken[] = [];
  const regex = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  const pushPlain = (chunk: string, emphasized: boolean) => {
    chunk
      .split(/\s+/)
      .filter(Boolean)
      .forEach((word) => tokens.push({ word, emphasized }));
  };
  while ((match = regex.exec(text)) !== null) {
    pushPlain(text.slice(lastIndex, match.index), false);
    pushPlain(match[1], true);
    lastIndex = match.index + match[0].length;
  }
  pushPlain(text.slice(lastIndex), false);
  return tokens;
}

function motionTransform(motion: CameraMotion, frame: number, durationInFrames: number): string {
  const zoom = (range: [number, number], easing = Easing.out(Easing.quad)) =>
    interpolate(frame, [0, durationInFrames], range, { easing, extrapolateRight: "clamp" });
  switch (motion) {
    case "slowZoomIn":
      return `scale(${zoom([1, 1.12])})`;
    case "slowZoomOut":
      return `scale(${zoom([1.12, 1])})`;
    case "pushIn":
      return `scale(${zoom([1, 1.22], Easing.out(Easing.cubic))})`;
    case "pullOut":
      return `scale(${zoom([1.18, 1], Easing.out(Easing.cubic))})`;
    case "panLeft":
      return `scale(1.1) translateX(${zoom([0, -6])}%)`;
    case "panRight":
      return `scale(1.1) translateX(${zoom([0, 6])}%)`;
    case "productReveal":
    case "staticHold":
    default:
      return "scale(1.02)";
  }
}

const ProductHeroVisual: React.FC<{ imageUrl: string | null; frame: number; fps: number }> = ({
  imageUrl,
  frame,
  fps,
}) => {
  if (!imageUrl) return null;
  // The real product asset is rendered unmodified — object-fit: contain
  // (never cropped) with only a spring scale-in entrance, no filters that
  // alter the source pixels.
  const entrance = spring({ frame, fps, config: { damping: 14, stiffness: 120, mass: 0.6 }, durationInFrames: 24 });
  const drift = interpolate(frame, [24, 24 + fps * 3], [1, 1.03], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        background: "radial-gradient(circle at 50% 45%, rgba(255,255,255,0.08) 0%, rgba(0,0,0,0.92) 70%)",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <Img
        src={imageUrl}
        style={{
          maxWidth: "78%",
          maxHeight: "78%",
          objectFit: "contain",
          transform: `scale(${entrance * drift})`,
          filter: "drop-shadow(0 30px 60px rgba(0,0,0,0.55))",
        }}
      />
    </AbsoluteFill>
  );
};

const WordReveal: React.FC<{ tokens: TextToken[]; frame: number }> = ({ tokens, frame }) => (
  <div
    style={{
      fontFamily: FONT,
      fontWeight: 800,
      fontSize: 60,
      lineHeight: 1.25,
      color: "white",
      textAlign: "center",
      textShadow: "0 2px 14px rgba(0,0,0,0.7)",
      display: "flex",
      flexWrap: "wrap",
      justifyContent: "center",
    }}
  >
    {tokens.map((t, i) => {
      const start = i * 4;
      const opacity = interpolate(frame, [start, start + 6], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      const y = interpolate(frame, [start, start + 6], [24, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      return (
        <span
          key={i}
          style={{
            display: "inline-block",
            opacity,
            transform: `translateY(${y}px)`,
            marginRight: 16,
            color: t.emphasized ? ACCENT : "white",
          }}
        >
          {t.word}
        </span>
      );
    })}
  </div>
);

const BadgeText: React.FC<{ tokens: TextToken[]; frame: number; fps: number; isCta: boolean }> = ({
  tokens,
  frame,
  fps,
  isCta,
}) => {
  const scale = spring({ frame, fps, config: { damping: 13, stiffness: 170, mass: 0.7 } });
  return (
    <div
      style={{
        transform: `scale(${scale})`,
        background: isCta ? `linear-gradient(135deg, ${ACCENT}, #C9781F)` : "rgba(10,10,10,0.72)",
        border: `2px solid ${ACCENT}`,
        borderRadius: 28,
        padding: "26px 46px",
        maxWidth: "86%",
      }}
    >
      <div
        style={{
          fontFamily: FONT,
          fontWeight: 800,
          fontSize: 46,
          lineHeight: 1.3,
          color: "white",
          textAlign: "center",
          textShadow: "0 2px 10px rgba(0,0,0,0.5)",
        }}
      >
        {tokens.map((t, i) => (
          <span
            key={i}
            style={{
              color: isCta && t.emphasized ? "white" : t.emphasized ? ACCENT : "white",
              textDecoration: isCta && t.emphasized ? "underline" : "none",
              textUnderlineOffset: "4px",
            }}
          >
            {t.word}{" "}
          </span>
        ))}
      </div>
    </div>
  );
};

const SlideUpText: React.FC<{ tokens: TextToken[]; frame: number }> = ({ tokens, frame }) => {
  const progress = interpolate(frame, [0, 14], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div
      style={{
        opacity: progress,
        transform: `translateY(${(1 - progress) * 50}px)`,
        fontFamily: FONT,
        fontWeight: 700,
        fontSize: 52,
        lineHeight: 1.3,
        color: "white",
        textAlign: "center",
        textShadow: "0 2px 12px rgba(0,0,0,0.6)",
      }}
    >
      {tokens.map((t, i) => (
        <span key={i} style={{ color: t.emphasized ? ACCENT : "white" }}>
          {t.word}{" "}
        </span>
      ))}
    </div>
  );
};

const FadeThroughText: React.FC<{ tokens: TextToken[]; frame: number; durationInFrames: number }> = ({
  tokens,
  frame,
  durationInFrames,
}) => {
  const opacity = interpolate(frame, [0, 10, durationInFrames - 10, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const pulse = interpolate(frame, [0, 10], [0.94, 1], { extrapolateRight: "clamp" });
  return (
    <div
      style={{
        opacity,
        transform: `scale(${pulse})`,
        fontFamily: FONT,
        fontWeight: 800,
        fontSize: 54,
        lineHeight: 1.28,
        color: "white",
        textAlign: "center",
        textShadow: "0 2px 12px rgba(0,0,0,0.65)",
      }}
    >
      {tokens.map((t, i) => (
        <span key={i} style={{ color: t.emphasized ? ACCENT : "white" }}>
          {t.word}{" "}
        </span>
      ))}
    </div>
  );
};

const SubtitleText: React.FC<{ tokens: TextToken[] }> = ({ tokens }) => (
  <div
    style={{
      fontFamily: FONT,
      fontWeight: 800,
      fontSize: 56,
      lineHeight: 1.25,
      color: "white",
      textAlign: "center",
      textShadow: "0 2px 12px rgba(0,0,0,0.6)",
    }}
  >
    {tokens.map((t, i) => (
      <span key={i} style={{ color: t.emphasized ? ACCENT : "white" }}>
        {t.word}{" "}
      </span>
    ))}
  </div>
);

const TextLayer: React.FC<{
  scene: VideoScene;
  tokens: TextToken[];
  frame: number;
  fps: number;
  durationInFrames: number;
}> = ({ scene, tokens, frame, fps, durationInFrames }) => {
  if (tokens.length === 0) return null;
  const isCentered = scene.textAnimation === "badge";
  return (
    <AbsoluteFill
      style={{
        display: "flex",
        justifyContent: isCentered ? "center" : "flex-end",
        alignItems: "center",
        paddingBottom: isCentered ? 0 : 140,
        paddingLeft: 60,
        paddingRight: 60,
      }}
    >
      {scene.textAnimation === "wordReveal" && <WordReveal tokens={tokens} frame={frame} />}
      {scene.textAnimation === "badge" && <BadgeText tokens={tokens} frame={frame} fps={fps} isCta={scene.isCta} />}
      {scene.textAnimation === "slideUp" && <SlideUpText tokens={tokens} frame={frame} />}
      {scene.textAnimation === "fadeThrough" && (
        <FadeThroughText tokens={tokens} frame={frame} durationInFrames={durationInFrames} />
      )}
      {scene.textAnimation === "subtitle" && <SubtitleText tokens={tokens} />}
    </AbsoluteFill>
  );
};

const Scene: React.FC<{ scene: VideoScene; productName: string; isLast: boolean }> = ({
  scene,
  productName,
  isLast,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const durationInFrames = sceneDurationInFrames(scene, fps);
  const tokens = useMemo(() => tokenize(scene.onScreenText || scene.text), [scene.onScreenText, scene.text]);

  const hardCut = scene.transition === "hardCut";
  const fadeIn = interpolate(frame, [0, TRANSITION_FRAMES], [0, 1], { extrapolateRight: "clamp" });
  const fadeOut =
    isLast || hardCut
      ? 1
      : interpolate(frame, [durationInFrames - TRANSITION_FRAMES, durationInFrames], [1, 0], {
          extrapolateLeft: "clamp",
        });
  const opacity = hardCut ? 1 : Math.min(fadeIn, fadeOut);

  const motionClipFrames = Math.round(ASSUMED_MOTION_CLIP_SECONDS * fps);

  return (
    <AbsoluteFill style={{ opacity }}>
      {scene.audioUrl && <Audio src={scene.audioUrl} />}
      <AbsoluteFill>
        {scene.videoUrl ? (
          <Loop durationInFrames={motionClipFrames}>
            <OffthreadVideo src={scene.videoUrl} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          </Loop>
        ) : scene.isProductAsset ? (
          <ProductHeroVisual imageUrl={scene.imageUrl} frame={frame} fps={fps} />
        ) : scene.imageUrl ? (
          <Img
            src={scene.imageUrl}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: motionTransform(scene.cameraMotion, frame, durationInFrames),
              transformOrigin: "center",
            }}
          />
        ) : null}
      </AbsoluteFill>
      {!scene.isProductAsset && (
        <AbsoluteFill
          style={{ background: "linear-gradient(to top, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.0) 40%)" }}
        />
      )}
      <TextLayer scene={scene} tokens={tokens} frame={frame} fps={fps} durationInFrames={durationInFrames} />
      <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "flex-start", padding: 40 }}>
        <div
          style={{
            fontFamily: FONT,
            fontWeight: 700,
            fontSize: 30,
            color: "white",
            opacity: 0.85,
            textShadow: "0 2px 8px rgba(0,0,0,0.6)",
          }}
        >
          {productName}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const ProductAdMold: React.FC<ProductAdProps> = ({ productName, scenes }) => {
  const { fps } = useVideoConfig();
  let cursor = 0;
  const placedScenes = scenes.map((scene, i) => {
    const durationInFrames = sceneDurationInFrames(scene, fps);
    const from = cursor;
    cursor += durationInFrames;
    return { scene, from, durationInFrames, isLast: i === scenes.length - 1 };
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {placedScenes.map(({ scene, from, durationInFrames, isLast }) => (
        <Sequence key={scene.sceneId} from={from} durationInFrames={durationInFrames}>
          <Scene scene={scene} productName={productName} isLast={isLast} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
