import { useQuery } from "@tanstack/react-query";
import { api } from "../../shared/api/client";
import type { Monitoring } from "../../shared/api/types";
import { Empty, ErrorState, Skeleton } from "../../shared/ui/States";

const LABELS: Record<string, string> = {
  bid_rate_vs_predicted: "Observed minus predicted bid rate",
  calibration_ece: "Calibration error",
  feature_psi: "Largest feature drift (PSI)",
  top1pct_invite_share: "Invitations to the busiest 1 % of firms",
  new_firm_slot_share: "Shortlist places for firms with little history",
  trade_reader_low_confidence_share: "Lots the trade reader is unsure about",
};

export function MonitoringScreen() {
  const q = useQuery({ queryKey: ["monitoring"], queryFn: () => api.get<Monitoring>("/v1/monitoring") });
  if (q.isPending) return <Skeleton rows={6} label="Loading monitoring" />;
  if (q.isError) return <ErrorState what="monitoring" error={q.error} retry={() => q.refetch()} />;
  const m = q.data;
  const alerting = new Set(m.alerts.map((a) => a.metric));
  return (
    <div>
      <h1>Monitoring</h1>
      <p className="meta">
        The ranker's checks over the held-out month, with thresholds from config/monitoring.yaml.
      </p>
      <div className="cards">
        {Object.entries(LABELS).map(([k, label]) => (
          <div className="card" key={k}>
            <div className="meta">{label}</div>
            <div className={`big ${alerting.has(k) ? "alert" : ""}`}>{String(m.metrics[k])}</div>
            {k === "feature_psi" && <div className="meta">on {String(m.metrics.feature_psi_worst)}</div>}
          </div>
        ))}
      </div>
      <h2>Alerts</h2>
      {m.alerts.length === 0 ? (
        <Empty title="No alerts">
          <p>Every check is inside its threshold.</p>
        </Empty>
      ) : (
        <ul>
          {m.alerts.map((a) => (
            <li key={a.metric} className="alert">
              {LABELS[a.metric] ?? a.metric}: {a.value} ({a.severity}, limit {JSON.stringify(a.limit)})
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
