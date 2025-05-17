# Agent DAG API Standards

This document outlines the API endpoints and expected request/response patterns for interacting with the Agent DAG system.

## How to run

Place  `key.json` from GCP in the wordking dir.
```
pip install -r requirements.txt
mkdir saved_graphs
python3 wsgi.py
```

## Base URL

```
http://127.0.0.1:8080
https://d8d1-202-168-85-34.ngrok-free.app
```

---

## 1. Create a Session

**Endpoint:** `/create-session` \[POST]
**Description:** Creates a new session with the specified ID.

**Request Body:**

```json
{
    "session_id": "sample_session"
}
```

**Success Response (200):**

```json
{
    "graph": {
        "create_env": false,
        "graph_id": "<graph_hash>",
        "nodes": {},
        "python_packages": [],
        "venv_path": "./runner_envs/venv"
    },
    "session_id": "sample_session"
}
```

**Error Response (4xx/5xx):**

```json
{
    "error": "Session with ID sample_session already exists."
}
```

---

## 2. Delete a Session

**Endpoint:** `/delete-session` \[POST]
**Description:** Deletes the specified session.

**Request Body:**

```json
{
    "session_id": "sample_session"
}
```

**Success Response:**

```json
{
    "success": true
}
```

**Error Response:**

```json
{
    "error": "Session with ID sample_session does not exist."
}
```

---

## 3. Add Inputs to Session

**Endpoint:** `/add-input` \[POST]
**Description:** Adds input fields to the `inputs` node of a session graph.

**Request Body:**

```json
{
    "session_id": "sample_session",
    "input_fields": {
        "input1": "10",
        "input2": "12",
        "input3": "41"
    }
}
```

---

## 4. Add a Generic Node

**Endpoint:** `/add-node` \[POST]
**Description:** Adds a generic node to the session's graph.

**Request Body:**

```json
{
    "session_id": "sample_session",
    "node_name": "node1",
    "system_instructions": "This is a test system instruction for Node1.",
    "user_prompt": "Calculate the sum of @[inputs.input1] and @[inputs.input2] and @[inputs.input1]^2",
    "python_code": {
        "argument": {
            "arg1": "@[inputs.input1]",
            "arg2": "@[inputs.input2]"
        },
        "function_body": "def function(arg1, arg2):\n    return {'output1': int(arg1) + int(arg2), 'output2': int(arg1)**2}"
    },
    "output_schema": {
        "output1": "This is the output1 of Node1 , sum of input1 and input2",
        "output2": "This is the output2 of Node1 , square of input1"
    },
   "use_LLM": true,
   "json_mode": false,
   "tool_name": "",
   "tool_description": ""
}
```

---

## 5. Update a Node

**Endpoint:** `/update-node` \[POST]
**Description:** Updates an existing generic node.
**Request Body:** Same structure as `/add-node`

---

## 6. Delete a Node

**Endpoint:** `/remove-node` \[POST]
**Description:** Deletes a node from the session's graph.

**Request Body:**

```json
{
    "session_id": "sample_session",
    "node_name": "node3"
}
```

---

## 7. Compile a Session

**Endpoint:** `/compile-session` \[POST]
**Description:** Compiles the graph associated with the session.

**Request Body:**

```json
{
    "session_id": "sample_session"
}
```

---

## 8. Get Session Graph Snapshot

**Endpoint:** `/get-session-graph` \[POST]
**Description:** Retrieves the current graph snapshot for the session.

**Request Body:**

```json
{
    "session_id": "sample_session"
}
```

**Sample Response:**

```json
{
    "graph": {
        "create_env": false,
        "graph_id": "<graph_hash>",
        "nodes": {
            "inputs": {
                "nodeName": "inputs",
                "outputSchema": {
                    "input1": "10",
                    "input2": "12",
                    "input3": "41"
                },
                ...
            },
            "node1": {
                "nodeName": "node1",
                "outputSchema": {
                    "output1": "This is the output1 of Node1 , sum of input1 and input2",
                    "output2": "This is the output2 of Node1 , square of input1"
                },
                ...
            },
            ...
        },
        "python_packages": [],
        "venv_path": "./runner_envs/venv"
    }
}
```

---

## 9. Execute Graph

**Endpoint:** `/execute-session` \[POST]
**Description:** Executes the graph starting from the specified node.

**Request Body:**

```json
{
    "session_id": "sample_session",
    "start_node": "node3"
}
```

---

## 10. List All Sessions

**Endpoint:** `/list-sessions` \[GET]
**Description:** Returns a list of all existing session IDs.

**Response:**

```json
{
    "sessions": [
        "sample_session",
        "test_session"
    ]
}
```

---

## Node Types Summary

* **Inputs Node:**

  * Special single node per session.
  * Contains input fields dynamically defined by the user.

* **Generic Node:**

  * Contains: `node_name`, `system_instructions`, `user_prompt`, `python_code`, `output_schema`.
  * References inputs or other node outputs using `@[node_name.output_key]` syntax.

---
