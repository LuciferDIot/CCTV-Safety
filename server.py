"""
Entry point for Hugging Face Spaces (Gradio SDK) and cloud runtimes.
Runs FastAPI on port 7860 (Hugging Face default) or the PORT environment variable.
"""
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "backend"))
sys.path.insert(0, str(ROOT_DIR))

import uvicorn
from main import app

# Gradio status dashboard when running on Hugging Face Spaces
try:
    import gradio as gr
    with gr.Blocks(title="AURA-Traffic: CCTV Safety Analyzer") as demo:
        gr.Markdown("# 🚦 AURA-Traffic: CCTV Motorcycle Safety Analyzer")
        gr.Markdown(
            """
            ### 🟢 Backend API is Live and Operational (16GB RAM)
            * **Swagger API Docs**: [/docs](/docs)
            * **ReDoc API Reference**: [/redoc](/redoc)
            * **System Health Check**: [/api/health](/api/health)
            
            ---
            *To connect your Vercel frontend, set `NEXT_PUBLIC_BACKEND_URL` to this Space's URL.*
            """
        )
    app = gr.mount_gradio_app(app, demo, path="/gradio")
except ImportError:
    pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    print(f"Starting AURA-Traffic server on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

