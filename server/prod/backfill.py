import argparse
import datetime
import time
from .pipeline.pipeline import Pipeline
from .services.nasdaq_updater import fetch_upcoming, apply_updates


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def _print_day_header(i: int, total: int, d: datetime.date, elapsed: float) -> None:
    pct = (i / total) * 100
    eta_str = ""
    if i > 0:
        rate = elapsed / i  # seconds per day
        remaining = rate * (total - i)
        eta_str = f" | ETA ~{_fmt_duration(remaining)}"
    bar_len = 30
    filled = int(bar_len * i / total)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\n{'=' * 60}")
    print(f"  Day {i + 1}/{total}  [{bar}] {pct:.0f}%  elapsed {_fmt_duration(elapsed)}{eta_str}")
    print(f"  Date: {d.isoformat()} ({d.strftime('%A')})")
    print(f"{'=' * 60}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill missed days in the IPO pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m server.prod.backfill --start 2026-03-01 --end 2026-03-10
  python -m server.prod.backfill --start 2026-03-01 --end 2026-03-10 --skip-weekends
  python -m server.prod.backfill --start 2026-04-07 --end 2026-04-07 --reconcile-only
        """,
    )
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument(
        "--skip-weekends",
        action="store_true",
        help="Skip Saturday and Sunday (SEC does not publish daily-index on weekends)",
    )
    parser.add_argument(
        "--efts-only",
        action="store_true",
        help="Run only the daytime EFTS pass (skip nightly reconcile)",
    )
    parser.add_argument(
        "--reconcile-only",
        action="store_true",
        help="Run only the nightly index reconcile (skip EFTS pass)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to sleep between days (default: 2.0)",
    )
    args = parser.parse_args()

    if args.efts_only and args.reconcile_only:
        raise SystemExit("--efts-only and --reconcile-only are mutually exclusive.")

    try:
        start = datetime.date.fromisoformat(args.start)
        end = datetime.date.fromisoformat(args.end)
    except ValueError as e:
        raise SystemExit(f"Invalid date format: {e}")

    if start > end:
        raise SystemExit(f"--start ({args.start}) must be <= --end ({args.end})")

    # Build list of dates to process
    dates = []
    d = start
    while d <= end:
        if args.skip_weekends and d.weekday() >= 5:
            pass  # silently skip weekends (no spam)
        else:
            dates.append(d)
        d += datetime.timedelta(days=1)

    total_days = len(dates)
    if total_days == 0:
        raise SystemExit("No dates to process after applying filters.")

    skipped_weekends = (end - start).days + 1 - total_days
    stage_label = "EFTS only" if args.efts_only else "Reconcile only" if args.reconcile_only else "EFTS + Reconcile"

    print(f"\n{'=' * 60}")
    print(f"  BACKFILL STARTING")
    print(f"{'=' * 60}")
    print(f"  Range   : {start} → {end}")
    print(f"  Days    : {total_days} trading days ({skipped_weekends} weekend days skipped)")
    print(f"  Stages  : {stage_label}")
    print(f"  AI      : deferred to post-pass (one call per CIK, best document)")
    print(f"  Delay   : {args.delay}s between days")
    print(f"{'=' * 60}\n")

    pipe = Pipeline()
    pipe.logo.backfill_mode = True  # use SEC filing + DuckDuckGo instead of Google API
    pipe.skip_ai = True             # skip inline AI; run single post-pass after all days

    t_start = time.monotonic()

    for i, d in enumerate(dates):
        elapsed = time.monotonic() - t_start
        _print_day_header(i, total_days, d, elapsed)

        # Stage 1: EFTS daytime pass
        if not args.reconcile_only:
            print(f"[BACKFILL] Stage 1: EFTS pass for {d.isoformat()}")
            try:
                pipe.fetch_and_push(d.isoformat(), d.isoformat())
            except Exception as e:
                print(f"[BACKFILL][ERROR] EFTS pass failed for {d.isoformat()}: {e}")

        # Stage 2: Nightly daily-index reconcile
        if not args.efts_only:
            ds = d.strftime("%Y%m%d")
            print(f"[BACKFILL] Stage 2: Nightly reconcile for {ds}")
            try:
                pipe.reconcile_daily_index(ds)
            except Exception as e:
                print(f"[BACKFILL][ERROR] Reconcile failed for {ds}: {e}")

        # Sleep between days (not after the last one)
        if i < total_days - 1:
            time.sleep(args.delay)

    ingestion_elapsed = time.monotonic() - t_start
    print(f"\n{'=' * 60}")
    print(f"  INGESTION COMPLETE")
    print(f"  Processed {total_days} day(s) in {_fmt_duration(ingestion_elapsed)}")
    print(f"{'=' * 60}")

    # AI post-pass: analyze each unanalyzed IPO once, using best document
    print("\n[BACKFILL] Running AI analysis post-pass...")
    try:
        pipe.analyze_backfill()
    except Exception as e:
        print(f"[BACKFILL][ERROR] AI post-pass failed: {e}")

    # Nasdaq update once at the end
    print("\n[BACKFILL] Updating IPO info from Nasdaq...")
    try:
        nasdaq_data = fetch_upcoming()
        apply_updates(nasdaq_data, apply=True, supabase=pipe.db.client)
        print("[BACKFILL] Nasdaq update complete.")
    except Exception as e:
        print(f"[BACKFILL][ERROR] Nasdaq update failed: {e}")

    # Push to Cloudflare KV once at the end
    print("\n[BACKFILL] Pushing final IPO table to Cloudflare KV...")
    try:
        pipe.kv.push_ipo_table()
        print("[BACKFILL] KV sync complete.")
    except Exception as e:
        print(f"[BACKFILL][ERROR] KV push failed: {e}")

    total_elapsed = time.monotonic() - t_start
    print(f"\n{'=' * 60}")
    print(f"  BACKFILL DONE")
    print(f"  {total_days} day(s) | total time {_fmt_duration(total_elapsed)}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
