"""
Vitalis AI Phone Number & OTP Verification Service.
Provides a clean provider abstraction supporting:
- Twilio SMS Gateway for production delivery
- DevelopmentMockOTPProvider for local dev and automated testing
- Cryptographic code generation, SHA-256 session hashing, rate limiting, and masking
"""

import os
import time
import secrets
import hashlib
import re
import logging
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Dict, Any
from flask import current_app, session

logger = logging.getLogger("vitalis.otp")


class BaseOTPProvider(ABC):
    """Abstract Base Class for SMS/OTP delivery providers."""

    @abstractmethod
    def send_sms(self, to_phone: str, message: str) -> Tuple[bool, str]:
        """
        Send an SMS message to the recipient phone number.
        Returns (success: bool, error_message: str).
        """
        pass


class TwilioOTPProvider(BaseOTPProvider):
    """Twilio REST API provider for production SMS delivery."""

    def __init__(self, account_sid: str = "", auth_token: str = "", from_phone: str = ""):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_phone = from_phone

    def send_sms(self, to_phone: str, message: str) -> Tuple[bool, str]:
        if not (self.account_sid and self.auth_token and self.from_phone):
            logger.error("Twilio provider error: Credentials not fully configured in environment.")
            return False, "SMS provider is not configured. Please contact support or use local credentials."

        try:
            import urllib.request
            import urllib.parse
            import base64

            api_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            post_data = urllib.parse.urlencode({
                "To": to_phone,
                "From": self.from_phone,
                "Body": message
            }).encode("utf-8")

            auth_header = "Basic " + base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode("utf-8")).decode("utf-8")
            req = urllib.request.Request(api_url, data=post_data, headers={
                "Authorization": auth_header,
                "Content-Type": "application/x-www-form-urlencoded"
            })

            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    logger.info("SMS successfully dispatched via Twilio.")
                    return True, ""
                return False, f"Twilio returned status {resp.status}"

        except Exception as e:
            logger.error(f"Twilio API request failure: {e}")
            return False, "Failed to deliver SMS. Please check your phone number and try again."


class DevelopmentMockOTPProvider(BaseOTPProvider):
    """
    Development and Testing OTP provider.
    Logs masked dispatch securely to system logs and maintains an in-memory test store.
    """
    _last_codes: Dict[str, str] = {}

    def send_sms(self, to_phone: str, message: str) -> Tuple[bool, str]:
        # Extract 4-digit OTP from message for testing retrieval
        match = re.search(r"\b(\d{4})\b", message)
        if match:
            DevelopmentMockOTPProvider._last_codes[to_phone] = match.group(1)

        masked = OTPService.mask_phone(to_phone)
        logger.info(f"[DEV_OTP] Simulated SMS to {masked}: {message}")
        return True, ""

    @classmethod
    def get_last_code(cls, phone: str) -> Optional[str]:
        return cls._last_codes.get(phone)

    @classmethod
    def clear_test_codes(cls):
        cls._last_codes.clear()


