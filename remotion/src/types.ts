export type ScenePurpose =
  | "HOOK"
  | "PROBLEM"
  | "TENSION"
  | "AGITATION"
  | "SOLUTION"
  | "PRODUCT_REVEAL"
  | "INGREDIENT"
  | "BENEFIT"
  | "PROOF"
  | "TRANSFORMATION"
  | "CTA";

export type MotionPreset =
  | "CINEMATIC"
  | "UGC"
  | "ENERGETIC"
  | "PREMIUM"
  | "PRODUCT_HERO"
  | "INGREDIENT_EXPLAINER"
  | "HOOK_IMPACT"
  | "CTA";

export type CameraMotion =
  | "slowZoomIn"
  | "slowZoomOut"
  | "panLeft"
  | "panRight"
  | "pushIn"
  | "pullOut"
  | "productReveal"
  | "staticHold";

export type TextAnimation = "wordReveal" | "fadeThrough" | "slideUp" | "badge" | "subtitle";

export type TransitionStyle = "crossfade" | "hardCut";

/** One scene in the plan — the backend's scene_plan_service.py builds this
 * deterministically from the script + resolved assets (see VideoScene in
 * app/models/scene_plan.py); this type mirrors that JSON shape exactly. */
export type VideoScene = {
  sceneId: string;
  order: number;
  durationSeconds: number;
  purpose: ScenePurpose;
  text: string;
  onScreenText: string;
  imageUrl: string | null;
  /** AI-generated motion clip — takes priority over imageUrl (Ken Burns) when present. */
  videoUrl?: string;
  audioUrl?: string;
  /** A real, approved Product Library asset — rendered exactly as uploaded, never redrawn/modified. */
  isProductAsset: boolean;
  visualStyle: MotionPreset;
  cameraMotion: CameraMotion;
  textAnimation: TextAnimation;
  transition: TransitionStyle;
  /** Words to visually emphasize, extracted from **bold** markdown in the script text. */
  emphasis: string[];
  isCta: boolean;
  isProductReveal: boolean;
};

export type ProductAdProps = {
  productName: string;
  scenes: VideoScene[];
};

export function sceneDurationInFrames(scene: VideoScene, fps: number): number {
  return Math.round(scene.durationSeconds * fps);
}

export const defaultProductAdProps: ProductAdProps = {
  productName: "Sample Product",
  scenes: [
    {
      sceneId: "hook",
      order: 0,
      durationSeconds: 3,
      purpose: "HOOK",
      text: "Still starting your day the hard way?",
      onScreenText: "",
      imageUrl:
        "https://images.pexels.com/photos/9788373/pexels-photo-9788373.jpeg?auto=compress&cs=tinysrgb&h=1920&w=1080",
      isProductAsset: false,
      visualStyle: "HOOK_IMPACT",
      cameraMotion: "pushIn",
      textAnimation: "wordReveal",
      transition: "crossfade",
      emphasis: [],
      isCta: false,
      isProductReveal: false,
    },
    {
      sceneId: "cta",
      order: 1,
      durationSeconds: 3,
      purpose: "CTA",
      text: "Meet the product that changes that.",
      onScreenText: "",
      imageUrl:
        "https://images.pexels.com/photos/321599/pexels-photo-321599.jpeg?auto=compress&cs=tinysrgb&h=1920&w=1080",
      isProductAsset: false,
      visualStyle: "CTA",
      cameraMotion: "slowZoomIn",
      textAnimation: "badge",
      transition: "crossfade",
      emphasis: [],
      isCta: true,
      isProductReveal: false,
    },
  ],
};
