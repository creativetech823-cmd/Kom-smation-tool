import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  Loop,
  OffthreadVideo,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from "remotion";
import { lineDurationSeconds, type ProductAdProps } from "./types";

const TRANSITION_FRAMES = 15;

// Wan2.1 image-to-video clips render ~2.5s by default — looped to fill
// however long the line actually needs to be on screen (voiceover-driven).
const ASSUMED_MOTION_CLIP_SECONDS = 2.5;

const LineSlide: React.FC<{
  text: string;
  imageUrl: string;
  videoUrl?: string;
  audioUrl?: string;
  durationInFrames: number;
  productName: string;
  isLast: boolean;
}> = ({ text, imageUrl, videoUrl, audioUrl, durationInFrames, productName, isLast }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Ken Burns (image-only fallback): slow zoom in across the whole slide.
  const scale = interpolate(frame, [0, durationInFrames], [1, 1.1], {
    easing: Easing.out(Easing.quad),
    extrapolateRight: "clamp",
  });

  // Crossfade in, and crossfade out unless this is the final slide.
  const fadeIn = interpolate(frame, [0, TRANSITION_FRAMES], [0, 1], {
    extrapolateRight: "clamp",
  });
  const fadeOut = isLast
    ? 1
    : interpolate(
        frame,
        [durationInFrames - TRANSITION_FRAMES, durationInFrames],
        [1, 0],
        { extrapolateLeft: "clamp" }
      );
  const opacity = Math.min(fadeIn, fadeOut);

  const motionClipFrames = Math.round(ASSUMED_MOTION_CLIP_SECONDS * fps);

  return (
    <AbsoluteFill style={{ opacity }}>
      {audioUrl && <Audio src={audioUrl} />}

      <AbsoluteFill>
        {videoUrl ? (
          // AI-generated motion clip — looped to fill the line's duration.
          <Loop durationInFrames={motionClipFrames}>
            <OffthreadVideo
              src={videoUrl}
              muted
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          </Loop>
        ) : (
          <Img
            src={imageUrl}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              transform: `scale(${scale})`,
            }}
          />
        )}
      </AbsoluteFill>

      {/* Bottom gradient for subtitle legibility */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to top, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.0) 35%)",
        }}
      />

      <AbsoluteFill
        style={{
          justifyContent: "flex-end",
          alignItems: "center",
          paddingBottom: 140,
          paddingLeft: 60,
          paddingRight: 60,
        }}
      >
        <div
          style={{
            fontFamily: "Arial, sans-serif",
            fontWeight: 800,
            fontSize: 56,
            lineHeight: 1.25,
            color: "white",
            textAlign: "center",
            textShadow: "0 2px 12px rgba(0,0,0,0.6)",
          }}
        >
          {text}
        </div>
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          justifyContent: "flex-start",
          alignItems: "flex-start",
          padding: 40,
        }}
      >
        <div
          style={{
            fontFamily: "Arial, sans-serif",
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

export const ProductAdMold: React.FC<ProductAdProps> = ({
  productName,
  lines,
  secondsPerLine,
}) => {
  const { fps } = useVideoConfig();

  let cursor = 0;
  const placedLines = lines.map((line, i) => {
    const durationInFrames = Math.round(
      lineDurationSeconds(line, secondsPerLine) * fps
    );
    const from = cursor;
    cursor += durationInFrames;
    return { line, from, durationInFrames, isLast: i === lines.length - 1 };
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {placedLines.map(({ line, from, durationInFrames, isLast }, i) => (
        <Sequence key={i} from={from} durationInFrames={durationInFrames}>
          <LineSlide
            text={line.text}
            imageUrl={line.imageUrl}
            videoUrl={line.videoUrl}
            audioUrl={line.audioUrl}
            durationInFrames={durationInFrames}
            productName={productName}
            isLast={isLast}
          />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
