from flask import Blueprint, render_template, request, redirect, url_for, session
from app.db import get_db_connection

auth = Blueprint("auth", __name__)


@auth.route("/")
def index():
    return render_template("index.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        if session.get("role") == "ADMIN":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("user.dashboard"))

    error = None

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT u.user_id, u.role, c.name, u.company_id
            FROM users u
            JOIN company c ON u.company_id = c.company_id
            WHERE u.email = %s AND u.password = %s
            """,
            (email, password),
        )

        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session["user_id"] = str(user[0])
            session["role"] = user[1]
            session["company_name"] = user[2]
            session["company_id"] = str(user[3])

            if session["role"] == "ADMIN":
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("user.dashboard"))

        error = "Invalid email or password"

    return render_template("login.html", error=error)


@auth.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
