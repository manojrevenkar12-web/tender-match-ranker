# 0003 Choose rankers by doubly-robust estimates, not NDCG on logs

On the test months, NDCG against logged labels ranks the policies in reverse order of their true value: it rewards
copying the ranking that wrote the logs. IPS corrects the position bias but cannot credit firms the old ranking
never showed (the best new rankers put about half their shortlist on firms the log has no outcome for), so it
also prefers the old ranking. The doubly-robust estimate (a direct model for every firm shown, plus the
IPS-weighted residual where the log has outcomes) tracks the truth within a few percent and orders the
policies correctly. The release gate uses its 95 % lower bound.
