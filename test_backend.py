import requests
import sys

BASE_URL = "http://localhost:5001"
SESSION = requests.Session()

def register_and_login(username, password):
    print(f"[*] Registering user '{username}'...")
    # Register
    # Note: Logic logic is: GET /register -> POST /register (redirects to dashboard)
    # Auth.py: register route handles both.
    
    # Login payload
    payload = {'username': username, 'password': password}
    
    # 1. Register (POST /register) - In auth.py it's /register POST
    # Wait, in auth.py: @auth.route('/register') ... if POST: ... redirects to dashboard.
    resp = SESSION.post(f"{BASE_URL}/register", data=payload, allow_redirects=True)
    if resp.status_code == 200 and 'Welcome,' in resp.text:
        print("[+] Registration/Login successful (Redirected to Dashboard).")
        return True
    
    # If already exists (flash 'Username already exists'), try login
    if 'Username already exists' in resp.text:
        print("[!] User exists. Logging in...")
        resp = SESSION.post(f"{BASE_URL}/login", data=payload, allow_redirects=True)
        if resp.status_code == 200 and 'Welcome,' in resp.text:
            print("[+] Login successful.")
            return True
        else:
            print(f"[-] Login Failed. Status: {resp.status_code}")
            return False
            
    print(f"[-] Registration Failed. Status: {resp.status_code}")
    # print(resp.text)
    return False

def upload_file():
    print("[*] Uploading file 'test_upload.txt'...")
    files = {'file': ('test_upload.txt', 'This is a test file content.')}
    data = {'parent_id': ''}
    
    resp = SESSION.post(f"{BASE_URL}/upload", files=files, data=data, allow_redirects=True)
    
    if resp.status_code == 200:
        print("[+] Upload request completed.")
        return True
    else:
        print(f"[-] Upload failed. Status: {resp.status_code}")
        return False

def check_dashboard():
    print("[*] Checking Dashboard for 'test_upload.txt'...")
    resp = SESSION.get(f"{BASE_URL}/")
    
    if 'test_upload.txt' in resp.text:
        print("[+] SUCCESS: File found in dashboard.")
        return True
    else:
        print("[-] FAILURE: File NOT found in dashboard.")
        # print(resp.text)
        return False

if __name__ == "__main__":
    try:
        if not register_and_login("qa_user", "qa_password"):
            sys.exit(1)
            
        if not upload_file():
            sys.exit(1)
            
        if not check_dashboard():
            sys.exit(1)
            
        print("\nAll Tests Passed!")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
