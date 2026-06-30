"""
CLI to test the extractor with a real Groq call.
Usage:
    export GROQ_API_KEY=your_key_here      # free key from console.groq.com
    python run_extract.py samples/sample_transcript.txt
"""
import sys, os, json
# Safety net: make sure the folder containing this script is importable,
# so `app` is found no matter which directory you run from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.extractor import extract

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "samples/sample_transcript.txt"
    transcript = open(path, encoding="utf-8").read()
    result = extract(transcript)                       # real Groq call
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
