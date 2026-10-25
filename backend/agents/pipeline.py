"""
Sequential Dispute Investigation Pipeline Orchestrator
Coordinates the 5 deterministic and cognitive agents:
1. Intake & Regime Router
2. Regulatory Clock Sentinel
3. Evidence Harvester
4. Adjudication & Policy Assessment
5. Fed-Compliant Determination Letter Generator
Plus Human-in-the-Loop Analyst approval and ledger execution.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.models.dispute import (
    DisputeCase,
    DisputeCaseState,
    DisputeClaim,
    ChannelType,
    AuditRecord,
    DecisionOutcome,
)
from backend.agents.intake_agent import IntakeAgent
from backend.agents.clock_agent import ClockAgent
from backend.agents.evidence_agent import EvidenceAgent
from backend.agents.assessment_agent import AssessmentAgent
from backend.agents.letter_agent import LetterAgent


class SequentialDisputePipeline:
    """
    Deterministic Sequential Pipeline for Regulatory Card & Payment Disputes.
    """

    @classmethod
    def run_investigation(
        cls,
        claim_id: str,
        cardholder_id: str,
        raw_text: str,
        channel: ChannelType = ChannelType.MOBILE_APP_CHAT,
        transaction_id: Optional[str] = None,
        attachment_paths: Optional[list] = None,
    ) -> DisputeCase:
        """
        Executes the entire sequential agent pipeline and returns the case.
        """
        audit_trail: List[AuditRecord] = []

        # Step 1: Intake & Regime Routing
        claim = IntakeAgent.process_claim(
            claim_id=claim_id,
            cardholder_id=cardholder_id,
            raw_text=raw_text,
            channel=channel,
            known_transaction_id=transaction_id,
            attachment_paths=attachment_paths,
        )
        audit_trail.append(AuditRecord(
            audit_id=f"AUD-{len(audit_trail)+1}",
            actor="Agent:IntakeAgent",
            action="INGEST_CLAIM_AND_ROUTE_REGIME",
            details={
                "claim_id": claim.claim_id,
                "category": claim.claimed_category.value if claim.claimed_category else None,
                "transaction_count": len(claim.transactions),
            }
        ))

        # Step 2: Clock Sentinel
        # Inferred regime
        account_type = claim.transactions[0].account_type if claim.transactions else "CHECKING"
        currency = claim.transactions[0].currency if claim.transactions else "USD"
        from backend.models.dispute import RegulatoryRegime
        if currency == "EUR" or "IBAN" in str(claim.transactions[0].account_id):
            regime = RegulatoryRegime.EU_PSR_PSD2
        elif account_type == "CREDIT_CARD":
            regime = RegulatoryRegime.REG_Z_CREDIT
        else:
            regime = RegulatoryRegime.REG_E_DEBIT

        clock = ClockAgent.initialize_clock(claim=claim, regime=regime)
        audit_trail.append(AuditRecord(
            audit_id=f"AUD-{len(audit_trail)+1}",
            actor="Agent:ClockAgent",
            action="INITIALIZE_STATUTORY_CLOCK",
            details={
                "regime": clock.regime.value,
                "provisional_credit_deadline": str(clock.provisional_credit_deadline) if clock.provisional_credit_deadline else None,
                "investigation_deadline": str(clock.investigation_deadline),
                "urgency": clock.urgency.value,
            }
        ))

        # Step 3: Evidence Harvester
        dossier = EvidenceAgent.harvest_dossier(claim=claim)
        audit_trail.append(AuditRecord(
            audit_id=f"AUD-{len(audit_trail)+1}",
            actor="Agent:EvidenceAgent",
            action="HARVEST_EVIDENCE_DOSSIER",
            details={
                "evidence_items_count": len(dossier.items),
                "telemetry_match_score": dossier.telemetry_match_score,
                "strong_auth_present": dossier.strong_customer_auth_present,
            }
        ))

        # Step 4: Adjudication & Policy Assessment
        proposal = AssessmentAgent.evaluate_claim(
            claim=claim,
            clock=clock,
            dossier=dossier,
        )
        audit_trail.append(AuditRecord(
            audit_id=f"AUD-{len(audit_trail)+1}",
            actor="Agent:AssessmentAgent",
            action="PROPOSE_ADJUDICATION_DECISION",
            details={
                "proposed_decision": proposal.proposed_decision.value,
                "confidence_score": proposal.confidence_score,
                "statutory_tests_count": len(proposal.statutory_tests),
                "primary_legal_basis": proposal.primary_legal_basis,
            }
        ))

        # Step 5: Fed-Compliant Determination Letter Generator
        letter = LetterAgent.generate_letter(
            claim=claim,
            proposal=proposal,
            dossier=dossier,
        )
        audit_trail.append(AuditRecord(
            audit_id=f"AUD-{len(audit_trail)+1}",
            actor="Agent:LetterAgent",
            action="GENERATE_FED_COMPLIANT_DETERMINATION_LETTER",
            details={
                "letter_id": letter.letter_id,
                "relied_upon_documents_count": len(letter.relied_upon_documents),
                "has_no_error_boilerplate": False,  # Strict verification flag
            }
        ))

        case = DisputeCase(
            case_id=f"CASE-{claim_id}",
            state=DisputeCaseState.PENDING_ANALYST_APPROVAL,
            claim=claim,
            clock=clock,
            evidence=dossier,
            adjudication=proposal,
            letter=letter,
            analyst_approved=False,
            analyst_id=None,
            analyst_notes=None,
            audit_trail=audit_trail,
        )

        return case

    @classmethod
    def approve_and_execute(
        cls,
        case: DisputeCase,
        analyst_id: str,
        analyst_notes: str = "Decision verified against telemetry and approved.",
        override_decision: Optional[DecisionOutcome] = None,
    ) -> DisputeCase:
        """
        Human-in-the-Loop Analyst execution gate.
        Posts mock core banking ledger entries and archives immutable audit trail.
        """
        final_decision = override_decision or (
            case.adjudication.proposed_decision if case.adjudication else DecisionOutcome.DENY_CLAIM
        )
        is_override = override_decision is not None and (
            case.adjudication and override_decision != case.adjudication.proposed_decision
        )

        case.analyst_approved = True
        case.analyst_id = analyst_id
        case.analyst_notes = analyst_notes
        case.state = DisputeCaseState.RESOLVED_OVERRIDDEN if is_override else DisputeCaseState.RESOLVED_APPROVED

        # Mock Core Banking Ledger / Chargeback Execution
        ledger_entry = None
        if final_decision in (DecisionOutcome.GRANT_PROVISIONAL_CREDIT, DecisionOutcome.APPROVE_IMMEDIATE_REFUND):
            amount = case.adjudication.provisional_credit_amount if case.adjudication else 0.0
            ledger_entry = {
                "ledger_action": "CREDIT_ACCOUNT",
                "account_id": case.claim.transactions[0].account_id,
                "amount": amount,
                "memo": f"Provisional/Statutory Credit for Dispute #{case.case_id}",
                "effective_timestamp": datetime.utcnow().isoformat(),
            }
        elif final_decision == DecisionOutcome.CHARGEBACK_INITIATED:
            ledger_entry = {
                "ledger_action": "INITIATE_NETWORK_CHARGEBACK",
                "network": "VISA/MASTERCARD",
                "reason_code": "4855",
                "amount": case.claim.transactions[0].amount,
                "memo": f"Chargeback dispatched to merchant acquirer for #{case.case_id}",
            }

        case.audit_trail.append(AuditRecord(
            audit_id=f"AUD-{len(case.audit_trail)+1}",
            actor=f"DisputeAnalyst:{analyst_id}",
            action="SIGN_OFF_AND_DISPATCH_LEDGER",
            details={
                "final_decision": final_decision.value,
                "is_override": is_override,
                "analyst_notes": analyst_notes,
                "ledger_posting": ledger_entry,
                "dispatch_customer_letter": True,
            }
        ))

        return case
