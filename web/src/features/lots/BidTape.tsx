import { motion, useReducedMotion } from "motion/react";
import { motionTokens } from "../../shared/theme/motion";

const TARGET = 3; // buyers want three comparable bids to compare a lot
const SCALE_MAX = 5;
const TICKS = Array.from({ length: SCALE_MAX + 1 }, (_, i) => i);

/** Expected comparable bids for the firms selected, on a measuring tape with the buyer's target marked. */
export function BidTape({ value, selected }: { value: number; selected: number }) {
  const reduce = useReducedMotion();
  const width = `${(Math.min(value, SCALE_MAX) / SCALE_MAX) * 100}%`;
  const short = value < TARGET;
  return (
    <section className="tape" aria-labelledby="tape-title">
      <div className="tape-head">
        <div>
          <h2 id="tape-title">Comparable bids to expect</h2>
          <p className="meta">
            From the {selected} firms selected: each bids with its predicted probability and is within 5 % of
            the reference price with the price model's probability.
          </p>
        </div>
        <output
          className="tape-number"
          aria-live="polite"
          aria-label={`${value.toFixed(1)} comparable bids expected`}
        >
          {value.toFixed(1)}
        </output>
      </div>
      <div className="tape-track" aria-hidden="true">
        <motion.div
          className="tape-fill"
          initial={false}
          animate={{ width }}
          transition={reduce ? { duration: 0 } : { duration: motionTokens.base, ease: motionTokens.ease }}
        />
        <div className="tape-target" style={{ left: `${(TARGET / SCALE_MAX) * 100}%` }} />
      </div>
      <div className="tape-scale" aria-hidden="true">
        {TICKS.map((t) => (
          <span key={t}>{t}</span>
        ))}
      </div>
      <p className="meta">
        {short
          ? `Below the target of ${TARGET}: add firms or widen the radius.`
          : `At or above the target of ${TARGET} comparable bids.`}
      </p>
    </section>
  );
}
