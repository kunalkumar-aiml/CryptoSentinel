"""
LSTM price forecaster — NaN/Inf safe.
Fixes ValueError: Out of range float values are not JSON compliant.
"""
import os, math
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler
from utils.logger import get_logger
from utils.serializer import clean_value
from config import settings

log = get_logger("forecaster")

SEQ_LEN    = 48
PRED_STEPS = 6
HIDDEN     = 128
LAYERS     = 2
EPOCHS     = 60
LR         = 1e-3


class LSTMForecaster(nn.Module):
    def __init__(self, input_size=5):
        super().__init__()
        self.lstm = nn.LSTM(input_size, HIDDEN, LAYERS, batch_first=True,
                            dropout=0.2 if LAYERS > 1 else 0)
        self.attn = nn.Linear(HIDDEN, 1)
        self.fc   = nn.Linear(HIDDEN, PRED_STEPS)

    def forward(self, x):
        out, _ = self.lstm(x)
        w = torch.softmax(self.attn(out), dim=1)
        ctx = (w * out).sum(dim=1)
        return self.fc(ctx)


class PriceForecaster:
    def __init__(self):
        self.model   = LSTMForecaster()
        self.scaler  = MinMaxScaler(feature_range=(0.01, 0.99))  # avoids 0/1 boundary issues
        self.device  = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.feature_cols = ["close", "open", "high", "low", "volume_norm"]
        self._load_or_train()

    def _load_or_train(self):
        if os.path.exists(settings.FORECAST_MODEL_PATH):
            state = torch.load(settings.FORECAST_MODEL_PATH, map_location=self.device, weights_only=False)
            self.model.load_state_dict(state["model"])
            self.scaler = state["scaler"]
            log.info("forecaster.loaded")
        else:
            log.info("forecaster.training_from_scratch")
            self._train(self._synthetic_df())

    def _clean_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Sanitise OHLCV before any processing."""
        d = df.copy()
        d["volume_norm"] = np.log1p(d.get("volume", pd.Series(np.ones(len(d)))).fillna(1).clip(lower=0))
        for col in self.feature_cols:
            if col not in d.columns:
                d[col] = 0.0
            d[col] = pd.to_numeric(d[col], errors="coerce")
            d[col] = d[col].replace([np.inf, -np.inf], np.nan)
            d[col] = d[col].ffill().bfill().fillna(0)
        return d

    def _train(self, df: pd.DataFrame):
        d = self._clean_df(df)
        feat = d[self.feature_cols].values
        scaled = self.scaler.fit_transform(feat)

        X, y = [], []
        for i in range(len(scaled) - SEQ_LEN - PRED_STEPS + 1):
            X.append(scaled[i:i + SEQ_LEN])
            y.append(scaled[i + SEQ_LEN:i + SEQ_LEN + PRED_STEPS, 0])

        if not X:
            log.error("forecaster.not_enough_data")
            return

        Xt = torch.tensor(np.array(X, dtype=np.float32)).to(self.device)
        yt = torch.tensor(np.array(y, dtype=np.float32)).to(self.device)

        opt   = torch.optim.Adam(self.model.parameters(), lr=LR)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, EPOCHS)
        loss_fn = nn.HuberLoss()

        self.model.train()
        for ep in range(1, EPOCHS + 1):
            opt.zero_grad()
            pred = self.model(Xt)
            loss = loss_fn(pred, yt)
            loss.backward()
            nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            opt.step(); sched.step()
            if ep % 20 == 0:
                log.info("forecaster.training", epoch=ep, loss=round(loss.item(), 6))

        os.makedirs("models", exist_ok=True)
        torch.save({"model": self.model.state_dict(), "scaler": self.scaler},
                   settings.FORECAST_MODEL_PATH)
        log.info("forecaster.saved")

    def predict(self, df: pd.DataFrame) -> dict:
        """
        Predict next PRED_STEPS * 4h price candles.
        All outputs are NaN/Inf safe (fixes Bug #3).
        """
        self.model.eval()
        d    = self._clean_df(df.tail(SEQ_LEN * 2))
        feat = d[self.feature_cols].values

        if len(feat) < SEQ_LEN:
            feat = np.pad(feat, ((SEQ_LEN - len(feat), 0), (0, 0)), mode="edge")

        scaled = self.scaler.transform(feat[-SEQ_LEN:])

        # Guard: clip scaled values to [0,1]
        scaled = np.clip(scaled, 0.0, 1.0)

        x = torch.tensor(scaled[np.newaxis], dtype=torch.float32).to(self.device)
        with torch.no_grad():
            raw = self.model(x).cpu().numpy()[0]

        # Clip predicted scaled values before inverse transform
        raw = np.clip(raw, 0.0, 1.0)

        dummy       = np.tile(scaled[-1], (PRED_STEPS, 1))
        dummy[:, 0] = raw
        pred_prices = self.scaler.inverse_transform(dummy)[:, 0]

        # Final NaN/Inf cleanup — critical for JSON serialization
        pred_prices = np.where(
            np.isfinite(pred_prices), pred_prices,
            float(df["close"].dropna().iloc[-1]) if len(df) else 0.0
        )

        last_price  = float(df["close"].dropna().iloc[-1]) if len(df) else 0.0
        change_pct  = ((pred_prices[-1] - last_price) / last_price * 100) if last_price > 0 else 0.0

        # Ensure all floats are finite
        if not math.isfinite(change_pct):
            change_pct = 0.0

        return clean_value({
            "predicted_prices": [round(float(p), 2) for p in pred_prices],
            "direction":        "UP" if pred_prices[-1] > last_price else "DOWN",
            "change_pct":       round(float(change_pct), 2),
            "current_price":    round(last_price, 2),
            "horizon_hours":    PRED_STEPS * 4,
        })

    def _synthetic_df(self) -> pd.DataFrame:
        np.random.seed(7)
        n, price = 2000, 45000.0
        rows = []
        for _ in range(n):
            price *= np.exp(np.random.normal(0.0001, 0.018))
            rows.append({
                "close":  price * np.random.uniform(0.998, 1.002),
                "open":   price * np.random.uniform(0.99, 1.01),
                "high":   price * np.random.uniform(1.001, 1.02),
                "low":    price * np.random.uniform(0.98, 0.999),
                "volume": float(np.random.lognormal(20, 1)),
            })
        return pd.DataFrame(rows)
