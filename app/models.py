from datetime import datetime
import uuid
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    user_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    national_id = db.Column(db.String(20), unique=True, nullable=False)
    kra_pin_enc = db.Column(db.String(255), nullable=False)  # Encrypted KRA PIN
    role = db.Column(db.String(20), default='motorist')      # motorist, fleet_admin, underwriter, admin
    kyc_status = db.Column(db.String(20), default='pending') # pending, verified
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    vehicles = db.relationship('Vehicle', backref='owner', lazy=True, cascade='all, delete-orphan')

class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    
    vehicle_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False)
    reg_number = db.Column(db.String(20), unique=True, nullable=False)  # e.g., KBC 123A
    chassis_no = db.Column(db.String(50), unique=True, nullable=False)
    make_model = db.Column(db.String(100), nullable=False)
    cover_type = db.Column(db.String(20), nullable=False)              # TPO or Comprehensive
    expiry_date = db.Column(db.DateTime, nullable=False)
    dmvic_cert_no = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    wallet = db.relationship('SinkingWallet', backref='vehicle', uselist=False, cascade='all, delete-orphan')
    renewal_job = db.relationship('RenewalJob', backref='vehicle', uselist=False, cascade='all, delete-orphan')

class SinkingWallet(db.Model):
    __tablename__ = 'sinking_wallets'
    
    wallet_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_id = db.Column(db.String(36), db.ForeignKey('vehicles.vehicle_id'), nullable=False)
    current_balance = db.Column(db.Numeric(10, 2), default=0.00)
    target_premium = db.Column(db.Numeric(10, 2), nullable=False)
    monthly_deduction = db.Column(db.Numeric(10, 2), nullable=False)
    payday_date = db.Column(db.Integer, nullable=False)                # Day of month (e.g., 25)
    mandate_status = db.Column(db.String(20), default='active')       # active, paused, completed
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    transactions = db.relationship('LedgerTransaction', backref='wallet', lazy=True, cascade='all, delete-orphan')

class LedgerTransaction(db.Model):
    __tablename__ = 'ledger_transactions'
    
    tx_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_id = db.Column(db.String(36), db.ForeignKey('sinking_wallets.wallet_id'), nullable=False)
    tx_type = db.Column(db.String(10), nullable=False)                  # CREDIT or DEBIT
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    provider_ref = db.Column(db.String(100), unique=True, nullable=False) # M-Pesa receipt or bank ref
    idempotency_key = db.Column(db.String(64), unique=True, nullable=False)
    status = db.Column(db.String(20), default='success')               # success, failed, pending
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RenewalJob(db.Model):
    __tablename__ = 'renewal_jobs'
    
    job_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_id = db.Column(db.String(36), db.ForeignKey('vehicles.vehicle_id'), nullable=False)
    day_7_alert_sent = db.Column(db.Boolean, default=False)
    day_3_alert_sent = db.Column(db.Boolean, default=False)
    day_2_autopay_status = db.Column(db.String(20), default='pending') # pending, success, failed
    user_override_flag = db.Column(db.Boolean, default=False)          # True if user manually renewed or cancelled
    new_policy_no = db.Column(db.String(50), nullable=True)
    certificate_url = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)