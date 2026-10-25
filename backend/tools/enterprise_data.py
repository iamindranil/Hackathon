"""
Mock Enterprise Banking Core, Telemetry, and Merchant Repositories.
Contains realistic dispute scenarios covering US Reg E, US Reg Z, and EU PSR.
"""

from datetime import datetime
from typing import Dict, Any, Optional

# --- Synthetic Core Banking Database ---

MOCK_TRANSACTIONS_DB: Dict[str, Dict[str, Any]] = {
    "TX-88201": {
        "transaction_id": "TX-88201",
        "cardholder_id": "CUST-1049",
        "cardholder_name": "Sarah Jenkins",
        "cardholder_email": "sarah.jenkins@example.com",
        "account_id": "CHK-992144",
        "account_type": "CHECKING",
        "card_last_four": "4491",
        "amount": 420.00,
        "currency": "USD",
        "merchant_name": "SUNTRUST ATM #4192",
        "merchant_raw_descriptor": "ATM W/D SUNTRUST MIAMI BEACH FL #4192",
        "merchant_category_code": "6011",  # Automated Cash Disbursements
        "transaction_date": "2026-10-20T03:14:00Z",
        "posting_date": "2026-10-20T06:00:00Z",
        "channel": "ATM",
        "auth_method": "MAG_STRIPE_FALLBACK",  # High fraud indicator: chip reader bypassed/skimmer
        "pin_verified": False,
        "three_ds_version": None,
        "pos_entry_mode": "02",  # Magnetic stripe read
        "terminal_location": "Miami Beach, FL, US",
        "terminal_id": "ATM-MIA-4192",
        "billing_address": "412 Pine Street, Seattle, WA 98101",
    },
    "TX-90184": {
        "transaction_id": "TX-90184",
        "cardholder_id": "CUST-3819",
        "cardholder_name": "Michael Chang",
        "cardholder_email": "michael.chang.atx@example.com",
        "account_id": "CHK-449182",
        "account_type": "CHECKING",
        "card_last_four": "1092",
        "amount": 1250.00,
        "currency": "USD",
        "merchant_name": "PlayStation Network",
        "merchant_raw_descriptor": "SONY*PLAYSTATION*NETWK SAN MATEO CA",
        "merchant_category_code": "5816",  # Digital Goods / Games
        "transaction_date": "2026-10-18T19:42:10Z",
        "posting_date": "2026-10-19T02:00:00Z",
        "channel": "E-COMMERCE",
        "auth_method": "3DS_BIOMETRIC_FACE_ID",
        "pin_verified": False,
        "three_ds_version": "2.2.0",
        "pos_entry_mode": "81",  # E-commerce with 3DS
        "terminal_location": "San Mateo, CA, US (Server)",
        "terminal_id": "PSN-ECOM-01",
        "billing_address": "8902 Barton Creek Blvd, Austin, TX 78735",
    },
    "TX-77312": {
        "transaction_id": "TX-77312",
        "cardholder_id": "CUST-7201",
        "cardholder_name": "Elena Rostova",
        "cardholder_email": "elena.rostova@example.com",
        "account_id": "CC-882711",
        "account_type": "CREDIT_CARD",
        "card_last_four": "8827",
        "amount": 899.00,
        "currency": "USD",
        "merchant_name": "Nordstrom Online",
        "merchant_raw_descriptor": "NORDSTROM #8801 DIRECT SEATTLE WA",
        "merchant_category_code": "5311",  # Department Stores
        "transaction_date": "2026-09-28T14:10:00Z",
        "posting_date": "2026-09-29T08:00:00Z",
        "channel": "E-COMMERCE",
        "auth_method": "CVV2_VERIFIED",
        "pin_verified": False,
        "three_ds_version": "2.1.0",
        "pos_entry_mode": "81",
        "terminal_location": "Seattle, WA, US",
        "terminal_id": "NRD-WEB-44",
        "billing_address": "550 5th Avenue, New York, NY 10036",
    },
    "TX-66105": {
        "transaction_id": "TX-66105",
        "cardholder_id": "CUST-5512",
        "cardholder_name": "David Müller",
        "cardholder_email": "d.mueller@example.de",
        "account_id": "IBAN-DE89370400440532013000",
        "account_type": "SEPA_CHECKING",
        "card_last_four": "9931",
        "amount": 3500.00,
        "currency": "EUR",
        "merchant_name": "Instant Transfer - Safe Account Hold",
        "merchant_raw_descriptor": "SEPA INSTANT TRF DE44500105175593827110 / FRAUD RECOVERY",
        "merchant_category_code": "4829",  # Wire Transfer Money Orders
        "transaction_date": "2026-10-24T11:05:00Z",
        "posting_date": "2026-10-24T11:05:00Z",
        "channel": "SEPA_INSTANT",
        "auth_method": "APP_PUSH_CONFIRMATION",
        "pin_verified": True,
        "three_ds_version": None,
        "pos_entry_mode": "07",
        "terminal_location": "Frankfurt am Main, DE",
        "terminal_id": "SEPA-GW-09",
        "billing_address": "Kaiserstraße 29, 60311 Frankfurt am Main, Germany",
    }
}


