import flask_cors
from flask import Flask, request, jsonify, send_from_directory
import rag
import os
from sb import sb1
import supabase

app = Flask(__name__)
flask_cors.CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all routes

# Global variable to store the current file path
current_file_path = None

# Serve frontend files
@app.route('/api/documents', methods=['GET'])
def get_current_documents():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Missing Authorization header'}), 401

    token = auth_header.split(" ")[1]
    user = sb1.verify_token(token)
    if not user:
        return jsonify({'error': 'Invalid or expired token'}), 401

    global current_file_path
    if not current_file_path:
        return jsonify({
            "error": "No file uploaded",
            "status": 404
        }), 404
    
    return jsonify({
        "current_file": os.path.basename(current_file_path),
        "status": 200,
        "user_id": user['sub']  # This is the Supabase user id
    }), 200

@app.route('/api/signup', methods=['POST'])
def create_profile():
    data = request.json

    result = sb1.table('user data').upsert(data).execute()
    if result.error:
        return jsonify(
            {
                "error": result.error,
                
            }, 400
        )
    return jsonify({"message": "Profile updated", "data" : result.data}, 200)


@app.route('/users')
def get_users():
    response = sb1.table('user data').select('*').execute()
    # Return or process the response as needed

@app.route("/api")
def serve_frontend():
    return send_from_directory('../research-spark-ai/dist', 'index.html')

@app.route("/api/assets/<path:path>")
def serve_assets(path):
    return send_from_directory('../research-spark-ai/dist/assets', path)

UPLOAD_FOLDER = 'folders'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'pdf', 'txt'}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/upload', methods=['POST'])
def uploadFile():
    global current_file_path
    if "file" not in request.files:
        print("No file part in request")
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        print("No selected file")
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename):
        print("File type not allowed:", file.filename)
        return jsonify({"error": "Invalid file type. Only PDFs and TXT files allowed."}), 400

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(file_path)
    current_file_path = file_path  # Store the file path globally
    print("File uploaded and saved to:", current_file_path)
    
    return jsonify({
        'status': 200, 
        'file_name': file.filename, 
        'message': "File uploaded successfully"
    }), 200

@app.route("/api/question/<prompt>")
def ask_question(prompt):
    print("Received prompt:", prompt)
    global current_file_path
    if not current_file_path:
        return jsonify({
            "error": "No file uploaded. Please upload a file first.",
            "status": 400
        }), 400
    
    # Pass the current file path to the RAG module for processing.
    answer = rag.ask(prompt, current_file_path)
    status_code = 200 if answer else 404
    
    sb1.table('queries').insert(
        {
            'question': prompt,
            'answer': answer,
            'created_at': 'now()'
        }
    ).execute()
    return jsonify({
        "user_query": prompt,
        "answer": answer,
        "status": status_code
    })

if __name__ == '__main__':
    app.run(debug=True)