from unittest.mock import MagicMock
import pytest

from ..pipeline.pipeline import Pipeline, _cap_ok, _is_acquisition_corp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_filing(**overrides) -> dict:
    """Return a complete, valid filing dict. Override any field per test."""
    base = {
        "cik": "1234567",
        "form_type": "S-1",
        "date_filed": "2026-01-15",
        "accession_number": "0001234567-26-000001",
        "company_name": "Acme Corp",
        "ticker": "ACME",
        "mainlink": "https://www.sec.gov/Archives/edgar/data/1234567/000123456726000001/acme-s1.htm",
        "is_ipo": True,
        "market_cap": 100_000_000,
        "primary_document": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pipeline() -> Pipeline:
    """
    Pipeline instance with all external dependencies replaced by mocks.
    Nothing here touches Supabase, Redis, SEC, or OpenAI.
    """
    p = Pipeline.__new__(Pipeline)

    p.db = MagicMock()
    p.cache = MagicMock()
    p.logo = MagicMock()
    p.ai = MagicMock()
    p.kv = MagicMock()
    p.fetcher = MagicMock()
    p.daily = MagicMock()
    p.skip_ai = False

    # Default state: nothing cached in Redis, nothing in the DB
    p.cache.seen_today.return_value = False
    p.db.get_ipo_snapshot.return_value = {}

    return p


# ---------------------------------------------------------------------------
# Pure-function unit tests  (no mocks needed)
# ---------------------------------------------------------------------------

class TestCapOk:
    def test_above_threshold_returns_true(self):
        assert _cap_ok(100_000_000) is True

    def test_none_returns_false(self):
        assert _cap_ok(None) is False


class TestIsAcquisitionCorp:
    def test_no_acquisition_returns_false(self):
        assert _is_acquisition_corp(None) is False

    def test_acquisition_returns_true(self):
        assert _is_acquisition_corp("acquisition") is True


# ---------------------------------------------------------------------------
# _process_filings — skip / guard branches
# ---------------------------------------------------------------------------

class TestMissingFields:
    def test_missing_cik_does_not_upsert(self, pipeline):
        filing = make_filing(cik=None)
        pipeline._process_filings([filing])
        pipeline.db.upsert_ipo.assert_not_called()

    def test_missing_form_type_does_not_upsert(self, pipeline):
        filing = make_filing(form_type=None)
        pipeline._process_filings([filing])
        pipeline.db.upsert_ipo.assert_not_called()

    def test_missing_date_does_not_upsert(self, pipeline):
        filing = make_filing(date_filed=None)
        pipeline._process_filings([filing])
        pipeline.db.upsert_ipo.assert_not_called()


class TestRedisCacheDedup:
    def test_seen_today_skips_upsert(self, pipeline):
        # Redis says this accession was already processed today
        pipeline.cache.seen_today.return_value = True
        filing = make_filing()
        pipeline._process_filings([filing])
        pipeline.db.upsert_ipo.assert_not_called()


class TestInitialFormAlreadyInDb:
    def test_s1_for_existing_cik_skips_upsert(self, pipeline):
        # CIK already exists in the ipo table
        pipeline.db.get_ipo_snapshot.return_value = {"1234567": {"cik": "1234567"}}
        filing = make_filing(form_type="S-1")
        pipeline._process_filings([filing])
        pipeline.db.upsert_ipo.assert_not_called()

    def test_f1_for_existing_cik_skips_upsert(self, pipeline):
        pipeline.db.get_ipo_snapshot.return_value = {"1234567": {"cik": "1234567"}}
        filing = make_filing(form_type="F-1")
        pipeline._process_filings([filing])
        pipeline.db.upsert_ipo.assert_not_called()


class TestNonInitialFormNewCik:
    def test_amendment_for_unknown_cik_skips_upsert(self, pipeline):
        # No existing record for this CIK, and form is an amendment not an initial filing
        pipeline.db.get_ipo_snapshot.return_value = {}
        filing = make_filing(form_type="S-1/A")
        pipeline._process_filings([filing])
        pipeline.db.upsert_ipo.assert_not_called()


class TestIpoPhraseFlagFalse:
    def test_s1_without_ipo_flag_skips_upsert(self, pipeline):
        # SEC filing didn't contain "initial public offering" phrase
        filing = make_filing(form_type="S-1", is_ipo=False)
        pipeline._process_filings([filing])
        pipeline.db.upsert_ipo.assert_not_called()


# ---------------------------------------------------------------------------
# _process_filings — action branches
# ---------------------------------------------------------------------------

class TestNewS1Upsert:
    def test_new_s1_with_ipo_flag_upserts(self, pipeline):
        # Clean slate: new CIK, valid S-1, IPO phrase detected
        filing = make_filing(form_type="S-1", is_ipo=True)
        pipeline._process_filings([filing])
        pipeline.db.upsert_ipo.assert_called_once()

    def test_upserted_record_has_correct_cik(self, pipeline):
        filing = make_filing(form_type="S-1", is_ipo=True, cik="9999999")
        pipeline._process_filings([filing])
        args, _ = pipeline.db.upsert_ipo.call_args
        assert args[0]["cik"] == "9999999"


class TestProspectusMovesToPublic:
    def test_424b4_deletes_from_ipo_and_moves_to_public(self, pipeline):
        # CIK exists in ipo table, prospectus filed — should move to public_companies
        pipeline.db.get_ipo_snapshot.return_value = {
            "1234567": {"cik": "1234567", "logo_url": None, "updated_logo_date": None}
        }
        filing = make_filing(form_type="424B4", is_ipo=True)
        pipeline._process_filings([filing])
        pipeline.db.delete_ipo.assert_called_once_with("1234567")
        pipeline.db.move_to_public.assert_called_once()

    def test_424b4_for_unknown_cik_does_not_move(self, pipeline):
        # Prospectus with no existing ipo record — nothing to move
        pipeline.db.get_ipo_snapshot.return_value = {}
        filing = make_filing(form_type="424B4", is_ipo=True)
        pipeline._process_filings([filing])
        pipeline.db.move_to_public.assert_not_called()


class TestWithdrawalDeletes:
    def test_rw_for_existing_cik_deletes(self, pipeline):
        pipeline.db.get_ipo_snapshot.return_value = {"1234567": {"cik": "1234567"}}
        filing = make_filing(form_type="RW", is_ipo=False)
        pipeline._process_filings([filing])
        pipeline.db.delete_ipo.assert_called_once_with("1234567")

    def test_rw_for_unknown_cik_does_not_delete(self, pipeline):
        # Withdrawal for a CIK we never tracked — nothing to delete
        pipeline.db.get_ipo_snapshot.return_value = {}
        filing = make_filing(form_type="RW", is_ipo=False)
        pipeline._process_filings([filing])
        pipeline.db.delete_ipo.assert_not_called()
