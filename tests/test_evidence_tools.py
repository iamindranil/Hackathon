"""
Unit tests for Evidence Harvesting Tools
"""

from backend.tools.evidence_tools import EvidenceTools
from backend.models.dispute import EvidenceSourceType


def test_transaction_telemetry_harvesting():
    # Case A: ATM Skim
    ev = EvidenceTools.get_transaction_telemetry("TX-88201")
    assert ev is not None
    assert ev.source_type == EvidenceSourceType.CORE_BANKING_AUTH
    assert ev.data_payload["auth_method"] == "MAG_STRIPE_FALLBACK"
    assert ev.indicates_fraud is True
    print("[OK] Transaction telemetry harvesting (ATM skim) passed.")


def test_device_and_security_telemetry():
    # Case A: Impossible Travel
    sec_a = EvidenceTools.get_device_and_security_telemetry("TX-88201")
    assert sec_a is not None
    assert sec_a.data_payload["impossible_travel_flag"] is True
    assert "Impossible travel detected" in sec_a.relevance_summary

    # Case B: Legitimate FaceID Biometrics on home WiFi
    sec_b = EvidenceTools.get_device_and_security_telemetry("TX-90184")
    assert sec_b is not None
    assert sec_b.data_payload["known_customer_device"] is True
    assert sec_b.indicates_fraud is False  # Legitimate auth
    assert "FaceID" in sec_b.relevance_summary
    print("[OK] Device and security telemetry (Impossible Travel vs FaceID) passed.")


def test_merchant_fulfillment_telemetry():
    # Case C: Returned to Sender (Nordstrom)
    merch_c = EvidenceTools.lookup_merchant_fulfillment("TX-77312")
    assert merch_c is not None
    assert merch_c.data_payload["carrier_status"] == "RETURNED_TO_SENDER"
    assert "MERCHANT BILLING ERROR CONFIRMED" in merch_c.relevance_summary

    # Case B: Digital Goods Downloaded & Played
    merch_b = EvidenceTools.lookup_merchant_fulfillment("TX-90184")
    assert merch_b is not None
    assert merch_b.data_payload["digital_fulfillment"]["hours_played"] == 18.5
    print("[OK] Merchant fulfillment telemetry passed.")


def test_cardholder_profile_history():
    # High risk dispute history
    hist = EvidenceTools.get_cardholder_dispute_history("CUST-3819")
    assert hist is not None
    assert hist.data_payload["friendly_fraud_risk"] == "HIGH"
    assert hist.data_payload["prior_disputes_last_24m"] == 4
    print("[OK] Cardholder dispute history test passed.")


if __name__ == "__main__":
    test_transaction_telemetry_harvesting()
    test_device_and_security_telemetry()
    test_merchant_fulfillment_telemetry()
    test_cardholder_profile_history()
    print("\nALL EVIDENCE TOOL TESTS PASSED SUCCESSFULLY!")
