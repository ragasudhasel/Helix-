import requests
import json
import time

BASE_URL = "http://127.0.0.1:8080"

def test_api():
    print("--- Starting SROP API Test ---\n")
    
    # 1. Create a session
    print("Step 1: Creating a new session...")
    resp = requests.post(f"{BASE_URL}/v1/sessions", json={
        "user_id": "demo_user_123",
        "plan_tier": "pro"
    })
    
    if resp.status_code != 201:
        print(f"[ERROR] Failed to create session: {resp.text}")
        return
        
    session_id = resp.json()["session_id"]
    print(f"[SUCCESS] Session created successfully! Session ID: {session_id}\n")
    
    # 2. Ask a Knowledge Question (RAG)
    print("Step 2: Asking a product knowledge question (Routing to Knowledge Agent)...")
    chat_resp_1 = requests.post(f"{BASE_URL}/v1/chat/{session_id}", json={
        "message": "How do I rotate a deploy key?"
    })
    
    if chat_resp_1.status_code == 200:
        data1 = chat_resp_1.json()
        print(f"[SUCCESS] Routed to: {data1.get('routed_to')}")
        print(f"[AI Reply] {data1.get('reply')}\n")
    else:
        print(f"[ERROR] Failed chat 1: {chat_resp_1.text}\n")
        
    # 3. Ask an Account Question (Mock DB)
    print("Step 3: Asking an account question (Routing to Account Agent)...")
    chat_resp_2 = requests.post(f"{BASE_URL}/v1/chat/{session_id}", json={
        "message": "Show me my recent builds"
    })
    
    if chat_resp_2.status_code == 200:
        data2 = chat_resp_2.json()
        print(f"[SUCCESS] Routed to: {data2.get('routed_to')}")
        print(f"[AI Reply] {data2.get('reply')}\n")
        
        # 4. Check the Trace for the second turn
        trace_id = data2.get("trace_id")
        print(f"Step 4: Fetching execution trace (Trace ID: {trace_id})...")
        trace_resp = requests.get(f"{BASE_URL}/v1/traces/{trace_id}")
        if trace_resp.status_code == 200:
            print("[SUCCESS] Trace retrieved successfully!")
            print(json.dumps(trace_resp.json(), indent=2))
        else:
            print(f"[ERROR] Failed to get trace: {trace_resp.text}")
    else:
        print(f"[ERROR] Failed chat 2: {chat_resp_2.text}\n")
        
    print("\n--- Test Completed Successfully! ---")

if __name__ == "__main__":
    test_api()
