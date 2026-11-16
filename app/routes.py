from app.integrations_service import AutoCoverIntegrationService
from app.models import (
    LedgerTransaction,
    RenewalJob,
    SinkingWallet,
    User,
    Vehicle,
    db,
)
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request

api_bp = Blueprint('api', __name__)
service_bp = Blueprint('service_api', __name__)
daraja_whatsapp = AutoCoverIntegrationService()


@api_bp.route('/health', methods=['GET'])
def health_check():
  return (
      jsonify({
          'status': 'healthy',
          'service': 'AutoCover API',
          'timestamp': datetime.utcnow().isoformat(),
      }),
      200,
  )


@api_bp.route('/vehicles/register', methods=['POST'])
def register_vehicle():
  data = request.get_json()

  try:
    # Verify or create user
    user = User.query.filter_by(phone_number=data.get('phone_number')).first()
    if not user:
      user = User(
          full_name=data.get('full_name'),
          phone_number=data.get('phone_number'),
          email=data.get('email'),
          national_id=data.get('national_id'),
          kra_pin_enc=data.get('kra_pin'),  # In production, encrypt before storing
      )
      db.session.add(user)
      db.session.commit()

    # Register vehicle
    expiry_dt = datetime.strptime(data.get('expiry_date'), '%Y-%m-%d')
    vehicle = Vehicle(
        user_id=user.user_id,
        reg_number=data.get('reg_number').upper(),
        chassis_no=data.get('chassis_no'),
        make_model=data.get('make_model'),
        cover_type=data.get('cover_type'),
        expiry_date=expiry_dt,
    )
    db.session.add(vehicle)
    db.session.commit()

    # Initialize sinking wallet
    target_prem = float(data.get('target_premium'))
    months_remaining = max(1, (expiry_dt - datetime.utcnow()).days // 30)
    monthly_ded = round(target_prem / months_remaining, 2)

    wallet = SinkingWallet(
        vehicle_id=vehicle.vehicle_id,
        target_premium=target_prem,
        monthly_deduction=monthly_ded,
        payday_date=int(data.get('payday_date', 25)),
    )
    db.session.add(wallet)

    # Initialize renewal job tracker
    job = RenewalJob(vehicle_id=vehicle.vehicle_id)
    db.session.add(job)

    db.session.commit()

    return (
        jsonify({
            'message': (
                'Vehicle registered successfully and sinking wallet'
                ' initialized.'
            ),
            'vehicle_id': vehicle.vehicle_id,
            'wallet_id': wallet.wallet_id,
            'monthly_deduction': monthly_ded,
        }),
        201,
    )

  except Exception as e:
    db.session.rollback()
    return jsonify({'error': str(e)}), 400


@api_bp.route('/webhooks/mpesa-ratiba', methods=['POST'])
def mpesa_ratiba_webhook():
  """Handles incoming M-Pesa Ratiba / STK push deposit confirmations."""
  data = request.get_json()

  idempotency_key = data.get('idempotency_key')
  existing_tx = LedgerTransaction.query.filter_by(
      idempotency_key=idempotency_key
  ).first()
  if existing_tx:
    return (
        jsonify({
            'status': 'ignored',
            'message': 'Duplicate transaction already processed.',
        }),
        200,
    )

  try:
    wallet_id = data.get('wallet_id')
    amount = float(data.get('amount'))
    provider_ref = data.get('provider_ref')

    wallet = SinkingWallet.query.get_or_404(wallet_id)
    wallet.current_balance = float(wallet.current_balance) + amount

    tx = LedgerTransaction(
        wallet_id=wallet.wallet_id,
        tx_type='CREDIT',
        amount=amount,
        provider_ref=provider_ref,
        idempotency_key=idempotency_key,
        status='success',
    )
    db.session.add(tx)
    db.session.commit()

    return (
        jsonify(
            {'status': 'success', 'new_balance': float(wallet.current_balance)}
        ),
        200,
    )

  except Exception as e:
    db.session.rollback()
    return jsonify({'error': str(e)}), 400


# ----------------------------------------------------
# Integration Endpoints (Daraja & WhatsApp)
# ----------------------------------------------------


@service_bp.route('/trigger-autopay', methods=['POST'])
def trigger_autopay():
  data = request.get_json()
  phone = data.get('phone')
  amount = data.get('amount')
  reg_no = data.get('reg_number')

  stk_result = daraja_whatsapp.trigger_stk_push(
      phone_number=phone, amount=amount, account_reference=reg_no
  )
  return jsonify(stk_result), 200


@service_bp.route('/dispatch-certificate', methods=['POST'])
def dispatch_certificate():
  data = request.get_json()
  phone = data.get('phone')
  pdf_path = data.get('pdf_path')
  reg_no = data.get('reg_number')

  wa_result = daraja_whatsapp.send_whatsapp_pdf_certificate(
      recipient_phone=phone, pdf_file_path=pdf_path, vehicle_reg=reg_no
  )
  return jsonify(wa_result), 200