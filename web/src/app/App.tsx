import { useCallback, useEffect, useState } from "react";
import { EvaluationScreen } from "../features/evaluation/EvaluationScreen";
import { LotsScreen } from "../features/lots/LotsScreen";
import { MonitoringScreen } from "../features/monitoring/MonitoringScreen";
import { PlannerScreen } from "../features/planner/PlannerScreen";

type Route =
  | { page: "lots"; id: number | null }
  | { page: "evaluation" }
  | { page: "monitoring" }
  | { page: "planner" };

function parse(hash: string): Route {
  const [, page, id] = hash.replace(/^#/, "").split("/");
  if (page === "evaluation" || page === "monitoring" || page === "planner") return { page };
  return { page: "lots", id: id ? Number(id) : null };
}

const LINKS: { page: Route["page"]; href: string; label: string }[] = [
  { page: "lots", href: "#/lots", label: "Open lots" },
  { page: "planner", href: "#/planner", label: "Planner" },
  { page: "evaluation", href: "#/evaluation", label: "Evaluation" },
  { page: "monitoring", href: "#/monitoring", label: "Monitoring" },
];

export function App() {
  const [route, setRoute] = useState<Route>(() => parse(location.hash));
  useEffect(() => {
    const on = () => setRoute(parse(location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = useCallback((id: number) => {
    location.hash = `#/lots/${id}`;
  }, []);
  return (
    <>
      <header className="top">
        <span className="brand">
          Invite planner<small>which firms to ask for this lot</small>
        </span>
        <nav className="nav" aria-label="Sections">
          {LINKS.map((l) => (
            <a key={l.page} href={l.href} aria-current={route.page === l.page ? "page" : undefined}>
              {l.label}
            </a>
          ))}
        </nav>
      </header>
      <main>
        {route.page === "lots" && <LotsScreen id={route.id} go={go} />}
        {route.page === "evaluation" && <EvaluationScreen />}
        {route.page === "monitoring" && <MonitoringScreen />}
        {route.page === "planner" && <PlannerScreen />}
      </main>
    </>
  );
}
