import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { motionTokens } from "../../shared/theme/motion";
import { Empty, ErrorState, Skeleton } from "../../shared/ui/States";
import { day, daysBetween, eur, expectedComparable, pct } from "../../shared/ui/format";
import { BidTape } from "./BidTape";
import { FirmRow } from "./FirmRow";
import { useInvite, useLot, useShortlist } from "./useLots";

const DEFAULT_SELECTED = 10;

export function LotDetailPanel({ id }: { id: number }) {
  const lot = useLot(id);
  const short = useShortlist(id);
  const invite = useInvite(id);
  const reduce = useReducedMotion();
  const [selected, setSelected] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (short.data) setSelected(new Set(short.data.firms.slice(0, DEFAULT_SELECTED).map((f) => f.firm_id)));
  }, [short.data]);

  const chosen = useMemo(
    () => short.data?.firms.filter((f) => selected.has(f.firm_id)) ?? [],
    [short.data, selected],
  );
  const toggle = (fid: number) =>
    setSelected((s) => {
      const n = new Set(s);
      n.has(fid) ? n.delete(fid) : n.add(fid);
      return n;
    });

  if (lot.isPending) return <Skeleton rows={3} label="Loading the lot" />;
  if (lot.isError) return <ErrorState what="the lot" error={lot.error} retry={() => lot.refetch()} />;
  const l = lot.data;
  return (
    <article className="detail" aria-labelledby="lot-title">
      <div className="lead">
        <div>
          <h1 id="lot-title">{l.title}</h1>
          <p className="meta">
            {l.city} · bids due {day(l.deadline)} ({daysBetween(l.published, l.deadline)} days) · reference{" "}
            {eur(l.reference_eur)} · filed as {l.trade_label}
          </p>
        </div>
      </div>
      <p className="spec">{l.text}</p>
      <div className="trades" aria-label="Trade the platform reads from the text">
        {l.trades.map((t) => (
          <span key={t.trade} className="trade">
            <b>{t.name}</b> {pct(t.prob)}
          </span>
        ))}
      </div>

      {short.isPending && <Skeleton rows={8} label="Ranking firms" />}
      {short.isError && <ErrorState what="the shortlist" error={short.error} retry={() => short.refetch()} />}
      {short.data && short.data.firms.length === 0 && (
        <Empty title="No firm fits this lot">
          <p>
            No active firm lists this trade within its radius of {l.city}. Check the trade or invite by hand.
          </p>
        </Empty>
      )}
      {short.data && short.data.firms.length > 0 && (
        <>
          <BidTape value={expectedComparable(chosen)} selected={chosen.length} />
          <div className="toolbar">
            <p className="meta">
              {short.data.firms.length} of {short.data.candidates} candidates, best first ·{" "}
              {pct(short.data.busy_share)} of candidates are busy · model {short.data.model_version}
            </p>
            <button
              type="button"
              className="primary"
              disabled={chosen.length === 0 || invite.isPending}
              onClick={() => invite.mutate(chosen.map((f) => f.firm_id))}
            >
              {invite.isPending ? "Inviting…" : `Invite ${chosen.length} firms`}
            </button>
          </div>
          <AnimatePresence>
            {invite.isSuccess && (
              <motion.output
                className="notice"
                style={{ display: "block" }}
                initial={reduce ? false : { opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: motionTokens.quick }}
              >
                Invited {invite.data.invited} firms. They count towards their workload at once.
              </motion.output>
            )}
            {invite.isError && (
              <p className="state error" role="alert">
                Could not invite: {(invite.error as Error).message}
              </p>
            )}
          </AnimatePresence>
          <ul className="firms" aria-label="Shortlist">
            {short.data.firms.map((f, i) => (
              <FirmRow
                key={f.firm_id}
                index={i}
                firm={f}
                checked={selected.has(f.firm_id)}
                toggle={() => toggle(f.firm_id)}
              />
            ))}
          </ul>
        </>
      )}
    </article>
  );
}
