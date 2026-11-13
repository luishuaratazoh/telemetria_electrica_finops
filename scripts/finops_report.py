"""Reporte FinOps desde terminal.

  python scripts/finops_report.py                 # ultimas 24 h
  python scripts/finops_report.py --hours 1 --save   # guarda estimaciones (las lee Grafana)
  python scripts/finops_report.py --apply-policies   # aplica FINOPS_RETENTION_DAYS / FINOPS_COMPRESS_AFTER_DAYS
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from telemetry_platform.common.config import get_settings  # noqa: E402
from telemetry_platform.finops import policies, reporter  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--save", action="store_true", help="persistir estimaciones en finops.cost_estimates")
    ap.add_argument("--apply-policies", action="store_true")
    args = ap.parse_args()

    if args.apply_policies:
        s = get_settings()
        policies.apply_policies(s.finops_retention_days, s.finops_compress_after_days)
    print(reporter.format_report(reporter.build_report(args.hours, save=args.save)))


if __name__ == "__main__":
    main()
