import traceback
import os
from flask import Flask, request, jsonify, session, render_template, redirect, url_for, cli
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_migrate import Migrate
from datetime import datetime, timedelta

app = Flask(__name__)

# --- Configuration ---

# === DATABASE CONFIGURATION START ===
# Get the database URL from the environment variable (Render standard)
database_url = os.environ.get('DATABASE_URL')

# Optional: Fallback to the specific internal URL if DATABASE_URL isn't set
# This might be useful if you want to force the internal URL even if Render provides the external one in DATABASE_URL
# OR if running locally without setting DATABASE_URL.
# Consider setting a dedicated env var like INTERNAL_DATABASE_URL in Render if you *must* use the internal one.
if not database_url:
    print("WARNING: DATABASE_URL environment variable not found. Falling back to hardcoded internal URL (ensure this is correct for your environment).")
    # The internal URL you provided:
    database_url = "postgresql://disaster_db_xdtu_user:loFkGpxAIXTNwKfqCD1x10kgsJJxkWV1@dpg-cvi54jd2ng1s73a1evpg-a/disaster_db_xdtu"
    # If using the hardcoded fallback locally, ensure you have PostgreSQL running and the DB exists.

# Ensure the URI starts with postgresql:// for SQLAlchemy compatibility
# Render's DATABASE_URL might start with postgres://
if database_url and database_url.startswith("postgres://"):
     database_url = database_url.replace("postgres://", "postgresql://", 1)

if not database_url:
     # If still no database_url after checks, raise an error.
     raise ValueError("Database URI is not configured. Set the DATABASE_URL environment variable or check the hardcoded fallback.")

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
# === DATABASE CONFIGURATION END ===

# IMPORTANT: Set SECRET_KEY as an environment variable in Render.
# The fallback value here is INSECURE and only for basic local testing if env var isn't set.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-me-in-render-environment-variables-to-something-secure')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Optional: Set SQLALCHEMY_ECHO to True for debugging SQL queries locally if needed
# app.config['SQLALCHEMY_ECHO'] = os.environ.get('SQLALCHEMY_ECHO', 'False').lower() == 'true'


# --- Extensions Initialization ---
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
# Allow requests from any origin for prototype, restrict later if needed.
CORS(app, supports_credentials=True, origins="*")
migrate = Migrate(app, db) # Keep Flask-Migrate for future schema changes

# --- Database Models ---
# NO CHANGES NEEDED HERE - SQLAlchemy ORM models are generally database-agnostic
class SOSMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True, default='Anonymous')
    location = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    source = db.Column(db.String(50), default='web')
    mobile_number = db.Column(db.String(20), nullable=True)
    disaster_type = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<SOSMessage {self.id} - {self.name} - {self.status}>'

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Announcement {self.id}>'

# --- Admin Credentials (Kept as is) ---
ADMIN_USERNAME = 'admin'
try:
    ADMIN_PASSWORD_HASH = bcrypt.generate_password_hash('admin').decode('utf-8')
except Exception as e:
    print(f"Warning: Could not generate admin password hash - {e}")
    ADMIN_PASSWORD_HASH = None

# --- Helper Functions ---
def is_admin():
    """Checks if the current session user is the admin."""
    return 'user' in session and session.get('user') == ADMIN_USERNAME

# --- Routes ---
# NO CHANGES NEEDED IN ROUTE LOGIC, assuming correct ORM usage

# Basic Pages & Auth
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login_page')
def login_page():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not is_admin():
        return redirect(url_for('login_page'))
    return render_template('dashboard.html')

@app.route('/check_login')
def check_login():
    return jsonify({'logged_in': is_admin()})

@app.route('/logout')
def logout():
    session.pop('user', None)
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/login', methods=['POST'])
def login():
    if not request.is_json:
        return jsonify({"message": "Request must be JSON"}), 400
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Missing username or password'}), 400

    if ADMIN_PASSWORD_HASH and username == ADMIN_USERNAME and bcrypt.check_password_hash(ADMIN_PASSWORD_HASH, password):
        session['user'] = username
        session.permanent = True
        app.permanent_session_lifetime = timedelta(days=1)
        return jsonify({'message': 'Login successful', 'logged_in': True}), 200
    else:
        return jsonify({'message': 'Invalid Credentials', 'logged_in': False}), 401

# --- SOS Submission Routes ---

