from __future__ import annotations

import pandas as pd

from swingtraderai.schemas.trade_setup import VolumeContext


def build_volume_context(row: pd.Series, ratio_threshold: float = 1.2) -> VolumeContext:
	ratio = row.get("volume_ratio")
	zscore = row.get("volume_zscore")
	spike = row.get("volume_spike")

	ratio_f = float(ratio) if ratio is not None and pd.notna(ratio) else None
	z_f = float(zscore) if zscore is not None and pd.notna(zscore) else None
	spike_b = bool(spike) if spike is not None and pd.notna(spike) else None

	confirmed = False
	if spike_b:
		confirmed = True
	elif ratio_f is not None and ratio_f >= ratio_threshold:
		confirmed = True
	elif z_f is not None and z_f >= 1.0:
		confirmed = True

	return VolumeContext(
		confirmed=confirmed,
		volume_ratio=ratio_f,
		volume_zscore=z_f,
		spike=spike_b,
	)
