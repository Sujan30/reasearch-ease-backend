import os
import uuid
import requests
import jwt
import json
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
import flask_cors
import rag
from sb import sb1

# Load environment variables
load_dotenv()

app = Flask(__name__)
flask_cors.CORS(app, resources={r"/*": {"origins": "*"}})

# Globals to hold the uploaded file info
current_file_path = None
current_file_uuid = None


@app.route('/login')
def login():
        """
        +    Expects JSON: { "email": "...", "password": "..." }
        +    Uses sb1 (Supabase client) to sign in, returns tokens and user.
        +    Also upserts into your 'users' table so you have a profile row.
        +    """
        payload = request.get_json(silent=True)
        if not payload or 'email' not in payload or 'password' not in payload:
            return jsonify({"error": "Must supply email and password"}), 400
        email = payload['email']
        password = payload['password']
        
        # Supabase GoTrue signIn
        try:
            res = sb1.sign_in_with_password({"email": email, "password": password})
        except Exception as e:
            return jsonify({"error": f"Auth client error: {e}"}), 500
        
        if hasattr(res, 'error') and res.error:
            return jsonify({"error": res.error.message}), 401
        # On success, res.data.session contains tokens, res.data.user the user record
        session = res.data.session
        user = res.data.user
        # Upsert into your own users table (so you can store additional profile info)
        try:
            sb1.table('user data').upsert({
                "id": user.id,
                "email": user.email
            }, {"on_conflict": "id"}).execute()
        except Exception as e:
            app.logger.warn(f"Could not upsert profile row: {e}")
            # Return back the session info to client
            return jsonify({
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
                "expires_in": session.expires_in,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role
                }
            }), 200


# === UPLOAD ROUTE ===
@app.route('/api/upload', methods=['POST'])
def uploadFile():
    global current_file_path, current_file_uuid

    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No selected file"}), 400

    # Only PDFs & TXT
    if "." not in file.filename or file.filename.rsplit(".", 1)[1].lower() not in {'pdf', 'txt'}:
        return jsonify({"error": "Invalid file type. Only PDFs and TXT allowed."}), 400

    # Save to disk
    file_path = os.path.join('folders', file.filename)
    os.makedirs('folders', exist_ok=True)
    file.save(file_path)

    # Generate and store a UUID for this document
    current_file_path = file_path
    current_file_uuid = str(uuid.uuid4())
    
    # Get user from auth token
    user_id = None
    auth_header = request.headers.get('Authorization')
    if auth_header:
        try:
            token = auth_header.split(" ", 1)[1] if " " in auth_header else auth_header
            user = sb1.verify_token(token)
            if user:
                user_id = user['sub']
        except Exception as e:
            print(f"Error verifying token: {e}")
    
    # Now insert into database with the UUID we just created
    try:
        sb1.table('documents').insert({
            'id': current_file_uuid,
            'user_id': user_id,
            'file_name': file.filename,
            'file_path': file_path,
            'uploaded_at': 'now()'  # This will use the server's current timestamp
        }).execute()
    except Exception as e:
        print(f"Error storing document: {e}")

    return jsonify({
        'status': 200,
        'file_name': file.filename,
        'document_id': current_file_uuid,
        'message': "File uploaded successfully"
    }), 200

# === QUESTION / SEARCH ROUTE ===
@app.route("/api/question/<prompt>", methods=['GET', 'OPTIONS'])
def ask_question(prompt):
    global current_file_path, current_file_uuid
    
    # Handle OPTIONS requests for CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    # 1) Auth
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing Authorization header'}), 401
    token = auth_header.split(" ", 1)[1]
    user = sb1.verify_token(token)
    if not user:
        return jsonify({'error': 'Invalid or expired token'}), 401

    # 2) Ensure file uploaded
    if not current_file_path or not current_file_uuid:
        return jsonify({"error": "No file uploaded. Please upload first."}), 400

    # 3) Ensure document exists in documents table
    try:
        document_check = sb1.table('documents').select('id').eq('id', current_file_uuid).execute()
        if not document_check.data or len(document_check.data) == 0:
            # If document doesn't exist in documents table, add it now
            print(f"Document {current_file_uuid} not found in documents table, fixing...")
            sb1.table('documents').insert({
                'id': current_file_uuid,
                'user_id': user['sub'],
                'file_name': os.path.basename(current_file_path),
                'file_path': current_file_path,
                'uploaded_at': 'now()'
            }).execute()
    except Exception as e:
        print(f"Error checking document: {e}")
        # Continue anyway
    
    # WORKAROUND: Add document ID to user_data table to satisfy the foreign key constraint
    try:
        user_data_check = sb1.table('user data').select('id').eq('id', current_file_uuid).execute()
        if not user_data_check.data or len(user_data_check.data) == 0:
            # If document ID doesn't exist in user data table, add a minimal record to satisfy FK
            print(f"Adding document {current_file_uuid} to user data table (workaround for FK constraint)")
            sb1.table('user data').insert({
                'id': current_file_uuid,
                'email': f"document-{current_file_uuid}@placeholder.com"  # Needed if email is a required field
            }).execute()
    except Exception as e:
        print(f"Error with user data workaround: {e}")
        # Continue anyway

    # 4) Run your RAG
    answer = rag.ask(prompt, current_file_path)
    status_code = 200 if answer else 404

    # 5) Store the query
    query_id = str(uuid.uuid4())
    try:
        sb1.table('queries').insert({
            'query id':          query_id,
            'question':    prompt,
            'answer':      answer,
            'user_id':     user['sub'],
            'document_id': current_file_uuid
        }).execute()
    except Exception as e:
        print(f"Error storing query in database: {e}")

    return jsonify({
        "query_id":    query_id,
        "user_query":  prompt,
        "answer":      answer,
        "document_id": current_file_uuid,
        "status":      status_code
    }), status_code

if __name__ == '__main__':
    app.run(debug=True)