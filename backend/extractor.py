"""
Two-stage extraction pipeline:
  Stage 1 — Azure Document Intelligence (OCR + pre-built field extraction)
  Stage 2 — Azure OpenAI / OpenAI / Groq  (NER, gap-fill, summarize, chat)
"""
import json
from openai import AsyncOpenAI, AsyncAzureOpenAI
from config import settings


DOCUMENT_SCHEMAS = {
    "invoice": {
        "description": "Financial invoice or bill",
        "fields": [
            "vendor_name", "vendor_address", "invoice_number", "invoice_date",
            "due_date", "subtotal", "tax_amount", "total_amount", "currency",
            "payment_terms", "po_number", "bank_details",
        ],
        "azure_model": "prebuilt-invoice",
    },
    "kyc": {
        "description": "KYC / identity verification form",
        "fields": [
            "full_name", "date_of_birth", "gender", "nationality",
            "id_type", "id_number", "id_expiry", "address",
            "phone", "email", "occupation", "annual_income", "risk_category",
        ],
        "azure_model": "prebuilt-idDocument",
    },
    "contract": {
        "description": "Legal contract or agreement",
        "fields": [
            "contract_title", "party_one", "party_two", "effective_date",
            "expiry_date", "governing_law", "payment_terms", "liability_cap",
            "indemnity_clause", "termination_clause", "key_obligations",
        ],
        "azure_model": "prebuilt-layout",
    },
    "bank_statement": {
        "description": "Bank account statement",
        "fields": [
            "account_holder", "account_number", "bank_name", "statement_period",
            "opening_balance", "closing_balance", "total_credits",
            "total_debits", "currency", "transaction_count",
        ],
        "azure_model": "prebuilt-document",
    },
    "regulatory_filing": {
        "description": "Regulatory or compliance filing",
        "fields": [
            "filing_type", "filing_date", "entity_name", "regulator",
            "reference_number", "period_covered", "signatory", "status",
        ],
        "azure_model": "prebuilt-document",
    },
}

SYSTEM_PROMPT = """You are an expert financial document analyst at a bank.
Extract structured data from the document text provided.

STRICT RULES:
1. Return ONLY valid JSON. No markdown fences. No text outside the JSON.
2. Every field must have: "value" (string or null), "confidence" (0.0-1.0), "status".
3. Status values: "auto_accept" if confidence>=0.85, "review_amber" if 0.60-0.84, "review_red" if below 0.60.
4. If a field is not present in the document: value=null, confidence=0.0, status="review_red".
5. If a value is ambiguous or unclear: confidence below 0.60 and add "ambiguity_reason" key.
6. Add top-level key "summary": 2 sentences describing the document in plain English.

Required JSON output format:
{
  "summary": "This is an invoice from...",
  "fields": {
    "vendor_name": {"value": "ABC Corp", "confidence": 0.97, "status": "auto_accept"},
    "due_date":    {"value": null, "confidence": 0.0, "status": "review_red"}
  }
}"""


def get_llm_client():
    """Returns (async_client, model_name) based on what is configured."""
    if settings.use_azure_openai:
        client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_key,
            api_version="2024-12-01-preview",
        )
        return client, settings.azure_openai_deployment
    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
    return client, settings.openai_model


