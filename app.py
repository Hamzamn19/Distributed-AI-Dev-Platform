from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/api/v1/agents/register', methods=['POST'])
def register_agent():
    data = request.json or {}
    return jsonify({"status": "registered", "agent_id": data.get("agent_id")}), 201

@app.route('/api/v1/projects', methods=['POST'])
def create_project():
    data = request.json or {}
    return jsonify({"project_id": "test-proj", "name": data.get("name")}), 201

@app.route('/api/v1/projects/decompose', methods=['POST'])
def decompose_project():
    return jsonify({"status": "decomposed", "tasks": ["t1"]}), 200

@app.route('/api/v1/tasks/assign', methods=['POST'])
def assign_task():
    return jsonify({"status": "assigned"}), 200

@app.route('/api/v1/tasks/next', methods=['GET'])
def next_task():
    agent_id = request.args.get('agent_id', 'unknown')
    return jsonify({"task_id": "t1", "assigned_to": agent_id}), 200

@app.route('/api/v1/tasks/result', methods=['POST'])
def task_result():
    return jsonify({"status": "result_received"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
