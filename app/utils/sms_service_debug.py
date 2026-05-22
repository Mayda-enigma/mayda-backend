import os
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
        
        print(f"[DEBUG] SMS Service initializing...")
        print(f"[DEBUG] Environment: {self.environment}")
        print(f"[DEBUG] Account SID: {self.account_sid[:10]}..." if self.account_sid else "❌ No Account SID")
        print(f"[DEBUG] Phone Number: {self.phone_number}")
        
        # Always try to initialize Twilio client if credentials exist
        if self.account_sid and self.auth_token and self.phone_number:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                print("✅ Twilio client initialized - will attempt real API calls")
            except Exception as e:
                print(f"❌ Failed to initialize Twilio client: {e}")
                self.client = None
        else:
            print("⚠️ Missing Twilio credentials - SMS will be simulated")
            self.client = None
    
    def send_sms(self, to_phone: str, message: str) -> dict:
        """
        Send SMS message using exact Twilio example code.
        
        Returns:
            dict: Detailed response with success status and Twilio details
        """
        try:
            print(f"[DEBUG] Attempting to send SMS to: {to_phone}")
            print(f"[DEBUG] Message: {message}")
            
            # Use the exact Twilio example pattern
            account_sid = settings.TWILIO_ACCOUNT_SID
            auth_token = settings.TWILIO_AUTH_TOKEN
            client = Client(account_sid, auth_token)
            
            # Smart phone number formatting
            if not to_phone.startswith('+'):
                # If the number already starts with 213, just add +
                if to_phone.startswith('213'):
                    formatted_phone = f"+{to_phone}"
                # If it's a local Algerian number (starts with 0), format it
                elif to_phone.startswith('0'):
                    formatted_phone = f"+213{to_phone[1:]}"  # Remove leading 0
                # If it's already without country code, add +213
                else:
                    formatted_phone = f"+213{to_phone}"
                
                print(f"[DEBUG] Formatted phone: {to_phone} -> {formatted_phone}")
                to_phone = formatted_phone
            
            print(f"[REAL SMS] Sending via Twilio to {to_phone}...")
            print(f"[REAL SMS] From: {settings.TWILIO_PHONE_NUMBER}")
            
            # Use exact Twilio example structure
            sms_message = client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=to_phone
            )
            
            print(f"[SUCCESS] SMS Body: {sms_message.body}")
            
            result = {
                "success": True,
                "sid": sms_message.sid,
                "status": sms_message.status,
                "to": sms_message.to,
                "from": sms_message.from_,
                "body": sms_message.body,
                "error_code": sms_message.error_code,
                "error_message": sms_message.error_message,
                "price": getattr(sms_message, 'price', None),
                "price_unit": getattr(sms_message, 'price_unit', None)
            }
            print(f"✅ SMS sent! Result: {result}")
            return result
            
        except TwilioException as e:
            result = {
                "success": False,
                "error_type": "TwilioException",
                "error_code": getattr(e, 'code', 'unknown'),
                "error_message": str(e),
                "details": getattr(e, 'details', None),
                "more_info": getattr(e, 'more_info', None)
            }
            print(f"❌ Twilio error: {result}")
            return result
        except Exception as e:
            result = {
                "success": False,
                "error_type": "Exception",
                "error_message": str(e),
                "error_class": e.__class__.__name__
            }
            print(f"❌ SMS sending error: {result}")
            return result
    
    def generate_otp_code(self, length: int = 6) -> str:
        """Generate a random OTP code."""
        return ''.join(random.choices(string.digits, k=length))
    
    async def send_otp(self, user_id: int, phone: str, purpose: str = "STAFF_AUTH") -> dict:
        """
        Generate and send OTP code to user.
        
        Returns:
            dict: Result with success status and SMS details
        """
        print(f"[DEBUG] send_otp called with user_id={user_id}, phone={phone}, purpose={purpose}")
        
        db = get_db()
        
        try:
            # Generate OTP code
            otp_code = self.generate_otp_code()
            print(f"[OTP] Generated OTP for user {user_id}: {otp_code}")
            
            # Set expiration time (20 minutes from now)
            expires_at = datetime.utcnow() + timedelta(minutes=20)
            
            # Send SMS immediately
            message = f"Your Caravane verification code is: {otp_code}. Valid for 20 minutes."
            print(f"[DEBUG] About to send SMS...")
            sms_result = self.send_sms(str(phone), message)
            print(f"[DEBUG] SMS send result: {sms_result}")
            
            if not sms_result.get("success", False):
                return {
                    "success": False,
                    "error": "Failed to send SMS",
                    "sms_details": sms_result
                }
            
            # Try to save to database (but don't fail if it doesn't work)
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
            
            return {
                "success": True,
                "otp_code": otp_code,  # For debugging only
                "sms_details": sms_result
            }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error sending OTP: {e}",
                "error_type": e.__class__.__name__
            }
    
    async def verify_otp(self, user_id: int, code: str, purpose: str = "STAFF_AUTH") -> bool:
        """
        Verify OTP code for user.
        """
        # In development mode, accept hardcoded OTP for testing
        if self.environment == 'development' and code == "123456":
            print(f"[DEVELOPMENT] Accepting hardcoded OTP for user {user_id}")
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
                print("[DEVELOPMENT] Database error - checking for hardcoded OTP")
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
