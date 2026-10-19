from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger


class BaseSMSProvider(ABC):
    @abstractmethod
    async def send_otp(self, mobile_number: str, otp: str, purpose: str) -> bool:
        pass


class MockSMSProvider(BaseSMSProvider):
    """
    Mock SMS provider for local development and testing.
    Never sends external network requests and safely retains messages in memory for test assertions.
    """

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []

    async def send_otp(self, mobile_number: str, otp: str, purpose: str) -> bool:
        message_record = {
            "mobile": mobile_number,
            "otp": otp,
            "purpose": purpose,
            "sent_at": datetime.now(timezone.utc),
        }
        self.sent_messages.append(message_record)
        # Redact the OTP from output/logs
        logger.info(f"[MockSMS] OTP sent successfully to mobile ending with ...{mobile_number[-4:]} for purpose '{purpose}'.")
        if settings.APP_ENV == "development":
            print(f"\n==================================================", flush=True)
            print(f"[MOCK SMS] OTP for {mobile_number}: {otp}", flush=True)
            print(f"(Default development OTP '123456' is also accepted)", flush=True)
            print(f"==================================================\n", flush=True)
        return True

    def get_last_otp(self, mobile_number: str) -> Optional[str]:
        for msg in reversed(self.sent_messages):
            if msg["mobile"] == mobile_number:
                return msg["otp"]
        return None

    def clear(self) -> None:
        self.sent_messages.clear()


class Fast2SMSProvider(BaseSMSProvider):
    """Fast2SMS gateway provider for production SMS delivery."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.FAST2SMS_API_KEY
        self.endpoint = "https://www.fast2sms.com/dev/bulkV2"

    async def send_otp(self, mobile_number: str, otp: str, purpose: str) -> bool:
        if not self.api_key:
            logger.error("Fast2SMS API key is not configured.")
            return False

        message = f"Your Kirana Kart verification code is {otp} for {purpose}. Valid for 5 minutes. Do not share this with anyone."
        payload = {
            "route": "q",
            "message": message,
            "language": "english",
            "flash": 0,
            "numbers": mobile_number,
        }
        headers = {
            "authorization": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.endpoint, json=payload, headers=headers)
                if response.status_code == 200 and response.json().get("return") is True:
                    logger.info(f"Fast2SMS OTP sent successfully to mobile ending with ...{mobile_number[-4:]}.")
                    return True
                logger.error(f"Fast2SMS error: {response.text}")
                return False
        except Exception as exc:
            logger.error(f"Failed to send SMS via Fast2SMS: {exc}")
            return False


class TwilioSMSProvider(BaseSMSProvider):
    """Twilio SMS provider for international/domestic delivery."""

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
    ):
        self.account_sid = account_sid or settings.TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or settings.TWILIO_AUTH_TOKEN
        self.from_number = from_number or settings.TWILIO_FROM_NUMBER

    async def send_otp(self, mobile_number: str, otp: str, purpose: str) -> bool:
        if not (self.account_sid and self.auth_token and self.from_number):
            logger.error("Twilio credentials or from_number are not fully configured.")
            return False

        # Prepend +91 if Indian 10 digits
        to_number = f"+91{mobile_number}" if not mobile_number.startswith("+") else mobile_number
        message = f"Your Kirana Kart OTP is {otp} for {purpose}. Valid for 5 minutes."

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        data = {
            "To": to_number,
            "From": self.from_number,
            "Body": message,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, data=data, auth=(self.account_sid, self.auth_token))
                if response.status_code in (200, 201):
                    logger.info(f"Twilio SMS sent to ...{mobile_number[-4:]}.")
                    return True
                logger.error(f"Twilio error: {response.text}")
                return False
        except Exception as exc:
            logger.error(f"Failed to send SMS via Twilio: {exc}")
            return False


mock_sms_instance = MockSMSProvider()


def get_sms_provider() -> BaseSMSProvider:
    provider_name = settings.SMS_PROVIDER.lower().strip()
    if provider_name == "fast2sms":
        return Fast2SMSProvider()
    elif provider_name == "twilio":
        return TwilioSMSProvider()
    return mock_sms_instance
