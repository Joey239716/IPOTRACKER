import argparse
import datetime
from zoneinfo import ZoneInfo
from .pipeline.pipeline import Pipeline
from .services.nasdaq_updater import upsert_to_supabase  # new Nasdaq updater

def main() -> None:
    parser = argparse.ArgumentParser(description="Nightly IPO pipeline")
    parser.add_argument("--ds", help="Date string YYYYMMDD (default=yesterday in ET)")
    args = parser.parse_args()

    # Determine date
    if args.ds:
        ds = args.ds
    else:
        et_now = datetime.datetime.now(ZoneInfo("America/Toronto"))
        prev_day = et_now.date() - datetime.timedelta(days=1)
        ds = prev_day.strftime("%Y%m%d")

    pipeline = Pipeline()

    # 1️⃣ SEC master daily index reconciliation
    pipeline.reconcile_daily_index(ds)

    # 2️⃣ Nasdaq estimated date / IPO column updates
    print("\n=== Updating IPO info from Nasdaq ===")
    upsert_to_supabase()
    print("=== Nasdaq update complete ===\n")

    # 3️⃣ Push latest IPO table to Cloudflare KV
    print("\n=== Pushing IPO table to Cloudflare KV ===")
    pipeline.kv.push_ipo_table()
    print("=== KV sync complete ===\n")

if __name__ == "__main__":
    main()
