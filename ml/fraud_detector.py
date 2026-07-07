import os, pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
import xgboost as xgb
import shap
from config import settings
FRAUD_MODEL_PATH = settings.FRAUD_MODEL_PATH
FRAUD_THRESHOLD = settings.FRAUD_THRESHOLD
from utils.logger import get_logger

log = get_logger("fraud_detector")

FEATURE_COLS = [
    "tx_velocity", "unique_out_addrs", "unique_in_addrs", "total_counterparties",
    "clustering_coeff", "avg_value_eth", "std_value_eth", "max_value_eth",
    "zero_value_ratio", "in_out_ratio", "gas_anomaly_score", "addr_reuse_score", "total_txns"
]

class FraudDetector:
    def __init__(self):
        self.model   = None
        self.scaler  = StandardScaler()
        self.explainer = None
        self._load_or_train()

    def _load_or_train(self):
        if os.path.exists(FRAUD_MODEL_PATH):
            with open(FRAUD_MODEL_PATH, "rb") as f:
                bundle = pickle.load(f)
            self.model   = bundle["model"]
            self.scaler  = bundle["scaler"]
            log.info("Fraud model loaded from disk")
        else:
            log.info("No saved model found — training on synthetic data")
            self._train_synthetic()

    def _train_synthetic(self):
        """Train XGBoost on synthetic labelled wallet-graph features."""
        np.random.seed(42)
        n = 5000

        # Legitimate wallets
        legit = pd.DataFrame({
            "tx_velocity":         np.random.uniform(0.1, 5, n//2),
            "unique_out_addrs":    np.random.randint(1, 50, n//2).astype(float),
            "unique_in_addrs":     np.random.randint(1, 30, n//2).astype(float),
            "total_counterparties":np.random.randint(2, 70, n//2).astype(float),
            "clustering_coeff":    np.random.uniform(0.1, 0.8, n//2),
            "avg_value_eth":       np.abs(np.random.lognormal(0, 2, n//2)),
            "std_value_eth":       np.abs(np.random.lognormal(-1, 1.5, n//2)),
            "max_value_eth":       np.abs(np.random.lognormal(2, 2, n//2)),
            "zero_value_ratio":    np.random.uniform(0, 0.2, n//2),
            "in_out_ratio":        np.random.uniform(0.3, 3, n//2),
            "gas_anomaly_score":   np.random.uniform(0, 0.15, n//2),
            "addr_reuse_score":    np.random.uniform(0, 0.3, n//2),
            "total_txns":          np.random.randint(5, 200, n//2).astype(float),
            "label": 0
        })

        # Fraudulent wallets (mixing services, bots, scammers)
        fraud = pd.DataFrame({
            "tx_velocity":         np.random.uniform(20, 200, n//2),
            "unique_out_addrs":    np.random.randint(1, 5, n//2).astype(float),
            "unique_in_addrs":     np.random.randint(50, 500, n//2).astype(float),
            "total_counterparties":np.random.randint(51, 510, n//2).astype(float),
            "clustering_coeff":    np.random.uniform(0, 0.1, n//2),
            "avg_value_eth":       np.abs(np.random.lognormal(-3, 1, n//2)),
            "std_value_eth":       np.abs(np.random.lognormal(2, 2, n//2)),
            "max_value_eth":       np.abs(np.random.lognormal(4, 2, n//2)),
            "zero_value_ratio":    np.random.uniform(0.5, 1.0, n//2),
            "in_out_ratio":        np.random.uniform(0.01, 0.1, n//2),
            "gas_anomaly_score":   np.random.uniform(0.6, 1.0, n//2),
            "addr_reuse_score":    np.random.uniform(0.7, 1.0, n//2),
            "total_txns":          np.random.randint(100, 5000, n//2).astype(float),
            "label": 1
        })

        df = pd.concat([legit, fraud]).sample(frac=1, random_state=42).reset_index(drop=True)
        X = df[FEATURE_COLS]
        y = df["label"]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

        X_train_s = self.scaler.fit_transform(X_train)
        X_test_s  = self.scaler.transform(X_test)

        self.model = xgb.XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            scale_pos_weight=1, eval_metric="auc",
            use_label_encoder=False, random_state=42, n_jobs=-1
        )
        self.model.fit(
            X_train_s, y_train,
            eval_set=[(X_test_s, y_test)],
            verbose=False
        )

        preds = self.model.predict_proba(X_test_s)[:, 1]
        auc = roc_auc_score(y_test, preds)
        log.info(f"Fraud model trained — AUC-ROC: {auc:.4f}")
        log.info("\n" + classification_report(y_test, (preds > FRAUD_THRESHOLD).astype(int)))

        os.makedirs("models", exist_ok=True)
        with open(FRAUD_MODEL_PATH, "wb") as f:
            pickle.dump({"model": self.model, "scaler": self.scaler}, f)
        log.info(f"Model saved to {FRAUD_MODEL_PATH}")

    def predict(self, features: dict) -> dict:
        """Score a wallet. Returns fraud probability + risk level + SHAP explanation."""
        X = pd.DataFrame([{col: features.get(col, 0.0) for col in FEATURE_COLS}])
        X_s = self.scaler.transform(X)
        prob = float(self.model.predict_proba(X_s)[0][1])

        # SHAP explanation
        if self.explainer is None:
            self.explainer = shap.TreeExplainer(self.model)
        shap_vals = self.explainer.shap_values(X_s)[0]
        top_features = sorted(
            zip(FEATURE_COLS, shap_vals),
            key=lambda x: abs(x[1]), reverse=True
        )[:5]

        if prob < 0.3:
            risk = "LOW"
        elif prob < 0.6:
            risk = "MEDIUM"
        elif prob < 0.8:
            risk = "HIGH"
        else:
            risk = "CRITICAL"

        return {
            "fraud_probability": round(prob, 4),
            "risk_level": risk,
            "is_suspicious": prob >= FRAUD_THRESHOLD,
            "top_features": [{"feature": f, "shap_value": round(float(v), 4)} for f, v in top_features],
        }
