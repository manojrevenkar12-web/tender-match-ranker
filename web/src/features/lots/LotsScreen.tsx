import { useEffect, useState } from "react";
import { Empty, ErrorState, Skeleton } from "../../shared/ui/States";
import { day } from "../../shared/ui/format";
import { LotDetailPanel } from "./LotDetailPanel";
import { useLots } from "./useLots";

export function LotsScreen({ id, go }: { id: number | null; go: (id: number) => void }) {
  const [q, setQ] = useState("");
  const lots = useLots(q);
  useEffect(() => {
    if (id === null && lots.data?.length) go(lots.data[0].lot_id);
  }, [id, lots.data, go]);
  return (
    <div className="split">
      <nav aria-label="Open lots">
        <label className="visually-hidden" htmlFor="q">
          Search lots
        </label>
        <input
          id="q"
          className="search"
          type="search"
          placeholder="Search title, text or city"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        {lots.isPending && <Skeleton label="Loading lots" />}
        {lots.isError && <ErrorState what="the lots" error={lots.error} retry={() => lots.refetch()} />}
        {lots.data && lots.data.length === 0 && (
          <Empty title={q ? "No lot matches" : "No open lots"}>
            <p>
              {q
                ? "Try a trade, a city or part of the title."
                : "New lots appear here when buyers publish them."}
            </p>
          </Empty>
        )}
        {lots.data && lots.data.length > 0 && (
          <ul className="lots">
            {lots.data.map((l) => (
              <li key={l.lot_id}>
                <button
                  type="button"
                  className="lot"
                  aria-current={l.lot_id === id}
                  onClick={() => go(l.lot_id)}
                >
                  <div className="title">{l.title}</div>
                  <div className="meta">
                    {l.city} · due {day(l.deadline)} · reads as {l.trade}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </nav>
      {id !== null ? <LotDetailPanel id={id} /> : <Skeleton rows={4} label="Choosing a lot" />}
    </div>
  );
}
