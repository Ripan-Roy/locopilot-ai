#!/usr/bin/env python3

import sys
import time
from langchain_ollama import OllamaLLM

def test_streaming():
    print("Testing Ollama streaming...")
    
    llm = OllamaLLM(model='qwen3:1.7b', base_url='http://localhost:11434')
    
    prompt = "Tell me a short story about a robot."
    
    print("Starting stream...")
    print("=" * 50)
    
    count = 0
    for chunk in llm.stream(prompt):
        print(f"[{count}]", repr(chunk))
        count += 1
        if count > 20:  # Show first 20 chunks
            print("... (truncated)")
            break
    
    print("=" * 50)
    print("Testing immediate output...")
    
    for chunk in llm.stream("Say hello world"):
        print(chunk, end="", flush=True)
        time.sleep(0.1)  # Small delay to see streaming
    
    print("\nDone!")

if __name__ == "__main__":
    test_streaming()