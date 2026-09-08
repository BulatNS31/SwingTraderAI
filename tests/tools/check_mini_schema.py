from datetime import datetime, timezone

from swingtraderai.schemas.trade_setup import (
	LevelContext,
	LevelType,
	RiskContext,
	SetupSide,
	SetupType,
	SignalStrength,
	TradeSetup,
	TrendContext,
	TrendDirection,
	TriggerContext,
	VolumeContext,
)

setup = TradeSetup(
	symbol="AMZN",
	timeframe="1D",
	bar_time=datetime.now(timezone.utc),
	side=SetupSide.LONG,
	setup_type=SetupType.BULLISH_DIVERGENCE,
	trend=TrendContext(direction=TrendDirection.UP, price_above_ema200=True),
	level=LevelContext(
		near_level=True, level_type=LevelType.SUPPORT, level_price=180.0
	),
	trigger=TriggerContext(
		setup_type=SetupType.BULLISH_DIVERGENCE,
		side=SetupSide.LONG,
		details={"oscillator": "rsi"},
	),
	volume=VolumeContext(confirmed=True, volume_ratio=1.4),
	risk=RiskContext(entry=182.0, invalidation=178.0, target_1=190.0),
	composite_signal=SignalStrength.BUY,
	signal_strength=7,
	indicators_used=["rsi", "ema200", "sr_levels"],
)

print(setup.is_actionable())  # True при R:R >= 1.5
print(setup.to_agent_payload())  # JSON для агента
