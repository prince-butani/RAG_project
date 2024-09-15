from flask import Flask, request, jsonify, current_app, make_response
from flask_cors import CORS, cross_origin
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from youtube_transcript_api import YouTubeTranscriptApi
from transformers import pipeline, BartTokenizer, BartForConditionalGeneration
import os
import time
import shutil
from dotenv import load_dotenv
from llama_index import VectorStoreIndex, SimpleDirectoryReader
from llama_index.retrievers import VectorIndexRetriever
from llama_index.query_engine import RetrieverQueryEngine
from llama_index.indices.postprocessor import SimilarityPostprocessor
from llama_index.response.pprint_utils import pprint_response
from llama_index import StorageContext, load_index_from_storage
import json
import datetime
from flask import request
import logging
import logging.config
from functools import wraps
# Replace with your MySQL connection details
from sqlalchemy_utils import database_exists, create_database

# Replace with your MySQL connection details
db_uri = 'mysql://root:root@db/project'

# Create the database if it doesn't exist
if not database_exists(db_uri):
    create_database(db_uri)
    print(f"Database 'project' created successfully.")
else:
    print(f"Database 'project' already exists.")

logging.config.fileConfig('logging.conf', disable_existing_loggers=False)

def log_request(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # logger.info(f'Request: {request.method} {request.path}')
        # return func(*args, **kwargs)
        request_data = {
            'request_method': request.method,
            'request_path': request.path,
            'request_headers': dict(request.headers),
            # 'request_data': request.get_data().decode('utf-8')
        }
        logger.info(json.dumps(request_data))
        return func(*args, **kwargs)
    return wrapper

app = Flask(__name__)
# CORS(app, resources={r"/*": {"origins": "*", "methods": "*", "allow_headers": "*"}})
CORS(app, supports_credentials=True, origins="http://localhost:3000")
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['JWT_SECRET_KEY'] = 'C2154BF222A336473C81B11EA2DB5C2154BF222A336473C81B11EA2DB5C2154BF222A336473C81B11EA2DB5'
app.config['DATA_DIR'] = 'data'
app.config['STORAGE_DIR'] = 'storage'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(hours=3)
db = SQLAlchemy(app)
jwt = JWTManager(app)
logger = logging.getLogger('flask_app')
migrate = Migrate(app, db)
load_dotenv()
os.environ['OPENAI_API_KEY'] = os.getenv("OPENAI_API_KEY")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)

from sqlalchemy import inspect

def create_user_table():
    with app.app_context():
        inspector = inspect(db.engine)
        if not inspector.has_table(User.__tablename__):
            try:
                User.__table__.create(db.engine, checkfirst=True)
                print("User table created successfully.")
            except Exception as e:
                print(f"Error creating user table: {e}")
        else:
            print("User table already exists.")


@app.route('/register', methods=['POST', "OPTIONS"])
@cross_origin()
@log_request
def register():
    username = request.json.get('username', None)
    password = request.json.get('password', None)

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'message': 'Username already exists'}), 409

    new_user = User(username=username, password=generate_password_hash(password))
    db.session.add(new_user)
    db.session.commit()
    user_dir = os.path.join(app.config['DATA_DIR'], username)
    os.makedirs(user_dir, exist_ok=True)
    user_storage_dir = os.path.join(app.config['STORAGE_DIR'], username)
    os.makedirs(user_storage_dir, exist_ok=True)

    return jsonify({'message': 'User created successfully'}), 201

@app.route('/login', methods=['POST', "OPTIONS"])
@cross_origin()
@log_request
def login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({'message': 'Invalid credentials'}), 401

    access_token = create_access_token(identity=user.username)
    return jsonify({'access_token': access_token}), 200

@app.route('/addData', methods=['POST', "OPTIONS"])
@log_request
@cross_origin()
@jwt_required()
def addData():
    current_user = get_jwt_identity()
    url = request.json.get('url', None)
    print(request.json)
    if not url:
        return jsonify({'message': 'No URL provided'}), 400
    
    video_id = url.split('=')[1]
    transcript = get_transcript(video_id)
    
    user_dir = os.path.join(app.config['DATA_DIR'], current_user)
    filename = f"{int(time.time())}.txt"
    file_path = os.path.join(user_dir, filename)

    with open(file_path, 'w') as f:
        f.write(transcript)

    return jsonify({'message': 'Data added successfully'}), 200

