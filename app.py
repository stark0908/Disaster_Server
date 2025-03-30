# --- START OF FILE app.py ---

import traceback
from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_migrate import Migrate
from datetime import datetime, timedelta # Added timedelta for session lifetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sos.db'
# IMPORTANT: Change this in production to a strong, random secret key!
app.config['SECRET_KEY'] = 'your_secret_key_please_change_me_again'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Configure session cookie settings for better security in production if needed
# app.config['SESSION_COOKIE_SECURE'] = True # Send cookie only over HTTPS
# app.config['SESSION_COOKIE_HTTPONLY'] = True # Prevent client-side JS access
# app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' # Or 'Strict'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
# Allow requests from any origin for now, restrict in production if possible
CORS(app, supports_credentials=True, origins="*")
migrate = Migrate(app, db)

# --- Database Models ---
# Model updated to handle fields from both formats
class SOSMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True, default='Anonymous') # Optional name
    location = db.Column(db.String(200), nullable=False) # Stores formatted lat/lng OR address string
    message = db.Column(db.Text, nullable=False)         # Stores combined details OR original message
    status = db.Column(db.String(50), default='Pending')
    source = db.Column(db.String(50), default='web')      # e.g., 'web', 'api_structured', 'api_legacy'
    mobile_number = db.Column(db.String(20), nullable=True) # Optional mobile number
    disaster_type = db.Column(db.String(100), nullable=True) # Optional disaster type
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<SOSMessage {self.id} - {self.name} - {self.status}>'

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Announcement {self.id}>'

# --- Admin Credentials (Consider moving to environment variables or a config file) ---
ADMIN_USERNAME = 'admin'
# Generate this hash outside the code or on first run and store securely
ADMIN_PASSWORD_HASH = bcrypt.generate_password_hash('admin').decode('utf-8')

# --- Helper Functions ---
def is_admin():
    """Checks if the current session user is the admin."""
    return 'user' in session and session.get('user') == ADMIN_USERNAME

# --- Routes ---

# Basic Pages & Auth (No changes needed here)
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

    if username == ADMIN_USERNAME and bcrypt.check_password_hash(ADMIN_PASSWORD_HASH, password):
        session['user'] = username
        session.permanent = True
        app.permanent_session_lifetime = timedelta(days=1)
        return jsonify({'message': 'Login successful', 'logged_in': True}), 200
    else:
        return jsonify({'message': 'Invalid Credentials', 'logged_in': False}), 401

# --- SOS Submission Routes ---

# Original Web Form SOS Submission (used by index.html) - No change needed here
@app.route('/submit_sos', methods=['POST'])
def submit_sos_web():
    try:
        if request.is_json:
             data = request.get_json()
             name = data.get('name')
             location = data.get('location')
             message = data.get('message')
        else:
            data = request.form
            name = data.get('name')
            location = data.get('location')
            message = data.get('message')

        if not name or not location or not message:
             return jsonify({'message': 'Missing required fields (name, location, message)'}), 400
        if not isinstance(name, str) or not isinstance(location, str) or not isinstance(message, str):
             return jsonify({'message': 'Invalid data types for name, location, or message'}), 400

        new_sos = SOSMessage(
            name=name.strip(),
            location=location.strip(),
            message=message.strip(),
            status='Pending',
            source='web' # Source is the standard web form
        )
        db.session.add(new_sos)
        db.session.commit()
        print(f"Successfully saved SOS from web form: ID {new_sos.id}")
        return jsonify({'message': 'SOS submitted successfully via web form', 'id': new_sos.id}), 201
    except Exception as e:
        db.session.rollback()
        print(f"ERROR submitting SOS via web: {str(e)}") # Keep this error log
        print(traceback.format_exc())                   # Keep this traceback
        return jsonify({'error': 'Error submitting SOS via web form', 'details': str(e)}), 500


