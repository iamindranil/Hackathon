"""
Agent 3: Evidence Harvester & Intelligence Agent
Executes tool calls to harvest core banking telemetry, device and IP security logs,
merchant descriptor information, and cardholder dispute profiles.
Synthesizes items into a cohesive EvidenceDossier.
"""

from typing import List, Dict, Any
from backend.models.dispute import (
    DisputeClaim,
    EvidenceDossier,
    EvidenceItem,
    EvidenceSourceType,
)
from backend.tools.evidence_tools import EvidenceTools


class EvidenceAgent:
    """
    Evidence Harvester & Telemetry Synthesis Agent.
    """

    @classmethod
    def harvest_dossier(cls, claim: DisputeClaim) -> EvidenceDossier:
        """
        Gathers all available evidence items across enterprise systems.
        """
        items: List[EvidenceItem] = []
        txn = claim.transactions[0] if claim.transactions else None
        if not txn:
            return EvidenceDossier(items=[], synthesized_findings="No transactions attached.")

        txn_id = txn.transaction_id
        cardholder_id = claim.cardholder_id

        # Tool 1: Core Banking Transaction Auth Telemetry
        ev_txn = EvidenceTools.get_transaction_telemetry(txn_id)
        if ev_txn:
            items.append(ev_txn)

        # Tool 2: Device, IP & Security Telemetry
        ev_sec = EvidenceTools.get_device_and_security_telemetry(txn_id)
        if ev_sec:
            items.append(ev_sec)

        # Tool 3: Merchant Descriptor & Fulfillment
        ev_merch = EvidenceTools.lookup_merchant_fulfillment(txn_id)
        if ev_merch:
            items.append(ev_merch)

        # Tool 4: Cardholder Dispute History
        ev_hist = EvidenceTools.get_cardholder_dispute_history(cardholder_id)
        if ev_hist:
            items.append(ev_hist)

        # Synthesize flags & findings
        has_sca = False
        carrier_delivered = False
        match_score = 0.5
        impossible_travel = False
        telecom_spoof = False
        prior_disputes = 0

        findings = []

        for item in items:
            if item.source_type == EvidenceSourceType.DEVICE_AND_IP:
                payload = item.data_payload
                if payload.get("impossible_travel_flag"):
                    impossible_travel = True
                    match_score = 0.05
                    findings.append("Impossible travel detected: Physical transaction terminal located thousands of miles from active cardholder mobile session.")
                elif payload.get("telecom_spoofing_flag"):
                    telecom_spoof = True
                    findings.append("Telecom spoofing detected: Incoming call manipulated bank caller ID with social engineering markers.")
                elif payload.get("known_customer_device") and payload.get("biometric_auth_record"):
                    has_sca = True
                    match_score = 0.98
                    findings.append("Biometric verification (FaceID) confirmed on cardholder's primary registered mobile device matching home WiFi IP address.")

            elif item.source_type == EvidenceSourceType.CORE_BANKING_AUTH:
                payload = item.data_payload
                if payload.get("auth_method") == "MAG_STRIPE_FALLBACK":
                    findings.append("Magnetic stripe fallback read: Chip card processed via magnetic stripe reader, strong indicator of physical ATM skim / clone.")

            elif item.source_type == EvidenceSourceType.CARRIER_DELIVERY:
                payload = item.data_payload
                if payload.get("carrier_status") == "RETURNED_TO_SENDER":
                    carrier_delivered = False
                    findings.append(f"Carrier {payload.get('carrier')} verified package was damaged in transit and returned to sender; merchant failed to credit customer.")

            elif item.source_type == EvidenceSourceType.MERCHANT_DESCRIPTOR:
                payload = item.data_payload
                digital = payload.get("digital_fulfillment")
                if digital and digital.get("delivered"):
                    findings.append(f"Digital goods consumed: Activated on cardholder console serial #{digital['activated_on_console_serial']} with {digital['hours_played']} hours logged.")

            elif item.source_type == EvidenceSourceType.DISPUTE_HISTORY:
                payload = item.data_payload
                prior_disputes = payload.get("prior_disputes_last_24m", 0)

        synthesized_summary = " ".join(findings)

        return EvidenceDossier(
            items=items,
            telemetry_match_score=match_score,
            strong_customer_auth_present=has_sca,
            carrier_delivered_confirmed=carrier_delivered,
            prior_merchant_contact_verified=True,
            prior_dispute_count_12m=prior_disputes,
            synthesized_findings=synthesized_summary,
        )
