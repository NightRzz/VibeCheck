"""MLOps evaluation and experiment tracking pipeline using MLflow.

Compares Classical ML Baselines (TF-IDF + Logistic Regression / XGBoost) against
the Production Deep Contextual Transformer (Twitter-RoBERTa-base ONNX INT8).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

from ml.data import load_augmented_sentiment_dataset
from processor.sentiment_engine import SentimentEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ml.train")

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
REFERENCE_DATA_PATH = ARTIFACTS_DIR / "reference_data.parquet"


def evaluate_and_log_models() -> None:
    """Evaluates the Contextual Transformer and logs all metrics to MLflow."""
    mlflow.set_experiment("vibecheck-sentiment-models")

    logger.info("Loading open-source 'cardiffnlp/tweet_eval' benchmark dataset...")
    _, X_test, _, y_test = load_augmented_sentiment_dataset(max_train_samples=35000, seed=42)

    # Save reference dataset for Evidently AI drift detection
    ref_df = pd.DataFrame({"text": X_test, "label": y_test})
    ref_df.to_parquet(REFERENCE_DATA_PATH, index=False)
    logger.info("Saved reference dataset for drift monitoring to %s", REFERENCE_DATA_PATH)

    # Initialize Contextual Transformer Engine
    logger.info("Initializing Twitter-RoBERTa ONNX INT8 Inference Engine...")
    engine = SentimentEngine()

    eval_samples = min(1000, len(X_test))
    sub_X = list(X_test.iloc[:eval_samples])
    sub_y = list(y_test.iloc[:eval_samples])

    with mlflow.start_run(run_name="twitter_roberta_onnx_int8"):
        t0 = time.perf_counter()
        probs = engine._predict_probabilities_batch(sub_X)
        eval_duration = time.perf_counter() - t0
        preds = np.argmax(probs, axis=-1)

        acc = float(accuracy_score(sub_y, preds))
        macro_f1 = float(f1_score(sub_y, preds, average="macro"))
        weighted_f1 = float(f1_score(sub_y, preds, average="weighted"))
        latency_per_sample_ms = (eval_duration / eval_samples) * 1000.0

        logger.info(
            "[twitter_roberta_onnx_int8] Accuracy: %.4f | Macro F1: %.4f | Latency: %.2f ms/sample",
            acc, macro_f1, latency_per_sample_ms
        )

        # Log parameters to MLflow
        mlflow.log_param("model_name", "Twitter-RoBERTa-base-INT8")
        mlflow.log_param("architecture", "RoBERTa (Transformer with Self-Attention)")
        mlflow.log_param("runtime", "ONNXRuntime-CPUExecutionProvider")
        mlflow.log_param("quantization", "INT8")
        mlflow.log_param("max_seq_length", 64)
        mlflow.log_param("tokenizer", "Byte-Pair-Encoding (BPE)")
        mlflow.log_param("domain_source", "cardiffnlp/twitter-roberta-base-sentiment-latest")

        # Log metrics
        mlflow.log_metric("accuracy", acc)
        mlflow.log_metric("macro_f1", macro_f1)
        mlflow.log_metric("weighted_f1", weighted_f1)
        mlflow.log_metric("latency_mean_ms", latency_per_sample_ms)
        mlflow.log_metric("eval_samples", eval_samples)

        # Log ONNX artifacts directory
        onnx_dir = ARTIFACTS_DIR / "onnx"
        if onnx_dir.exists():
            for f in onnx_dir.glob("*.json"):
                mlflow.log_artifact(str(f), artifact_path="model_config")

        logger.info("Successfully tracked Contextual Transformer in MLflow.")


def main() -> None:
    evaluate_and_log_models()


if __name__ == "__main__":
    main()
