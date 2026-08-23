
import pytest
from skills_engine.rerank.reranker import LexicalReranker, get_reranker


def test_lexical_f1_scoring():
    r = LexicalReranker()
    assert r.score('machine learning', 'machine learning') == 1.0
    assert r.score('machine learning fundamentals', 'machine learning') == pytest.approx(0.8, abs=0.01)
    assert r.score('quantum', 'machine learning') == 0.0


def test_get_reranker_backends():
    assert isinstance(get_reranker('lexical'), LexicalReranker)
    try:
        get_reranker('cross_encoder')
        installed = True
    except Exception:
        installed = False
    if not installed:
        with pytest.raises(Exception):
            get_reranker('bogus_backend')
