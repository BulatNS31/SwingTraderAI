from dataclasses import dataclass


@dataclass(frozen=True)
class ExchangeInfo:
	code: str
	name: str
	asset_type: str


class Exchanges:
	MOEX = ExchangeInfo(
		code="moex",
		name="Moscow Exchange",
		asset_type="stock",
	)

	BYBIT = ExchangeInfo(
		code="bybit",
		name="Bybit",
		asset_type="crypto",
	)

	YAHOO = ExchangeInfo(
		code="yahoo",
		name="Yahoo Finance",
		asset_type="stock",
	)

	NASDAQ = ExchangeInfo(
		code="nasdaq",
		name="NASDAQ",
		asset_type="stock",
	)

	NYSE = ExchangeInfo(
		code="nyse",
		name="New York Stock Exchange",
		asset_type="stock",
	)

	BINANCE = ExchangeInfo(
		code="binance",
		name="Binance",
		asset_type="crypto",
	)

	EXCHANGES = {
		MOEX.code: MOEX,
		BYBIT.code: BYBIT,
		YAHOO.code: YAHOO,
		NASDAQ.code: NASDAQ,
		NYSE.code: NYSE,
		BINANCE.code: BINANCE,
	}
