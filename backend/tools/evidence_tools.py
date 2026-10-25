"""
Evidence Harvesting Tools
Standardized tools called by the Evidence Agent to retrieve transaction telemetry,
device and IP security logs, merchant descriptor data, and customer dispute history.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from backend.models.dispute import EvidenceItem, EvidenceSourceType
from backend.tools.enterprise_data import (
    MOCK_TRANSACTIONS_DB,
    MOCK_SECURITY_TELEMETRY,
    MOCK_MERCHANT_FULFILLMENT,
    MOCK_CUSTOMER_PROFILES,
)


class EvidenceTools:
    """
    Evidence tool suite for the Card & Payment Dispute Investigation Agent.
    """

    @classmethod
    def get_transaction_telemetry(cls, transaction_id: str) -> Optional[EvidenceItem]:
        """
        Retrieves core banking transaction details including authentication method,
        POS entry mode, 3DS version, and terminal location.
        """
        txn = MOCK_TRANSACTIONS_DB.get(transaction_id)
        if not txn:
            return None

        is_suspicious_auth = txn.get("auth_method") == "MAG_STRIPE_FALLBACK" or not txn.get("pin_verified", True)

        summary = (
            f"Transaction #{transaction_id} on card ending in {txn['card_last_four']} for ${txn['amount']:.2f}. "
            f"Auth Method: {txn['auth_method']} (POS Entry: {txn['pos_entry_mode']}). "
            f"Terminal: {txn['terminal_location']}."
        )

        return EvidenceItem(
            evidence_id=f"EV-TXN-{transaction_id}",
            source_type=EvidenceSourceType.CORE_BANKING_AUTH,
            title="Core Banking Transaction & Auth Telemetry",
            timestamp=datetime.fromisoformat(txn["transaction_date"].replace("Z", "+00:00")),
            relevance_summary=summary,
            data_payload=txn,
            indicates_fraud=is_suspicious_auth,
            confidence_score=0.99,
        )

    @classmethod
    def get_device_and_security_telemetry(cls, transaction_id: str) -> Optional[EvidenceItem]:
        """
        Retrieves device fingerprint, IP geolocation vs. cardholder home address,
        and biometric FIDO attestation records.
        """
        sec = MOCK_SECURITY_TELEMETRY.get(transaction_id)
        if not sec:
            return None

        impossible_travel = sec.get("impossible_travel_flag", False)
        known_device = sec.get("known_customer_device", False)
        has_biometrics = bool(sec.get("biometric_auth_record"))
        telecom_spoofed = sec.get("telecom_spoofing_flag", False)

        if impossible_travel:
            summary = (
                f"CRITICAL FRAUD SIGNAL: Impossible travel detected. Terminal in {sec.get('ip_geolocation')} "
                f"while customer mobile session active in {sec.get('concurrent_mobile_session', {}).get('ip_location')} "
                f"1 minute apart."
            )
            indicates_fraud = True
        elif telecom_spoofed:
            summary = (
                f"IMPERSONATION SCAM DETECTED: Telecom spoofing log confirms incoming call with spoofed "
                f"bank caller ID ({sec['incoming_call_log']['caller_id']}) using social engineering scripts."
            )
            indicates_fraud = True
        elif has_biometrics and known_device:
            bio = sec["biometric_auth_record"]
            summary = (
                f"LEGITIMATE CARDHOLDER AUTH: Transaction verified via {bio['biometric_type']} "
                f"(FIDO verified) on registered customer device ({sec['device_model']}) "
                f"from cardholder's home IP network in {sec['ip_geolocation']}."
            )
            indicates_fraud = False  # Indicates transaction was NOT fraudulent (friendly fraud indicator)
        else:
            summary = f"Security telemetry retrieved for transaction #{transaction_id}."
            indicates_fraud = None

        return EvidenceItem(
            evidence_id=f"EV-SEC-{transaction_id}",
            source_type=EvidenceSourceType.DEVICE_AND_IP,
            title="Device, IP & Biometric Security Telemetry",
            timestamp=datetime.utcnow(),
            relevance_summary=summary,
            data_payload=sec,
            indicates_fraud=indicates_fraud,
            confidence_score=0.98,
        )

    @classmethod
    def lookup_merchant_fulfillment(cls, transaction_id: str) -> Optional[EvidenceItem]:
        """
        Retrieves resolved merchant entity, shipping carrier tracking scans,
        or digital download and consumption records.
        """
        merch = MOCK_MERCHANT_FULFILLMENT.get(transaction_id)
        if not merch:
            return None

        carrier_status = merch.get("carrier_status")
        digital = merch.get("digital_fulfillment")

        if carrier_status == "RETURNED_TO_SENDER":
            summary = (
                f"MERCHANT BILLING ERROR CONFIRMED: Carrier {merch['carrier']} tracking #{merch['tracking_number']} "
                f"confirms package was damaged in transit and returned to merchant on {merch['carrier_scan_history'][-1]['date']}. "
                f"Merchant failed to issue refund."
            )
            indicates_fraud = False  # Merchant billing dispute, not fraud
        elif digital and digital.get("delivered"):
            summary = (
                f"DIGITAL FULFILLMENT PROOF: Digital goods activated on cardholder's registered console "
                f"(Serial #{digital['activated_on_console_serial']}). {digital['hours_played']} hours played "
                f"under cardholder account ({digital['account_owner']})."
            )
            indicates_fraud = False
        elif merch.get("destination_bank_reported_mule"):
            summary = (
                f"FRAUD DESTINATION IDENTIFIED: Destination account reported as flagged money mule account "
                f"at intermediary financial institution."
            )
            indicates_fraud = True
        else:
            summary = f"Merchant fulfillment data verified for #{transaction_id} ({merch.get('merchant_name')})."
            indicates_fraud = None

        return EvidenceItem(
            evidence_id=f"EV-MERCH-{transaction_id}",
            source_type=EvidenceSourceType.CARRIER_DELIVERY if carrier_status else EvidenceSourceType.MERCHANT_DESCRIPTOR,
            title="Merchant Descriptor & Fulfillment Verification",
            timestamp=datetime.utcnow(),
            relevance_summary=summary,
            data_payload=merch,
            indicates_fraud=indicates_fraud,
            confidence_score=0.95,
        )

    @classmethod
    def get_cardholder_dispute_history(cls, cardholder_id: str) -> Optional[EvidenceItem]:
        """
        Retrieves customer dispute frequency, account tenure, credit profile,
        and first-party fraud risk rating.
        """
        profile = MOCK_CUSTOMER_PROFILES.get(cardholder_id)
        if not profile:
            return None

        prior_disputes = profile.get("prior_disputes_last_24m", 0)
        risk = profile.get("friendly_fraud_risk", "LOW")

        summary = (
            f"Cardholder Profile: {profile['customer_name']} (Tenure: {profile['account_vintage_months']} months). "
            f"Prior disputes in 24 months: {prior_disputes}. Friendly Fraud Risk Rating: {risk}."
        )

        return EvidenceItem(
            evidence_id=f"EV-HIST-{cardholder_id}",
            source_type=EvidenceSourceType.DISPUTE_HISTORY,
            title="Cardholder Dispute Profile & Risk History",
            timestamp=datetime.utcnow(),
            relevance_summary=summary,
            data_payload=profile,
            indicates_fraud=True if risk == "HIGH" else False,
            confidence_score=0.90,
        )
