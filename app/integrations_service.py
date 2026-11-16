import base64
from datetime import datetime
import os
import requests
from requests.auth import HTTPBasicAuth


class AutoCoverIntegrationService:

  def __init__(self):
    # Safaricom Daraja Sandbox/Production Credentials
    self.daraja_consumer_key = os.getenv("DARAJA_CONSUMER_KEY")
    self.daraja_consumer_secret = os.getenv("DARAJA_CONSUMER_SECRET")
    self.business_shortcode = os.getenv(
        "DARAJA_SHORTCODE", "174379"
    )  # Sandbox default Lipa na M-Pesa test shortcode
    self.passkey = os.getenv("DARAJA_PASSKEY")
    self.daraja_env = os.getenv("DARAJA_ENV", "sandbox")  # sandbox or production

    # WhatsApp Cloud API Credentials
    self.whatsapp_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    self.whatsapp_api_version = os.getenv("WHATSAPP_API_VERSION", "v27.0")

    # Set Base URLs
    if self.daraja_env == "production":
      self.auth_url = (
          "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
      )
      self.stk_url = (
          "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
      )
    else:
      self.auth_url = (
          "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
      )
      self.stk_url = (
          "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
      )

  # ----------------------------------------------------
  # 1. SAFARICOM DARAJA API (M-PESA STK PUSH)
  # ----------------------------------------------------
  def get_daraja_access_token(self):
    """Generates an OAuth client credentials access token for Daraja API."""
    try:
      response = requests.get(
          self.auth_url,
          auth=HTTPBasicAuth(
              self.daraja_consumer_key, self.daraja_consumer_secret
          ),
          timeout=30,
      )
      response.raise_for_status()
      return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
      print(f"Error fetching Daraja access token: {e}")
      return None

  def trigger_stk_push(
      self, phone_number: str, amount: float, account_reference: str
  ):
    """Initiates an M-Pesa Express (STK Push) prompt on the customer's phone."""
    access_token = self.get_daraja_access_token()
    if not access_token:
      return {"success": False, "error": "Failed to authenticate with Daraja"}

    # Format Timestamp: YYYYMMDDHHMMSS
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # Generate Password: Base64 encode (Shortcode + Passkey + Timestamp)
    raw_password = f"{self.business_shortcode}{self.passkey}{timestamp}"
    encoded_password = base64.b64encode(raw_password.encode()).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "BusinessShortCode": int(self.business_shortcode),
        "Password": encoded_password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone_number,  # Format: 2547XXXXXXXX
        "PartyB": int(self.business_shortcode),
        "PhoneNumber": phone_number,
        "CallBackURL": os.getenv("DARAJA_CALLBACK_URL"),
        "AccountReference": account_reference,
        "TransactionDesc": "AutoCover Insurance Premium Sinking Fund",
    }

    try:
      response = requests.post(
          self.stk_url, json=payload, headers=headers, timeout=30
      )
      response_data = response.json()

      if response.status_code == 200 and response_data.get("ResponseCode") == "0":
        return {
            "success": True,
            "checkout_request_id": response_data.get("CheckoutRequestID"),
            "merchant_request_id": response_data.get("MerchantRequestID"),
            "customer_message": response_data.get("CustomerMessage"),
        }
      else:
        return {
            "success": False,
            "error": response_data.get(
                "errorMessage", "STK push request rejected"
            ),
        }
    except requests.exceptions.RequestException as e:
      return {"success": False, "error": str(e)}

  # ----------------------------------------------------
  # 2. WHATSAPP CLOUD API (SEND PDF CERTIFICATE)
  # ----------------------------------------------------
  def upload_media_to_whatsapp(self, file_path: str, mime_type: str = "application/pdf"):
    """Uploads a PDF document to Meta's media endpoint to obtain a media ID."""
    upload_url = f"https://graph.facebook.com/{self.whatsapp_api_version}/{self.phone_number_id}/media"
    
    headers = {
        "Authorization": f"Bearer {self.whatsapp_token}"
    }
    
    try:
      with open(file_path, "rb") as file_to_upload:
        files = {
            "file": (os.path.basename(file_path), file_to_upload, mime_type)
        }
        data = {
            "messaging_product": "whatsapp",
            "type": "document"
        }
        
        response = requests.post(upload_url, headers=headers, data=data, files=files, timeout=60)
        response_data = response.json()
        
        if response.status_code == 200 and "id" in response_data:
          return {"success": True, "media_id": response_data["id"]}
        else:
          return {"success": False, "error": response_data}
    except Exception as e:
      return {"success": False, "error": str(e)}

  def send_whatsapp_pdf_certificate(
      self, recipient_phone: str, pdf_file_path: str, vehicle_reg: str
  ):
    """Uploads the DMVIC PDF certificate and delivers it as an interactive WhatsApp document message."""
    # Step 1: Upload the PDF to get a Meta Media ID
    upload_result = self.upload_media_to_whatsapp(pdf_file_path)
    if not upload_result["success"]:
      return {
          "success": False,
          "error": f"Media upload failed: {upload_result['error']}",
      }

    media_id = upload_result["media_id"]
    filename = f"DMVIC_Certificate_{vehicle_reg.replace(' ', '_')}.pdf"
    caption = (
        f"✅ Your motor insurance policy for vehicle *{vehicle_reg}* has been"
        " successfully renewed!\n\nAttached is your official AKI DMVIC digital"
        " certificate."
    )

    # Step 2: Send the document message via WhatsApp Messages API
    messages_url = f"https://graph.facebook.com/{self.whatsapp_api_version}/{self.phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {self.whatsapp_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_phone,
        "type": "document",
        "document": {
            "id": media_id,
            "caption": caption,
            "filename": filename,
        },
    }

    try:
      response = requests.post(
          messages_url, json=payload, headers=headers, timeout=30
      )
      response_data = response.json()

      if response.status_code == 200 and "messages" in response_data:
        return {"success": True, "message_id": response_data["messages"][0]["id"]}
      else:
        return {"success": False, "error": response_data}
    except requests.exceptions.RequestException as e:
      return {"success": False, "error": str(e)}