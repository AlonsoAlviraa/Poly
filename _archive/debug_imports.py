
import sys
import os

print(f"Python Executable: {sys.executable}")
print(f"Python Version: {sys.version}")
print(f"CWD: {os.getcwd()}")
print("Path:", sys.path)

print("-" * 20)
print("Attempting to import sentence_transformers...")
try:
    import sentence_transformers
    print("✅ sentence_transformers imported successfully!")
    print(f"Version: {sentence_transformers.__version__}")
except ImportError as e:
    print(f"❌ Failed to import sentence_transformers: {e}")
except Exception as e:
    print(f"❌ Critical error importing sentence_transformers: {e}")

print("-" * 20)
print("Attempting to import chromadb...")
try:
    import chromadb
    print("✅ chromadb imported successfully!")
    print(f"Version: {chromadb.__version__}")
except ImportError as e:
    print(f"❌ Failed to import chromadb: {e}")
except Exception as e:
    print(f"❌ Critical error importing chromadb: {e}")
