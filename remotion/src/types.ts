export type AdLine = {
  text: string;
  imageUrl: string;
  /** AI-generated motion clip for this line — takes priority over imageUrl (Ken Burns) when present. */
  videoUrl?: string;
  audioUrl?: string;
  /** Overrides secondsPerLine for this line — used to fit a voiceover clip without cutting it off. */
  durationSeconds?: number;
};

export type ProductAdProps = {
  productName: string;
  lines: AdLine[];
  secondsPerLine: number;
};

export const defaultProductAdProps: ProductAdProps = {
  productName: "Sample Product",
  secondsPerLine: 3,
  lines: [
    {
      text: "Still starting your day the hard way?",
      imageUrl:
        "https://images.pexels.com/photos/9788373/pexels-photo-9788373.jpeg?auto=compress&cs=tinysrgb&h=1920&w=1080",
    },
    {
      text: "Meet the product that changes that.",
      imageUrl:
        "https://images.pexels.com/photos/321599/pexels-photo-321599.jpeg?auto=compress&cs=tinysrgb&h=1920&w=1080",
    },
  ],
};

export function lineDurationSeconds(line: AdLine, secondsPerLine: number): number {
  return line.durationSeconds ?? secondsPerLine;
}
