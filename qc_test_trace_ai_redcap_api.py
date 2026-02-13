import requests
import time

# List your 16 Record IDs here (ensure these exist in Project A)
records = [str(i) for i in range(30, 46)]

# Your Flask address
BASE_URL = "http://127.0.0.1:5000/transfer"

print("---STARTING QC BATCH TEST---")
print("-" * 50)

for rid in records:
    print(f"Testing Record {rid}: ", end="")
    try:
        # Your Flask app uses GET and expects 'record'
        response = requests.get(BASE_URL, params={'record': rid})
        
        if response.status_code == 200:
            # Check if it was In-person or Electronic in the HTML response
            if "Electronic Consent" in response.text:
                print("SUCCESS [Electronic Consent]")
            elif "In-Person Consent" in response.text:
                print("SUCCESS [In-Person Consent]")
            else:
                print("SUCCESS [Synced]")
        
        elif response.status_code == 404:
            print("FAILED | Record not found in Project A.")
        
        elif response.status_code == 400:
            print("FAILED | Missing Record ID.")
            
        else:
            print(f"ERROR | Status: {response.status_code}")
            
    except Exception as e:
        print(f"CONNECTION ERROR | Is Flask running?: {e}")

    time.sleep(0.5)

print("-" * 50)
print("Batch Test Complete. Check your Flask terminal for Sync logs.")
