import { useQuery } from "@tanstack/react-query";
import { api } from "../../shared/api/client";
import type { Results } from "../../shared/api/types";
import { ErrorState, Skeleton } from "../../shared/ui/States";
import { pct, signed } from "../../shared/ui/format";

const SHIPPING = "ranker";

export function EvaluationScreen() {
  const q = useQuery({ queryKey: ["results"], queryFn: () => api.get<Results>("/v1/experiments") });
  if (q.isPending) return <Skeleton rows={8} label="Loading the evaluation" />;
  if (q.isError) return <ErrorState what="the evaluation" error={q.error} retry={() => q.refetch()} />;
  const r = q.data;
  const rules = r.policies.rules;
  const ship = r.policies[SHIPPING];
  return (
    <div>
      <h1>How the ranker was judged</h1>
      <p className="meta">
        Test months of the simulated market ({r.profile} profile), generated {r.generated}. The market is
        simulated, so the true value of every policy is known and each estimate can be checked against it.
      </p>
      <div className="cards">
        <div className="card">
          <div className="meta">Comparable bids per lot, market replay</div>
          <div className="big">
            {ship.replay.expected_competitive_per_lot.toFixed(2)}{" "}
            <span className="meta">
              vs {rules.replay.expected_competitive_per_lot.toFixed(2)} with the rules
            </span>
          </div>
        </div>
        <div className="card">
          <div className="meta">Lift, doubly-robust estimate from logs</div>
          <div className="big">{signed(ship.offline.dr_lift[0])}</div>
          <div className="meta">
            95 % {signed(ship.offline.dr_lift[1])} to {signed(ship.offline.dr_lift[2])} · truth{" "}
            {signed(ship.offline.truth_lift[0])}
          </div>
        </div>
        <div className="card">
          <div className="meta">Release gate</div>
          <div className={`big ${r.release.ships ? "ok" : "alert"}`}>
            {r.release.ships ? "Ships" : "Does not ship"}
          </div>
          <div className="meta">
            {r.release.gates.filter((g) => g.pass).length} of {r.release.gates.length} gates pass
          </div>
        </div>
      </div>

      <section className="section" aria-labelledby="t-offline">
        <h2 id="t-offline">Offline estimates against the truth</h2>
        <p>
          The logs were written by the rules, which put some firms at the top far more often. NDCG on those
          logs rewards whoever copies the rules; the position-corrected estimates (IPS, doubly robust) track
          the truth.
        </p>
        <div className="table-wrap">
          <table>
            <caption className="visually-hidden">Policies, offline estimates and truth</caption>
            <thead>
              <tr>
                <th scope="col">Policy</th>
                <th scope="col">NDCG on logs</th>
                <th scope="col">IPS</th>
                <th scope="col">Doubly robust</th>
                <th scope="col">Truth</th>
                <th scope="col">Logged support</th>
                <th scope="col">Replay (all buyers)</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(r.policies).map(([k, p]) => (
                <tr key={k} className={k === SHIPPING ? "shipping" : undefined}>
                  <th scope="row">{p.label}</th>
                  <td>{p.offline.ndcg.toFixed(3)}</td>
                  <td>{p.offline.ips.toFixed(3)}</td>
                  <td>{p.offline.dr.toFixed(3)}</td>
                  <td>{p.offline.truth.toFixed(3)}</td>
                  <td>{pct(p.offline.support)}</td>
                  <td>{p.replay.expected_competitive_per_lot.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section" aria-labelledby="t-ab">
        <h2 id="t-ab">The A/B test, as the platform would run it</h2>
        <p>
          Buyers split 50/50, analysed per buyer (clustered), with CUPED on each buyer's earlier months and
          four O'Brien-Fleming looks. Both arms share the same firms, so the estimate can differ from the
          effect of switching everyone.
        </p>
        <div className="table-wrap">
          <table>
            <caption className="visually-hidden">A/B estimates</caption>
            <thead>
              <tr>
                <th scope="col">Estimate</th>
                <th scope="col">Effect (comparable bids per lot)</th>
                <th scope="col">95 % interval</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Plain difference</th>
                <td>{signed(r.ab.plain.effect, 3)}</td>
                <td>
                  {signed(r.ab.plain.ci[0], 3)} to {signed(r.ab.plain.ci[1], 3)}
                </td>
              </tr>
              <tr>
                <th scope="row">CUPED</th>
                <td>{signed(r.ab.cuped.effect, 3)}</td>
                <td>
                  {signed(r.ab.cuped.ci[0], 3)} to {signed(r.ab.cuped.ci[1], 3)}
                </td>
              </tr>
              <tr>
                <th scope="row">True effect of switching all buyers</th>
                <td>{signed(r.ab.true_effect, 3)}</td>
                <td>–</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
