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
    "tender": {
    "description": "Government tender notice or NIT (Notice Inviting Tender)",
    "fields": [
        "tender_reference_number",
        "issuing_authority",
        "work_description",
        "estimated_cost",
        "earnest_money",
        "bid_document_cost",
        "completion_period",
        "last_submission_date",
        "submission_time",
        "bid_opening_date",
        "bid_opening_location",
        "contact_email",
        "project_location",
    ],
    "azure_model": "prebuilt-document",
},
}

SYSTEM_PROMPT = """You are an expert financial document analyst at a bank.
Extract structured data from the document text provided.

STRICT RULES:
1. Return ONLY valid JSON. No markdown. No trailing commas. Start with { end with }.
2. Every field must have: "value" (string or null), "confidence" (0.0-1.0), "status".
3. Status: "auto_accept" (>=0.85), "review_amber" (0.60-0.84), "review_red" (<0.60).
4. If a field is absent: value=null, confidence=0.0, status="review_red".
5. If ambiguous: confidence<0.60, add "ambiguity_reason".
6. Add top-level "summary": 2-sentence plain English document description.
7. IMPORTANT: Look carefully inside tables - values in table cells are critical.
8. IMPORTANT: Numbers written as "Rs. X Lacs" mean X * 100000 Indian Rupees.
9. IMPORTANT: Look for values in ALL columns of every table row.
10. The document may contain Hindi text - extract English values where present.

Output format:
{
  "summary": "...",
  "fields": {
    "field_name": {"value": "...", "confidence": 0.95, "status": "auto_accept"}
  }
}"""


def get_llm_client():
    """Returns (async_client, model_name) based on what is configured."""
    if settings.use_azure_openai:
        client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_key,
            api_version="2025-03-01-preview",
        )
        return client, settings.azure_openai_deployment
    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
    return client, settings.openai_model

