import sys
import httpx
import json

def test_process_audio(audio_path: str):
    url = "http://127.0.0.1:8000/api/v1/process-audio"
    
    with open(audio_path, "rb") as f:
        # We explicitly don't hardcode the content type so it's guessed, but we can provide audio/mpeg
        files = {"file": (audio_path, f, "audio/mpeg")}
        print(f"Sending audio file {audio_path} to {url}...")
        
        # We use a long timeout because Whisper STT + LLM Generation might take 10-15 seconds
        response = httpx.post(url, files=files, timeout=60.0)
        
    if response.status_code == 200:
        print("=== Success! Response ===")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error ({response.status_code}): {response.text}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_client.py <path_to_audio_file>")
        sys.exit(1)
        
    test_process_audio(sys.argv[1])
