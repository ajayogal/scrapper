import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from src.routes.grocery import grocery_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

# Enable CORS for all routes
CORS(app, origins=['http://localhost:5173', 'http://127.0.0.1:5173','http://localhost:5170', 'http://127.0.0.1:5170'])

app.register_blueprint(grocery_bp, url_prefix='/api/grocery')



@app.route('/')
def health_status():
    """Return simple health status for the API"""
    return jsonify({
        'status': 'healthy',
        'message': 'Grocery API is running',
        'version': '1.0.0'
    })


if __name__ == '__main__':
    print("Starting Flask server on port 5002...")
    sys.stdout.flush()
    app.run(host='0.0.0.0', port=5002, debug=True)