async def call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    Calls whichever LLM is configured.
    Handles both old Chat Completions API (gpt-4.1-mini)
    and new Responses API (gpt-5-mini) automatically.
    """
    client, model = get_llm_client()

    # Try new Responses API first (gpt-5-mini)
    try:
        resp = await client.responses.create(
            model=model,
            instructions=system_prompt,
            input=user_prompt,
            max_output_tokens=2000,
        )
        return resp.output_text

    except Exception as responses_error:
        error_str = str(responses_error)

        # If Responses API not supported, fall back to Chat Completions API
        if "responses" in error_str.lower() or "not found" in error_str.lower() or "404" in error_str:
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    max_tokens=2000,
                )
                return resp.choices[0].message.content
            except Exception as chat_error:
                raise Exception(f"Both APIs failed. Responses: {responses_error}. Chat: {chat_error}")
        else:
            raise responses_error


def detect_document_type(text: str, filename: str) -> str:
    combined = (text + " " + filename).lower()
    scores = {
        "invoice": sum(1 for kw in [
            "invoice", "bill", "total amount", "due date", "subtotal", "vendor", "tax", "gst", "vat",
        ] if kw in combined),
        "kyc": sum(1 for kw in [
            "kyc", "know your customer", "date of birth", "passport", "pan", "aadhaar", "nationality",
        ] if kw in combined),
        "contract": sum(1 for kw in [
            "agreement", "contract", "governing law", "liability", "indemnity", "termination", "parties",
        ] if kw in combined),
        "bank_statement": sum(1 for kw in [
            "statement", "account number", "balance", "debit", "credit", "opening balance",
        ] if kw in combined),
        "regulatory_filing": sum(1 for kw in [
            "filing", "regulator", "rbi", "sebi", "compliance", "regulatory",
        ] if kw in combined),

        # NEW: Tender documents
        "tender": sum(1 for kw in [
            "tender", "nit", "e-tender", "notice inviting tender",
            "earnest money", "bid document", "estimated cost",
            "turn-key", "technical bid", "financial bid",
            "jal nigam", "nagar palika", "municipal",
        ] if kw in combined),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "invoice"

def extract_text_basic(self, content: bytes, suffix: str) -> str:
    """
    Extract text from document.
    For image-based PDFs: uses OCR via pdf2image + pytesseract.
    For text-based PDFs: uses pypdf.
    For text files: direct decode.
    """
    if suffix in [".txt", ".md", ".csv"]:
        return content.decode("utf-8", errors="replace")[:15000]

    if suffix == ".pdf":
        # First try pypdf for text-based PDFs
        try:
            from pypdf import PdfReader
            import io
            reader   = PdfReader(io.BytesIO(content))
            pages    = [p.extract_text() or "" for p in reader.pages]
            combined = "\n".join(pages).strip()

            # If pypdf got meaningful text (>100 chars), use it
            if len(combined) > 100:
                return combined[:15000]

            # Otherwise it is an image-based PDF — fall through to OCR
            print("PDF appears image-based, attempting OCR...")
        except Exception as e:
            print(f"pypdf error: {e}")

        # OCR fallback for image-based PDFs
        try:
            from pdf2image import convert_from_bytes
            import pytesseract
            from PIL import Image

            # Convert PDF pages to images
            images = convert_from_bytes(content, dpi=300)
            ocr_text = ""
            for i, image in enumerate(images):
                # Use English + Hindi OCR
                text = pytesseract.image_to_string(
                    image,
                    lang="eng+hin",    # eng for English, hin for Hindi
                    config="--psm 6"   # Assume uniform block of text
                )
                ocr_text += f"\n--- Page {i+1} ---\n{text}"
                if len(ocr_text) > 15000:
                    break

            if ocr_text.strip():
                print(f"OCR extracted {len(ocr_text)} characters")
                return ocr_text[:15000]

        except Exception as e:
            print(f"OCR error: {e}")
            return f"[OCR failed: {e}. Install tesseract and pdf2image for image PDF support]"

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
    schema  = DOCUMENT_SCHEMAS.get(doc_type, DOCUMENT_SCHEMAS["invoice"])
    fields  = schema["fields"]
    missing = [f for f in fields if f not in already_found]
    if not missing:
        missing = fields[:4]

    fields_to_find = missing + custom_keywords

    system_prompt = (
        SYSTEM_PROMPT +
        "\n\nCRITICAL: Return ONLY valid JSON. "
        "No trailing commas. No comments. No markdown. "
        "Every string must be in double quotes. "
        "Start your response with { and end with }. "
        "Do not truncate the JSON."
    )

    user_prompt = (
        f"Document type: {doc_type} - {schema['description']}\n"
        f"Fields to extract: {', '.join(fields_to_find)}\n\n"
        f"Document text:\n{text[:9000]}\n\n"
        f"Return ONLY valid complete JSON. No trailing commas."
    )

    client, model = get_llm_client()

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=3000,  # Increased from 2000
        )

        raw = resp.choices[0].message.content.strip()

        # Step 1: Remove markdown code fences
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break

        raw = raw.strip()

        # Step 2: Find the outermost JSON object
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end+1]

        # Step 3: Fix trailing commas before } or ]
        import re
        raw = re.sub(r',\s*}', '}', raw)
        raw = re.sub(r',\s*]', ']', raw)

        # Step 4: Try to parse
        return json.loads(raw)

    except json.JSONDecodeError as e:
        # Step 5: If still failing, try to extract partial data
        print(f"JSON parse error: {e}")
        print(f"Raw response: {raw[:500]}")
        return {
            "summary": f"Partial extraction - JSON formatting issue in model response.",
            "fields": {}
        }
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
    fields_str = json.dumps(
        {k: v.get("value") for k, v in fields.items() if isinstance(v, dict)},
        indent=2,
    )

    system_prompt = (
        "You are a document analyst for a bank. "
        "Answer questions using only the document content provided. "
        "Be concise - maximum 3 sentences. "
        "If the answer is not in the document, say so explicitly."
    )

    user_prompt = (
        f"Document type: {doc_type}\n\n"
        f"Extracted fields:\n{fields_str}\n\n"
        f"Raw text:\n{raw_text[:3000]}\n\n"
        f"Question: {question}"
    )

    try:
        return await call_llm(system_prompt, user_prompt)
    except Exception as e:
        return f"Agent error: {e}"
