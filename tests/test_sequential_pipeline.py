"""
Unit and Integration Tests for the 5-Stage Agentic Pipeline
Tests all 4 canonical scenarios end-to-end:
1. Reg E Unauthorized ATM Skim
2. Friendly Fraud (FaceID Biometrics on Home WiFi) - Defensible Denial
3. Reg Z Merchant Billing Error (Carrier Damaged Return)
4. EU PSR Impersonation Scam Reimbursement
"""

from backend.agents.pipeline import SequentialDisputePipeline
from backend.models.dispute import (
    RegulatoryRegime,
    DecisionOutcome,
    DisputeCaseState,
    ChannelType,
)


def test_scenario_1_reg_e_atm_skim():
    raw_text = "I saw an ATM withdrawal of $420 at SunTrust in Miami Beach (TX-88201) on my checking statement. I was asleep at home in Seattle! My card was never lost."
    
    case = SequentialDisputePipeline.run_investigation(
        claim_id="CLM-001",
        cardholder_id="CUST-1049",
        raw_text=raw_text,
        channel=ChannelType.MOBILE_APP_CHAT,
        transaction_id="TX-88201",
    )

    # Verify Pipeline Progression
    assert case.clock.regime == RegulatoryRegime.REG_E_DEBIT
    assert case.adjudication.proposed_decision == DecisionOutcome.GRANT_PROVISIONAL_CREDIT
    assert case.adjudication.provisional_credit_amount == 420.00
    assert "Miami Beach" in case.letter.detailed_factual_explanation
    assert "Seattle" in case.letter.detailed_factual_explanation
    assert len(case.evidence.items) >= 3
    assert len(case.audit_trail) == 5

    # Test Human-in-the-Loop Analyst Execution
    resolved_case = SequentialDisputePipeline.approve_and_execute(
        case=case,
        analyst_id="ANALYST-JONES-99",
        analyst_notes="Confirmed impossible travel; skimmer cluster detected at ATM. Provisional credit posted.",
    )

    assert resolved_case.state == DisputeCaseState.RESOLVED_APPROVED
    assert resolved_case.analyst_approved is True
    assert len(resolved_case.audit_trail) == 6
    print("[OK] Scenario 1 (Reg E ATM Skim Unauthorized Debit) passed.")


def test_scenario_2_friendly_fraud_fed_compliant_denial():
    raw_text = "I did not make this $1,250 transaction at PlayStation Network (TX-90184). Please refund my money immediately."

    case = SequentialDisputePipeline.run_investigation(
        claim_id="CLM-002",
        cardholder_id="CUST-3819",
        raw_text=raw_text,
        channel=ChannelType.MOBILE_APP_CHAT,
        transaction_id="TX-90184",
    )

    # Verify Reg E Denial with Specific Factual Evidence
    assert case.clock.regime == RegulatoryRegime.REG_E_DEBIT
    assert case.adjudication.proposed_decision == DecisionOutcome.DENY_CLAIM
    
    # Critical Federal Reserve compliance check:
    # Must NOT contain generic "no error" boilerplate
    explanation = case.letter.detailed_factual_explanation
    assert "no error occurred" not in explanation.lower()
    assert "FaceID" in explanation
    assert "Austin, Texas" in explanation
    assert "18.5 hours" in explanation
    assert len(case.letter.relied_upon_documents) >= 3
    assert "12 CFR § 1005.11(c)(2)(iv)" in case.letter.right_to_request_documents_notice

    print("[OK] Scenario 2 (Defensible Denial with Fed-Compliant Factual Evidence) passed.")


def test_scenario_3_reg_z_billing_error():
    raw_text = "I was charged $899 by Nordstrom (TX-77312) on my credit card. The package was damaged by FedEx and returned to the merchant on Oct 2, but they haven't refunded me."

    case = SequentialDisputePipeline.run_investigation(
        claim_id="CLM-003",
        cardholder_id="CUST-7201",
        raw_text=raw_text,
        channel=ChannelType.EMAIL,
        transaction_id="TX-77312",
    )

    assert case.clock.regime == RegulatoryRegime.REG_Z_CREDIT
    assert case.adjudication.proposed_decision == DecisionOutcome.CHARGEBACK_INITIATED
    assert "Reason Code 4855" in case.letter.detailed_factual_explanation
    assert "FedEx Express" in case.letter.detailed_factual_explanation
    print("[OK] Scenario 3 (Reg Z Credit Card Merchant Billing Error) passed.")


def test_scenario_4_eu_psr_impersonation_scam():
    raw_text = "Someone claiming to be from Bank Security called me from the bank's phone number and told me to transfer €3,500 to a safe account (TX-66105). It was a scam!"

    case = SequentialDisputePipeline.run_investigation(
        claim_id="CLM-004",
        cardholder_id="CUST-5512",
        raw_text=raw_text,
        channel=ChannelType.MOBILE_APP_CHAT,
        transaction_id="TX-66105",
    )

    assert case.clock.regime == RegulatoryRegime.EU_PSR_PSD2
    assert case.adjudication.proposed_decision == DecisionOutcome.APPROVE_IMMEDIATE_REFUND
    assert "caller-ID spoofing" in case.letter.detailed_factual_explanation
    assert "Payment Services Regulation" in case.letter.detailed_factual_explanation
    print("[OK] Scenario 4 (EU PSR Bank Impersonation Scam Reimbursement) passed.")


if __name__ == "__main__":
    test_scenario_1_reg_e_atm_skim()
    test_scenario_2_friendly_fraud_fed_compliant_denial()
    test_scenario_3_reg_z_billing_error()
    test_scenario_4_eu_psr_impersonation_scam()
    print("\nALL 5-STAGE AGENTIC PIPELINE SCENARIO TESTS PASSED SUCCESSFULLY!")
