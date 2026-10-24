"""TF-IDF + NMF topic fitting (scikit-learn)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

from textanalysis.text import Tokenizer, tokenize

# Fixed settings from the original analysis (kept so results reproduce).
MAX_FEATURES = 5000
RANDOM_STATE = 42
NMF_INIT = "nndsvda"
NMF_MAX_ITER = 400


def fit_nmf(
    texts: Sequence[str],
    n_topics: int = 6,
    n_top_words: int = 15,
    tokenizer: Tokenizer = tokenize,
) -> tuple[list[list[str]], Any]:
    """Fit TF-IDF + NMF and return (top words per topic, topic index per document).

    The number of topics is capped at the number of documents. The second
    value is a numpy array of topic indices (the highest-weight topic for each
    document), or an empty list when there are no documents.
    """
    vectorizer = TfidfVectorizer(
        tokenizer=tokenizer,
        lowercase=False,
        token_pattern=None,  # unused because a tokenizer is given
        max_features=MAX_FEATURES,
    )
    X = vectorizer.fit_transform(texts)

    n_topics = min(n_topics, X.shape[0]) if X.shape[0] else 0
    if n_topics == 0:
        return [], []

    nmf = NMF(
        n_components=n_topics,
        random_state=RANDOM_STATE,
        init=NMF_INIT,
        max_iter=NMF_MAX_ITER,
    )
    W = nmf.fit_transform(X)  # (n_docs, n_topics)
    H = nmf.components_       # (n_topics, n_terms)

    feats = vectorizer.get_feature_names_out()
    top_words = []
    for vec in H:
        top_idx = vec.argsort()[::-1][:n_top_words]
        top_words.append([feats[i] for i in top_idx])

    doc_topic = W.argmax(axis=1)
    return top_words, doc_topic


def fit_topics(
    texts: Sequence[str], n_topics: int = 6, n_top_words: int = 15
) -> tuple[list[dict[str, Any]], Any]:
    """Fit topics with tokenize() and return ([{topic_id, top_words}], topic per document).

    top_words is a comma-separated string, which is how the topic tables are saved.
    """
    top_words, doc_topic = fit_nmf(texts, n_topics, n_top_words, tokenize)
    topics = [
        {"topic_id": k, "top_words": ", ".join(words)} for k, words in enumerate(top_words)
    ]
    return topics, doc_topic


def topic_bin_labels(name: str, doc_topic: Iterable[int]) -> list[str]:
    """Turn topic indices into labels like "cultural_topic_2"."""
    return [f"{name}_topic_{int(t)}" for t in doc_topic]
