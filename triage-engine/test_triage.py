import os
import sys
import json
import base64
from unittest.mock import MagicMock

# Simple test script to verify main.py logic locally
# Usage:
# export VIRUSTOTAL_API_KEY="your_key"
# export GEMINI_API_KEY="your_key"
# python test_triage.py

try:
    import main
except ImportError:
    print("Error: Could not import main.py. Make sure you are running this from the triage-engine directory or have added it to python path.")
    sys.exit(1)

# Mock CloudEvent class
class MockCloudEvent:
    def __init__(self, data):
        self.data = data

def run_local_test():
    print("--- Starting Local Triage Engine Test ---")
    
    # 1. Check API Keys
    vt_key = os.environ.get("VIRUSTOTAL_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    if not vt_key:
        print("[WARNING] VIRUSTOTAL_API_KEY environment variable is not set. VirusTotal lookup will be skipped.")
    if not gemini_key:
        print("[WARNING] GEMINI_API_KEY environment variable is not set. Gemini analysis will use static mock response.")
        
    # 2. Construct mock Cowrie log (an attacker attempting a brute-force SSH login)
    mock_log = {
        "jsonPayload": {
            "eventid": "cowrie.login.failed",
            "src_ip": "185.156.74.65",  # Known scanner IP
            "username": "admin",
            "password": "password123",
            "timestamp": "2026-07-20T22:23:32.999Z"
        },
        "logName": "projects/test-project/logs/cowrie_log"
    }
    
    # 3. Base64 encode the mock log to simulate Pub/Sub payload structure
    encoded_data = base64.b64encode(json.dumps(mock_log).encode("utf-8")).decode("utf-8")
    
    # 4. Construct mock CloudEvent structure
    event_data = {
        "message": {
            "data": encoded_data,
            "messageId": "12345678"
        }
    }
    cloud_event = MockCloudEvent(event_data)
    
    # 5. Run the Cloud Function locally
    print("\nInvoking triage_pubsub_event cloud function with mock SSH brute-force alert...")
    try:
        # We temporarily mock Firestore client if Firestore credentials aren't set
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            print("[INFO] GOOGLE_APPLICATION_CREDENTIALS not set. Mocking Firestore client write to prevent crash...")
            main.db = MagicMock()
            
        main.triage_pubsub_event(cloud_event)
        
        print("\n--- Test Run Completed ---")
        print("[SUCCESS] Check terminal logs above to verify execution details.")
        
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            print("[INFO] Simulated Firestore Document Write payload:")
            # If main.db was mocked, we print the call arguments
            if main.db.collection.called:
                # Get the set dict values
                write_call = main.db.collection().document().set.call_args
                if write_call:
                    print(json.dumps(write_call[0][0], indent=2, default=str))
                else:
                    print("Firestore document created, but write data not captured.")
            else:
                print("Firestore db.collection was not called.")
                
    except Exception as e:
        print(f"\n[FAILURE] Test run crashed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_local_test()