# --- Device, Security & Geolocation Telemetry Store ---

MOCK_SECURITY_TELEMETRY: Dict[str, Dict[str, Any]] = {
    "TX-88201": {
        "ip_address": "N/A (Physical ATM Terminal)",
        "ip_geolocation": "Miami Beach, Florida (Lat: 25.7907, Lon: -80.1300)",
        "cardholder_home_location": "Seattle, Washington (Distance: 2,730 miles)",
        "known_customer_device": False,
        "device_fingerprint": "UNRECOGNIZED_ATM_HARDWARE",
        "concurrent_mobile_session": {
            "active": True,
            "ip_address": "73.157.22.8",
            "ip_location": "Seattle, Washington (Cardholder Home WiFi)",
            "device": "Apple iPhone 14 Pro (iOS 19.4)",
            "timestamp": "2026-10-20T03:15:22Z"  # 1 minute after ATM transaction!
        },
        "impossible_travel_flag": True,  # 2,730 miles in 1 minute = 100% impossible travel
        "card_present": True,
        "skimmer_cluster_detected_at_atm": True,
    },
    "TX-90184": {
        "ip_address": "66.76.14.192",
        "ip_geolocation": "Austin, Texas (Matches Home Billing ISP: AT&T Fiber)",
        "cardholder_home_location": "Austin, Texas (Distance: 0.2 miles)",
        "known_customer_device": True,
        "device_fingerprint": "DEV-IPHONE15-MC-9941",
        "device_model": "Apple iPhone 15 Pro (iOS 19.4)",
        "biometric_auth_record": {
            "biometric_type": "FaceID",
            "auth_status": "SUCCESS",
            "fido_attestation_verified": True,
            "timestamp": "2026-10-18T19:42:08Z"
        },
        "impossible_travel_flag": False,
        "console_hardware_id": "PS5-SER-8829410-ATX",
        "playstation_account_registered_email": "michael.chang.atx@example.com",
    },
    "TX-77312": {
        "ip_address": "108.41.90.11",
        "ip_geolocation": "New York, New York",
        "cardholder_home_location": "New York, New York",
        "known_customer_device": True,
        "device_fingerprint": "DEV-MACBOOK-ER-3301",
        "impossible_travel_flag": False,
    },
    "TX-66105": {
        "ip_address": "84.119.201.55",
        "ip_geolocation": "Frankfurt am Main, Germany",
        "cardholder_home_location": "Frankfurt am Main, Germany",
        "known_customer_device": True,
        "device_fingerprint": "DEV-SAMSUNG-S25-DM",
        "impossible_travel_flag": False,
        "telecom_spoofing_flag": True,
        "incoming_call_log": {
            "caller_id": "+49 69 123456 (Spoofed Bank Support Line)",
            "call_duration_seconds": 840,
            "social_engineering_markers": [
                "URGENCY_INDUCEMENT",
                "FAKE_SECURITY_SAFE_ACCOUNT",
                "SPOOFED_BANK_CLI"
            ]
        }
    }
}


