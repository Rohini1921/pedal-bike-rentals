# Pedal Bike Rentals

A customer-facing bike rental website built with Flask, MySQL, and plain HTML/CSS/JavaScript.

## Run locally

1. Install MySQL Server and create the sample database:

   ```sql
   SOURCE C:/path/to/project/schema.sql;
   ```

   Alternatively, open `schema.sql` in MySQL Workbench and execute it.
2. Install the Python dependencies:

   ```powershell
   py -m pip install -r requirements.txt
   ```
3. Set the database environment variables in PowerShell, using your MySQL password:

   ```powershell
   $env:DB_HOST = "localhost"
   $env:DB_PORT = "3306"
   $env:DB_USER = "root"
   $env:DB_PASSWORD = "your_mysql_password"
   $env:DB_NAME = "bike_rental"
   ```
4. Start the site:

   ```powershell
   py app.py
   ```
5. Open `http://127.0.0.1:5000`.

The bike list and booking form use the MySQL database. A booking is created in a transaction, and overlapping confirmed bookings for the same bike are rejected.

## Accounts

The schema creates a `users` table for signup/login accounts. Passwords are stored as Werkzeug password hashes, never as plain text. Re-run `schema.sql` in Workbench to create the table if the database already exists. Visit `/signup` to create an account or `/login` to sign in.

For a stable session key, set `FLASK_SECRET_KEY` to a long random value in the environment before starting Flask. For HTTPS deployments, set `SESSION_COOKIE_SECURE=1`.

## Customer and admin accounts

The `/login` and `/signup` pages include an account-type selector. Customer
accounts can be created normally. Admin accounts can be created from `/admin/signup` or by choosing **Admin** on
the home-page signup form. Admins can then sign in from `/admin/login` or
choose **Admin** on the home-page login form.
