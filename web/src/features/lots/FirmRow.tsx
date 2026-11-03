import { motion, useReducedMotion } from "motion/react";
import type { Firm } from "../../shared/api/types";
import { motionTokens } from "../../shared/theme/motion";
import { pct } from "../../shared/ui/format";

const BAND_MIN = 0.8; // the price band is drawn from 80 % to 130 % of the reference price
const BAND_MAX = 1.3;
const LIMIT = 1.05;

function x(v: number): string {
  return `${((Math.min(Math.max(v, BAND_MIN), BAND_MAX) - BAND_MIN) / (BAND_MAX - BAND_MIN)) * 100}%`;
}

export function FirmRow({
  firm,
  checked,
  toggle,
  index,
}: { firm: Firm; checked: boolean; toggle: () => void; index: number }) {
  const reduce = useReducedMotion();
  const [lo, mid, hi] = firm.price_band;
  const id = `firm-${firm.firm_id}`;
  return (
    <motion.li
      className="firm"
      initial={reduce ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: motionTokens.reveal,
        delay: index * motionTokens.stagger,
        ease: motionTokens.ease,
      }}
    >
      <label htmlFor={id}>
        <input id={id} type="checkbox" checked={checked} onChange={toggle} />
        <div>
          <div className="name">
            Firm {firm.firm_id} · {firm.city}
          </div>
          <div className="chips">
            <span className="chip">{firm.distance_km.toFixed(0)} km</span>
            <span className="chip">{firm.trades.join(", ")}</span>
            {firm.busy && <span className="chip busy">{firm.invites_14} requests in 14 days</span>}
            {firm.new && <span className="chip new">few requests so far</span>}
            {firm.knows_buyer && <span className="chip">has bid for you before</span>}
          </div>
        </div>
      </label>
      <div className="odds">
        <b>{pct(firm.p_bid)}</b> bids · <b>{pct(firm.p_competitive)}</b> comparable
        <div className="meta">
          {firm.bids_365} bids in 12 months ({pct(firm.bid_rate)} of requests)
        </div>
      </div>
      <div className="price">
        <div className="meta">
          Price {pct(lo - 1, 0)} to {pct(hi - 1, 0)} vs reference
        </div>
        <div
          className="band"
          role="img"
          aria-label={`Expected price between ${pct(lo)} and ${pct(hi)} of the reference, most likely ${pct(mid)}`}
        >
          <span style={{ left: x(lo), right: `calc(100% - ${x(hi)})` }} />
          <i style={{ left: x(LIMIT) }} />
        </div>
      </div>
    </motion.li>
  );
}
