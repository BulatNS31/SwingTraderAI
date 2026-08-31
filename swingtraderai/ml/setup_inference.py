from __future__ import annotations

from typing import List

import joblib
import pandas as pd

from swingtraderai.ml.setup_dataset import setup_to_features
from swingtraderai.schemas.trade_setup import TradeSetup, TradeSetupList


class SetupModelInference:
	def __init__(self, model_path: str) -> None:
		blob = joblib.load(model_path)
		self.model = blob["model"]
		self.scaler = blob["scaler"]
		self.features: List[str] = blob["features"]
		self.meta = {k: v for k, v in blob.items() if k not in ("model", "scaler")}

	def predict_proba(self, setup: TradeSetup) -> float:
		feats = setup_to_features(setup)
		row = pd.DataFrame([{f: feats.get(f, 0.0) for f in self.features}])
		Xs = self.scaler.transform(row)
		return float(self.model.predict_proba(Xs)[0, 1])

	def enrich(self, setups: List[TradeSetup]) -> List[TradeSetup]:
		out: List[TradeSetup] = []
		for s in setups:
			prob = self.predict_proba(s)
			out.append(s.model_copy(update={"ml_prob": prob}))
		return out

	def enrich_list(self, result: TradeSetupList) -> TradeSetupList:
		return TradeSetupList(
			symbol=result.symbol,
			timeframe=result.timeframe,
			as_of=result.as_of,
			setups=self.enrich(result.setups),
		)