class OTPService:
    """Core manager for phone validation, OTP generation, session storage, and rate limiting."""

    COOLDOWN_SECONDS = 30
    EXPIRATION_SECONDS = 300  # 5 minutes
    MAX_ATTEMPTS = 3
    MAX_SENDS_PER_WINDOW = 5
    WINDOW_SECONDS = 900  # 15 minutes

    @staticmethod
    def normalize_phone(phone_input: str) -> Optional[str]:
        """
        Normalize and validate an international phone number (E.164 format: +[country][digits]).
        Accepts formats like '+91 98765 43210', '9876543210' with country code, etc.
        """
        if not phone_input or not isinstance(phone_input, str):
            return None

        # Remove spaces, parentheses, hyphens, dots
        cleaned = re.sub(r"[\s\(\)\-\.]", "", phone_input.strip())

        if not cleaned:
            return None

        # Ensure leading +
        if not cleaned.startswith("+"):
            # Default to +91 if 10 digits provided without code, or +1 if 10 digits
            if len(cleaned) == 10:
                cleaned = "+91" + cleaned
            else:
                cleaned = "+" + cleaned

        # Validate format: + followed by 8 to 15 digits
        if not re.match(r"^\+[1-9]\d{7,14}$", cleaned):
            return None

        return cleaned

    @staticmethod
    def mask_phone(normalized_phone: str) -> str:
        """
        Mask a phone number for user-facing display.
        Example: '+919876543210' -> '+91 9876 •••• 10'
        """
        if not normalized_phone or len(normalized_phone) < 6:
            return normalized_phone or ""

        # Extract country code (first 2-4 chars e.g. +91 or +1)
        prefix = normalized_phone[:3] if normalized_phone.startswith(("+91", "+44", "+61", "+49")) else normalized_phone[:2]
        rest = normalized_phone[len(prefix):]

        if len(rest) >= 8:
            lead = rest[:4]
            tail = rest[-2:]
            return f"{prefix} {lead} •••• {tail}"
        elif len(rest) >= 4:
            lead = rest[:2]
            tail = rest[-2:]
            return f"{prefix} {lead} ••• {tail}"
        return f"{prefix} •••• {rest[-2:]}"

    @classmethod
    def get_provider(cls) -> BaseOTPProvider:
        """Factory returning the active OTP delivery provider based on application config."""
        provider_type = current_app.config.get("SMS_PROVIDER", "mock").lower()

        if provider_type == "twilio":
            sid = current_app.config.get("TWILIO_ACCOUNT_SID", "")
            token = current_app.config.get("TWILIO_AUTH_TOKEN", "")
            from_phone = current_app.config.get("TWILIO_PHONE_NUMBER", "")
            return TwilioOTPProvider(sid, token, from_phone)

        # Fallback to Development / Testing provider
        return DevelopmentMockOTPProvider()

    @classmethod
    def send_otp(cls, phone_input: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Generate and send an OTP code.
        Returns: (success: bool, message: str, masked_phone: Optional[str], dev_code: Optional[str])
        """
        normalized = cls.normalize_phone(phone_input)
        if not normalized:
            return False, "Please enter a valid phone number with country code.", None, None

        now = time.time()

        # Check resend cooldown
        last_sent = session.get("phone_otp_last_sent", 0)
        elapsed = now - last_sent
        if elapsed < cls.COOLDOWN_SECONDS:
            remaining = int(cls.COOLDOWN_SECONDS - elapsed)
            return False, f"Please wait {remaining} seconds before requesting a new code.", None, None

        # Check window rate limiting
        send_history = session.get("phone_otp_history", [])
        # Filter within window
        send_history = [t for t in send_history if (now - t) < cls.WINDOW_SECONDS]
        if len(send_history) >= cls.MAX_SENDS_PER_WINDOW:
            return False, "Too many code requests. Please wait a few minutes before trying again.", None, None

        # Generate cryptographically strong 4-digit code (1000 - 9999)
        otp = str(secrets.randbelow(9000) + 1000)

        # Hash code with secret key and salt for storage
        secret_key = current_app.secret_key or "vitalis-default-secret"
        otp_hash = hashlib.sha256(f"{normalized}:{otp}:{secret_key}".encode("utf-8")).hexdigest()

        # Record session state
        session["phone_otp"] = {
            "phone": normalized,
            "hash": otp_hash,
            "created_at": now,
            "expires_at": now + cls.EXPIRATION_SECONDS,
            "attempts": 0
        }
        session["phone_otp_last_sent"] = now
        send_history.append(now)
        session["phone_otp_history"] = send_history

        # Dispatch via provider
        provider = cls.get_provider()
        message = f"Your Vitalis AI verification code is: {otp}. Valid for 5 minutes. Do not share this code."
        sent_ok, err_msg = provider.send_sms(normalized, message)

        if not sent_ok:
            # Revert session state if delivery failed
            session.pop("phone_otp", None)
            return False, err_msg or "Failed to send verification code. Please try again.", None, None

        masked = cls.mask_phone(normalized)

        # In debug/testing mode, return the dev_code to assist automated tests and local verification
        is_debug = current_app.config.get("DEBUG") or current_app.config.get("TESTING")
        is_mock_provider = isinstance(provider, DevelopmentMockOTPProvider)
        dev_code = otp if (is_debug and is_mock_provider) else None

        return True, "Verification code sent successfully.", masked, dev_code

    @classmethod
    def verify_otp(cls, phone_input: str, candidate_otp: str) -> Tuple[bool, str]:
        """
        Verify the candidate OTP against the stored session hash.
        Returns: (success: bool, message: str)
        """
        normalized = cls.normalize_phone(phone_input)
        if not normalized:
            return False, "Invalid phone number."

        stored = session.get("phone_otp")
        if not stored:
            return False, "No active verification code found. Please request a new code."

        if stored.get("phone") != normalized:
            return False, "Phone number mismatch. Please request a new code."

        now = time.time()
        if now > stored.get("expires_at", 0):
            session.pop("phone_otp", None)
            return False, "Verification code has expired. Please request a new code."

        if stored.get("attempts", 0) >= cls.MAX_ATTEMPTS:
            session.pop("phone_otp", None)
            return False, "Too many incorrect attempts. Please request a new code."

        clean_candidate = str(candidate_otp).strip()
        if not clean_candidate or not clean_candidate.isdigit() or len(clean_candidate) != 4:
            stored["attempts"] = stored.get("attempts", 0) + 1
            session["phone_otp"] = stored
            return False, "That code is incorrect. Please enter the 4-digit code."

        # Compute hash
        secret_key = current_app.secret_key or "vitalis-default-secret"
        expected_hash = hashlib.sha256(f"{normalized}:{clean_candidate}:{secret_key}".encode("utf-8")).hexdigest()

        if not secrets.compare_digest(stored.get("hash", ""), expected_hash):
            stored["attempts"] = stored.get("attempts", 0) + 1
            session["phone_otp"] = stored
            remaining = cls.MAX_ATTEMPTS - stored["attempts"]
            if remaining <= 0:
                session.pop("phone_otp", None)
                return False, "Too many incorrect attempts. Please request a new code."
            return False, "That code is incorrect. Please try again."

        # Successfully verified: clean up OTP session state
        session.pop("phone_otp", None)
        return True, "Verification successful."
