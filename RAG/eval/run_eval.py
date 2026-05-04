import requests
import json
import time

BASE_URL = "http://localhost:8080"

TEST_CASES = [
    {
        "query": "How do I rotate a deploy key?",
        "expected_agent": "knowledge_agent",
        "description": "Knowledge Search"
    },
    {
        "query": "Show me my last 3 failed builds",
        "expected_agent": "account_agent",
        "description": "Account Lookup"
    },
    {
        "query": "I am very frustrated and want to talk to a human!",
        "expected_agent": "escalation_agent",
        "description": "Escalation"
    },
    {
        "query": "Tell me a joke about robots.",
        "expected_agent": "srop_root",
        "description": "Root (Guardrails - Refusal)"
    }
]

def run_eval():
    print(f"{'='*60}")
    print(f" SROP Evaluation Harness (E7) ")
    print(f"{'='*60}\n")

    # 1. Create a session
    resp = requests.post(f"{BASE_URL}/v1/sessions", json={"user_id": "eval_user", "plan_tier": "pro"})
    session_id = resp.json()["session_id"]
    print(f"Created Session: {session_id}\n")

    results = []
    passed = 0

    for test in TEST_CASES:
        print(f"Testing: {test['description']}...")
        print(f"Query:   {test['query']}")
        
        start_time = time.time()
        resp = requests.post(f"{BASE_URL}/v1/chat/{session_id}", json={"message": test["query"]})
        latency = (time.time() - start_time) * 1000
        
        if resp.status_code != 200:
            print(f"[FAIL] Error response: {resp.status_code}")
            results.append({"desc": test["description"], "status": "FAIL (Error)", "latency": latency})
            continue
            
        data = resp.json()
        actual_agent = data.get("routed_to")
        
        status = "PASS" if actual_agent == test["expected_agent"] else "FAIL"
        if status == "PASS":
            passed += 1
            
        print(f"Result:  {status} (Routed to: {actual_agent}, Expected: {test['expected_agent']})")
        print(f"Latency: {latency:.2f}ms\n")
        
        results.append({
            "desc": test["description"],
            "status": status,
            "actual": actual_agent,
            "expected": test["expected_agent"],
            "latency": latency
        })

    print(f"{'='*60}")
    print(f" Summary: {passed}/{len(TEST_CASES)} Passed ")
    print(f"{'='*60}")
    
    # Simple table output
    print(f"{'Description':<25} | {'Status':<10} | {'Latency':<10}")
    print("-" * 50)
    for res in results:
        print(f"{res['desc']:<25} | {res['status']:<10} | {res['latency']:>8.2f}ms")

if __name__ == "__main__":
    try:
        run_eval()
    except Exception as e:
        print(f"Evaluation failed: {e}")
        print("Make sure the server is running on http://localhost:8080")
