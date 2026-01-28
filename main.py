import os
import requests
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

app = Flask(__name__)
# --- CONFIGURATION ---
# This allows all origins, all methods, and all headers
CORS(app, resources={r"/*": {"origins": "*"}}, methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
# --- CONFIGURATION ---
MONGO_URI = os.environ.get('MONGO_URI')
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_API_KEY = os.environ.get('TWILIO_API_KEY')
TWILIO_API_SECRET = os.environ.get('TWILIO_API_SECRET')
TWILIO_SERVICE_SID = os.environ.get('TWILIO_SERVICE_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# --- DATABASE CONNECTION ---
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client['connect_learn_grow']
    users_collection = db['users']
    print("✅ Connected to MongoDB")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

# --- TWILIO CLIENT ---
try:
    # We need the real Auth Token to create conversations via API
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
except Exception as e:
    print(f"⚠️ Twilio Client Error: {e}")


# --- API ROUTES ---

@app.route('/api/users', methods=['POST'])
def create_user():
    """ Saves a new user profile to MongoDB. """
    data = request.json
    if not data.get('firebaseUid') or not data.get('email'):
        return jsonify({'error': 'Missing required fields'}), 400

    try:
        existing_user = users_collection.find_one({"firebaseUid": data['firebaseUid']})
        if existing_user:
            users_collection.update_one({"firebaseUid": data['firebaseUid']}, {"$set": data})
            return jsonify({'message': 'User profile updated', 'id': str(existing_user['_id'])}), 200
        else:
            data['createdAt'] = datetime.utcnow()
            result = users_collection.insert_one(data)
            return jsonify({'message': 'User profile created', 'id': str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat/token', methods=['POST'])
def generate_chat_token():
    """
    Generates a Twilio Access Token. 
    Required for the React frontend to connect to Twilio SDK.
    """
    data = request.json
    identity = data.get('identity') # e.g., 'user_123' or email

    if not identity:
        return jsonify({'error': 'Identity is required'}), 400

    try:
        token = AccessToken(
            TWILIO_ACCOUNT_SID,
            TWILIO_API_KEY,
            TWILIO_API_SECRET,
            identity=identity
        )

        chat_grant = ChatGrant(service_sid=TWILIO_SERVICE_SID)
        token.add_grant(chat_grant)

        return jsonify({'token': token.to_jwt()})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat/create', methods=['POST'])
def create_conversation():
    """
    Creates a new conversation between two users.
    Frontend sends: { "userA": "uid1", "userB": "uid2" }
    """
    data = request.json
    userA = data.get('userA')
    userB = data.get('userB')

    if not userA or not userB:
        return jsonify({'error': 'Both user identities are required'}), 400

    try:
        # 1. Create the Conversation
        conversation = twilio_client.conversations.v1.conversations.create(
            friendly_name=f"Chat: {userA} & {userB}"
        )

        # 2. Add User A
        twilio_client.conversations.v1.conversations(conversation.sid) \
            .participants.create(identity=userA)

        # 3. Add User B
        twilio_client.conversations.v1.conversations(conversation.sid) \
            .participants.create(identity=userB)

        return jsonify({
            'sid': conversation.sid,
            'friendlyName': conversation.friendly_name
        })

    except Exception as e:
        print(f"Twilio Conversation Error: {e}")
        return jsonify({'error': str(e)}), 500


# (Optional) Endpoint to list a user's conversations if needed by backend logic
# The Frontend SDK usually handles this, but this is useful for debugging.
@app.route('/api/chat/list', methods=['GET'])
def list_conversations():
    try:
        conversations = twilio_client.conversations.v1.conversations.list(limit=20)
        return jsonify([{'sid': c.sid, 'friendlyName': c.friendly_name} for c in conversations])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
