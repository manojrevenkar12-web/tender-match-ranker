"""The trade reader: which trade (Gewerk) a lot belongs to, from the text a buyer wrote.

Two readers, compared on the test months and on a blind set written by someone who never saw the data:
- `TfidfReader`: word and character n-gram TF-IDF with logistic regression (the baseline).
- `HashReader`: a fastText-style network in PyTorch (hashed word and character n-grams, an embedding bag
  and a linear layer). Small enough to train on a laptop CPU in seconds and serve in microseconds.

Labels are what buyers file the lot under, corrected by who bid: when at least two bidders' main trade
agrees and disagrees with the buyer's label, the bidders win (buyers file lots under the wrong trade).
"""

from __future__ import annotations

import re
import unicodedata
import zlib
from collections import Counter
from typing import Any

import numpy as np
import torch
from torch import nn

from .. import config

WORD = re.compile(r"[a-zäöüß0-9]+(?:[-/][a-zäöüß0-9]+)*")


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFC", text.lower())
    t = re.sub(r"\b\d+[\d.,]*\b", " 0 ", t)  # quantities say nothing about the trade
    return t


def tokens(text: str, ngrams: tuple[int, int]) -> list[str]:
    out: list[str] = []
    words = WORD.findall(normalise(text))
    for i, w in enumerate(words):
        out.append("w:" + w)
        if i + 1 < len(words):
            out.append("b:" + w + "_" + words[i + 1])
        if len(w) > 2 and not w.isdigit():
            g = f"<{w}>"
            for n in range(ngrams[0], ngrams[1] + 1):
                out.extend("c:" + g[j : j + n] for j in range(len(g) - n + 1))
    return out


def corrected_labels(lots: list[dict[str, Any]], bidders: dict[int, list[str]]) -> list[str]:
    """The buyer's label, unless two or more bidders' main trades agree on another one."""
    out = []
    for lot in lots:
        mains = Counter(bidders.get(lot["lot_id"], []))
        label = lot["trade_label"]
        if mains:
            top, n = mains.most_common(1)[0]
            if top != label and n >= 2 and mains[label] < n:
                label = top
        out.append(label)
    return out


class HashReader(nn.Module):
    def __init__(self, trades: list[str] | None = None) -> None:
        super().__init__()
        cfg = config.load("models")["trade_reader"]
        self.cfg = cfg
        self.trades = trades or config.trades()
        self.buckets = int(cfg["buckets"])
        self.ng = tuple(cfg["char_ngrams"])
        self.emb = nn.EmbeddingBag(self.buckets, int(cfg["dim"]), mode="mean", sparse=True)
        self.out = nn.Linear(int(cfg["dim"]), len(self.trades))

    def ids(self, text: str) -> list[int]:
        return [zlib.crc32(t.encode()) % self.buckets for t in tokens(text, self.ng)] or [0]

    def _batch(self, texts: list[str]) -> tuple[torch.Tensor, torch.Tensor]:
        flat: list[int] = []
        offs: list[int] = []
        for t in texts:
            offs.append(len(flat))
            flat.extend(self.ids(t))
        return torch.tensor(flat, dtype=torch.long), torch.tensor(offs, dtype=torch.long)

    def forward(self, flat: torch.Tensor, offs: torch.Tensor) -> torch.Tensor:
        return self.out(self.emb(flat, offs))

    def fit(self, texts: list[str], labels: list[str], seed: int = 7) -> HashReader:
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        y = torch.tensor([self.trades.index(lbl) for lbl in labels])
        lr = float(self.cfg["lr"])
        opts = [
            torch.optim.SparseAdam(list(self.emb.parameters()), lr=lr),
            torch.optim.Adam(self.out.parameters(), lr=lr),
        ]
        bs = int(self.cfg["batch"])
        cached = [self.ids(t) for t in texts]
        for _ in range(int(self.cfg["epochs"])):
            order = rng.permutation(len(texts))
            for s in range(0, len(order), bs):
                idx = order[s : s + bs]
                flat: list[int] = []
                offs: list[int] = []
                for i in idx:
                    offs.append(len(flat))
                    flat.extend(cached[i])
                logits = self(torch.tensor(flat), torch.tensor(offs))
                loss = nn.functional.cross_entropy(logits, y[idx])
                for o in opts:
                    o.zero_grad()
                loss.backward()
                for o in opts:
                    o.step()
        self.eval()
        return self

    @torch.no_grad()
    def predict_proba(self, texts: list[str]) -> np.ndarray:
        out = []
        for s in range(0, len(texts), 1024):
            flat, offs = self._batch(texts[s : s + 1024])
            out.append(torch.softmax(self(flat, offs), dim=1).numpy())
        return np.concatenate(out) if out else np.zeros((0, len(self.trades)))


class TfidfReader:
    def __init__(self, trades: list[str] | None = None) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import FeatureUnion, make_pipeline

        self.trades = trades or config.trades()
        feats = FeatureUnion(
            [
                ("w", TfidfVectorizer(preprocessor=normalise, ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
                (
                    "c",
                    TfidfVectorizer(
                        preprocessor=normalise, analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True
                    ),
                ),
            ]
        )
        self.model = make_pipeline(feats, LogisticRegression(C=8.0, max_iter=2000))

    def fit(self, texts: list[str], labels: list[str], seed: int = 7) -> TfidfReader:
        self.model.fit(texts, labels)
        return self

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        p = self.model.predict_proba(texts)
        out = np.zeros((len(texts), len(self.trades)))
        for j, c in enumerate(self.model.classes_):
            out[:, self.trades.index(c)] = p[:, j]
        return out


def lot_string(lot: dict[str, Any]) -> str:
    return f"{lot['title']}\n{lot['text']}"


def scores(y_true: list[str], proba: np.ndarray, trades: list[str]) -> dict[str, float]:
    from sklearn.metrics import f1_score

    pred = [trades[i] for i in proba.argmax(1)]
    top3 = np.argsort(-proba, axis=1)[:, :3]
    t3 = np.mean([trades.index(t) in row for t, row in zip(y_true, top3)])
    return {
        "accuracy": round(float(np.mean([a == b for a, b in zip(y_true, pred)])), 4),
        "macro_f1": round(float(f1_score(y_true, pred, average="macro", labels=sorted(set(y_true)))), 4),
        "top3": round(float(t3), 4),
        "low_confidence_share": round(float(np.mean(proba.max(1) < 0.5)), 4),
    }
