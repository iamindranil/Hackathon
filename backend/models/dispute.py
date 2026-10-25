"""
Card and Payment Dispute Investigation Agent - Domain Models
Defines all structured types for claims, regulatory regimes, statutory clocks,
evidence artifacts, adjudication decisions, and audit records.
"""

from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DisputeCategory(str, Enum):
    UNAUTHORIZED_TRANSACTION = "UNAUTHORIZED_TRANSACTION"
    BILLING_ERROR = "BILLING_ERROR"
    GOODS_SERVICES_NOT_RECEIVED = "GOODS_SERVICES_NOT_RECEIVED"
    DEFECTIVE_OR_INCORRECT = "DEFECTIVE_OR_INCORRECT"
    IMPERSONATION_APP_SCAM = "IMPERSONATION_APP_SCAM"
    DUPLICATE_PROCESSING = "DUPLICATE_PROCESSING"
    ATM_CASH_DISCREPANCY = "ATM_CASH_DISCREPANCY"


class RegulatoryRegime(str, Enum):
    REG_E_DEBIT = "REG_E_DEBIT"          # US 12 CFR § 1005.11 (Electronic Fund Transfers / Debit / ACH)
    REG_Z_CREDIT = "REG_Z_CREDIT"        # US 12 CFR § 1026.13 (Truth in Lending / Credit Cards)
    EU_PSR_PSD2 = "EU_PSR_PSD2"          # EU Payment Services Directive / Regulation (2026/2027 PSR)


class ClockUrgency(str, Enum):
    NORMAL = "NORMAL"                    # > 48 hours remaining
    EXPEDITED = "EXPEDITED"              # 24-48 hours remaining
    CRITICAL = "CRITICAL"                # < 24 hours remaining
    BREACHED = "BREACHED"                # Past statutory deadline


class DecisionOutcome(str, Enum):
    APPROVE_IMMEDIATE_REFUND = "APPROVE_IMMEDIATE_REFUND"
    GRANT_PROVISIONAL_CREDIT = "GRANT_PROVISIONAL_CREDIT"
    CHARGEBACK_INITIATED = "CHARGEBACK_INITIATED"
    DENY_CLAIM = "DENY_CLAIM"
    REQUEST_CARDHOLDER_AFFIDAVIT = "REQUEST_CARDHOLDER_AFFIDAVIT"


class ChannelType(str, Enum):
    MOBILE_APP_CHAT = "MOBILE_APP_CHAT"
    EMAIL = "EMAIL"
    CALL_CENTER_TRANSCRIPT = "CALL_CENTER_TRANSCRIPT"
    PAPER_FORM_SCAN = "PAPER_FORM_SCAN"
    UPLOADED_RECEIPT = "UPLOADED_RECEIPT"


# --- Transaction & Claim Schemas ---

class DisputedTransaction(BaseModel):
    transaction_id: str
    amount: float
    currency: str = "USD"
    merchant_name: str
    merchant_raw_descriptor: str
    transaction_date: datetime
    posting_date: Optional[datetime] = None
    account_id: str
    card_last_four: str
    account_type: str = "CHECKING"       # CHECKING, SAVINGS, CREDIT_CARD
    is_new_account: bool = False         # Account opened < 30 days ago (affects Reg E 90-day extension)
    is_foreign_or_pos: bool = False      # POS or outside US transaction


class DisputeClaim(BaseModel):
    claim_id: str
    cardholder_id: str
    cardholder_name: str
    cardholder_email: str
    cardholder_phone: Optional[str] = None
    channel: ChannelType
    raw_claim_text: str
    attachment_paths: List[str] = Field(default_factory=list)
    intake_timestamp: datetime = Field(default_factory=datetime.utcnow)
    transactions: List[DisputedTransaction]
    claimed_category: Optional[DisputeCategory] = None
    cardholder_stated_reason: Optional[str] = None


# --- Regulatory Clock Schema ---

class RegulatoryClock(BaseModel):
    regime: RegulatoryRegime
    intake_date: date
    statutory_start_date: date           # T_0
    
    # Deadlines computed deterministically
    acknowledgment_deadline: Optional[date] = None      # Reg Z: 30 days
    provisional_credit_deadline: Optional[date] = None  # Reg E: 10 business days
    investigation_deadline: date                        # Reg E: 10/45/90 days; Reg Z: 2 billing cycles/90 days; EU: 1/15 days
    customer_notice_deadline: date                      # Post-investigation notice
    
    # Live status
    days_to_provisional_credit: Optional[int] = None
    days_to_final_resolution: int
    urgency: ClockUrgency = ClockUrgency.NORMAL
    statutory_citation: str                             # e.g., "12 CFR § 1005.11(c)(1)"
    business_days_applied: int                          # Count of business days calculated
    calendar_days_applied: int


