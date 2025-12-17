"""
Test the /api/onboarding/start endpoint directly
"""
import httpx
import asyncio

async def test_start_endpoint():
    url = "http://127.0.0.1:8000/api/onboarding/start"

    payload = {
        "user_id": "test_user_123"
    }

    print("=" * 60)
    print("TESTING /api/onboarding/start ENDPOINT")
    print("=" * 60)
    print(f"\nURL: {url}")
    print(f"Payload: {payload}")
    print("\nSending request...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)

            print(f"\nStatus Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"\nResponse Body:")
            print(response.text)

            if response.status_code == 200:
                print("\n[SUCCESS] Endpoint is working!")
                data = response.json()
                print(f"Session ID: {data.get('session_id')}")
                print(f"Response: {data.get('response')}")
            else:
                print(f"\n[ERROR] Status code: {response.status_code}")

    except httpx.ConnectError as e:
        print(f"\n[ERROR] Cannot connect to server!")
        print(f"Make sure the server is running: uvicorn main:app --reload")
        print(f"Error: {e}")
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_start_endpoint())