@app.route('/submit_sos', methods=['POST'])
def submit_sos_web():
    try:
        if request.is_json:
            data = request.get_json()
            name = data.get('name')
            location = data.get('location')
            message = data.get('message')
        elif request.form:
            data = request.form
            name = data.get('name')
            location = data.get('location')
            message = data.get('message')
        else:
             return jsonify({'message': 'Unsupported content type or no data provided'}), 400

        if not name or not location or not message:
             return jsonify({'message': 'Missing required fields (name, location, message)'}), 400
        if not isinstance(name, str) or not isinstance(location, str) or not isinstance(message, str):
             return jsonify({'message': 'Invalid data types for name, location, or message'}), 400

        new_sos = SOSMessage(
            name=name.strip(),
            location=location.strip(),
            message=message.strip(),
            status='Pending',
            source='web'
        )
        db.session.add(new_sos)
        db.session.commit()
        print(f"Successfully saved SOS from web form: ID {new_sos.id}")
        if request.is_json:
            return jsonify({'message': 'SOS submitted successfully via web form', 'id': new_sos.id}), 201
        else:
             return "SOS submitted successfully!", 201

    except Exception as e:
        db.session.rollback()
        print(f"ERROR submitting SOS via web: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': 'Error submitting SOS via web form', 'details': str(e)}), 500

@app.route('/api/v1/sos', methods=['POST'])
def api_submit_sos_flexible():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    print(f"\n--- INCOMING /api/v1/sos REQUEST ---")
    print(f"Received Raw Data: {data}")

    sos_name = None
    sos_location = None
    sos_message = None
    sos_mobile_number = None
    sos_disaster_type = None
    sos_source = data.get('source')
    errors = {}
    detected_format = "Invalid/Unknown"
    location_data = data.get('location')

    if isinstance(location_data, dict):
        detected_format = "Structured"
        print(f"Detected Format: {detected_format}")
        if sos_source is None: sos_source = 'api_structured'
        disaster_type = data.get('disasterType')
        details = data.get('details')
        mobile_number = data.get('mobileNumber')
        latitude = None
        longitude = None

        if not disaster_type or not isinstance(disaster_type, str) or not disaster_type.strip():
            errors['disasterType'] = 'Missing or invalid disasterType (must be a non-empty string)'
        else:
             sos_disaster_type = disaster_type.strip()

        lat_in = location_data.get('latitude')
        lon_in = location_data.get('longitude')
        if lat_in is None or lon_in is None:
            errors['location'] = 'Location object must contain numeric latitude and longitude'
        else:
            try:
                latitude = float(lat_in)
                longitude = float(lon_in)
                if not (-90 <= latitude <= 90): errors['latitude'] = 'Latitude must be between -90 and 90'
                if not (-180 <= longitude <= 180): errors['longitude'] = 'Longitude must be between -180 and 180'
            except (ValueError, TypeError):
                errors['location'] = 'Latitude and Longitude must be valid numbers'

        if mobile_number:
            if isinstance(mobile_number, str):
                trimmed_mobile = mobile_number.strip()
                if trimmed_mobile: sos_mobile_number = trimmed_mobile
            elif isinstance(mobile_number, (int, float)):
                 sos_mobile_number = str(mobile_number)
            else:
                 errors['mobileNumber'] = 'Mobile number must be a string or number if provided'

        if not errors:
            sos_name = "API Structured Submission"
            sos_location = f"Lat: {latitude:.6f}, Lng: {longitude:.6f}"
            message_parts = [f"Disaster Type: {sos_disaster_type}"]
            if details and isinstance(details, str) and details.strip():
                message_parts.append(f"Details: {details.strip()}")
            if sos_mobile_number:
                message_parts.append(f"Contact Number: {sos_mobile_number}")
            sos_message = "\n".join(message_parts)

    elif isinstance(location_data, str):
        detected_format = "Legacy"
        print(f"Detected Format: {detected_format}")
        if sos_source is None: sos_source = 'api_legacy'
        message = data.get('message')
        name = data.get('name')

        if not location_data.strip():
             errors['location'] = 'Location string cannot be empty'
        else:
             sos_location = location_data.strip()

        if not message or not isinstance(message, str) or not message.strip():
            errors['message'] = 'Missing or invalid message (must be a non-empty string)'
        else:
            sos_message = message.strip()

        if name and isinstance(name, str) and name.strip():
             sos_name = name.strip()

    else:
        errors['location'] = 'Missing or invalid location field. Must be a string or an object {"latitude": ..., "longitude": ...}'

    if errors:
        print(f"Validation failed for /api/v1/sos: {errors}")
        return jsonify({"error": "Validation failed", "details": errors}), 400

    print("-" * 20)
    print(f"Attempting to save with format: {detected_format}")
    print(f"  Name: {sos_name!r}")
    print(f"  Location: {sos_location!r}")
    print(f"  Message: {sos_message!r}")
    print(f"  Mobile: {sos_mobile_number!r}")
    print(f"  Disaster Type: {sos_disaster_type!r}")
    print(f"  Source: {sos_source!r}")
    print("-" * 20)
    try:
        if not sos_location: raise ValueError("Internal processing error: sos_location cannot be empty.")
        if not sos_message: raise ValueError("Internal processing error: sos_message cannot be empty.")

        new_sos = SOSMessage(
            name=sos_name,
            location=sos_location,
            message=sos_message,
            status='Pending',
            source=sos_source.strip() if sos_source else 'api_unknown',
            mobile_number=sos_mobile_number,
            disaster_type=sos_disaster_type
        )
        print("SOSMessage object created successfully.")
        db.session.add(new_sos)
        print("Added to session.")
        db.session.commit()
        print("Committed successfully.")

        print(f"Successfully saved SOS from /api/v1/sos (Source: {new_sos.source}): ID {new_sos.id}")
        return jsonify({
            "status": "success",
            "message": f"SOS submitted successfully via API (Source: {new_sos.source})",
            "id": new_sos.id
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"\n--- DATABASE OR PROCESSING ERROR during save ---")
        print(f"ERROR saving SOS from /api/v1/sos: {str(e)}")
        print(f"Data attempted:")
        print(f"  Name: {sos_name!r}")
        print(f"  Location: {sos_location!r}")
        print(f"  Message: {sos_message!r}")
        print(f"  Mobile: {sos_mobile_number!r}")
        print(f"  Disaster Type: {sos_disaster_type!r}")
        print(f"  Source: {sos_source!r}")
        print(f"--- Traceback ---")
        print(traceback.format_exc())
        print(f"--- END ERROR ---")
        return jsonify({
            "error": "Internal server error during API SOS submission",
            "details": str(e)
        }), 500


# --- Admin Data Retrieval & Management ---
@app.route('/get_sos_messages')
def get_sos_messages():
    #if not is_admin(): # Decide if you want to enforce admin check here
    #    return jsonify({'message': 'Unauthorized'}), 401
    try:
        sos_messages = SOSMessage.query.order_by(SOSMessage.created_at.desc()).all()
        output = []
        for sos in sos_messages:
            output.append({
                "id": sos.id, "name": sos.name, "location": sos.location,
                "message": sos.message, "status": sos.status, "source": sos.source,
                "mobile_number": sos.mobile_number, "disaster_type": sos.disaster_type,
                "created_at": sos.created_at.isoformat() if sos.created_at else None
            })
        return jsonify(output)
    except Exception as e:
        print(f"Error fetching SOS messages: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to retrieve SOS messages", "details": str(e)}), 500

@app.route('/update_status/<int:sos_id>', methods=['POST'])
def update_status(sos_id):
    #if not is_admin(): # Decide if you want to enforce admin check here
    #    return jsonify({'message': 'Unauthorized'}), 401
    if not request.is_json:
         return jsonify({"message": "Request must be JSON"}), 400
    data = request.get_json()
    new_status = data.get('status')
    if not new_status:
        return jsonify({'message': 'Missing status field in request body'}), 400

    allowed_statuses = ['Pending', 'Under Review', 'Resolved', 'False Alarm']
    if new_status not in allowed_statuses:
        return jsonify({'message': f'Invalid status: "{new_status}". Allowed statuses are: {", ".join(allowed_statuses)}'}), 400

    try:
        # Use db.session.get() for primary key lookup (more efficient)
        sos = db.session.get(SOSMessage, sos_id)
        if sos:
            sos.status = new_status
            db.session.commit()
            print(f"Updated status for SOS ID {sos_id} to {new_status}")
            return jsonify({'message': 'Status updated successfully', 'id': sos_id, 'new_status': new_status})
        else:
            return jsonify({'message': f'SOS message with ID {sos_id} not found'}), 404
    except Exception as e:
        db.session.rollback()
        print(f"Error updating status for SOS ID {sos_id}: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': 'Internal server error during status update', 'details': str(e)}), 500

# --- Announcements ---
@app.route('/get_announcements')
def get_announcements():
    try:
        announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(10).all()
        output = [{
            "id": a.id, "content": a.content, "created_at": a.created_at.isoformat() if a.created_at else None
            } for a in announcements]
        return jsonify(output)
    except Exception as e:
        print(f"Error fetching announcements: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to retrieve announcements", "details": str(e)}), 500

@app.route('/create_announcement', methods=['POST'])
def create_announcement():
    #if not is_admin(): return jsonify({'message': 'Unauthorized'}), 401 # Decide if you want to enforce admin check here
    if not request.is_json: return jsonify({"message": "Request must be JSON"}), 400
    data = request.get_json()
    content = data.get('content')
    if not content or not isinstance(content, str) or not content.strip():
        return jsonify({'message': 'Missing or empty content field'}), 400
    try:
        new_announcement = Announcement(content=content.strip())
        db.session.add(new_announcement)
        db.session.commit()
        print(f"Created announcement: ID {new_announcement.id}")
        return jsonify({
            'message': 'Announcement created successfully',
            'announcement': { 'id': new_announcement.id, 'content': new_announcement.content, 'created_at': new_announcement.created_at.isoformat() if new_announcement.created_at else None }
            }), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error creating announcement: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': 'Internal server error during announcement creation', 'details': str(e)}), 500

@app.route('/update_announcement/<int:id>', methods=['PUT'])
def update_announcement(id):
    #if not is_admin(): return jsonify({'message': 'Unauthorized'}), 401 # Decide if you want to enforce admin check here
    if not request.is_json: return jsonify({"message": "Request must be JSON"}), 400

    try:
        # Use db.session.get() for primary key lookup
        announcement = db.session.get(Announcement, id)
        if not announcement:
            return jsonify({"message": "Announcement not found"}), 404

        data = request.get_json()
        content = data.get('content')

        if not content or not isinstance(content, str) or not content.strip():
            return jsonify({'message': 'Missing or empty content field'}), 400

        announcement.content = content.strip()
        db.session.commit()

        print(f"Updated announcement: ID {announcement.id}")
        return jsonify({
            "message": "Announcement updated successfully",
            "id": announcement.id,
            "content": announcement.content,
            "created_at": announcement.created_at.isoformat() if announcement.created_at else None
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error updating announcement ID {id}: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to update announcement", "details": str(e)}), 500

@app.route('/delete_announcement/<int:id>', methods=['DELETE'])
def delete_announcement(id):
    #if not is_admin(): return jsonify({'message': 'Unauthorized'}), 401 # Decide if you want to enforce admin check here

    try:
        # Use db.session.get() for primary key lookup
        announcement = db.session.get(Announcement, id)
        if not announcement:
            return jsonify({"message": "Announcement not found"}), 404

        db.session.delete(announcement)
        db.session.commit()

        print(f"Deleted announcement: ID {id}")
        return jsonify({"message": "Announcement deleted successfully"})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting announcement ID {id}: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to delete announcement", "details": str(e)}), 500


# --- Database Initialization Command ---
# Remove the @app.before_first_request - it's deprecated and not suitable for prod DB setup.
# Use a Flask CLI command instead. Run `flask init-db` in Render shell ONCE after deployment.
@app.cli.command('init-db')
def init_db_command():
    """Creates the database tables in the configured database."""
    try:
        print(f"Attempting to create database tables for URI: {app.config['SQLALCHEMY_DATABASE_URI'][:app.config['SQLALCHEMY_DATABASE_URI'].find('@')] if '@' in app.config['SQLALCHEMY_DATABASE_URI'] else app.config['SQLALCHEMY_DATABASE_URI']}...") # Avoid logging credentials
        # No need for app.app_context() here, Flask CLI handles it.
        db.create_all()
        print("Database tables created successfully (if they didn't exist).")
        # If using Flask-Migrate, you might initialize it here too if needed for the very first time
        # print("Initializing Flask-Migrate...")
        # os.system('flask db init') # Only if migrations folder doesn't exist
        # os.system('flask db migrate -m "Initial migration."') # Optional: Create initial migration
        # os.system('flask db upgrade') # Apply migrations
    except Exception as e:
        print(f"ERROR creating database tables: {e}")
        print(traceback.format_exc())
        # Exit with error code so Render knows if the command failed
        cli.abort(1)


# --- App Initialization & Run (for Local Development) ---
# This block is ignored by production WSGI servers like Gunicorn (used by Render)
if __name__ == '__main__':
    # Use PORT environment variable provided by Render (or others), default to 5000 locally
    port = int(os.environ.get('PORT', 5000))
    # Set debug=False if you want to test closer to production locally
    # Debug mode should generally be OFF in production (Render handles this)
    use_debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    print(f"Starting Flask development server locally on port {port} (Debug: {use_debug})...")
    # host='0.0.0.0' makes it accessible on your network, not just localhost
    app.run(host='0.0.0.0', port=port, debug=use_debug)
