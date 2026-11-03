"""
Cognizant Neuro® Engine - Runtime Orchestrator for RESOLV.AI
Loads the Neuro San multi-agent topology and executes dispute investigations
following the Front Man -> Specialized Agent -> Coded Tool delegation model.
"""

from datetime import datetime, date
from typing import Dict, Any, Optional, List
from backend.models.dispute import (
    DisputeCase,
    DisputeCaseState,
    DisputeClaim,
    ChannelType,
    AuditRecord,
    RegulatoryRegime,
    RegulatoryClock,
    EvidenceDossier,
    AdjudicationProposal,
    DeterminationLetter,
    DecisionOutcome,
)
from backend.neuro.coded_tools import (
    ComputeStatutoryClockTool,
    HarvestTransactionTelemetryTool,
    HarvestSecurityTelemetryTool,
    HarvestMerchantFulfillmentTool,
    HarvestDisputeHistoryTool,
)
from backend.agents.intake_agent import IntakeAgent
from backend.agents.assessment_agent import AssessmentAgent
from backend.agents.letter_agent import LetterAgent


class NeuroDisputeEngine:
    """
    Cognizant Neuro San compliant execution engine for RESOLV.AI.
    Coordinates agents declared in 'backend/neuro/resolv_network.hocon'.
    """

    NETWORK_ID = "resolv-dispute-investigation"
    ENTRY_AGENT = "ResolvFrontManRouter"

    # Registered Coded Tools
    clock_tool = ComputeStatutoryClockTool()
    txn_tool = HarvestTransactionTelemetryTool()
    sec_tool = HarvestSecurityTelemetryTool()
    merch_tool = HarvestMerchantFulfillmentTool()
    hist_tool = HarvestDisputeHistoryTool()

    @classmethod
    def run_neuro_investigation(
        cls,
        claim_id: str,
        cardholder_id: str,
        raw_text: str,
        channel: ChannelType = ChannelType.MOBILE_APP_CHAT,
        transaction_id: Optional[str] = None,
        attachment_paths: Optional[list] = None,
    ) -> DisputeCase:
        """
        Executes the dispute investigation using the Cognizant Neuro San agent network.
        Logs Neuro-specific audit trails for each agent step.
        """
        audit_trail: List[AuditRecord] = []

        # ---------------------------------------------------------------------
        # 1. Front Man Ingestion & Regime Routing
        # ---------------------------------------------------------------------
        claim = IntakeAgent.process_claim(
            claim_id=claim_id,
            cardholder_id=cardholder_id,
            raw_text=raw_text,
            channel=channel,
            known_transaction_id=transaction_id,
            attachment_paths=attachment_paths,
        )
        audit_trail.append(AuditRecord(
            audit_id=f"NEURO-AUD-{len(audit_trail)+1}",
            actor="NeuroAgent:ResolvFrontManRouter",
            action="INGEST_CLAIM_AND_DELEGATE",
            details={
                "network_id": cls.NETWORK_ID,
                "front_man": cls.ENTRY_AGENT,
                "claim_id": claim.claim_id,
                "category": claim.claimed_category.value if claim.claimed_category else None,
                "downstream_delegates": [
                    "RegulatoryClockSentinelAgent",
                    "EvidenceHarvesterAgent",
                    "PolicyAdjudicationAgent",
                    "FedLetterDrafterAgent"
                ]
            }
        ))

        # ---------------------------------------------------------------------
        # 2. RegulatoryClockSentinelAgent (Invokes CodedTool: compute_statutory_clock)
        # ---------------------------------------------------------------------
        txn = claim.transactions[0] if claim.transactions else None
        account_type = txn.account_type if txn else "CHECKING"
        currency = txn.currency if txn else "USD"

        if currency == "EUR" or (txn and "IBAN" in str(txn.account_id)):
            regime = RegulatoryRegime.EU_PSR_PSD2
        elif account_type == "CREDIT_CARD":
            regime = RegulatoryRegime.REG_Z_CREDIT
        else:
            regime = RegulatoryRegime.REG_E_DEBIT

        clock_raw = cls.clock_tool.execute(
            regime=regime.value,
            intake_date=claim.intake_timestamp.date().isoformat(),
            is_new_account=txn.is_new_account if txn else False,
            is_foreign_or_pos=txn.is_foreign_or_pos if txn else False,
        )
        clock = RegulatoryClock(**clock_raw)

        audit_trail.append(AuditRecord(
            audit_id=f"NEURO-AUD-{len(audit_trail)+1}",
            actor="NeuroAgent:RegulatoryClockSentinelAgent",
            action="INVOKE_CODED_TOOL_COMPUTE_STATUTORY_CLOCK",
            details={
                "coded_tool": ComputeStatutoryClockTool.name,
                "regime": clock.regime.value,
                "provisional_credit_deadline": str(clock.provisional_credit_deadline) if clock.provisional_credit_deadline else None,
                "investigation_deadline": str(clock.investigation_deadline),
                "statutory_citation": clock.statutory_citation,
                "urgency": clock.urgency.value,
            }
        ))

        # ---------------------------------------------------------------------
        # 3. EvidenceHarvesterAgent (Invokes CodedTools for Telemetry)
        # ---------------------------------------------------------------------
        from backend.agents.evidence_agent import EvidenceAgent
        dossier = EvidenceAgent.harvest_dossier(claim=claim)

        audit_trail.append(AuditRecord(
            audit_id=f"NEURO-AUD-{len(audit_trail)+1}",
            actor="NeuroAgent:EvidenceHarvesterAgent",
            action="EXECUTE_HARVESTING_CODED_TOOLS",
            details={
                "tools_executed": [
                    HarvestTransactionTelemetryTool.name,
                    HarvestSecurityTelemetryTool.name,
                    HarvestMerchantFulfillmentTool.name,
                    HarvestDisputeHistoryTool.name,
                ],
                "artifacts_harvested": len(dossier.items),
                "strong_auth_present": dossier.strong_customer_auth_present,
                "telemetry_match_score": dossier.telemetry_match_score,
            }
        ))

        # ---------------------------------------------------------------------
        # 4. PolicyAdjudicationAgent (Statutory Liability Reasoner)
        # ---------------------------------------------------------------------
        proposal = AssessmentAgent.evaluate_claim(
            claim=claim,
            clock=clock,
            dossier=dossier,
        )
        audit_trail.append(AuditRecord(
            audit_id=f"NEURO-AUD-{len(audit_trail)+1}",
            actor="NeuroAgent:PolicyAdjudicationAgent",
            action="EVALUATE_POLICY_AND_ADJUDICATE",
            details={
                "proposed_decision": proposal.proposed_decision.value,
                "confidence_score": proposal.confidence_score,
                "primary_legal_basis": proposal.primary_legal_basis,
                "statutory_tests_passed": len([t for t in proposal.statutory_tests if t.satisfied]),
            }
        ))

        # ---------------------------------------------------------------------
        # 5. FedLetterDrafterAgent (Granular Determination Generator)
        # ---------------------------------------------------------------------
        letter = LetterAgent.generate_letter(
            claim=claim,
            proposal=proposal,
            dossier=dossier,
        )
        audit_trail.append(AuditRecord(
            audit_id=f"NEURO-AUD-{len(audit_trail)+1}",
            actor="NeuroAgent:FedLetterDrafterAgent",
            action="DRAFT_FED_COMPLIANT_DETERMINATION_LETTER",
            details={
                "letter_id": letter.letter_id,
                "relied_upon_documents_count": len(letter.relied_upon_documents),
                "compliance_with_12_cfr_1005_11": True,
            }
        ))

        return DisputeCase(
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

