export type LotSummary = {
  lot_id: number;
  tender_id: number;
  title: string;
  city: string;
  published: string;
  deadline: string;
  trade_label: string;
  reference_eur: number;
  trade: string;
  trade_prob: number;
};

export type LotDetail = LotSummary & {
  text: string;
  trades: { trade: string; name: string; prob: number }[];
};

export type Firm = {
  firm_id: number;
  position: number;
  score: number;
  p_bid: number;
  p_competitive: number;
  price_band: [number, number, number];
  distance_km: number;
  bids_365: number;
  bid_rate: number;
  invites_14: number;
  busy: boolean;
  new: boolean;
  knows_buyer: boolean;
  trades: string[];
  city: string;
};

export type Shortlist = {
  lot_id: number;
  model_version: string;
  candidates: number;
  firms: Firm[];
  expected_competitive: number;
  busy_share: number;
};

export type PolicyOffline = {
  lots: number;
  ndcg: number;
  ips: number;
  dr: number;
  truth: number;
  support: number;
  dr_lift: [number, number, number];
  truth_lift: [number, number, number];
};

export type PolicyReplay = {
  expected_competitive_per_lot: number;
  realised_competitive_per_lot: number;
  bids_per_lot: number;
  bid_rate: number;
  top1pct_invite_share: number;
  new_firm_slot_share: number;
};

export type Results = {
  generated: string;
  profile: string;
  policies: Record<string, { label: string; offline: PolicyOffline; replay: PolicyReplay }>;
  ab: {
    lots: number;
    plain: { effect: number; ci: [number, number] };
    cuped: { effect: number; ci: [number, number] };
    true_effect: number;
    sequential: { look: number; lots: number; z: number; bound: number; stop: boolean }[];
  };
  reader: Record<string, { macro_f1: number; accuracy: number; top3: number }>;
  blind: Record<string, { macro_f1: number; accuracy: number }> | null;
  release: { ships: boolean; gates: { gate: string; value: number | null; limit: string; pass: boolean }[] };
};

export type Monitoring = {
  metrics: Record<string, number | string>;
  alerts: { metric: string; value: number; severity: string; limit: Record<string, number> }[];
};

export type Plan = {
  request: {
    city: string;
    deadline: string;
    max_km: number | null;
    min_invites: number | null;
    exclude_firm_ids: number[];
  };
  lots: {
    title: string;
    trade: string;
    trade_prob: number;
    offered: { firm_id: number; score: number; reasons: string[] }[];
    invite: number[];
    message: string;
    escalate: boolean;
    reason: string;
    verified: boolean;
  }[];
  violations: string[];
  model: { calls?: number; cost_usd?: number };
};