# MODIFIED API Endpoint to handle BOTH formats
@app.route('/api/v1/sos', methods=['POST'])
def api_submit_sos_flexible():
    """
    Handles SOS submissions via API. Accepts two formats:

    1. New Format (Structured Location):
       {
           "details": "(optional string)",
           "disasterType": "string",
           "location": {"latitude": float, "longitude": float},
           "mobileNumber": "(optional string)",
           "source": "(optional string)" // Optional override
       }

    2. Legacy Format (String Location):
       {
           "name": "(optional string)",
           "location": "string",
           "message": "string",
           "source": "(optional string)" // Optional override
       }
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    print(f"\n--- INCOMING /api/v1/sos REQUEST ---") # Header for log clarity
    print(f"Received Raw Data: {data}") # Debugging raw data

    sos_name = None
    sos_location = None
    sos_message = None
    sos_mobile_number = None
    sos_disaster_type = None
    sos_source = data.get('source') # Check for explicit source first
    errors = {}
    detected_format = "Invalid/Unknown" # Default

    # --- Detect format based on 'location' field ---
    location_data = data.get('location')

    if isinstance(location_data, dict):
        # --- Assume NEW Format (Structured Location) ---
        detected_format = "Structured"
        print(f"Detected Format: {detected_format}")
        if sos_source is None:
             sos_source = 'api_structured' # Default source for this format

        # Validation for new format
        disaster_type = data.get('disasterType')
        details = data.get('details') # Optional
        mobile_number = data.get('mobileNumber') # Optional
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

        if mobile_number: # Check if mobile_number exists and is not None
            if isinstance(mobile_number, str):
                # Only assign if it's a non-empty string after stripping
                trimmed_mobile = mobile_number.strip()
                if trimmed_mobile:
                     sos_mobile_number = trimmed_mobile
            # Allow numbers too, convert to string? Or enforce string type strictly? Let's be flexible for now.
            elif isinstance(mobile_number, (int, float)):
                 sos_mobile_number = str(mobile_number)
            else:
                 # If it exists but isn't a string or number, it's invalid type
                 errors['mobileNumber'] = 'Mobile number must be a string or number if provided'

        if not errors:
            # Construct fields for DB
            sos_name = "API Structured Submission" # Default name for this format
            sos_location = f"Lat: {latitude:.6f}, Lng: {longitude:.6f}" # Format location
            message_parts = [f"Disaster Type: {sos_disaster_type}"]
            # Only add details if it exists, is a string, and not empty after stripping
            if details and isinstance(details, str) and details.strip():
                message_parts.append(f"Details: {details.strip()}")
            # Add contact number if available
            if sos_mobile_number:
                message_parts.append(f"Contact Number: {sos_mobile_number}")
            sos_message = "\n".join(message_parts)

    elif isinstance(location_data, str):
        # --- Assume LEGACY Format (String Location) ---
        detected_format = "Legacy"
        print(f"Detected Format: {detected_format}")
        if sos_source is None:
            sos_source = 'api_legacy' # Default source for this format

        # Validation for legacy format
        message = data.get('message')
        name = data.get('name') # Optional in legacy

        if not location_data.strip():
             errors['location'] = 'Location string cannot be empty'
        else:
             sos_location = location_data.strip()

        if not message or not isinstance(message, str) or not message.strip():
            errors['message'] = 'Missing or invalid message (must be a non-empty string)'
        else:
            sos_message = message.strip()

        # Only set name if provided, is string, and not empty
        if name and isinstance(name, str) and name.strip():
             sos_name = name.strip()
        # No else needed, name is nullable in DB, defaults to Anonymous

        # No disaster_type or mobile_number expected in this format, they remain None

    else:
        # --- Invalid location format ---
        errors['location'] = 'Missing or invalid location field. Must be a string or an object {"latitude": ..., "longitude": ...}'

    # --- Final Validation Check ---
    if errors:
        print(f"Validation failed for /api/v1/sos: {errors}")
        return jsonify({"error": "Validation failed", "details": errors}), 400

    # --- Database Save Attempt ---
    # <<< ADDED DEBUG PRINTS >>>
    print("-" * 20)
    print(f"Attempting to save with format: {detected_format}")
    print(f"Data to be saved:")
    print(f"  Name: {sos_name!r}") # Use !r to clearly show None vs empty string
    print(f"  Location: {sos_location!r}")
    print(f"  Message: {sos_message!r}")
    print(f"  Mobile: {sos_mobile_number!r}")
    print(f"  Disaster Type: {sos_disaster_type!r}")
    print(f"  Source: {sos_source!r}")
    print("-" * 20)

    try:
        # Ensure required fields (location, message) are not None or empty before creating object
        if not sos_location:
             raise ValueError("Internal processing error: sos_location cannot be empty.")
        if not sos_message:
             raise ValueError("Internal processing error: sos_message cannot be empty.")

        new_sos = SOSMessage(
            name=sos_name, # Already handled optional logic above
            location=sos_location,
            message=sos_message,
            status='Pending',
            source=sos_source.strip() if sos_source else 'api_unknown', # Ensure source is set and stripped
            mobile_number=sos_mobile_number, # Will be None if not applicable/provided
            disaster_type=sos_disaster_type  # Will be None if not applicable/provided
        )
        print("SOSMessage object created successfully.")

        db.session.add(new_sos)
        print("Added to session.")

        db.session.commit() # <<< The potential point of failure
        print("Committed successfully.")

        # If commit was successful:
        print(f"Successfully saved SOS from /api/v1/sos (Source: {new_sos.source}): ID {new_sos.id}")
        return jsonify({
            "status": "success",
            "message": f"SOS submitted successfully via API (Source: {new_sos.source})",
            "id": new_sos.id
        }), 201

    except Exception as e:
        db.session.rollback() # Rollback on ANY exception during save process
        # <<< ENHANCED ERROR LOGGING >>>
        print(f"\n--- DATABASE OR PROCESSING ERROR during save ---")
        print(f"ERROR saving SOS from /api/v1/sos: {str(e)}")
        print(f"Data attempted:") # Log data again right before error
        print(f"  Name: {sos_name!r}")
        print(f"  Location: {sos_location!r}")
        print(f"  Message: {sos_message!r}")
        print(f"  Mobile: {sos_mobile_number!r}")
        print(f"  Disaster Type: {sos_disaster_type!r}")
        print(f"  Source: {sos_source!r}")
        print(f"--- Traceback ---")
        print(traceback.format_exc()) # Ensure full traceback is printed
        print(f"--- END ERROR ---")
        return jsonify({
            "error": "Internal server error during API SOS submission",
            "details": str(e) # Send general error type back
        }), 500


# --- Admin Data Retrieval & Management ---

@app.route('/get_sos_messages')
def get_sos_messages():
    #if not is_admin():
        #return jsonify({'message': 'Unauthorized'}), 401
    try:
        sos_messages = SOSMessage.query.order_by(SOSMessage.created_at.desc()).all()
        output = []
        for sos in sos_messages:
            output.append({
                "id": sos.id,
                "name": sos.name,
                "location": sos.location,
                "message": sos.message,
                "status": sos.status,
                "source": sos.source,
                "mobile_number": sos.mobile_number,
                "disaster_type": sos.disaster_type,
                "created_at": sos.created_at.isoformat() if sos.created_at else None
            })
        return jsonify(output)
    except Exception as e:
        print(f"Error fetching SOS messages: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to retrieve SOS messages", "details": str(e)}), 500

@app.route('/update_status/<int:sos_id>', methods=['POST'])
def update_status(sos_id):
    #if not is_admin():
        #return jsonify({'message': 'Unauthorized'}), 401
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

# --- Announcements --- (No changes needed here)
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
    #if not is_admin(): return jsonify({'message': 'Unauthorized'}), 401
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
    print(request.headers)
    #if not is_admin(): return jsonify({'message': 'Unauthorized'}), 401 # Add admin check if needed
    if not request.is_json: return jsonify({"message": "Request must be JSON"}), 400

    try:
        announcement = db.session.get(Announcement, id)  # Use get instead of query.get
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
        print(f"Error updating announcement: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to update announcement", "details": str(e)}), 500

@app.route('/delete_announcement/<int:id>', methods=['DELETE'])
def delete_announcement(id):
    #if not is_admin(): return jsonify({'message': 'Unauthorized'}), 401 # Add admin check if needed

    try:
        announcement = db.session.get(Announcement, id)  # Use get instead of query.get
        if not announcement:
            return jsonify({"message": "Announcement not found"}), 404

        db.session.delete(announcement)
        db.session.commit()

        print(f"Deleted announcement: ID {id}")
        return jsonify({"message": "Announcement deleted successfully"})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting announcement: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to delete announcement", "details": str(e)}), 500
    

# --- App Initialization & Run ---
if __name__ == '__main__':
    with app.app_context():
        print("Ensuring database tables exist...")
        db.create_all()
        print("Database tables checked/created.")
    print(f"Starting Flask server...") # Removed address here as app.run specifies it
    # Make sure debug mode is enabled for development
    app.run(host='0.0.0.0', port=8080, debug=True) # Runs on http://127.0.0.1:5000 by default with debug=True44
    #app.run(debug=True)

# --- END OF FILE app.py ---
