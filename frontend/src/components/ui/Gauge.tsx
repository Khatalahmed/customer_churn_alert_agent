/**
 * A radial gauge, in the idiom of the hostel dashboard's occupancy ring.
 *
 * Used only where a number has a natural ceiling — a fidelity percentage, a
 * rules-passed fraction. A ring around a number that has no maximum would be
 * decoration pretending to be information.
 */
export function Gauge({
  value,
  label,
  caption,
  size = 92,
  stroke = 7,
  track = "rgba(255,255,255,0.18)",
  color = "#ffffff",
}: {
  /** 0–1. */
  value: number;
  /** What sits inside the ring — already formatted. */
  label: string;
  caption?: string;
  size?: number;
  stroke?: number;
  track?: string;
  color?: string;
}) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = Math.max(0, Math.min(1, value)) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`${label}${caption ? `, ${caption}` : ""}`}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={track}
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dasharray 900ms cubic-bezier(0.22,1,0.36,1)" }}
        />
        <text
          x="50%"
          y="50%"
          textAnchor="middle"
          dominantBaseline="central"
          fill={color}
          className="tnum"
          style={{ fontSize: size * 0.24, fontWeight: 900, letterSpacing: "-0.02em" }}
        >
          {label}
        </text>
      </svg>
      {caption ? (
        <p className="mt-2 text-center text-[10.5px] font-bold uppercase tracking-[0.14em] opacity-70">
          {caption}
        </p>
      ) : null}
    </div>
  );
}
