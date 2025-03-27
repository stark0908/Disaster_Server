# Added missing import
import traceback

from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_migrate import Migrate
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sos.db'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
CORS(app, supports_credentials=True)
migrate = Migrate(app, db)

# Fixed SOSMessage model (added source field)
class SOSMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    location = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    source = db.Column(db.String(50), default='web')  # Added source field
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

ADMIN_CREDENTIALS = {
    'username': 'admin',
    'password': bcrypt.generate_password_hash('admin').decode('utf-8')
}

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login_page')
def login_page():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session or session['user'] != ADMIN_CREDENTIALS['username']:
        return redirect(url_for('login_page'))
    return render_template('dashboard.html')

@app.route('/check_login')
def check_login():
    return jsonify({'logged_in': 'user' in session})

@app.route('/logout')
def logout():
    session.pop('user', None)
    return jsonify({'message': 'Logged out'}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if username == ADMIN_CREDENTIALS['username'] and bcrypt.check_password_hash(ADMIN_CREDENTIALS['password'], password):
        session['user'] = username
        return jsonify({'message': 'Login successful', 'logged_in': True})
    return jsonify({'message': 'Invalid Credentials', 'logged_in': False}), 401

@app.route('/submit_sos', methods=['POST'])
def submit_sos():
    try:
        data = request.get_json()
        
        if not all(key in data for key in ['name', 'location', 'message']):
            return jsonify({'message': 'Missing required fields'}), 400

        new_sos = SOSMessage(
            name=data['name'],
            location=data['location'],
            message=data['message'],
            status='Pending'  # Explicitly set status
        )
        
        db.session.add(new_sos)
        db.session.commit()
        return jsonify({'message': 'SOS submitted successfully'}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error submitting SOS: {str(e)}'}), 500
    
@app.route('/get_sos_messages')
def get_sos_messages():
    if 'user' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    sos_messages = SOSMessage.query.order_by(SOSMessage.created_at.desc()).all()
    categorized = {
        "pending": [{"id": sos.id, "name": sos.name, "location": sos.location, 
                    "message": sos.message, "status": sos.status} 
                   for sos in sos_messages if sos.status == 'Pending'],
        "under_review": [{"id": sos.id, "name": sos.name, "location": sos.location,
                        "message": sos.message, "status": sos.status} 
                        for sos in sos_messages if sos.status == 'Under Review']
    }
    return jsonify(categorized)

@app.route('/update_status/<int:sos_id>', methods=['POST'])
def update_status(sos_id):
    if 'user' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    data = request.get_json()
    sos = SOSMessage.query.get(sos_id)

    if sos:
        sos.status = data.get('status', sos.status)
        db.session.commit()
        return jsonify({'message': 'Status updated successfully'})
    return jsonify({'message': 'SOS not found'}), 404

@app.route('/get_announcements')
def get_announcements():
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(5).all()
    return jsonify([{"content": a.content, "created_at": a.created_at} for a in announcements])

@app.route('/create_announcement', methods=['POST'])
def create_announcement():
    if 'user' not in session:
        return jsonify({'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    new_announcement = Announcement(content=data['content'])
    db.session.add(new_announcement)
    db.session.commit()
    return jsonify({'message': 'Announcement created successfully'}), 201

@app.route('/api/v1/sos', methods=['POST'])
def api_submit_sos():
    try:
        print("\n=== INCOMING REQUEST ===")
        print("Headers:", request.headers)
        
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()
        print("Parsed Data:", data)

        required = ['location', 'message']
        if not all(field in data for field in required):
            missing = [f for f in required if f not in data]
            return jsonify({"error": f"Missing fields: {missing}"}), 400

        new_sos = SOSMessage(
            name=data.get('name', 'Anonymous'),
            location=data['location'],
            message=data['message'],
            status='Pending',
            source=data.get('source', 'external_api')
        )
        
        print("Object to be saved:", {
            'name': new_sos.name,
            'location': new_sos.location,
            'message': new_sos.message,
            'source': new_sos.source
        })
        
        db.session.add(new_sos)
        db.session.commit()
        
        print("=== SAVE SUCCESSFUL ===")
        return jsonify({
            "status": "success",
            "id": new_sos.id
        }), 201
        
    except Exception as e:
        print("\n=== ERROR DETAILS ===")
        print("Type:", type(e))
        print("Error:", str(e))
        print("Traceback:", traceback.format_exc())
        
        db.session.rollback()
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)