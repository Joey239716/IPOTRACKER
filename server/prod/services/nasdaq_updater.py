import re
import requests
from datetime import datetime
from typing import Optional, List, Dict
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://api.nasdaq.com/api/ipo/calendar"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nasdaq.com/market-activity/ipos",
    "Origin": "https://www.nasdaq.com",
}

def normalize_date(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    v = re.sub(r"\s+", " ", v.strip())
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", v):
        try:
            return datetime.strptime(v, "%m/%d/%Y").date().isoformat()
        except Exception as e:
            logger.warning(f"Failed to parse date '{v}': {e}")
            return v
    return v

def normalize_shares(v: Optional[str]) -> Optional[int]:
    if not v:
        return None
    v = v.replace(",", "").strip()
    return int(v) if v.isdigit() else None

def normalize_price(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    v = v.strip()
    # Check for TBD or unknown indicators
    if v.upper() in ["TBD", "N/A", "UNKNOWN", ""]:
        return None
    if "-" in v:
        parts = v.split("-")
        return " - ".join(f"{p.strip()}$" for p in parts)
    return f"{v}$"

def normalize_market_cap(v: Optional[str]) -> Optional[int]:
    if not v:
        return None
    v = re.sub(r"[,\$]", "", v.strip())
    return int(v) if v.isdigit() else None

def normalize_exchange(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    v = v.upper()
    if "NASDAQ" in v:
        return "NASDAQ"
    elif "NYSE" in v:
        return "NYSE"
    elif "CBOE" in v:
        return "CBOE"
    return v

def fetch_upcoming() -> List[Dict[str, Optional[str]]]:
    try:
        month = datetime.now().strftime("%Y-%m")
        logger.info(f"Fetching upcoming IPOs from Nasdaq API for {month}...")
        r = requests.get(BASE_URL, headers=HEADERS, params={"date": month}, timeout=30)
        r.raise_for_status()
        j = r.json()
        rows = j.get("data", {}).get("upcoming", {}).get("upcomingTable", {}).get("rows", [])

        if not rows:
            logger.warning("No upcoming IPO data found in Nasdaq API response")
            return []

        results: List[Dict[str, Optional[str]]] = []
        for row in rows:
            company = (row.get("companyName") or "").strip()
            if not company:
                continue
            results.append({
                "company_name": company,
                "ticker": row.get("proposedTickerSymbol"),
                "shares_offered": normalize_shares(row.get("sharesOffered")),
                "share_price": normalize_price(row.get("proposedSharePrice")),
                "market_cap": normalize_market_cap(row.get("dollarValueOfSharesOffered")),
                "exchange": normalize_exchange(row.get("proposedExchange")),
                "estimated_ipo_date": normalize_date(row.get("expectedPriceDate")),
            })

        logger.info(f"Successfully fetched {len(results)} upcoming IPOs from Nasdaq")
        return results

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch data from Nasdaq API: {e}")
        raise
    except (KeyError, ValueError) as e:
        logger.error(f"Failed to parse Nasdaq API response: {e}")
        raise

def apply_updates(normalized_data: List[Dict[str, Optional[str]]], apply: bool = True, supabase=None):
    """
    Apply updates from Nasdaq data to Supabase IPO table.

    Returns:
        dict: Statistics about the update operation
            - total_checked: number of IPOs checked
            - matched: number of companies found in database
            - updated: number of companies actually updated
            - errors: number of errors encountered
    """
    stats = {
        "total_checked": len(normalized_data),
        "matched": 0,
        "updated": 0,
        "errors": 0
    }

    logger.info(f"Processing {stats['total_checked']} IPOs from Nasdaq...")

    for ipo in normalized_data:
        company_name = ipo["company_name"]
        try:
            resp = supabase.table("ipo").select("*").eq("company_name", company_name).limit(1).execute()

            if resp.data:
                stats["matched"] += 1
                row = resp.data[0]
                diffs = {}

                for col in ["ticker", "shares_offered", "share_price", "market_cap", "exchange", "estimated_ipo_date"]:
                    old_val = row.get(col)
                    new_val = ipo.get(col)
                    if old_val != new_val:
                        diffs[col] = {"old": old_val, "new": new_val}

                if diffs:
                    if apply:
                        logger.info(f"Updating {company_name}: {diffs}")
                        supabase.table("ipo").update(ipo).eq("company_name", company_name).execute()
                        stats["updated"] += 1
                    else:
                        logger.info(f"[DRY RUN] Would update {company_name}: {diffs}")
                else:
                    logger.debug(f"No changes needed for {company_name}")
            else:
                logger.debug(f"Company not found in database: {company_name}")

        except Exception as e:
            logger.error(f"Error processing {company_name}: {e}")
            stats["errors"] += 1
            continue

    logger.info(f"Update complete - Checked: {stats['total_checked']}, Matched: {stats['matched']}, Updated: {stats['updated']}, Errors: {stats['errors']}")
    return stats
