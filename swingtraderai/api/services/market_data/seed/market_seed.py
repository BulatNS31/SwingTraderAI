from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.db.models.market import Exchange, Ticker


async def seed_markets(
	session: AsyncSession,
) -> None:
	"""
	Создаёт биржи и тикеры, если их нет.
	Запускается один раз при старте приложения.
	"""
	exchanges = [
		{
			"code": "moex",
			"name": "Moscow Exchange",
			"tickers": [
				"SBER",
				"GAZP",
				"LKOH",
				"YNDX",
				"NVTK",
			],
		},
		{
			"code": "bybit",
			"name": "Bybit",
			"tickers": [
				"BTCUSDT",
				"ETHUSDT",
			],
		},
	]

	for exchange_data in exchanges:
		# Получаем или создаем биржу
		result = await session.execute(
			select(Exchange).where(Exchange.code == exchange_data["code"])
		)

		exchange: Optional[Exchange] = result.scalar_one_or_none()

		if exchange is None:
			exchange = Exchange(
				code=exchange_data["code"],
				name=exchange_data["name"],
				timezone="UTC",
				currency="USD",
			)
			session.add(exchange)
			await session.flush()

		if exchange is None:
			continue

		# Создаем тикеры для биржи
		for symbol in exchange_data["tickers"]:
			ticker_query = await session.execute(
				select(Ticker).where(
					Ticker.symbol == symbol,
					Ticker.exchange_id == exchange.id,
				)
			)
			ticker = ticker_query.scalar_one_or_none()

			if ticker is None:
				asset_type = "crypto" if "/" in symbol else "stock"

				ticker = Ticker(
					symbol=symbol,
					asset_type=asset_type,
					exchange_id=exchange.id,
					is_active=True,
				)
				session.add(ticker)

	await session.commit()
