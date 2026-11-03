import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../shared/api/client";
import type { Plan } from "../../shared/api/types";
import { Empty, ErrorState } from "../../shared/ui/States";
import { day, pct } from "../../shared/ui/format";

const EXAMPLE = `Neubau Kita Leipzig.
Los 1 Trockenbau: Metallständerwände CW 75, abgehängte GK-Decken, ca. 1.800 m²
Los 2 Maler: Dispersionsanstrich Wände und Decken, Q3-Spachtelung
Angebotsfrist 15.12.2026. Mindestens 8 Firmen je Los, bitte nicht Firma 1203.`;

export function PlannerScreen() {
  const [text, setText] = useState(EXAMPLE);
  const run = useMutation({ mutationFn: (request: string) => api.post<Plan>("/v1/agent/plan", { request }) });
  return (
    <div>
      <h1>Plan invitations from a request</h1>
      <p className="meta">
        The model reads the request and words the invitations; the ranking, the constraints and a verifier
        decide.
      </p>
      <label htmlFor="req" className="visually-hidden">
        Request
      </label>
      <textarea id="req" value={text} onChange={(e) => setText(e.target.value)} />
      <div className="toolbar">
        <span className="meta">{text.length} characters</span>
        <button
          type="button"
          className="primary"
          disabled={run.isPending || text.trim().length < 10}
          onClick={() => run.mutate(text)}
        >
          {run.isPending ? "Planning…" : "Plan invitations"}
        </button>
      </div>
      {run.isError && <ErrorState what="a plan" error={run.error} retry={() => run.mutate(text)} />}
      {run.isIdle && (
        <Empty title="No plan yet">
          <p>Paste a request with lots, a deadline and any constraints, then plan.</p>
        </Empty>
      )}
      {run.data && <PlanView plan={run.data} />}
    </div>
  );
}

function PlanView({ plan }: { plan: Plan }) {
  const r = plan.request;
  return (
    <section aria-labelledby="plan-title">
      <h2 id="plan-title">
        {plan.lots.length} lots · {r.city} · due {r.deadline ? day(r.deadline) : "?"}
      </h2>
      <p className="meta">
        {r.max_km ? `within ${r.max_km} km · ` : ""}
        {r.min_invites ? `at least ${r.min_invites} firms per lot · ` : ""}
        {r.exclude_firm_ids.length ? `excluding ${r.exclude_firm_ids.join(", ")} · ` : ""}
        {plan.model.calls ?? 0} model calls
      </p>
      {plan.violations.length > 0 && (
        <div className="state error" role="alert">
          <h3>The verifier replaced {plan.violations.length} decisions</h3>
          <ul>
            {plan.violations.map((v) => (
              <li key={v}>{v}</li>
            ))}
          </ul>
        </div>
      )}
      {plan.lots.map((l) => (
        <div key={l.title} className="plan-lot">
          <h3>{l.title}</h3>
          <p className="meta">
            reads as {l.trade} ({pct(l.trade_prob)}) · invites {l.invite.length} of {l.offered.length} offered
            {l.escalate ? ` · needs you: ${l.reason || "too few firms"}` : ""}
          </p>
          <p className="message">{l.message}</p>
        </div>
      ))}
    </section>
  );
}
