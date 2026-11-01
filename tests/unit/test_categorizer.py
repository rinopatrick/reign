"""Unit tests: categorizer keyword matching."""

from reign.domain.models import Category
from reign.services.categorizer import match_category


def _cat(id_, name, keywords):
    return Category(id=id_, name=name, type="expense", color="#fff", keywords=keywords)


def test_match_food():
    cats = [_cat(1, "Food", "starbucks,cafe"), _cat(2, "Transport", "gojek,grab")]
    assert match_category("STARBUCKS COFFEE", cats) == 1


def test_match_no_keywords_returns_none():
    cats = [_cat(1, "Food", ""), _cat(2, "Misc", None)]
    assert match_category("RANDOM SHOP", cats) is None


def test_match_best_score_wins():
    cats = [_cat(1, "Food", "cafe"), _cat(2, "Coffee", "cafe,starbucks")]
    assert match_category("STARBUCKS CAFE", cats) == 2


def test_match_case_insensitive():
    cats = [_cat(1, "Food", "Starbucks")]
    assert match_category("starbucks indonesia", cats) == 1
