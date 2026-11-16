from datetime import datetime, timedelta
from app.models import db, Vehicle, SinkingWallet, RenewalJob

def evaluate_renewal_lifecycle():
    """Background job executed daily by Celery / Cron."""
    now = datetime.utcnow()
    window_7_days = now + timedelta(days=7)
    window_2_days = now + timedelta(days=2)
    
    # 1. Process Day -7 Primary Alerts
    expiring_soon = Vehicle.query.filter(Vehicle.expiry_date <= window_7_days, Vehicle.expiry_date > window_2_days).all()
    for vehicle in expiring_soon:
        job = RenewalJob.query.filter_by(vehicle_id=vehicle.vehicle_id).first()
        if job and not job.day_7_alert_sent:
            # Trigger WhatsApp / SMS quote & readiness notification
            print(f"Sending Day -7 Renewal Quote Alert for Vehicle: {vehicle.reg_number}")
            job.day_7_alert_sent = True
            db.session.commit()
            
    # 2. Process Day -2 Fail-Safe Auto-Renewals
    fail_safe_window = Vehicle.query.filter(Vehicle.expiry_date <= window_2_days, Vehicle.expiry_date > now).all()
    for vehicle in fail_safe_window:
        job = RenewalJob.query.filter_by(vehicle_id=vehicle.vehicle_id).first()
        wallet = SinkingWallet.query.filter_by(vehicle_id=vehicle.vehicle_id).first()
        
        if job and wallet and not job.user_override_flag and job.day_2_autopay_status == 'pending':
            if float(wallet.current_balance) >= float(wallet.target_premium):
                print(f"Executing Day -2 Fail-Safe Auto-Renewal for Vehicle: {vehicle.reg_number}")
                # TODO: Transmit policy binding request to Underwriter API
                job.day_2_autopay_status = 'success'
                job.new_policy_no = f"POL-{datetime.utcnow().year}-{vehicle.reg_number}"
                job.certificate_url = f"https://api.autocover.co.ke/certificates/{job.new_policy_no}.pdf"
                db.session.commit()
                # TODO: Trigger WhatsApp DMVIC certificate delivery
            else:
                print(f"Wallet shortfall for {vehicle.reg_number}. Triggering emergency STK push.")
                job.day_2_autopay_status = 'failed_shortfall'
                db.session.commit()