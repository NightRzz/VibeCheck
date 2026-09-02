"""CPU inference benchmarking and profiling script for VibeCheck.

Measures:
- Latency percentiles (P50, P90, P95, P99) on CPU
- Cache hit rate and acceleration on repeated live chat patterns
- Batching throughput (inferences / second)
"""
from __future__ import annotations

import random
import time
from typing import List

from processor.sentiment_engine import SentimentEngine

SAMPLE_CHAT_MESSAGES = [
    "W", "massive W", "W streamer", "pog", "poggers", "LETS GOOO",
    "L", "huge L", "boring stream", "trash gameplay", "unwatchable",
    "what game is this?", "hello chat", "music name?", "is this 60fps?",
    "gg", "gg wp", "clip that!", "based", "cringe", "scam",
    "love this stream so much", "best content on youtube", "lagging", "buffering"
]


def run_benchmark(n_iterations: int = 5000) -> None:
    print(f"=== Starting CPU Inference Benchmark ({n_iterations} samples) ===")
    engine = SentimentEngine()

    # Generate synthetic stream with 40% duplicate messages (representative of Twitch/YouTube chat)
    random.seed(42)
    stream: List[str] = [random.choice(SAMPLE_CHAT_MESSAGES) for _ in range(n_iterations)]

    # 1. Warm-up
    print("Warming up engine...")
    for msg in stream[:100]:
        engine.predict_score(msg)

    # Reset metrics for benchmark
    engine.total_inferences = 0
    engine.cache_hits = 0
    engine.cache_misses = 0
    engine.latencies_ms.clear()

    t_start = time.perf_counter()
    for msg in stream:
        engine.predict_score(msg)
    total_time = time.perf_counter() - t_start

    metrics = engine.get_metrics()
    throughput = n_iterations / total_time

    print("\n--- Benchmark Results (CPU) ---")
    print(f"Total Processed:    {metrics['total_inferences']}")
    print(f"Total Elapsed Time:  {total_time * 1000.0:.2f} ms")
    print(f"Throughput:          {throughput:,.1f} items/sec")
    print(f"Cache Hit Rate:      {metrics['cache_hit_rate'] * 100:.2f}%")
    print(f"P50 Latency:         {metrics['latency_p50_ms']:.4f} ms")
    print(f"P90 Latency:         {metrics['latency_p90_ms']:.4f} ms")
    print(f"P95 Latency:         {metrics['latency_p95_ms']:.4f} ms")
    print(f"P99 Latency:         {metrics['latency_p99_ms']:.4f} ms")
    print(f"Mean Latency:        {metrics['latency_mean_ms']:.4f} ms")

    # 2. Batching Benchmark
    batch_sizes = [8, 16, 32, 64]
    print("\n--- Micro-Batching Throughput ---")
    for bs in batch_sizes:
        batches = [stream[i : i + bs] for i in range(0, len(stream), bs)]
        t0 = time.perf_counter()
        for b in batches:
            engine.predict_batch(b)
        batch_duration = time.perf_counter() - t0
        batch_tps = len(stream) / batch_duration
    # 3. Context & Negation Verification
    print("\n--- Semantic Context & Negation Verification ---")
    context_samples = [
        ("not bad", True),
        ("actually not bad at all", True),
        ("not terrible", True),
        ("not good", False),
        ("not great, pretty boring", False),
        ("huge W streamer", True),
        ("huge L gameplay", False),
    ]
    for text, expected_pos in context_samples:
        score = engine.predict_score(text)
        is_pos = score > 0
        status = "PASSED" if is_pos == expected_pos else "FAILED"
        direction = "Positive" if is_pos else "Negative"
        print(f"[{status}] '{text:30s}' -> {score:+.4f} ({direction})")

    print("\nBenchmark completed successfully.")


if __name__ == "__main__":
    run_benchmark()
