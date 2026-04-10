 # === services/ai_analysis.py ===
# Purpose: Analyze SEC IPO filings with GPT and upsert results

import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup
from supabase import Client
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class AnalyzeIPO:
    # Minimum seconds between OpenRouter API calls (free tier: ~20 RPM)
    _MIN_INTERVAL = 4.0

    def __init__(self, supabase_client: Client, openai_client: OpenAI):
        self.supabase = supabase_client
        self.openai = openai_client
        self.headers = {"User-Agent": "joeydaspam@gmail.com"}
        self._last_call_at: float = 0.0

    def _wait_for_rate_limit(self):
        """Block until at least _MIN_INTERVAL seconds have passed since the last call."""
        elapsed = time.monotonic() - self._last_call_at
        wait = self._MIN_INTERVAL - elapsed
        if wait > 0:
            print(f"[AI] Rate limiting: waiting {wait:.1f}s before next OpenRouter call...")
            time.sleep(wait)

    def null_if_unknown(self, val):
        return None if isinstance(val, str) and val.strip().lower() == "unknown" else val

    def null_if_unknown_numeric(self, val):
        if isinstance(val, str):
            if val.strip().lower() == "unknown":
                return None
            val = val.replace(",", "").replace("$", "").strip()
        try:
            return int(val)
        except ValueError:
            try:
                return float(val)
            except ValueError:
                return None

    def _is_placeholder(self, val):
        """Return True if the value is a known placeholder pattern."""
        if not isinstance(val, str):
            return False
        patterns = [
            r"^\[.*\]$",        # anything in brackets like [•], [__], []
            r"^XX$", r"^TBD$", r"^N/A$", r"^-$", r"^–$", r"^—$",  # dash variants
            r"^\s*$"            # empty/whitespace
        ]
        return any(re.match(p, val.strip(), flags=re.IGNORECASE) for p in patterns)

    def analyze_one(self, cik: str, filing_url: str, company_name: str):
        """Analyze a single filing and update the database."""
        try:
            # Fetch the filing text
            r = requests.get(filing_url, headers=self.headers)
            r.raise_for_status()
            try:
                soup = BeautifulSoup(r.text, "lxml")
            except Exception:
                soup = BeautifulSoup(r.text, "html.parser")

            for tag in soup(["script", "style", "head", "title", "meta", "[document]"]):
                tag.decompose()
            text = re.sub(r"\s+", " ", soup.get_text()).strip()
            snippet = " ".join(text.split()[:1000])

            # Build the GPT prompt
            prompt = (
                f"You extract IPO metadata from SEC filing text.\n\n"
                f"INPUT:\n{snippet}\nCOMPANY: {company_name}\n\n"
                "Operate in two phases: (A) reason privately; (B) OUTPUT JSON ONLY (no markdown, no notes).\n\n"
                "------------------------------------------------------------\n"
                "IPO CLASSIFICATION\n"
                "------------------------------------------------------------\n"
                "\"IPO\" = \"yes\" if:\n"
                "- Issuer is registering NEW securities for cash proceeds AND seeking FIRST-TIME listing on a national exchange (see normalized list below), including SPAC IPOs selling UNITS.\n\n"
                "\"IPO\" = \"no\" if ANY of these apply:\n"
                "- Pure resale/secondary (no primary proceeds to issuer)\n"
                "- General shelf (Rule 415) not tied to IPO\n"
                "- Business combination / de-SPAC (e.g., S-4/DEFM14A)\n"
                "- Exchange offer or follow-on offering\n"
                "- Rule 462(b) / S-1MEF / F-1MEF / RW\n"
                "- Warrant-only / rights-only / preferred-only sale\n"
                "- OTC-only listing (OTCQX / OTCQB / OTCBB / Over-the-Counter) without national exchange\n\n"
                "------------------------------------------------------------\n"
                "EXTRACTION RULES\n"
                "------------------------------------------------------------\n"
                "1) Shares Offered:\n"
                "- If UNITS are sold:\n"
                "  • Identify unit composition (e.g., “each unit consists of…”).\n"
                "  • If a unit includes ≥1 share or ADS, Shares Offered = number_of_units × shares_per_unit (ignore warrants/rights).\n"
                "  • If a unit includes NO share/ADS → IPO=\"no\".\n"
                "- If ADS are sold: count ADS (do NOT convert to underlying shares).\n"
                "- If common/ordinary/Class A shares are sold: use that share count.\n"
                "- Ignore over-allotment (greenshoe) and selling shareholder blocks.\n"
                "- Placeholders ([•], [*], [__], [], [ . ], XX, TBD, N/A, em/en dash, underscores) → \"unknown\".\n"
                "- Output digits only; no commas or text.\n\n"
                "2) share_price:\n"
                "- Use the price for the sold security (per UNIT if units; else per share/ADS).\n"
                "- Format exactly:\n"
                "  \"<number>$\"  OR  \"<number>$ - <number>$\"\n"
                "- No commas. If placeholder/ambiguous → \"unknown\".\n\n"
                "3) exchange (normalize to exactly one of):\n"
                "- \"NASDAQ\",\n"
                "  \"NYSE\",\"CBOE\"\n"
                "- Normalize examples:\n"
                "  • \"The Nasdaq Stock Market LLC\", \"NASDAQ Stock Exchange\" → \"NASDAQ\"\n"
                "  • \"Nasdaq CM\", \"Nasdaq Capital\" → \"NASDAQ\"\n"
                "  • \"Nasdaq Global\" → \"NASDAQ\"\n"
                "  • \"Nasdaq Global Select\" → \"NASDAQ\"\n"
                "  • \"New York Stock Exchange\", \"The NYSE\" → \"NYSE\"\n"
                "  • \"NYSE American LLC\" → \"NYSE\"\n"
                "  • \"NYSE Arca LLC\" → \"NYSE\"\n"
                "  • \"Cboe BZX/EDGX/EDGA Exchange, Inc.\" → \"CBOE\"\n"
                "- If OTC-only or unclear → \"unknown\".\n"
                "- Must not be a placeholder.\n\n"
                "4) market_cap:\n"
                "- This should be the raise amount, Compute ONLY if BOTH post-IPO total shares outstanding AND a price (or range) exist.\n"
                "- For price ranges, use midpoint. Multiply shares × price. Digits only; else \"unknown\".\n\n"
                "5) website:\n"
                "- Look for the company's official website URL in the filing text.\n"
                "- Common phrases: \"our website is located at\", \"our website address is\", \"visit us at\", \"available at www.\"\n"
                "- Output the full URL including https:// (e.g. \"https://www.example.com\").\n"
                "- Strip any trailing paths — homepage root only (e.g. \"https://stripe.com\" not \"https://stripe.com/about\").\n"
                "- If no website is mentioned → \"N/A\".\n\n"
                "------------------------------------------------------------\n"
                "HARD VALIDATION (apply before output)\n"
                "------------------------------------------------------------\n"
                "- Placeholders for Shares Offered, share_price, or exchange → \"unknown\".\n"
                "- \"Shares Offered\": ^[0-9]+$ or \"unknown\".\n"
                "- \"share_price\": ^[0-9]+(\\.[0-9]+)?\\$$  OR  ^[0-9]+(\\.[0-9]+)?\\$ - [0-9]+(\\.[0-9]+)?\\$$  OR \"unknown\".\n"
                "- \"market_cap\": ^[0-9]+$ or \"unknown\".\n"
                "- \"exchange\": must be in normalized list or \"unknown\".\n"
                "- \"website\": must start with http:// or https://, or be \"N/A\".\n"
                "- If per-unit and per-share prices both appear for a unit deal, prefer per-unit.\n"
                "- If only secondary shares are offered → IPO = \"no\".\n\n"
                "------------------------------------------------------------\n"
                "OUTPUT JSON ONLY:\n"
                "------------------------------------------------------------\n"
                "{{\n"
                "  \"IPO\": \"yes\" or \"no\",\n"
                "  \"Shares Offered\": \"...\",\n"
                "  \"share_price\": \"...\",\n"
                "  \"exchange\": \"...\",\n"
                "  \"market_cap\": \"...\",\n"
                "  \"website\": \"...\"\n"
                "}}\n"
            )


            # Call OpenRouter (rate-limited)
            from ..config import settings as _settings
            self._wait_for_rate_limit()
            self._last_call_at = time.monotonic()
            ai_resp = self.openai.chat.completions.create(
                model=_settings.OPENROUTER_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=1
            )
            content = ai_resp.choices[0].message.content.strip()
            if content.startswith("json"):
                content = content.removeprefix("json").removesuffix("")
            parsed = json.loads(content)

            # Sanitize placeholders
            for field in ["Shares Offered", "share_price", "exchange", "market_cap"]:
                if self._is_placeholder(parsed.get(field)):
                    parsed[field] = "unknown"

            # Parse website — treat "N/A" or non-http values as None
            raw_website = parsed.get("website", "N/A") or "N/A"
            website = (
                raw_website
                if isinstance(raw_website, str) and raw_website.startswith("http")
                else None
            )

            # Upsert results into DB & set analyzed=True
            update_data = {
                "is_ipo": parsed.get("IPO", "").lower() == "yes",
                "shares_offered": self.null_if_unknown_numeric(parsed.get("Shares Offered")),
                "share_price": self.null_if_unknown(parsed.get("share_price")),
                "exchange": self.null_if_unknown(parsed.get("exchange")),
                "market_cap": self.null_if_unknown_numeric(parsed.get("market_cap")),
                "analyzed": True,
            }
            if website:
                update_data["website_homepage"] = website

            self.supabase.table("ipo").update(update_data).eq("cik", cik).execute()

        except Exception as e:
            print(f"Analysis failed for {cik}: {e}")