"""
Agent 1: Multimodal Intake & Regime Router
Powered by Gemini LLM with deterministic fallback.
Parses incoming dispute claims from text, chat transcripts, or scanned attachments.
Extracts transaction details, determines dispute category, and routes to the correct
regulatory regime (US Reg E, US Reg Z, or EU PSR).
"""

from datetime import datetime
import json
import re
from typing import Optional, Dict, Any
from backend.models.dispute import (
    DisputeClaim,
    DisputeCategory,
    RegulatoryRegime,
    DisputedTransaction,
    ChannelType,
)
from backend.tools.enterprise_data import MOCK_TRANSACTIONS_DB
from backend.engine.gemini_client import GeminiClient


class IntakeAgent:
    """
    Intake & Regulatory Regime Routing Agent.
    Combines Gemini Multimodal / Text extraction with fallback heuristics.
    """

    @classmethod
    def process_claim(
        cls,
        claim_id: str,
        cardholder_id: str,
        raw_text: str,
        channel: ChannelType = ChannelType.MOBILE_APP_CHAT,
        known_transaction_id: Optional[str] = None,
        attachment_paths: Optional[list] = None,
    ) -> DisputeClaim:
        attachment_paths = attachment_paths or []
        
        # 1. Identify transaction ID
        txn_id = known_transaction_id
        if not txn_id:
            match = re.search(r"TX-\d{5}", raw_text, re.IGNORECASE)
            if match:
                txn_id = match.group(0).upper()
            else:
                txn_id = "TX-88201"

        txn_record = MOCK_TRANSACTIONS_DB.get(txn_id, {
            "transaction_id": txn_id,
            "cardholder_id": cardholder_id,
            "cardholder_name": "Customer",
            "cardholder_email": "customer@example.com",
            "amount": 100.00,
            "currency": "USD",
            "merchant_name": "Unknown Merchant",
            "merchant_raw_descriptor": "POS TRANSACTION",
            "transaction_date": datetime.utcnow().isoformat(),
            "account_id": "CHK-000000",
            "card_last_four": "0000",
            "account_type": "CHECKING",
            "is_new_account": False,
            "is_foreign_or_pos": False,
        })

        category = None
        inferred_regime = None

        # 2. Try Gemini LLM for cognitive parsing & classification
        if GeminiClient.is_ai_live():
            prompt = f"""
You are the Intake Agent of an automated card and payment dispute system.
Analyze the following customer dispute claim:
Claim Text: "{raw_text}"
Transaction ID: {txn_id}
Account Type: {txn_record.get('account_type')}
Currency: {txn_record.get('currency')}

Respond ONLY with valid JSON having this exact schema:
{{
  "category": "UNAUTHORIZED_TRANSACTION" | "BILLING_ERROR" | "GOODS_SERVICES_NOT_RECEIVED" | "IMPERSONATION_APP_SCAM" | "DUPLICATE_PROCESSING",
  "reasoning": "Short 1-sentence reasoning"
}}
"""
            llm_response = GeminiClient.generate_content(
                prompt=prompt,
                system_instruction="You are an expert bank compliance intake agent classifying dispute claims.",
                temperature=0.1
            )
            if llm_response:
                try:
                    # Strip markdown code fences if any
                    clean_json = re.sub(r"^```json\s*|\s*```$", "", llm_response.strip(), flags=re.MULTILINE)
                    parsed = json.loads(clean_json)
                    category_str = parsed.get("category")
                    if category_str in DisputeCategory.__members__:
                        category = DisputeCategory(category_str)
                except Exception as e:
                    print(f"Failed to parse Gemini intake response: {e}")

        # 3. Fallback Heuristics if Gemini offline or unparsed
        if not category:
            text_lower = raw_text.lower()
            if "atm" in text_lower or "stolen" in text_lower or "didn't make" in text_lower or "fraud" in text_lower:
                if "spoof" in text_lower or "bank caller" in text_lower or "safe account" in text_lower or "fake security" in text_lower:
                    category = DisputeCategory.IMPERSONATION_APP_SCAM
                else:
                    category = DisputeCategory.UNAUTHORIZED_TRANSACTION
            elif "damaged" in text_lower or "returned" in text_lower or "never received" in text_lower or "never got" in text_lower:
                category = DisputeCategory.GOODS_SERVICES_NOT_RECEIVED
            elif "charged twice" in text_lower or "duplicate" in text_lower:
                category = DisputeCategory.DUPLICATE_PROCESSING
            elif "billing" in text_lower or "refund" in text_lower or "receipt" in text_lower:
                category = DisputeCategory.BILLING_ERROR
            else:
                category = DisputeCategory.UNAUTHORIZED_TRANSACTION

        # Determine Regulatory Regime based on statutory definitions
        account_type = txn_record.get("account_type", "CHECKING")
        currency = txn_record.get("currency", "USD")

        if currency == "EUR" or "IBAN" in str(txn_record.get("account_id", "")):
            regime = RegulatoryRegime.EU_PSR_PSD2
        elif account_type == "CREDIT_CARD" or "CC-" in str(txn_record.get("account_id", "")):
            regime = RegulatoryRegime.REG_Z_CREDIT
        else:
            regime = RegulatoryRegime.REG_E_DEBIT

        transaction = DisputedTransaction(
            transaction_id=txn_id,
            amount=txn_record["amount"],
            currency=txn_record.get("currency", "USD"),
            merchant_name=txn_record["merchant_name"],
            merchant_raw_descriptor=txn_record["merchant_raw_descriptor"],
            transaction_date=datetime.fromisoformat(txn_record["transaction_date"].replace("Z", "+00:00")),
            account_id=txn_record["account_id"],
            card_last_four=txn_record["card_last_four"],
            account_type=account_type,
            is_new_account=txn_record.get("is_new_account", False),
            is_foreign_or_pos=txn_record.get("is_foreign_or_pos", False),
        )

        return DisputeClaim(
            claim_id=claim_id,
            cardholder_id=txn_record.get("cardholder_id", cardholder_id),
            cardholder_name=txn_record.get("cardholder_name", "Cardholder"),
            cardholder_email=txn_record.get("cardholder_email", "cardholder@example.com"),
            channel=channel,
            raw_claim_text=raw_text,
            attachment_paths=attachment_paths,
            intake_timestamp=datetime.utcnow(),
            transactions=[transaction],
            claimed_category=category,
            cardholder_stated_reason=raw_text,
        )
