from flask import Flask
from app.routes import auth, user, admin
from app.db import init_db

def create_app():
    app = Flask(__name__)
    app.secret_key = 'carbonkey2024'

    # Initialize database with schema and seed data
    init_db()

    app.register_blueprint(auth)
    app.register_blueprint(user)
    app.register_blueprint(admin)

    return app