# --- Evidence Schemas ---

class EvidenceSourceType(str, Enum):
    CORE_BANKING_AUTH = "CORE_BANKING_AUTH"
    THREE_DS_TELEMETRY = "THREE_DS_TELEMETRY"
    DEVICE_AND_IP = "DEVICE_AND_IP"
    MERCHANT_DESCRIPTOR = "MERCHANT_DESCRIPTOR"
    CARRIER_DELIVERY = "CARRIER_DELIVERY"
    DISPUTE_HISTORY = "DISPUTE_HISTORY"
    CUSTOMER_COMMUNICATION = "CUSTOMER_COMMUNICATION"


class EvidenceItem(BaseModel):
    evidence_id: str
    source_type: EvidenceSourceType
    title: str
    timestamp: datetime
    relevance_summary: str
    data_payload: Dict[str, Any]
    indicates_fraud: Optional[bool] = None
    confidence_score: float = 1.0


class EvidenceDossier(BaseModel):
    items: List[EvidenceItem] = Field(default_factory=list)
    telemetry_match_score: float = 0.0          # 0.0 to 1.0 match to cardholder known devices/IPs
    strong_customer_auth_present: bool = False  # 3DS / EMV Chip + PIN / Biometric FaceID
    carrier_delivered_confirmed: bool = False
    prior_merchant_contact_verified: bool = False
    prior_dispute_count_12m: int = 0
    synthesized_findings: str = ""


# --- Adjudication & Determination Letter Schemas ---

class StatutoryTestResult(BaseModel):
    test_name: str
    statutory_rule: str
    satisfied: bool
    rationale: str
    relying_evidence_ids: List[str]


class AdjudicationProposal(BaseModel):
    proposed_decision: DecisionOutcome
    regime: RegulatoryRegime
    confidence_score: float
    provisional_credit_amount: Optional[float] = None
    final_reversal_amount: Optional[float] = None
    chargeback_amount: Optional[float] = None
    primary_legal_basis: str
    statutory_tests: List[StatutoryTestResult]
    relied_upon_evidence_ids: List[str]
    compliance_officer_summary: str


class DeterminationLetter(BaseModel):
    letter_id: str
    recipient_name: str
    recipient_address: Optional[str] = "123 Cardholder Way, New York, NY 10001"
    date_issued: date
    claim_id: str
    decision_summary: str
    detailed_factual_explanation: str    # Fed compliance: specific findings, NO boilerplate "no error"
    relied_upon_documents: List[str]     # Exact itemization of records used
    right_to_request_documents_notice: str
    provisional_credit_status_notice: Optional[str] = None
    contact_phone: str = "1-800-555-CARD"


# --- Complete Case Lifecycle Container ---

class DisputeCaseState(str, Enum):
    INTAKE_COMPLETED = "INTAKE_COMPLETED"
    CLOCK_INITIALIZED = "CLOCK_INITIALIZED"
    EVIDENCE_HARVESTED = "EVIDENCE_HARVESTED"
    ASSESSMENT_PROPOSED = "ASSESSMENT_PROPOSED"
    LETTER_DRAFTED = "LETTER_DRAFTED"
    PENDING_ANALYST_APPROVAL = "PENDING_ANALYST_APPROVAL"
    RESOLVED_APPROVED = "RESOLVED_APPROVED"
    RESOLVED_OVERRIDDEN = "RESOLVED_OVERRIDDEN"


class AuditRecord(BaseModel):
    audit_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: str                         # e.g., "Agent:Intake", "Agent:Evidence", "Analyst:J.Smith"
    action: str
    details: Dict[str, Any]


class DisputeCase(BaseModel):
    case_id: str
    state: DisputeCaseState
    claim: DisputeClaim
    clock: Optional[RegulatoryClock] = None
    evidence: Optional[EvidenceDossier] = None
    adjudication: Optional[AdjudicationProposal] = None
    letter: Optional[DeterminationLetter] = None
    analyst_approved: bool = False
    analyst_id: Optional[str] = None
    analyst_notes: Optional[str] = None
    audit_trail: List[AuditRecord] = Field(default_factory=list)
