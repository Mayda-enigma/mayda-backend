import random
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy import update as sa_update
from twilio.base.exceptions import TwilioException
from twilio.rest import Client

from app.core.config import settings
from app.core.database import get_db
from app.models.sqlalchemy_models import OtpCode, OtpPurpose
from app.utils.logging import logger


class SMSService:
    """Service for sending SMS messages using Twilio."""

    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.phone_number = settings.TWILIO_PHONE_NUMBER
        self.environment = getattr(settings, "ENVIRONMENT", "development")

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
            logger.warning("Missing Twilio credentials - SMS will be simulated")
            self.client = None

    def _format_phone_number(self, to_phone: str) -> str:
        """Format local phone numbers for Twilio delivery."""
        if to_phone.startswith("+"):
            return to_phone
        if to_phone.startswith("213"):
            return f"+{to_phone}"
        if to_phone.startswith("0"):
            return f"+213{to_phone[1:]}"
        return f"+213{to_phone}"

    def send_sms(self, to_phone: str, message: str) -> dict:
        """Send SMS message using Twilio and return a detailed result."""
        try:
            logger.debug("Attempting to send SMS to: {}", to_phone)
            formatted_phone = self._format_phone_number(to_phone)
            logger.debug("Formatted phone: {} -> {}", to_phone, formatted_phone)

            if self.client:
                logger.info("Sending SMS via Twilio to {}", formatted_phone)

                sms_message = self.client.messages.create(
                    body=message,
                    from_=self.phone_number,
                    to=formatted_phone,
                )

                result = {
                    "success": True,
                    "sid": sms_message.sid,
                    "status": sms_message.status,
                    "to": sms_message.to,
                    "from": sms_message.from_,
                    "body": sms_message.body,
                    "error_code": sms_message.error_code,
                    "error_message": sms_message.error_message,
                    "price": getattr(sms_message, "price", None),
                    "price_unit": getattr(sms_message, "price_unit", None),
                }
                logger.info("SMS sent successfully: {}", result)
                return result

            result = {
                "success": True,
                "simulated": True,
                "to": formatted_phone,
                "from": self.phone_number,
                "body": message,
            }
            logger.info("Simulated SMS send: {}", result)
            return result

        except TwilioException as e:
            result = {
                "success": False,
                "error_type": "TwilioException",
                "error_code": getattr(e, "code", "unknown"),
                "error_message": str(e),
                "details": getattr(e, "details", None),
                "more_info": getattr(e, "more_info", None),
            }
            logger.error("Twilio error: {}", result)
            return result
        except Exception as e:
            result = {
                "success": False,
                "error_type": "Exception",
                "error_message": str(e),
                "error_class": e.__class__.__name__,
            }
            logger.error("SMS sending error: {}", result)
            return result

    def generate_otp_code(self, length: int = 6) -> str:
        """Generate a random OTP code."""
        return "".join(random.choices(string.digits, k=length))

    async def send_otp(self, user_id: int, phone: str, purpose: str = "STAFF_AUTH") -> dict:
        """Generate and send OTP code to user."""
        logger.debug("send_otp called: user_id={}, phone={}, purpose={}", user_id, phone, purpose)

        db = await get_db()

        try:
            otp_code = self.generate_otp_code()
            logger.debug("Generated OTP for user {}: {}", user_id, otp_code)

            expires_at = datetime.now(timezone.utc) + timedelta(minutes=20)
            message = f"Your Caravane verification code is: {otp_code}. Valid for 20 minutes."
            sms_result = self.send_sms(str(phone), message)
            logger.debug("SMS send result: {}", sms_result)

            if not sms_result.get("success", False):
                logger.error("Failed to send OTP SMS to user {}", user_id)
                await db.close()
                return {
                    "success": False,
                    "error": "Failed to send SMS",
                    "sms_details": sms_result,
                }

            try:
                await db.execute(
                    sa_update(OtpCode)
                    .where(
                        OtpCode.userId == user_id,
                        OtpCode.purpose == OtpPurpose(purpose),
                        OtpCode.isUsed == False,
                    )
                    .values(isUsed=True)
                )
                await db.commit()

                otp_record = OtpCode(
                    userId=user_id,
                    code=otp_code,
                    purpose=OtpPurpose(purpose),
                    expiresAt=expires_at,
                )
                db.add(otp_record)
                await db.commit()
                await db.refresh(otp_record)
                logger.info("OTP saved to database with ID: {}", otp_record.id)
            except Exception as db_error:
                await db.rollback()
                logger.warning("Could not save OTP to database: {}", db_error)

            return {
                "success": True,
                "otp_code": otp_code,
                "sms_details": sms_result,
            }

        except Exception as e:
            logger.error("Error sending OTP: {}", e)
            return {
                "success": False,
                "error": f"Error sending OTP: {e}",
                "error_type": e.__class__.__name__,
            }
        finally:
            await db.close()

    async def verify_otp(self, user_id: int, code: str, purpose: str = "STAFF_AUTH") -> bool:
        """Verify OTP code for user."""
        if self.environment == "development" and code == "123456":
            logger.debug("[DEVELOPMENT] Accepting hardcoded OTP for user {}", user_id)
            return True

        db = await get_db()

        try:
            result = await db.execute(
                select(OtpCode).where(
                    OtpCode.userId == user_id,
                    OtpCode.code == code,
                    OtpCode.purpose == OtpPurpose(purpose),
                    OtpCode.isUsed == False,
                    OtpCode.expiresAt > datetime.now(timezone.utc),
                )
            )
            otp_record = result.scalar_one_or_none()

            if otp_record:
                otp_record.isUsed = True
                await db.commit()
                return True

            return False

        except Exception as e:
            logger.error("Error verifying OTP: {}", e)
            if self.environment == "development":
                logger.debug("[DEVELOPMENT] Database error - checking for hardcoded OTP")
                return code == "123456"
            return False
        finally:
            await db.close()


def get_sms_service() -> SMSService | None:
    """Get SMS service instance if properly configured."""
    try:
        return SMSService()
    except ValueError:
        logger.warning("SMS service not available - Twilio not configured")
        return None


sms_service = get_sms_service()
