# 0001 The label is a comparable bid, not an invitation

A buyer wants enough comparable bids to compare a lot, not a long invitation list. A click-style label
("the buyer invited the firm") rewards firms that look good and never answer. The ranker scores
P(invited and bid) × (0.7 × P(bid within 5 % of the reference) + 0.3) (`config/ranking.yaml: utility`), and every
evaluation counts expected comparable bids per lot. The 0.3 keeps firms that bid but price high in play: a buyer
still needs them to know the market.