@app.route('/summary', methods=['POST', "OPTIONS"])
@log_request
@cross_origin()
@jwt_required()
def summary():
    current_user = get_jwt_identity()
    url = request.json.get('url', None)
    print(request.json)
    if not url:
        return jsonify({'message': 'No URL provided'}), 400
    
    video_id = url.split('=')[1]
    transcript = get_transcript(video_id)
    
    summary = get_summary(transcript)
    return summary, 200

    # return jsonify({'message': 'Data added successfully'}), 200

@app.route('/removeData', methods=['POST', "OPTIONS"])
@log_request
@cross_origin()
@jwt_required()
def removeData():
    current_user = get_jwt_identity()
    user_dir = os.path.join(app.config['DATA_DIR'], current_user)
    storage_dir = os.path.join(app.config['STORAGE_DIR'], current_user)

    # Delete user directory and all its contents
    try:
        shutil.rmtree(user_dir)
        shutil.rmtree(storage_dir)
    except Exception as e:
        return jsonify({'message': f'Error deleting data: {str(e)}'}), 500

    os.makedirs(user_dir, exist_ok=True)
    os.makedirs(storage_dir, exist_ok=True)

    return jsonify({'message': 'Data deleted successfully'}), 200

@app.route('/generate', methods=['GET', "OPTIONS"])
@log_request
@cross_origin()
@jwt_required()
def generate():
    current_user = get_jwt_identity()
    user_dir = os.path.join(app.config['STORAGE_DIR'], current_user)

    # Delete user directory and all its contents
    try:
        shutil.rmtree(user_dir)
    except Exception as e:
        return jsonify({'message': f'Error deleting data: {str(e)}'}), 500

    # Check if storage already exists
    os.makedirs(user_dir, exist_ok=True)
    PERSIST_DIR = user_dir
    data_path = os.path.join(app.config['DATA_DIR'], current_user)
    documents = SimpleDirectoryReader(data_path).load_data()
    index = VectorStoreIndex.from_documents(documents)

    index.storage_context.persist(persist_dir=PERSIST_DIR)

    return jsonify({'message': 'Your Chat is ready now'}), 200

@app.route("/query", methods=["POST", "OPTIONS"])
@log_request
@cross_origin()
@jwt_required()
def handle_query():
    current_user = get_jwt_identity()
    
    data = json.loads(request.data)
    query = data["query"]
    PERSIST_DIR = os.path.join(app.config["STORAGE_DIR"], current_user)
    
    storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
    index = load_index_from_storage(storage_context)

    retriever = VectorIndexRetriever(index=index, similarity_top_k=4)
    postprocessor = SimilarityPostprocessor(similarity_cutoff=0.3)

    query_engine = RetrieverQueryEngine(retriever=retriever, node_postprocessors=[postprocessor])
    response = query_engine.query(query)
    pprint_response(response,show_source=True)
    print(response)
    return jsonify({"result":str(response)})


def get_transcript(video_id):
    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
    transcript = ' '.join([d['text'] for d in transcript_list])
    return transcript

def get_summary(transcript):
    model_name = "sshleifer/distilbart-cnn-12-6"
    model = BartForConditionalGeneration.from_pretrained(model_name)
    tokenizer = BartTokenizer.from_pretrained(model_name)

    summariser = pipeline('summarization', model=model, tokenizer=tokenizer)
    summary = ''
    for i in range(0, (len(transcript)//1000)+1):
        summary_text = summariser(transcript[i*1000:(i+1)*1000])[0]['summary_text']
        summary = summary + summary_text + ' '
    return summary

if __name__ == '__main__':
    create_user_table()
    if not os.path.exists(app.config['DATA_DIR']):
        os.makedirs(app.config['DATA_DIR'])
    if not os.path.exists(app.config['STORAGE_DIR']):
        os.makedirs(app.config['STORAGE_DIR'])
    app.run(debug=True, port=5000, host="0.0.0.0")