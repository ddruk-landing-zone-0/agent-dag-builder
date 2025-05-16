# A simple flask server
from flask import Flask, request, jsonify
from flask_cors import CORS
import json

app = Flask(__name__)
CORS(app)

@app.route('/api', methods=['POST'])
def api():
    data = json.loads(request.data)
    return jsonify(data), 200

@app.route('/')
def index():
    return 'Hello World', 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8080)