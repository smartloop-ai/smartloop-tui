"""PyInstaller runtime hook: disable ChromaDB telemetry before import."""
import os
os.environ["CHROMA_ANONYMIZED_TELEMETRY"] = "False"