# --- Merchant Descriptor & Delivery Verification Store ---

MOCK_MERCHANT_FULFILLMENT: Dict[str, Dict[str, Any]] = {
    "TX-88201": {
        "merchant_name": "SunTrust Bank ATM Terminal",
        "resolved_entity": "SunTrust / Truist Financial Corp.",
        "physical_terminal": True,
        "carrier_tracking": None,
        "merchant_dispute_history": "Low merchant fault, ATM skimmer fraud ring under federal investigation.",
    },
    "TX-90184": {
        "merchant_name": "Sony Interactive Entertainment LLC",
        "resolved_entity": "PlayStation Network Store",
        "physical_terminal": False,
        "carrier_tracking": None,
        "digital_fulfillment": {
            "delivered": True,
            "download_timestamp": "2026-10-18T19:45:00Z",
            "activated_on_console_serial": "PS5-SER-8829410-ATX",
            "hours_played": 18.5,
            "account_owner": "Michael Chang"
        }
    },
    "TX-77312": {
        "merchant_name": "Nordstrom Direct Inc.",
        "resolved_entity": "Nordstrom Department Stores",
        "physical_terminal": False,
        "carrier": "FedEx Express",
        "tracking_number": "FDX-9948271049",
        "carrier_status": "RETURNED_TO_SENDER",
        "carrier_scan_history": [
            {"date": "2026-09-29T10:00:00Z", "event": "Shipment picked up in Newark, NJ"},
            {"date": "2026-09-30T14:15:00Z", "event": "Damaged in transit - package torn/contents crushed"},
            {"date": "2026-10-02T09:30:00Z", "event": "Returned to Nordstrom Fulfillment Center, Seattle WA"}
        ],
        "merchant_refund_issued": False,
        "cardholder_contact_history": [
            {"date": "2026-10-05T11:00:00Z", "channel": "Email", "summary": "Customer requested refund for damaged return; merchant automated response promised 5-7 business days but never posted."}
        ]
    },
    "TX-66105": {
        "merchant_name": "Beneficiary: 'Fraud Resolution Escrow'",
        "resolved_entity": "Mule Account at NeoBank Revolut / N26",
        "physical_terminal": False,
        "carrier_tracking": None,
        "destination_account_flagged": True,
        "destination_bank_reported_mule": True,
    }
}


# --- Cardholder Dispute & Risk Profile Store ---

MOCK_CUSTOMER_PROFILES: Dict[str, Dict[str, Any]] = {
    "CUST-1049": {
        "customer_name": "Sarah Jenkins",
        "account_vintage_months": 84,
        "credit_score": 780,
        "prior_disputes_last_24m": 0,
        "friendly_fraud_risk": "VERY_LOW",
        "customer_segment": "PREMIER_CHECKING"
    },
    "CUST-3819": {
        "customer_name": "Michael Chang",
        "account_vintage_months": 36,
        "credit_score": 690,
        "prior_disputes_last_24m": 4,  # High dispute history
        "friendly_fraud_risk": "HIGH",
        "past_dispute_types": ["DIGITAL_GOODS_NOT_RECOGNIZED", "SUBSCRIPTION_RENEWAL"],
        "customer_segment": "RETAIL_STANDARD"
    },
    "CUST-7201": {
        "customer_name": "Elena Rostova",
        "account_vintage_months": 48,
        "credit_score": 810,
        "prior_disputes_last_24m": 0,
        "friendly_fraud_risk": "VERY_LOW",
        "customer_segment": "SIGNATURE_REWARDS"
    },
    "CUST-5512": {
        "customer_name": "David Müller",
        "account_vintage_months": 120,
        "credit_score": None,  # EU SCHUFA rating: Excellent
        "prior_disputes_last_24m": 0,
        "friendly_fraud_risk": "VERY_LOW",
        "customer_segment": "PRIVATE_BANKING"
    }
}
