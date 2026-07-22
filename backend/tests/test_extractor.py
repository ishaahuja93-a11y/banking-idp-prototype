import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from extractor import detect_document_type, extract_text_basic
from config import settings


# ── Type detection ────────────────────────────────────────────────────────────

def test_detects_invoice():
    assert detect_document_type(
        "INVOICE Invoice #INV-001 Total Amount INR 50000 GST 18%", "invoice.txt"
    ) == "invoice"

def test_detects_kyc():
    assert detect_document_type(
        "KYC Form Full Name John Smith Date of Birth PAN ABCDE1234F", "kyc.txt"
    ) == "kyc"

def test_detects_contract():
    assert detect_document_type(
        "SERVICE AGREEMENT governing law liability indemnity termination parties", "c.txt"
    ) == "contract"

def test_detects_bank_statement():
    assert detect_document_type(
        "Bank Statement Account Number Opening Balance Closing Balance Debit Credit", "s.txt"
    ) == "bank_statement"

def test_fallback_to_invoice():
    assert detect_document_type("random unrelated text", "file.txt") == "invoice"

def test_filename_hint_kyc():
    assert detect_document_type("name age address", "kyc_form.pdf") == "kyc"


# ── Text extraction ───────────────────────────────────────────────────────────

def test_extract_plain_text():
    from extractor import extract_text_basic
    result = extract_text_basic(b"Invoice total INR 1000", ".txt")
    assert "Invoice" in result
    assert "1000" in result


def test_extract_handles_bad_bytes():
    from extractor import extract_text_basic
    result = extract_text_basic(b"Invoice \xff\xfe total INR 2000", ".txt")
    assert "Invoice" in result


def test_extract_truncates_large_file():
    from extractor import extract_text_basic
    result = extract_text_basic(("x" * 20000).encode(), ".txt")
    assert len(result) <= 15001


# ── Storage ───────────────────────────────────────────────────────────────────

def test_local_store_save_and_retrieve():
    from storage import LocalStore
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        f.write("[]")
        path = f.name
    try:
        store = LocalStore(path)
        doc   = {"id": "test-001", "doc_type": "invoice", "filename": "test.txt"}
        store.save(doc)
        result = store.get("test-001")
        assert result is not None
        assert result["id"] == "test-001"
        assert result["doc_type"] == "invoice"
    finally:
        os.unlink(path)

def test_local_store_list_all():
    from storage import LocalStore
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        f.write("[]")
        path = f.name
    try:
        store = LocalStore(path)
        store.save({"id": "a", "doc_type": "invoice"})
        store.save({"id": "b", "doc_type": "kyc"})
        all_docs = store.list_all()
        assert len(all_docs) == 2
    finally:
        os.unlink(path)

def test_local_store_update():
    from storage import LocalStore
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        f.write("[]")
        path = f.name
    try:
        store = LocalStore(path)
        store.save({"id": "c", "status": "pending_review"})
        store.save({"id": "c", "status": "approved"})
        result = store.get("c")
        assert result["status"] == "approved"
        assert len(store.list_all()) == 1  # no duplicates
    finally:
        os.unlink(path)


# ── LLM extraction (skipped if no API key) ───────────────────────────────────

@pytest.mark.asyncio
async def test_llm_extract_invoice():
    if not settings.use_azure_openai and not settings.openai_api_key:
        pytest.skip("No LLM API key configured")

    from extractor import extract_fields_llm
    text   = "INVOICE INV-SMOKE-001 Date 01/07/2026 Total INR 29500 Vendor Test Corp"
    result = await extract_fields_llm(text, "invoice", [], [])
    assert isinstance(result, dict)
    assert "fields" in result
    assert "summary" in result


@pytest.mark.asyncio
async def test_llm_returns_dict_on_garbage():
    if not settings.use_azure_openai and not settings.openai_api_key:
        pytest.skip("No LLM API key configured")

    from extractor import extract_fields_llm
    result = await extract_fields_llm("xkcd @#$ 123 noise", "invoice", [], [])
    assert isinstance(result, dict)
    assert "fields" in result

@pytest.mark.asyncio
async def test_llm_extract_with_custom_keywords():
    if not settings.use_azure_openai and not settings.openai_api_key:
        pytest.skip("No LLM API key configured")

    from extractor import extract_fields_llm

    text = """
    INVOICE INV-2026-001
    Vendor: Test Corp Ltd, Mumbai
    SWIFT Code: TESTINBB123
    Bank: HDFC Bank
    Total Amount: INR 50000
    Due Date: 31 July 2026
    """

    # Just verify the function accepts custom_keywords without crashing
    # and returns the correct structure
    result = await extract_fields_llm(text, "invoice", [], ["SWIFT Code"])

    # These are the only guarantees we test in CI
    assert isinstance(result, dict), "Result must be a dict"
    assert "fields" in result, "Result must contain a fields key"
    assert isinstance(result["fields"], dict), "fields must be a dict"
    # summary may or may not be present depending on model response
    # but the call must not raise an exception


@pytest.mark.asyncio
async def test_custom_keywords_accepted_without_crash():
    """Verifies extract_fields_llm accepts custom_keywords parameter correctly."""
    if not settings.use_azure_openai and not settings.openai_api_key:
        pytest.skip("No LLM API key configured")

    from extractor import extract_fields_llm

    # Pass multiple custom keywords
    result = await extract_fields_llm(
        "Some banking document text",
        "invoice",
        [],
        ["SWIFT Code", "Vendor Tax ID", "ESG Rating"]
    )

    # Must return a dict and not crash
    assert isinstance(result, dict)
    assert "fields" in result
