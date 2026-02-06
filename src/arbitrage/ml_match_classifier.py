import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np


@dataclass
class MatchModel:
    weights: List[float]
    bias: float
    feature_names: List[str]
    trained_at: str

    def to_dict(self) -> Dict:
        return {
            "weights": self.weights,
            "bias": self.bias,
            "feature_names": self.feature_names,
            "trained_at": self.trained_at,
        }


class HybridMatchClassifier:
    """Lightweight logistic regression classifier for match prediction."""

    def __init__(self, model: Optional[MatchModel] = None):
        self.model = model

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [t for t in "".join(c if c.isalnum() else " " for c in text.lower()).split() if t]

    @classmethod
    def _features(cls, left: str, right: str) -> np.ndarray:
        left_tokens = set(cls._tokenize(left))
        right_tokens = set(cls._tokenize(right))
        intersection = left_tokens & right_tokens
        union = left_tokens | right_tokens
        jaccard = len(intersection) / max(len(union), 1)
        length_ratio = min(len(left), len(right)) / max(len(left), len(right), 1)
        overlap = len(intersection)
        return np.array([jaccard, length_ratio, overlap], dtype=float)

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-x))

    @classmethod
    def train_from_temporal_events(
        cls,
        events_path: str = "data/learning/temporal_events.jsonl",
        output_path: str = "data/learning/ml_match_model.json",
        epochs: int = 200,
        lr: float = 0.1,
    ) -> MatchModel:
        if not os.path.exists(events_path):
            raise FileNotFoundError(events_path)

        samples: List[np.ndarray] = []
        labels: List[int] = []
        with open(events_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("type") not in {"match", "near_miss"}:
                    continue
                left = row.get("poly_name") or row.get("poly_id") or ""
                right = row.get("bf_candidate") or row.get("bf_market_id") or ""
                if not left or not right:
                    continue
                samples.append(cls._features(left, right))
                labels.append(1 if row.get("type") == "match" else 0)

        if not samples:
            raise ValueError("No training samples found in temporal events.")

        X = np.vstack(samples)
        y = np.array(labels, dtype=float)

        weights = np.zeros(X.shape[1])
        bias = 0.0

        for _ in range(epochs):
            logits = X @ weights + bias
            preds = cls._sigmoid(logits)
            error = preds - y
            grad_w = X.T @ error / len(y)
            grad_b = error.mean()
            weights -= lr * grad_w
            bias -= lr * grad_b

        model = MatchModel(
            weights=weights.tolist(),
            bias=float(bias),
            feature_names=["jaccard", "length_ratio", "overlap"],
            trained_at=datetime.utcnow().isoformat(),
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(model.to_dict(), f, indent=2)
        return model

    @classmethod
    def load_if_available(cls, path: str = "data/learning/ml_match_model.json") -> "HybridMatchClassifier":
        if not os.path.exists(path):
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        model = MatchModel(
            weights=raw.get("weights", []),
            bias=raw.get("bias", 0.0),
            feature_names=raw.get("feature_names", []),
            trained_at=raw.get("trained_at", ""),
        )
        return cls(model=model)

    def predict_proba(self, left: str, right: str) -> float:
        if not self.model:
            return 0.0
        feats = self._features(left, right)
        weights = np.array(self.model.weights)
        bias = self.model.bias
        return float(self._sigmoid(feats @ weights + bias))
