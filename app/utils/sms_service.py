import random
import string
from datetime import datetime, timedelta
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

from app.core.config import settings
from app.core.database import get_db
from app.utils.logging import logger


class SMSService:
    """Service for sending SMS messages using Twilio."""

    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.phone_number = settings.TWILIO_PHONE_NUMBER
        self.environment = getattr(settings, 'ENVIRONMENT', 'development')

        logger.debug("SMS Service initializing...")
        logger.debug("Environment: {}", self.environment)
        if self.account_sid:
            logger.debug("Account SID: {}...", self.account_sid[:10])
        else:
            logger.debug("No Account SID configured")
        logger.debug("Phone Number: {}", self.phone_number)

        if self.account_sid and self.auth_token and self.phone_number:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio client initialized successfully")
            except Exception as e:
                logger.error("Failed to initialize Twilio client: {}", e)
                self.client = None
        else:
            logger.warning("Missing Twilio credentials — SMS will be simulated")
            self.client = None

    def send_sms(self, to_phone: str, message: str) -> bool:
        """Send SMS message to a phone number."""
        try:
            logger.debug("Attempting to send SMS to: {}", to_phone)
            logger.debug("Client available: {}", self.client is not None)

            if self.client:
                if not to_phone.startswith('+'):
                    formatted_phone = f"+213{to_phone.lstrip('0')}"
                    logger.debug("Formatted phone: {} -> {}", to_phone, formatted_phone)
                    to_phone = formatted_phone

                logger.info("Sending SMS via Twilio to {}", to_phone)

                sms_message = self.client.messages.create(
                    body=message,
                    from_=self.phone_number,
                    to=to_phone
                )

                logger.info("SMS sent successfully. SID: {}", sms_message.sid)
                return True
            else:
                logger.info("[SIMULATED] SMS to {}: {}", to_phone, message)
                return True

        except TwilioException as e:
            logger.error("Twilio error: {}", e)
            return False
        except Exception as e:
            logger.error("SMS sending error: {}", e)
            return False

    def generate_otp_code(self, length: int = 6) -> str:
        """Generate a random OTP code."""
        return ''.join(random.choices(string.digits, k=length))

    async def send_otp(self, user_id: int, phone: str, purpose: str = "STAFF_AUTH") -> bool:
        """Generate and send OTP code to user."""
        logger.debug("send_otp called: user_id={}, phone={}, purpose={}", user_id, phone, purpose)

        db = get_db()

        try:
            otp_code = self.generate_otp_code()
            logger.debug("Generated OTP for user {}: {}", user_id, otp_code)

            expires_at = datetime.utcnow() + timedelta(minutes=20)

            message = f"Your Caravane verification code is: {otp_code}. Valid for 20 minutes."
            logger.debug("Sending OTP SMS...")
            result = self.send_sms(str(phone), message)
            logger.debug("SMS send result: {}", result)

            if not result:
                logger.error("Failed to send OTP SMS to user {}", user_id)
                return False

            try:
                await db.otpcode.update_many(
                    where={
                        "userId": user_id,
                        "purpose": purpose,
                        "isUsed": False
                    },
                    data={"isUsed": True}
                )

                otp_record = await db.otpcode.create(
                    data={
                        "userId": user_id,
                        "code": otp_code,
                        "purpose": purpose,
                        "expiresAt": expires_at
                    }
                )
                logger.info("OTP saved to database with ID: {}", otp_record.id)
            except Exception as db_error:
                logger.warning("Could not save OTP to database: {}", db_error)

            return True

        except Exception as e:
            logger.error("Error sending OTP: {}", e)
            return False

    async def verify_otp(self, user_id: int, code: str, purpose: str = "STAFF_AUTH") -> bool:
        """Verify OTP code for user."""
        if self.environment == 'development' and code == "123456":
            logger.debug("[DEVELOPMENT] Accepting hardcoded OTP for user {}", user_id)
            return True

        db = get_db()

        try:
            otp_record = await db.otpcode.find_first(
                where={
                    "userId": user_id,
                    "code": code,
                    "purpose": purpose,
                    "isUsed": False,
                    "expiresAt": {"gt": datetime.utcnow()}
                }
            )

            if otp_record:
                await db.otpcode.update(
                    where={"id": otp_record.id},
                    data={"isUsed": True}
                )
                return True

            return False

        except Exception as e:
            logger.error("Error verifying OTP: {}", e)
            if self.environment == 'development':
                logger.debug("[DEVELOPMENT] Database error — checking for hardcoded OTP")
                return code == "123456"
            return False


def get_sms_service() -> Optional[SMSService]:
    """Get SMS service instance if properly configured."""
    try:
        return SMSService()
    except ValueError:
        logger.warning("SMS service not available — Twilio not configured")
        return None


sms_service = get_sms_service()
