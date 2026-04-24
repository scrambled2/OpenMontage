import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

interface SpecimenLowerThirdProps {
  /** Top line, gets the red accent. e.g. "SPECIMEN 0042" */
  specimenId: string;
  /** Middle line, the typed/phase descriptor. e.g. "Adult Male — Pre-Caffeine Phase" */
  classification: string;
  /** Bottom line, the habitat metadata. e.g. "Habitat: Domestic Kitchen, 06:42 Local Time" */
  habitat: string;
  /** Accent color for the specimen ID. Defaults to the minimalist-diagram red. */
  accentColor?: string;
}

/**
 * Bureaucratic-archive lower third for the alien-anthropology pipeline.
 * 3-line stacked metadata in a translucent cream panel with a navy left rule.
 * Designed to feel like a page from a long-running alien research log.
 */
export const SpecimenLowerThird: React.FC<SpecimenLowerThirdProps> = ({
  specimenId,
  classification,
  habitat,
  accentColor = "#E94560",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const fadeIn = spring({
    frame,
    fps,
    config: { damping: 22, stiffness: 60 },
    durationInFrames: 18,
  });

  const exitStart = durationInFrames - 14;
  const fadeOut = interpolate(frame, [exitStart, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const opacity = Math.min(fadeIn, fadeOut);

  // Subtle slide from the left
  const slide = interpolate(fadeIn, [0, 1], [-24, 0]);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "flex-start",
        padding: 64,
      }}
    >
      <div
        style={{
          opacity,
          transform: `translateX(${slide}px)`,
          background: "rgba(250, 250, 250, 0.93)",
          borderLeft: "3px solid #1A1A2E",
          padding: "18px 28px 18px 22px",
          minWidth: 460,
          maxWidth: 640,
          fontFamily: "IBM Plex Sans, system-ui, sans-serif",
          boxShadow: "0 10px 32px rgba(0,0,0,0.18)",
        }}
      >
        <div
          style={{
            fontSize: 26,
            fontWeight: 700,
            color: accentColor,
            letterSpacing: "0.06em",
            lineHeight: 1.05,
            marginBottom: 4,
          }}
        >
          {specimenId}
        </div>
        <div
          style={{
            fontSize: 18,
            fontWeight: 500,
            color: "#1A1A2E",
            lineHeight: 1.25,
            marginBottom: 4,
          }}
        >
          {classification}
        </div>
        <div
          style={{
            fontSize: 13,
            fontWeight: 400,
            color: "#6B7280",
            letterSpacing: "0.02em",
            lineHeight: 1.3,
          }}
        >
          {habitat}
        </div>
      </div>
    </AbsoluteFill>
  );
};
