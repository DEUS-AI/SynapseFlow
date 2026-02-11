#!/usr/bin/env python3
"""
Quick test to verify WebSocket endpoint is accessible
"""
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws/chat/patient:test/session:test"

    try:
        print(f"Attempting to connect to: {uri}")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected successfully!")

            # Send a test message
            test_message = {"message": "Hello, this is a test"}
            await websocket.send(json.dumps(test_message))
            print(f"📤 Sent: {test_message}")

            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print(f"📥 Received: {response}")
            except asyncio.TimeoutError:
                print("⏱️  No response received within 5 seconds (this might be expected)")

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Is the backend running? Try: uv run uvicorn src.application.api.main:app --reload --port 8000")
        print("2. Check if port 8000 is in use: lsof -i :8000")
        print("3. Verify WebSocket endpoint exists in src/application/api/main.py")

if __name__ == "__main__":
    asyncio.run(test_websocket())
