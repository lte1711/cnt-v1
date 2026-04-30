from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import SYMBOL_VALIDATION_LOG_FILE, SYMBOL_VALIDATION_REPORT_FILE
from src.analytics.symbol_validation_report import generate_and_save_symbol_validation_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CNT symbol validation report")
    parser.add_argument("--log-file", default=SYMBOL_VALIDATION_LOG_FILE)
    parser.add_argument("--report-file", default=SYMBOL_VALIDATION_REPORT_FILE)
    parser.add_argument("--symbol", default=None)
    args = parser.parse_args()

    report = generate_and_save_symbol_validation_report(
        log_file=args.log_file,
        report_file=args.report_file,
        symbol=args.symbol,
    )
    print(
        json.dumps(
            {
                "report_file": args.report_file,
                "event_count": report["event_count"],
                "closed_trades": report["closed_trades"],
                "order_count": report["order_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
