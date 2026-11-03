# Release decision: the shipping ranker on the test months

**Ships.**

| Gate | Value | Limit | Result |
|---|---:|---|---|
| doubly-robust lift over the rules, 95 % lower bound | 0.5158 | > 0.0 | pass |
| P(invited and bid) calibration error | 0.0022 | <= 0.03 | pass |
| trade reader macro F1, simulated test lots | 0.9986 | >= 0.85 | pass |
| shortlist places for firms under 6 months on the platform (replay) | 0.1206 | >= 0.05 | pass |
| invitations to the busiest 1 % of firms (replay) | 0.0875 | <= 0.12 | pass |
| value lost to fatigue, replay vs single-lot | -0.0349 | <= 0.1 | pass |
| serving p95 latency, ms | 16.9 | <= 120 | pass |
