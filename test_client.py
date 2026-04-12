import json
import os
import sys

import httpx


def test_process_audio(audio_path: str) -> None:
    url = "http://127.0.0.1:8000/api/v1/process-audio"
    api_key = (os.getenv("API_KEY") or "").strip()
    if not api_key:
        print("Set API_KEY in the environment (same value as on the server).", file=sys.stderr)
        sys.exit(1)

    headers = {"X-API-Key": api_key}

    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
        print(f"Sending audio file {audio_path} to {url}...")
        response = httpx.post(url, files=files, headers=headers, timeout=120.0)

    if response.status_code == 200:
        print("=== Success! Response ===")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error ({response.status_code}): {response.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: API_KEY=... python test_client.py <path_to_audio_file>")
        sys.exit(1)

    test_process_audio(sys.argv[1])
