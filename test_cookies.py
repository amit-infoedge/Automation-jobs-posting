"""
Quick test script to debug cookie fetching
"""

import requests
import json

# Test 1: Simple GET request
print("Test 1: Simple GET request to cookie API")
url = "https://dashboard.infoedge.com:8282/common/v1/logins?name=offline"

try:
    response = requests.get(url, timeout=30, verify=False)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    print()
except Exception as e:
    print(f"Error: {str(e)}")
    print()

# Test 2: Try with headers
print("\nTest 2: GET request with headers")
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json'
}

try:
    response = requests.get(url, timeout=30, headers=headers, verify=False)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    print()
except Exception as e:
    print(f"Error: {str(e)}")
    print()

# Test 3: Try with different parameter
print("\nTest 3: Try different endpoint variations")
urls = [
    "https://dashboard.infoedge.com:8282/common/v1/logins",
    "https://dashboard.infoedge.com:8282/common/v1/login",
    "https://dashboard.infoedge.com:8282/auth/logins?name=offline",
]

for test_url in urls:
    try:
        print(f"Testing: {test_url}")
        response = requests.get(test_url, timeout=10, verify=False)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            print(f"  SUCCESS! Response: {response.text[:100]}")
        else:
            print(f"  Response: {response.text[:100]}")
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")
    print()
