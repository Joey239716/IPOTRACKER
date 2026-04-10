"""
logo_fill.py — Find and upload logos for IPOs that are missing one or have a placeholder.

Queries both the `ipo` and `public_companies` tables. For each company:
  1. Uses website_homepage already stored in DB (from AI analysis) if available
  2. Falls back to DuckDuckGo instant answer
  3. Falls back to Google Custom Search (unless --no-google)
  4. Falls back to a generated placeholder

Usage:
  python -m server.prod.logo_fill
  python -m server.prod.logo_fill --table ipo
  python -m server.prod.logo_fill --table public_companies
  python -m server.prod.logo_fill --placeholder-only   # only regenerate placeholders
  python -m server.prod.logo_fill --no-google          # skip Google API (DuckDuckGo only)
  python -m server.prod.logo_fill --limit 50           # process at most N companies
"""

import argparse
import datetime
import time

from .services.db import Database
from .services.logo_service import LogoService


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def _fetch_targets(db: Database, table: str, placeholder_only: bool) -> list[dict]:
    """Return rows that need a logo from the given table."""
    # public_companies has no logo_type or website_homepage column
    has_logo_type = table == "ipo"

    if has_logo_type:
        q = db.client.table(table).select("cik, company_name, logo_url, logo_type, website_homepage")
        if placeholder_only:
            q = q.eq("logo_type", "placeholder")
        else:
            q = q.or_("logo_url.is.null,logo_type.eq.placeholder")
    else:
        q = db.client.table(table).select("cik, company_name, logo_url")
        if placeholder_only:
            # Can't filter by logo_type — skip placeholder-only mode for this table
            return []
        else:
            q = q.is_("logo_url", "null")

    resp = q.execute()
    return resp.data or []


def _find_homepage(logo_svc: LogoService, row: dict, google_budget: list[int]) -> str | None:
    """Try to find a homepage for the company using available strategies.
    google_budget is a one-element list acting as a mutable counter [remaining_queries].
    """
    # Strategy 1: already stored from AI analysis — free, instant
    stored = (row.get("website_homepage") or "").strip()
    if stored.startswith("http"):
        return stored

    name = row.get("company_name") or ""

    # Strategy 2: Google Custom Search (capped at 100 queries)
    if google_budget[0] > 0:
        homepage = logo_svc.search_homepage_google(name)
        google_budget[0] -= 1
        if homepage:
            return homepage

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill missing / placeholder logos for IPOs")
    parser.add_argument(
        "--table",
        choices=["ipo", "public_companies", "both"],
        default="both",
        help="Which table to process (default: both)",
    )
    parser.add_argument(
        "--placeholder-only",
        action="store_true",
        help="Only re-process companies that currently have a placeholder logo",
    )
    parser.add_argument(
        "--google-cap",
        type=int,
        default=100,
        help="Max Google API queries to spend (default: 100, set 0 to disable)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of companies to process (0 = no limit)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to sleep between companies (default: 1.0)",
    )
    args = parser.parse_args()

    db = Database()
    logo_svc = LogoService(db)
    google_budget = [args.google_cap]  # mutable counter passed by reference

    # Collect targets
    tables = (
        ["ipo", "public_companies"] if args.table == "both"
        else [args.table]
    )

    rows: list[tuple[str, dict]] = []  # (table_name, row)
    for tbl in tables:
        fetched = _fetch_targets(db, tbl, args.placeholder_only)
        rows.extend((tbl, r) for r in fetched)

    if args.limit > 0:
        rows = rows[: args.limit]

    total = len(rows)
    if total == 0:
        print("[LOGO-FILL] No companies need logo updates.")
        return

    mode = "placeholder-only" if args.placeholder_only else "missing + placeholder"
    google_str = f"Google API (cap: {args.google_cap} queries)" if args.google_cap > 0 else "disabled"
    print(f"\n{'=' * 60}")
    print(f"  LOGO FILL")
    print(f"{'=' * 60}")
    print(f"  Tables  : {', '.join(tables)}")
    print(f"  Mode    : {mode}")
    print(f"  Search  : {google_str}")
    print(f"  Total   : {total} companies")
    print(f"  Delay   : {args.delay}s between companies")
    print(f"{'=' * 60}\n")

    stats = {"found": 0, "placeholder": 0, "failed": 0, "skipped": 0}
    t0 = time.monotonic()

    for i, (table, row) in enumerate(rows, 1):
        cik = str(row.get("cik", ""))
        name = row.get("company_name") or ""
        current_type = row.get("logo_type") or ("none" if not row.get("logo_url") else "unknown")

        elapsed = time.monotonic() - t0
        done = i - 1
        eta_str = ""
        if done > 0:
            rate = elapsed / done
            remaining = rate * (total - done)
            eta_str = f" | ETA ~{_fmt_duration(remaining)}"

        bar_len = 25
        filled = int(bar_len * done / total)
        bar = "█" * filled + "░" * (bar_len - filled)
        pct = (done / total) * 100
        print(f"\n[{bar}] {pct:.0f}%  {i}/{total}  elapsed {_fmt_duration(elapsed)}{eta_str}")
        print(f"  CIK={cik}  table={table}  current={current_type}  name={name!r}")

        if not cik:
            print(f"  SKIP: missing CIK")
            stats["skipped"] += 1
            continue

        logo_bytes = logo_svc.generate_placeholder_webp(name)
        logo_type = "placeholder"
        homepage = None
        if logo_bytes:
            print(f"  Result  : generated placeholder ({len(logo_bytes):,} bytes)")

        if not logo_bytes:
            print(f"  FAIL: could not generate any logo")
            stats["failed"] += 1
            continue

        # Upload
        object_name = logo_svc.hashed_object_name(cik)
        public_url = logo_svc.upload_and_get_url(object_name, logo_bytes)
        if not public_url:
            print(f"  FAIL: upload failed")
            stats["failed"] += 1
            continue

        today = datetime.date.today().isoformat()
        try:
            update_data: dict = {"logo_url": public_url, "updated_logo_date": today}
            if table == "ipo":
                update_data["logo_type"] = logo_type
                if homepage and not row.get("website_homepage"):
                    update_data["website_homepage"] = homepage
            db.client.table(table).update(update_data).eq("cik", cik).execute()
            print(f"  SAVED   : {logo_type} → {public_url[:80]}...")
            if logo_type == "favicon":
                stats["found"] += 1
            else:
                stats["placeholder"] += 1
        except Exception as e:
            print(f"  FAIL: DB update error: {e}")
            stats["failed"] += 1

        if i < total:
            time.sleep(args.delay)

    total_elapsed = time.monotonic() - t0
    google_used = args.google_cap - google_budget[0]
    print(f"\n{'=' * 60}")
    print(f"  LOGO FILL COMPLETE")
    print(f"  Real logos  : {stats['found']}")
    print(f"  Placeholders: {stats['placeholder']}")
    print(f"  Failed      : {stats['failed']}")
    print(f"  Skipped     : {stats['skipped']}")
    print(f"  Google API  : {google_used}/{args.google_cap} queries used")
    print(f"  Total time  : {_fmt_duration(total_elapsed)}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
