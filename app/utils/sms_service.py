import random
import string
from datetime import datetime, timedelta
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

from app.core.config import settings
from app.core.database import get_db


class SMSService:
    """Service for sending SMS messages using Twilio."""
    
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.phone_number = settings.TWILIO_PHONE_NUMBER
        self.environment = getattr(settings, 'ENVIRONMENT', 'development')
        
        print("🔍 [DEBUG] SMS Service initializing...")
        print(f"🔍 [DEBUG] Environment: {self.environment}")
        print(f"🔍 [DEBUG] Account SID: {self.account_sid[:10]}..." if self.account_sid else "❌ No Account SID")
        print(f"🔍 [DEBUG] Phone Number: {self.phone_number}")
        
        # Always try to initialize Twilio client if credentials exist
        if self.account_sid and self.auth_token and self.phone_number:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                print("✅ Twilio client initialized successfully")
            except Exception as e:
                print(f"❌ Failed to initialize Twilio client: {e}")
                self.client = None
        else:
            print("⚠️ Missing Twilio credentials - SMS will be simulated")
            self.client = None
    
    def send_sms(self, to_phone: str, message: str) -> bool:
        """
        Send SMS message to a phone number.
        
        Args:
            to_phone: Destination phone number (international format)
            message: Message content
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            print(f"🔍 [DEBUG] Attempting to send SMS to: {to_phone}")
            print(f"🔍 [DEBUG] Client available: {self.client is not None}")
            print(f"🔍 [DEBUG] Message: {message}")
            
            # If we have a Twilio client, try to send real SMS
            if self.client:
                # Ensure phone number is in international format
                if not to_phone.startswith('+'):
                    # Assume Algerian number if no country code
                    formatted_phone = f"+213{to_phone.lstrip('0')}"
                    print(f"🔍 [DEBUG] Formatted phone: {to_phone} -> {formatted_phone}")
                    to_phone = formatted_phone
                
                print(f"� [REAL SMS] Sending via Twilio to {to_phone}...")
                
                sms_message = self.client.messages.create(
                    body=message,
                    from_=self.phone_number,
                    to=to_phone
                )
                
                print(f"✅ SMS sent successfully! SID: {sms_message.sid}")
                return True
            else:
                # Fallback to simulation
                print(f"📱 [SIMULATED] SMS to {to_phone}: {message}")
                return True
            
        except TwilioException as e:
            print(f"❌ Twilio error: {e}")
            return False
        except Exception as e:
            print(f"❌ SMS sending error: {e}")
            return False
    
    def generate_otp_code(self, length: int = 6) -> str:
        """Generate a random OTP code."""
        return ''.join(random.choices(string.digits, k=length))
    
    async def send_otp(self, user_id: int, phone: str, purpose: str = "STAFF_AUTH") -> bool:
        """
        Generate and send OTP code to user.
        
        Args:
            user_id: User ID
            phone: Phone number to send to
            purpose: Purpose of OTP (STAFF_AUTH, PAYMENT_CONFIRMATION, etc.)
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        print(f"🔍 [DEBUG] send_otp called with user_id={user_id}, phone={phone}, purpose={purpose}")
        
        db = get_db()
        
        try:
            # Generate OTP code
            otp_code = self.generate_otp_code()
            print(f"🔍 [DEBUG] Generated OTP: {otp_code}")
            
            # Set expiration time (20 minutes from now)
            expires_at = datetime.utcnow() + timedelta(minutes=20)
            
            # Always log the OTP for debugging
            print(f"🔐 [OTP] Generated OTP for user {user_id}: {otp_code}")
            
            # Send SMS immediately
            message = f"Your Caravane verification code is: {otp_code}. Valid for 20 minutes."
            print("🔍 [DEBUG] About to send SMS...")
            result = self.send_sms(str(phone), message)
            print(f"🔍 [DEBUG] SMS send result: {result}")
            
            if not result:
                print("❌ Failed to send SMS")
                return False
            
            try:
                # Invalidate previous unused OTP codes for this user and purpose
                await db.otpcode.update_many(
                    where={
                        "userId": user_id,
                        "purpose": purpose,
                        "isUsed": False
                    },
                    data={"isUsed": True}
                )
                
                # Create new OTP record
                otp_record = await db.otpcode.create(
                    data={
                        "userId": user_id,
                        "code": otp_code,
                        "purpose": purpose,
                        "expiresAt": expires_at
                    }
                )
                print(f"✅ OTP saved to database with ID: {otp_record.id}")
            except Exception as db_error:
                print(f"⚠️ Could not save OTP to database: {db_error}")
                # Don't fail the SMS sending because of database issues
            
            return True
                
        except Exception as e:
            print(f"Error sending OTP: {e}")
            return False
    
    async def verify_otp(self, user_id: int, code: str, purpose: str = "STAFF_AUTH") -> bool:
        """
        Verify OTP code for user.
        
        Args:
            user_id: User ID
            code: OTP code to verify
            purpose: Purpose of OTP
            
        Returns:
            bool: True if code is valid, False otherwise
        """
        # In development mode, accept hardcoded OTP for testing
        if self.environment == 'development' and code == "123456":
            print(f"🔐 [DEVELOPMENT] Accepting hardcoded OTP for user {user_id}")
            return True
        
        db = get_db()
        
        try:
            # Find valid OTP code
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
                # Mark OTP as used
                await db.otpcode.update(
                    where={"id": otp_record.id},
                    data={"isUsed": True}
                )
                return True
            
            return False
            
        except Exception as e:
            print(f"Error verifying OTP: {e}")
            # In development mode, be more lenient
            if self.environment == 'development':
                print("🔐 [DEVELOPMENT] Database error - checking for hardcoded OTP")
                return code == "123456"
            return False


# Create global SMS service instance
def get_sms_service() -> Optional[SMSService]:
    """Get SMS service instance if properly configured."""
    try:
        return SMSService()
    except ValueError:
        print("SMS service not available - Twilio not configured")
        return None


sms_service = get_sms_service()
