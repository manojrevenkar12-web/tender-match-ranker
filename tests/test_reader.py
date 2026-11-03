import numpy as np

from tmr.text.reader import HashReader, TfidfReader, corrected_labels, normalise, scores, tokens


def test_quantities_are_ignored_and_ngrams_carry_word_parts():
    assert "0" in normalise("ca. 1.800 m² Gipskarton").split()
    t = tokens("Trockenbauwand", (3, 5))
    assert "w:trockenbauwand" in t and "c:<tr" in t and "c:wan" in t


def test_bidders_correct_a_wrong_label_but_one_bidder_does_not():
    lots = [{"lot_id": 1, "trade_label": "maler"}, {"lot_id": 2, "trade_label": "maler"}]
    assert corrected_labels(lots, {1: ["putz", "putz", "maler"], 2: ["putz"]}) == ["putz", "maler"]


def test_both_readers_learn_a_toy_set():
    texts = [
        "Ständerwand CW 75 beplankt",
        "Gipskartondecke abgehängt",
        "Dispersionsanstrich Wände",
        "Lackierung Stahlzargen",
        "Ständerwerk doppelt beplankt",
        "Anstrich Decken weiß",
    ] * 8
    labels = ["trockenbau", "trockenbau", "maler", "maler", "trockenbau", "maler"] * 8
    trades = ["trockenbau", "maler"]
    for r in (HashReader(trades), TfidfReader(trades)):
        r.fit(texts, labels)
        p = r.predict_proba(["Metallständerwand doppelt beplankt", "Wandanstrich Dispersion"])
        assert list(np.argmax(p, 1)) == [0, 1]
    s = scores(["maler", "trockenbau"], np.array([[0.2, 0.8], [0.9, 0.1]]), trades)
    assert s["accuracy"] == 1.0 and s["top3"] == 1.0
