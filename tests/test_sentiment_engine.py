"""Comprehensive unit & concurrency tests for SentimentEngine."""
from __future__ import annotations

import concurrent.futures
import pytest
from processor.sentiment_engine import SentimentEngine, normalize_chat_text


def test_normalize_chat_text():
    assert normalize_chat_text("   hello   ") == "hello"
    assert normalize_chat_text("WWWWWWWW") == "WW"
    assert normalize_chat_text("noooooooo") == "noo"
    assert normalize_chat_text("") == ""


def test_sentiment_scoring():
    engine = SentimentEngine()
    pos_score = engine.predict_score("This game is an absolute masterpiece, 10/10 love it!")
    neg_score = engine.predict_score("Worst stream ever, complete scam, unwatchable trash")
    neu_score = engine.predict_score("What time is the tournament starting today?")

    assert pos_score > 0.4
    assert neg_score < -0.4
    assert -0.3 <= neu_score <= 0.3


def test_lru_caching_and_metrics():
    engine = SentimentEngine(cache_capacity=5)
    text = "Massive W play!"

    # First call -> miss
    score1 = engine.predict_score(text)
    metrics1 = engine.get_metrics()
    assert metrics1["cache_misses"] == 1
    assert metrics1["cache_hits"] == 0

    # Second call -> hit
    score2 = engine.predict_score(text)
    metrics2 = engine.get_metrics()
    assert score1 == score2
    assert metrics2["cache_hits"] == 1
    assert metrics2["cache_hit_rate"] == 0.5


def test_batch_prediction_with_duplicates():
    engine = SentimentEngine()
    batch = ["massive W", "huge L", "massive W", "massive W", "what time is it?"]
    scores = engine.predict_batch(batch)

    assert len(scores) == 5
    assert scores[0] == scores[2] == scores[3]  # Duplicate items have identical scores
    assert scores[0] > 0.5  # massive W is strongly positive
    assert scores[1] < -0.3  # huge L is negative


def test_concurrent_thread_safety():
    engine = SentimentEngine()
    phrases = [
        "W stream!", "Huge L", "what is this?", "poggers", "cringe bro",
        "clean gameplay", "bad audio", "hello chat", "masterpiece", "waste of time"
    ]

    def worker(i: int):
        phrase = phrases[i % len(phrases)]
        return engine.predict_score(phrase)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(worker, range(200)))

    assert len(results) == 200
    metrics = engine.get_metrics()
    assert metrics["total_inferences"] == 200
    assert metrics["cache_hits"] > 0


def test_single_char_tokens():
    engine = SentimentEngine()
    w_score = engine.predict_score("W")
    l_score = engine.predict_score("L")
    assert w_score > 0.5, f"Expected 'W' to be strongly positive, got {w_score}"
    assert l_score < -0.5, f"Expected 'L' to be strongly negative, got {l_score}"


def test_empty_and_whitespace_handling():
    engine = SentimentEngine()
    assert engine.predict_score("") == 0.0
    assert engine.predict_score("   ") == 0.0
    assert engine.predict_batch([]) == []
    batch_res = engine.predict_batch(["", "   ", "W"])
    assert len(batch_res) == 3
    assert batch_res[0] == 0.0
    assert batch_res[1] == 0.0
    assert batch_res[2] > 0.5


def test_latency_buffer_rollover():
    engine = SentimentEngine()
    # Fill beyond capacity (10,000)
    engine._record_latencies_bulk(0.05, count=12000)
    metrics = engine.get_metrics()
    assert metrics["total_inferences"] == 12000
    assert metrics["latency_p50_ms"] == 0.05
    assert len(engine.latencies_ms) == 10000


def test_contextual_negation_understanding():
    engine = SentimentEngine()
    # Negation turning a negative word positive
    score_not_bad = engine.predict_score("not bad")
    score_not_bad_at_all = engine.predict_score("actually not bad at all")
    assert score_not_bad > 0.1, f"Expected 'not bad' to be positive, got {score_not_bad}"
    assert score_not_bad_at_all > 0.2, f"Expected 'actually not bad at all' to be positive, got {score_not_bad_at_all}"

    # Negation turning a positive word negative
    score_not_good = engine.predict_score("not good")
    assert score_not_good < -0.2, f"Expected 'not good' to be negative, got {score_not_good}"
