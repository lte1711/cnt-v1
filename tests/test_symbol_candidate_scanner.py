from __future__ import annotations

import unittest

from tools.symbol_candidate_scanner import list_usdt_spot_symbols, replay_pullback_v1


def _kline(index: int, close: float) -> dict:
    return {
        "open_time": index * 60000,
        "open": close,
        "high": close * 1.002,
        "low": close * 0.998,
        "close": close,
        "volume": 100.0,
        "close_time": (index + 1) * 60000 - 1,
    }


class SymbolCandidateScannerTests(unittest.TestCase):
    def test_list_usdt_spot_symbols_filters_and_sorts(self) -> None:
        exchange_info = {
            "symbols": [
                {"symbol": "LOWUSDT", "quoteAsset": "USDT", "status": "TRADING", "isSpotTradingAllowed": True},
                {"symbol": "HIGHUSDT", "quoteAsset": "USDT", "status": "TRADING", "isSpotTradingAllowed": True},
                {"symbol": "BTCEUR", "quoteAsset": "EUR", "status": "TRADING", "isSpotTradingAllowed": True},
                {"symbol": "OLDUSDT", "quoteAsset": "USDT", "status": "BREAK", "isSpotTradingAllowed": True},
            ]
        }
        tickers = {
            "LOWUSDT": {"quoteVolume": "10"},
            "HIGHUSDT": {"quoteVolume": "100"},
        }

        result = list_usdt_spot_symbols(exchange_info, tickers)

        self.assertEqual([item["symbol"] for item in result], ["HIGHUSDT", "LOWUSDT"])

    def test_replay_pullback_returns_metrics(self) -> None:
        klines = [_kline(index, 100.0 + (index * 0.01)) for index in range(240)]

        result = replay_pullback_v1("ETHUSDT", klines, klines)

        self.assertIn("trades_closed", result)
        self.assertIn("win_rate", result)
        self.assertIn("expectancy_pct", result)
        self.assertIn("profit_factor", result)


if __name__ == "__main__":
    unittest.main()
