import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from src.routes.grocery import grocery_bp
from src.routes.merger import merger_bp

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Get configuration from environment variables
SECRET_KEY = os.getenv('SECRET_KEY', 'asdf#FGSgvasgf$5$WGT')
CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')

app.config['SECRET_KEY'] = SECRET_KEY

# Enable CORS for all routes - convert comma-separated string to list
cors_origins_list = [origin.strip() for origin in CORS_ORIGINS.split(',')]
CORS(app, origins=cors_origins_list)

app.register_blueprint(grocery_bp, url_prefix='/api/grocery')
app.register_blueprint(merger_bp, url_prefix='/api/merger')


@app.route('/')
def health_status():
    """Return simple health status for the API"""
    return jsonify({
        'status': 'healthy',
        'message': 'Grocery API is running',
        'version': '1.0.0'
    })


if __name__ == '__main__':
    # Get Flask configuration from environment variables
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', '5002'))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"Starting Flask server on {FLASK_HOST}:{FLASK_PORT}...")
    print(cors_origins_list)
    sys.stdout.flush()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
