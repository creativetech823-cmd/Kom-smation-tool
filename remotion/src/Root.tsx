import React from "react";
import { Composition } from "remotion";
import { ProductAdMold } from "./ProductAdMold";
import { defaultProductAdProps, type ProductAdProps } from "./types";

const FPS = 30;
const WIDTH = 1080;
const HEIGHT = 1920;

function totalDurationInFrames(props: ProductAdProps): number {
  const totalSeconds = props.scenes.reduce((sum, scene) => sum + scene.durationSeconds, 0);
  return Math.round(totalSeconds * FPS);
}

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ProductAdMold"
      component={ProductAdMold}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
      durationInFrames={totalDurationInFrames(defaultProductAdProps)}
      defaultProps={defaultProductAdProps}
      calculateMetadata={async ({ props }) => {
        const p = props as ProductAdProps;
        return {
          durationInFrames: totalDurationInFrames(p),
        };
      }}
    />
  );
};
