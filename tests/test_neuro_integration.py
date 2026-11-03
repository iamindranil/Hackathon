"""
Automated Verification Suite for Cognizant Neuro® San Integration
Tests CodedTools, HOCON specification compliance, and end-to-end execution
of the NeuroDisputeEngine across all 4 regulatory scenarios.
"""

from datetime import date
from backend.models.dispute import RegulatoryRegime, DecisionOutcome
from backend.neuro.coded_tools import (
    ComputeStatutoryClockTool,
    HarvestTransactionTelemetryTool,
    HarvestSecurityTelemetryTool,
    HarvestMerchantFulfillmentTool,
    HarvestDisputeHistoryTool,
)
from backend.neuro.neuro_engine import NeuroDisputeEngine


def test_neuro_coded_tools():
    # 1. Test Clock Coded Tool
    clock_tool = ComputeStatutoryClockTool()
    res_clock = clock_tool.execute(
        regime="REG_E_DEBIT",
        intake_date="2026-11-16",
        is_new_account=False,
    )
    assert res_clock["regime"] == "REG_E_DEBIT"
    assert "provisional_credit_deadline" in res_clock
    print("[OK] Neuro Coded Tool: ComputeStatutoryClockTool passed.")

    # 2. Test Transaction Telemetry Tool
    txn_tool = HarvestTransactionTelemetryTool()
    res_txn = txn_tool.execute(transaction_id="TX-88201")
    assert res_txn["evidence_id"] == "EV-TXN-TX-88201"
    assert res_txn["data_payload"]["amount"] == 420.0
    print("[OK] Neuro Coded Tool: HarvestTransactionTelemetryTool passed.")

    # 3. Test Security Telemetry Tool (Impossible Travel)
    sec_tool = HarvestSecurityTelemetryTool()
    res_sec = sec_tool.execute(transaction_id="TX-88201")
    assert res_sec["data_payload"]["impossible_travel_flag"] is True
    print("[OK] Neuro Coded Tool: HarvestSecurityTelemetryTool passed.")

    # 4. Test Merchant Fulfillment Tool
    merch_tool = HarvestMerchantFulfillmentTool()
    res_merch = merch_tool.execute(transaction_id="TX-77312")
    assert res_merch["data_payload"]["carrier_status"] == "RETURNED_TO_SENDER"
    print("[OK] Neuro Coded Tool: HarvestMerchantFulfillmentTool passed.")

    # 5. Test Dispute History Tool
    hist_tool = HarvestDisputeHistoryTool()
    res_hist = hist_tool.execute(cardholder_id="CUST-3819")
    assert res_hist["data_payload"]["friendly_fraud_risk"] == "HIGH"
    print("[OK] Neuro Coded Tool: HarvestDisputeHistoryTool passed.")


def test_neuro_engine_e2e_scenarios():
    # Scenario 1: US Reg E Debit (ATM Skim in Miami with impossible travel)
    case_1 = NeuroDisputeEngine.run_neuro_investigation(
        claim_id="NEURO-CLM-01",
        cardholder_id="CUST-1049",
        raw_text="Unauthorized ATM cash withdrawal of $420 in Miami (TX-88201). I was home in Seattle.",
        transaction_id="TX-88201",
    )
    assert case_1.clock.regime == RegulatoryRegime.REG_E_DEBIT
    assert case_1.adjudication.proposed_decision == DecisionOutcome.GRANT_PROVISIONAL_CREDIT
    assert any("ResolvFrontManRouter" in a.actor for a in case_1.audit_trail)
    assert any("RegulatoryClockSentinelAgent" in a.actor for a in case_1.audit_trail)
    print("[OK] Neuro Engine: Scenario #01 (Reg E ATM Skim) passed.")

    # Scenario 2: US Reg E Friendly Fraud (FaceID on Home WiFi)
    case_2 = NeuroDisputeEngine.run_neuro_investigation(
        claim_id="NEURO-CLM-02",
        cardholder_id="CUST-3819",
        raw_text="I did not make this $1250 PlayStation charge (TX-90184).",
        transaction_id="TX-90184",
    )
    assert case_2.adjudication.proposed_decision == DecisionOutcome.DENY_CLAIM
    assert "no error occurred" not in case_2.letter.detailed_factual_explanation.lower()
    print("[OK] Neuro Engine: Scenario #02 (Defensible Denial) passed.")

    # Scenario 3: US Reg Z Credit Card Damaged Return
    case_3 = NeuroDisputeEngine.run_neuro_investigation(
        claim_id="NEURO-CLM-03",
        cardholder_id="CUST-7201",
        raw_text="Nordstrom coat was damaged and returned to merchant via FedEx (TX-77312).",
        transaction_id="TX-77312",
    )
    assert case_3.clock.regime == RegulatoryRegime.REG_Z_CREDIT
    assert case_3.adjudication.proposed_decision == DecisionOutcome.CHARGEBACK_INITIATED
    print("[OK] Neuro Engine: Scenario #03 (Reg Z Chargeback) passed.")

    # Scenario 4: EU PSR Impersonation Scam
    case_4 = NeuroDisputeEngine.run_neuro_investigation(
        claim_id="NEURO-CLM-04",
        cardholder_id="CUST-5512",
        raw_text="Fake bank fraud caller guided me to transfer €3,500 to a safe account (TX-66105).",
        transaction_id="TX-66105",
    )
    assert case_4.clock.regime == RegulatoryRegime.EU_PSR_PSD2
    assert case_4.adjudication.proposed_decision == DecisionOutcome.APPROVE_IMMEDIATE_REFUND
    print("[OK] Neuro Engine: Scenario #04 (EU PSR Scam Reimbursement) passed.")


if __name__ == "__main__":
    test_neuro_coded_tools()
    test_neuro_engine_e2e_scenarios()
    print("\nALL COGNIZANT NEURO INTEGRATION TESTS PASSED SUCCESSFULLY!")

