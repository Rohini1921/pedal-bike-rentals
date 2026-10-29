import os
from functools import wraps
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv
from flask import (
    Flask, request, jsonify, render_template,
    redirect, url_for, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-local-secret")


# ---------------- DATABASE ----------------

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "bike_rental")
    )


# ---------------- ACCESS CONTROL ----------------

def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return function(*args, **kwargs)
    return wrapper


def customer_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Please log in first"}), 401
        return function(*args, **kwargs)
    return wrapper


# ---------------- WEBSITE PAGES ----------------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login")
def login_page():
    return render_template("auth.html", mode="login")


@app.route("/signup")
def signup_page():
    return render_template("auth.html", mode="signup")


@app.route("/admin/signup")
def admin_signup_page():
    return render_template("auth.html", mode="signup", account_type="admin")


# ---------------- CUSTOMER SESSION ----------------

@app.route("/api/session")
def api_session():
    user = None
    if session.get("user_id"):
        user = {
            "user_id": session["user_id"],
            "full_name": session.get("full_name"),
            "email": session.get("email"),
        }
    return jsonify({
        "logged_in": bool(session.get("user_id")),
        "authenticated": bool(session.get("user_id")),
        "user_id": session.get("user_id"),
        "full_name": session.get("full_name"),
        "email": session.get("email"),
        "user": user,
    })


