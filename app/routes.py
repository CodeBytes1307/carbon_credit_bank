from flask import Blueprint, render_template
from app.db import get_db_connection

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT company_id, name, sector, status FROM company;")
    companies = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('dashboard.html', companies=companies)