def detect_document_type(text: str, filename: str) -> str:
    combined = (text + " " + filename).lower()
    scores = {
        "invoice": sum(1 for kw in [
            "invoice", "bill", "total amount", "due date",
            "subtotal", "vendor", "tax", "gst", "vat",
        ] if kw in combined),
        "kyc": sum(1 for kw in [
            "kyc", "know your customer", "date of birth",
            "passport", "pan", "aadhaar", "aadhar", "nationality",
        ] if kw in combined),
        "contract": sum(1 for kw in [
            "agreement", "contract", "governing law",
            "liability", "indemnity", "termination", "parties",
        ] if kw in combined),
        "bank_statement": sum(1 for kw in [
            "statement", "account number", "balance",
            "debit", "credit", "opening balance",
        ] if kw in combined),
        "regulatory_filing": sum(1 for kw in [
            "filing", "regulator", "rbi", "sebi",
            "compliance", "regulatory",
        ] if kw in combined),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "invoice"


def extract_text_basic(content: bytes, suffix: str) -> str:
    """Plain text extraction — used for .txt files and as fallback."""
    if suffix in [".txt", ".md", ".csv"]:
        return content.decode("utf-8", errors="replace")[:15000]
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(p.extract_text() or "" for p in reader.pages)[:15000]
        except Exception as e:
            return f"[PDF error: {e}]"
    try:
        return content.decode("utf-8", errors="replace")[:15000]
    except Exception:
        return "[Could not extract text]"


def extract_with_azure_doc_intel(content: bytes, doc_type: str):
    """
    Stage 1: Azure Document Intelligence.
    Returns (raw_text: str, azure_fields: dict).
    """
    from azure.ai.formrecognizer import DocumentAnalysisClient
    from azure.core.credentials import AzureKeyCredential
    import io

    schema   = DOCUMENT_SCHEMAS.get(doc_type, DOCUMENT_SCHEMAS["invoice"])
    model_id = schema["azure_model"]

    client = DocumentAnalysisClient(
        endpoint=settings.azure_doc_intel_endpoint,
        credential=AzureKeyCredential(settings.azure_doc_intel_key),
    )
    poller = client.begin_analyze_document(model_id, document=io.BytesIO(content))
    result = poller.result()

    # Raw text from all pages
    raw_text = "\n".join(
        line.content
        for page in result.pages
        for line in page.lines
    )

    # Structured fields from pre-built model
    azure_fields = {}
    if result.documents:
        for doc in result.documents:
            for fname, field in doc.fields.items():
                c = field.confidence if field.confidence is not None else 0.0
                azure_fields[fname.lower()] = {
                    "value": str(field.value) if field.value else field.content,
                    "confidence": round(c, 3),
                    "status": (
                        "auto_accept"  if c >= 0.85 else
                        "review_amber" if c >= 0.60 else
                        "review_red"
                    ),
                    "source": "azure_document_intelligence",
                }
    return raw_text, azure_fields


async def extract_fields_llm(text: str, doc_type: str, already_found: list, custom_keywords: list) -> dict:
    """
    Stage 2: LLM fills gaps not found by Document Intelligence, summarizes, NER.
    """
    schema  = DOCUMENT_SCHEMAS.get(doc_type, DOCUMENT_SCHEMAS["invoice"])
    fields  = schema["fields"]
    missing = [f for f in fields if f not in already_found]
    if not missing:
        missing = fields[:4]  # always get summary + spot-check

    fields_to_find = missing + custom_keywords
    client, model = get_llm_client()

    try:
        resp = await client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"Document type: {doc_type} — {schema['description']}\n"
                    f"Fields to extract: {', '.join(fields_to_find)}\n\n"
                    f"Document text:\n{text[:9000]}"
                )},
            ],
            temperature=0.05,
            max_tokens=2000,
        )
        return json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError:
        return {"summary": "LLM returned invalid JSON.", "fields": {}}
    except Exception as e:
        return {"summary": f"LLM error: {e}", "fields": {}}


async def extract_document(content: bytes, suffix: str, doc_type: str, custom_keywords: list = None) -> dict:
    """
    Full two-stage pipeline.
    Returns dict with: summary, fields, raw_text, llm_used.
    """
    if custom_keywords is None:
        custom_keywords = []

    azure_fields = {}
    raw_text     = ""

    # Stage 1 — Azure Document Intelligence (PDFs and images)
    if settings.use_doc_intel and suffix in [".pdf", ".png", ".jpg", ".jpeg", ".tiff"]:
        try:
            raw_text, azure_fields = extract_with_azure_doc_intel(content, doc_type)
        except Exception as e:
            print(f"Doc Intelligence warning: {e}")
            raw_text = extract_text_basic(content, suffix)
    else:
        raw_text = extract_text_basic(content, suffix)

    # Stage 2 — LLM enrichment
    llm_result = await extract_fields_llm(raw_text, doc_type, list(azure_fields.keys()), custom_keywords)

    # Merge: Azure fields override LLM on same keys (Azure has higher accuracy)
    merged = {**llm_result.get("fields", {}), **azure_fields}

    return {
        "summary":  llm_result.get("summary", ""),
        "fields":   merged,
        "raw_text": raw_text[:600],
        "llm_used": settings.llm_label,
    }


async def chat_about_document(raw_text: str, fields: dict,
                               doc_type: str, question: str) -> str:
    """Agent: answer natural language questions about a document."""
    fields_str = json.dumps(
        {k: v.get("value") for k, v in fields.items() if isinstance(v, dict)},
        indent=2,
    )
    client, model = get_llm_client()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "You are a document analyst for a bank. "
                    "Answer questions using only the document content provided. "
                    "Be concise — maximum 3 sentences. "
                    "If the answer is not in the document, say so clearly."
                )},
                {"role": "user", "content": (
                    f"Document type: {doc_type}\n\n"
                    f"Extracted fields:\n{fields_str}\n\n"
                    f"Raw text:\n{raw_text[:3000]}\n\n"
                    f"Question: {question}"
                )},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"Agent error: {e}"
