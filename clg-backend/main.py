import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import ChatGrant
from twilio.rest import Client
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()
CORS(app, resources={r"/*": {"origins": "*"}})

app = Flask(__name__)
CORS(app)  # Enable CORS for React

# --- CONFIGURATION ---
MONGO_URI = os.environ.get('MONGO_URI')
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_API_KEY = os.environ.get('TWILIO_API_KEY')
TWILIO_API_SECRET = os.environ.get('TWILIO_API_SECRET')
TWILIO_SERVICE_SID = os.environ.get('TWILIO_SERVICE_SID')

# --- DATABASE CONNECTION ---
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client['connect_learn_grow']  # Database Name
    users_collection = db['users']           # Collection for Profiles
    print("✅ Connected to MongoDB")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

# --- TWILIO CLIENT ---
twilio_client = Client(TWILIO_ACCOUNT_SID, os.environ.get('TWILIO_AUTH_TOKEN'))


# --- API ROUTES ---

@app.route('/api/users', methods=['POST'])
def create_user():
    """
    Saves a new user profile (Trainer or Learner) to MongoDB.
    Called by the React 'handleSubmit' function.
    """
    data = request.json
    
    # Basic validation
    if not data.get('firebaseUid') or not data.get('email'):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        # Check if user already exists
        existing_user = users_collection.find_one({"firebaseUid": data['firebaseUid']})
        
        if existing_user:
            # Update existing user
            users_collection.update_one(
                {"firebaseUid": data['firebaseUid']},
                {"$set": data}
            )
            return jsonify({'message': 'User profile updated', 'id': str(existing_user['_id'])}), 200
        else:
            # Create new user
            data['createdAt'] = datetime.utcnow()
            result = users_collection.insert_one(data)
            return jsonify({'message': 'User profile created', 'id': str(result.inserted_id)}), 201

    except Exception as e:
        print(f"Error saving user: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500


@app.route('/api/chat/token', methods=['POST'])
def generate_chat_token():
    """
    Generates a Twilio Access Token for the frontend chat client.
    """
    data = request.json
    identity = data.get('identity')  # The unique user ID (e.g., email or firebaseUid)

    if not identity:
        return jsonify({'error': 'Identity is required'}), 400

    try:
        # Create access token
        token = AccessToken(
            TWILIO_ACCOUNT_SID,
            TWILIO_API_KEY,
            TWILIO_API_SECRET,
            identity=identity
        )

        # Grant access to Chat
        chat_grant = ChatGrant(service_sid=TWILIO_SERVICE_SID)
        token.add_grant(chat_grant)

        return jsonify({'token': token.to_jwt()})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Run on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
