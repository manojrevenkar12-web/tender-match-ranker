# 0005 A model reads the lots the trade reader is unsure about

The hashed n-gram reader learns the simulator's wording almost perfectly and was right on 63 % of the first blind
set, written by someone who never saw the data (91 % of the easy lots, under half of the near-misses). It was
unsure (top probability under 0.5) on half of the blind lots and on 0.2 % of the simulated ones, so confidence
separates the two. Lots below 0.5 now also go to a model (Claude Haiku, batched, the trade list as the only
allowed answers, cached); its answer is weighted 0.85 against the reader's. On blind-1 this reaches 91 %, at
about $0.07 per 1,000 lots; blind-1 became a regression set and blind-2 was written fresh to measure it.
