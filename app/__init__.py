from app.models import db
from flask import Flask, render_template
from flask_migrate import Migrate

migrate = Migrate()


def create_app():
  app = Flask(__name__)

  # Configuration (pulls from environment or uses local SQLite/PostgreSQL fallback)
  app.config['SQLALCHEMY_DATABASE_URI'] = (
      'sqlite:///autocover.db'  # Change to PostgreSQL URI in production
  )
  app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
  app.config['SECRET_KEY'] = 'autocover-secure-dev-key'

  # Initialize extensions
  db.init_app(app)
  migrate.init_app(app, db)

  # Register Blueprints / Routes
  from app.routes import api_bp, service_bp

  app.register_blueprint(api_bp, url_prefix='/api/v1')
  app.register_blueprint(service_bp, url_prefix='/api/v1')

  # Create database tables automatically on startup
  with app.app_context():
    db.create_all()

  @app.route('/')
  def home():
    return render_template('index.html')

  return app