@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json(silent=True) or request.form

    full_name = str(data.get("full_name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", ""))

    if not full_name or not email or not password:
        return jsonify({"error": "Name, email and password are required"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must contain at least 8 characters"}), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO users (full_name, email, phone, password_hash)
            VALUES (%s, %s, %s, %s)
            """,
            (full_name, email, phone, generate_password_hash(password))
        )
        user_id = cursor.lastrowid
        conn.commit()
        session.clear()
        session["user_id"] = user_id
        session["full_name"] = full_name
        session["email"] = email
        session["role"] = "customer"

        return jsonify({"message": "Account created successfully"}), 201

    except mysql.connector.IntegrityError:
        return jsonify({"error": "This email may already be registered"}), 409

    except mysql.connector.Error as exc:
        app.logger.exception("Signup database error")
        return jsonify({"error": "Database error. Check your database tables."}), 500

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


@app.route("/api/admin-signup", methods=["POST"])
def api_admin_signup():
    data = request.get_json(silent=True) or request.form
    full_name = str(data.get("full_name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", ""))
    if not full_name or not email or not password or len(password) < 8:
        return jsonify({"error": "Name, email and a password of at least 8 characters are required."}), 400

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (full_name, email, phone, password_hash, role)
            VALUES (%s, %s, %s, %s, 'admin')
            """,
            (full_name, email, phone, generate_password_hash(password)),
        )
        conn.commit()
        return jsonify({"message": "Admin account created successfully."}), 201
    except mysql.connector.IntegrityError:
        return jsonify({"error": "This email may already be registered."}), 409
    except mysql.connector.Error:
        app.logger.exception("Admin signup database error")
        return jsonify({"error": "Could not create the admin account."}), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or request.form
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_id, full_name, email, password_hash, role FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Invalid email or password"}), 401

        session.clear()
        session["user_id"] = user["user_id"]
        session["full_name"] = user["full_name"]
        session["email"] = user["email"]
        session["role"] = user.get("role", "customer")

        return jsonify({"message": "Login successful"})

    except mysql.connector.Error:
        app.logger.exception("Login database error")
        return jsonify({"error": "Could not connect to the database"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


@app.route("/api/admin-login", methods=["POST"])
def api_admin_login():
    data = request.get_json(silent=True) or request.form
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_id, full_name, email, password_hash FROM users WHERE email = %s AND role = 'admin'",
            (email,),
        )
        admin = cursor.fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["is_admin"] = True
            session["admin_email"] = admin["email"]
            return jsonify({"message": "Admin login successful."})

        configured_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        configured_password = os.getenv("ADMIN_PASSWORD", "")
        if email == configured_email and password == configured_password and configured_email and configured_password:
            session.clear()
            session["is_admin"] = True
            session["admin_email"] = configured_email
            return jsonify({"message": "Admin login successful."})
        return jsonify({"error": "Invalid admin email or password."}), 401
    except mysql.connector.Error:
        app.logger.exception("Admin login database error")
        return jsonify({"error": "Could not connect to the database."}), 500
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


# ---------------- BIKES API ----------------

@app.route("/api/bikes")
def api_bikes():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT bike_id, name, category, description,
                   hourly_rate, image_url, status
            FROM bikes
            ORDER BY bike_id DESC
        """)
        bikes = cursor.fetchall()

        for bike in bikes:
            if bike.get("hourly_rate") is not None:
                bike["hourly_rate"] = float(bike["hourly_rate"])

        return jsonify(bikes)

    except mysql.connector.Error:
        app.logger.exception("Could not load bikes")
        return jsonify({"error": "Could not load bikes"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


# ---------------- BOOKINGS API ----------------

@app.route("/api/bookings", methods=["GET", "POST"])
@customer_required
def api_bookings():
    user_id = session["user_id"]
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == "GET":
            cursor.execute("""
                SELECT r.rental_id, r.bike_id, b.name AS bike_name,
                       r.start_time, r.end_time, r.status
                FROM rentals r
                JOIN customers c ON c.customer_id = r.customer_id
                JOIN bikes b ON b.bike_id = r.bike_id
                JOIN users u ON u.email = c.email
                WHERE u.user_id = %s
                ORDER BY r.rental_id DESC
            """, (user_id,))
            bookings = cursor.fetchall()

            for booking in bookings:
                for key in ("start_time", "end_time"):
                    if booking.get(key):
                        booking[key] = booking[key].isoformat(
                            sep=" ", timespec="minutes"
                        )

            return jsonify(bookings)

        data = request.get_json(silent=True) or request.form

        bike_id = data.get("bike_id")
        start_time = data.get("start_time")
        end_time = data.get("end_time")

        if not bike_id or not start_time or not end_time:
            return jsonify({
                "error": "Bike, start time and end time are required"
            }), 400

        try:
            start = datetime.fromisoformat(str(start_time))
            end = datetime.fromisoformat(str(end_time))
        except ValueError:
            return jsonify({"error": "Invalid date/time format"}), 400

        if end <= start:
            return jsonify({"error": "End time must be after start time"}), 400

        cursor.execute(
            "SELECT full_name, email, phone FROM users WHERE user_id = %s",
            (user_id,)
        )
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "User not found"}), 404

        cursor.execute(
            "SELECT customer_id FROM customers WHERE email = %s",
            (user["email"],)
        )
        customer = cursor.fetchone()

        if customer:
            customer_id = customer["customer_id"]
            cursor.execute("""
                UPDATE customers
                SET full_name = %s, phone = %s
                WHERE customer_id = %s
            """, (user["full_name"], user["phone"], customer_id))
        else:
            cursor.execute("""
                INSERT INTO customers (full_name, email, phone)
                VALUES (%s, %s, %s)
            """, (user["full_name"], user["email"], user["phone"]))
            customer_id = cursor.lastrowid

        # Lock the bike row while checking availability.
        cursor.execute(
            "SELECT status FROM bikes WHERE bike_id = %s FOR UPDATE",
            (bike_id,)
        )
        bike = cursor.fetchone()

        if not bike or bike["status"] != "available":
            conn.rollback()
            return jsonify({"error": "Bike is not available"}), 409

        cursor.execute("""
            SELECT rental_id FROM rentals
            WHERE bike_id = %s
              AND status = 'confirmed'
              AND start_time < %s
              AND end_time > %s
            LIMIT 1
        """, (bike_id, end, start))

        if cursor.fetchone():
            conn.rollback()
            return jsonify({"error": "Bike is already booked for that time"}), 409

        cursor.execute("""
            INSERT INTO rentals (customer_id, bike_id, start_time, end_time, status)
            VALUES (%s, %s, %s, %s, 'confirmed')
        """, (customer_id, bike_id, start, end))

        rental_id = cursor.lastrowid
        conn.commit()

        return jsonify({
            "message": "Booking created",
            "rental_id": rental_id
        }), 201

    except mysql.connector.Error:
        if conn and conn.is_connected():
            conn.rollback()
        app.logger.exception("Booking database error")
        return jsonify({"error": "Booking failed. Check your database schema."}), 500

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


# ==================================================
#                  ADMIN PANEL
# ==================================================

@app.route("/admin")
@admin_required
def admin_home():
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        email = str(request.form.get("email", "")).strip().lower()
        password = str(request.form.get("password", ""))

        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT email, password_hash
                FROM users
                WHERE email = %s AND role = 'admin'
                """,
                (email,),
            )
            admin = cursor.fetchone()
            if admin and check_password_hash(admin["password_hash"], password):
                session.clear()
                session["is_admin"] = True
                session["admin_email"] = admin["email"]
                return redirect(url_for("admin_dashboard"))
        except mysql.connector.Error:
            app.logger.exception("Database admin login error")
            flash("Admin login is temporarily unavailable.", "error")
            return render_template("admin_login.html")
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

        admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        admin_password = os.getenv("ADMIN_PASSWORD", "")

        if (
            admin_email
            and admin_password
            and email == admin_email
            and password == admin_password
        ):
            session.clear()
            session["is_admin"] = True
            session["admin_email"] = admin_email
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin email or password.", "error")

    return render_template("admin_login.html")


@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total FROM bikes")
        total_bikes = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM customers")
        total_customers = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM rentals")
        total_bookings = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT bike_id, name, category, hourly_rate, status
            FROM bikes ORDER BY bike_id DESC
        """)
        bikes = cursor.fetchall()

        cursor.execute("""
            SELECT customer_id, full_name, email, phone
            FROM customers ORDER BY customer_id DESC
        """)
        customers = cursor.fetchall()

        cursor.execute("""
            SELECT r.rental_id, c.full_name AS customer_name,
                   c.email AS customer_email, c.phone AS customer_phone,
                   b.name AS bike_name, r.start_time, r.end_time, r.status
            FROM rentals r
            JOIN customers c ON c.customer_id = r.customer_id
            JOIN bikes b ON b.bike_id = r.bike_id
            ORDER BY r.rental_id DESC
        """)
        bookings = cursor.fetchall()

        for booking in bookings:
            for key in ("start_time", "end_time"):
                if booking.get(key):
                    booking[key] = booking[key].strftime("%Y-%m-%d %H:%M")

        return render_template(
            "admin_dashboard.html",
            total_bikes=total_bikes,
            total_customers=total_customers,
            total_bookings=total_bookings,
            bikes=bikes,
            customers=customers,
            bookings=bookings
        )

    except mysql.connector.Error:
        app.logger.exception("Admin dashboard database error")
        return (
            "Database error. Check that MySQL is running and the "
            "bike_rental database and required tables exist.",
            500
        )

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


@app.route("/admin/bikes/add", methods=["POST"])
@admin_required
def admin_add_bike():
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    image_url = request.form.get("image_url", "").strip()
    hourly_rate = request.form.get("hourly_rate", "").strip()

    if not name or not category or not hourly_rate:
        flash("Bike name, category and hourly rate are required.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        hourly_rate = float(hourly_rate)
        if hourly_rate < 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid hourly rate.", "error")
        return redirect(url_for("admin_dashboard"))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bikes
                (name, category, description, hourly_rate, image_url, status)
            VALUES (%s, %s, %s, %s, %s, 'available')
        """, (name, category, description, hourly_rate, image_url))
        conn.commit()
        flash("Bike added successfully.", "success")

    except mysql.connector.Error:
        if conn and conn.is_connected():
            conn.rollback()
        app.logger.exception("Could not add bike")
        flash("Could not add bike. Check the database table columns.", "error")

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/bikes/<int:bike_id>/status", methods=["POST"])
@admin_required
def admin_update_bike_status(bike_id):
    status = request.form.get("status", "").strip().lower()

    if status not in ("available", "unavailable", "maintenance"):
        flash("Invalid bike status.", "error")
        return redirect(url_for("admin_dashboard"))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE bikes SET status = %s WHERE bike_id = %s",
            (status, bike_id)
        )
        conn.commit()

        if cursor.rowcount:
            flash("Bike status updated.", "success")
        else:
            flash("Bike not found or status unchanged.", "error")

    except mysql.connector.Error:
        if conn and conn.is_connected():
            conn.rollback()
        app.logger.exception("Could not update bike status")
        flash("Could not update bike status.", "error")

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

    return redirect(url_for("admin_dashboard"))


# ---------------- START SERVER ----------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=os.getenv("FLASK_DEBUG", "0") == "1"
    )