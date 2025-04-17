      
# SOS Alert & Announcement Platform - Backend

This is the backend service for an SOS Alert and Announcement platform, built with Flask. It provides API endpoints for submitting SOS messages (via web form or dedicated API), managing these messages via an admin dashboard, and handling public announcements. The backend is designed to connect to a PostgreSQL database, suitable for deployment on platforms like Render.

## Table of Contents

*   [Features](#features)
*   [Tech Stack](#tech-stack)
*   [Project Structure](#project-structure)
*   [Setup and Installation](#setup-and-installation)
    *   [Prerequisites](#prerequisites)
    *   [Local Setup](#local-setup)
*   [Configuration](#configuration)
    *   [Environment Variables](#environment-variables)
*   [Running the Application](#running-the-application)
    *   [Local Development](#local-development)
    *   [Production (Render)](#production-render)
*   [Database Management](#database-management)
    *   [Initial Setup](#initial-setup)
    *   [Migrations](#migrations)
*   [API Endpoints](#api-endpoints)
    *   [Authentication](#authentication)
    *   [SOS Messages](#sos-messages)
    *   [Announcements](#announcements)
    *   [Admin/UI Support](#adminui-support)
*   [Deployment (Render)](#deployment-render)
*   [Security Considerations](#security-considerations)

## Features

*   **SOS Message Submission:**
    *   Accepts submissions via a simple web form (`/submit_sos`).
    *   Provides a flexible API endpoint (`/api/v1/sos`) supporting:
        *   **Legacy Format:** Simple `name`, `location` (string), `message`.
        *   **Structured Format:** `location` (object with `latitude`, `longitude`), `disasterType`, optional `details`, `mobileNumber`.
*   **Admin Dashboard Functionality (Backend Support):**
    *   Secure admin login.
    *   View all submitted SOS messages with details (name, location, message, status, source, timestamp, etc.).
    *   Update the status of SOS messages (`Pending`, `Under Review`, `Resolved`, `False Alarm`).
*   **Announcement Management:**
    *   Admin can create, view, update, and delete public announcements.
    *   Endpoint to fetch recent announcements for public display.
*   **Database:** Uses PostgreSQL via Flask-SQLAlchemy ORM.
*   **Deployment Ready:** Configured for deployment on Render using environment variables.

## Tech Stack

*   **Backend:** Python 3.x
*   **Framework:** Flask
*   **Database:** PostgreSQL (Production), SQLite (Optional for basic local testing if PG not available)
*   **ORM:** Flask-SQLAlchemy
*   **Migrations:** Flask-Migrate
*   **Password Hashing:** Flask-Bcrypt
*   **CORS Handling:** Flask-Cors
*   **WSGI Server (Production):** Gunicorn
*   **Database Driver:** psycopg2-binary

## Project Structure (Example)

    



.
├── app.py # Main Flask application file
├── requirements.txt # Python dependencies
├── migrations/ # Flask-Migrate migration files
├── templates/ # HTML templates for web pages (index.html, login.html, etc.)
├── static/ # CSS, JavaScript, images (if serving static files)
├── .env # (Optional, for local development) Environment variables - DO NOT COMMIT
├── .gitignore # Git ignore file
└── README.md


## Setup and Installation

### Prerequisites

*   Python 3.8+
*   `pip` and `virtualenv`
*   PostgreSQL Server (Recommended for local development to match production)
*   Git

### Local Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up PostgreSQL Database (Recommended):**
    *   Ensure PostgreSQL is installed and running.
    *   Create a database and a user for the application.
    *   Grant privileges to the user on the database.
    *   Note the connection details (user, password, host, port, database name).

5.  **Configure Environment Variables:**
    *   Create a `.env` file in the project root (and add `.env` to your `.gitignore`!).
    *   Add the necessary environment variables (see [Configuration](#configuration)). Use your local PostgreSQL details for `DATABASE_URL`.

6.  **Initialize the Database:**
    *   Run the initial database setup command (see [Database Management](#database-management)).
    ```bash
    flask init-db
    # Or, if using Flask-Migrate from the start:
    # flask db init  (only needed once per project)
    # flask db migrate -m "Initial database setup."
    # flask db upgrade
    ```

## Configuration

### Environment Variables

Configure these variables in your environment (e.g., in your `.env` file for local development, or directly in Render's environment settings).

| Variable        | Description                                                                                                  | Example (Local `.env`)                                                      | Required |
| :-------------- | :----------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------- | :------- |
| `DATABASE_URL`  | **Full** connection string for the PostgreSQL database. Render provides this automatically when linked.        | `postgresql://user:password@host:port/dbname`                               | Yes      |
| `SECRET_KEY`    | A strong, random secret key used for session signing and security. **Generate a secure one!**                    | `your-very-strong-random-secret-key-here`                                   | Yes      |
| `FLASK_ENV`     | Set to `development` for local debugging (enables debug mode, reloader). Set to `production` (default) otherwise. | `development`                                                               | No       |
| `FLASK_DEBUG`   | Set to `1` or `True` to explicitly enable debug mode (often controlled by `FLASK_ENV`).                        | `1`                                                                         | No       |
| `PORT`          | Port the application should listen on (Render sets this automatically).                                        | `5000`                                                                      | No       |

**Note:** For local development *without* PostgreSQL, you *could* modify `app.py` to temporarily use a SQLite URI, but it's highly recommended to use PostgreSQL locally to mirror the production environment.

## Running the Application

### Local Development

Ensure your virtual environment is active and environment variables are set.

Basic

    POST /login

        Body (JSON): { "username": "admin", "password": "admin_password" }

        Response: Sets a session cookie on success (200), returns error on failure (401).

    GET /logout

        Response: Clears session cookie (200).

    GET /check_login

        Response: { "logged_in": true/false } (200).

SOS Messages

    POST /submit_sos (Web Form)

        Body: Can be application/x-www-form-urlencoded or application/json.

        Fields: name, location, message.

        Response: Success message (201) or error (400, 500).

    POST /api/v1/sos (API)

        Body (JSON): Accepts two formats:

            Legacy: { "name": "optional name", "location": "Location string", "message": "SOS details" }

            Structured: { "location": {"latitude": 12.34, "longitude": 56.78}, "disasterType": "Flood", "details": "optional details", "mobileNumber": "optional number", "source": "optional source" }

        Response: { "status": "success", "message": "...", "id": <new_sos_id> } (201) or error object (400, 500).

    GET /get_sos_messages (Requires Admin Auth - Currently commented out in code)

        Response: Array of SOS message objects (200) or error (500).

    POST /update_status/<int:sos_id> (Requires Admin Auth - Currently commented out in code)

        Body (JSON): { "status": "Resolved" } (Allowed: Pending, Under Review, Resolved, False Alarm)

        Response: Success message (200) or error (400, 404, 500).

Announcements

    POST /create_announcement (Requires Admin Auth - Currently commented out in code)

        Body (JSON): { "content": "New announcement text" }

        Response: New announcement object (201) or error (400, 500).

    GET /get_announcements

        Response: Array of recent announcement objects (200) or error (500).

    PUT /update_announcement/<int:id> (Requires Admin Auth - Currently commented out in code)

        Body (JSON): { "content": "Updated announcement text" }

        Response: Updated announcement object (200) or error (400, 404, 500).

    DELETE /delete_announcement/<int:id> (Requires Admin Auth - Currently commented out in code)

        Response: Success message (200) or error (404, 500).

Admin/UI Support

    GET / - Renders index.html.

    GET /login_page - Renders login.html.

    GET /dashboard (Requires Admin Auth) - Renders dashboard.html.

Deployment (Render)

    Create PostgreSQL Database: Create a new PostgreSQL instance on Render. Copy the Internal Connection String.

    Create Web Service: Create a new Web Service on Render, connecting it to your Git repository.

    Settings:

        Environment: Python 3

        Build Command: pip install -r requirements.txt

        Start Command: gunicorn app:app (replace app if your Flask instance variable or filename is different)

    Environment Variables:

        Render will automatically add the DATABASE_URL variable (using the External connection string) when you link the database from Step 1 to this web service. The code prioritizes DATABASE_URL.

        Manually add a SECRET_KEY variable with a strong, unique value.

        Optionally add PYTHON_VERSION if you need a specific Python 3 version.

    Deploy: Trigger the first deploy.

    Initialize Database (One Time): After the first successful deploy, open the "Shell" tab for your web service on Render and run:

          
    flask init-db

        

    IGNORE_WHEN_COPYING_START

    Use code with caution. Bash
    IGNORE_WHEN_COPYING_END

    Future Deployments: Subsequent pushes to your connected Git branch will trigger auto-deploys. If you make database model changes, remember to run flask db upgrade in the Render shell after the deployment finishes.

Security Considerations

    Admin Credentials: The default admin credentials (admin/admin) are HIGHLY INSECURE. Change them immediately in app.py or implement a proper user management system.

    Secret Key: Ensure SECRET_KEY is set to a strong, random, and unique value in the production environment and is not hardcoded or committed to Git.

    CORS: The current CORS configuration (origins="*") allows requests from any origin. For production, restrict this to the specific domain(s) of your frontend application.

          
    # Example: Restrict CORS
    # CORS(app, supports_credentials=True, origins=["https://your-frontend-domain.com", "http://localhost:3000"])

        


Input Validation: While basic validation is present, ensure all inputs (especially from the API) are robustly validated and sanitized to prevent injection attacks or unexpected errors.

HTTPS: Ensure Render is configured to use HTTPS for all traffic.

Rate Limiting: Consider adding rate limiting (e.g., using Flask-Limiter) to API endpoints to prevent abuse.

Authentication: The current admin authentication is basic (session-based). Depending on requirements, consider more robust methods like JWT if the API will be consumed by non-browser clients frequently. The commented-out auth checks on admin routes should be re-enabled if security is paramount.
