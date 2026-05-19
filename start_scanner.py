"""Wrapper para iniciar Streamlit correctamente en Windows."""
import sys, os, asyncio

# Fijar policy de event loop para Windows antes de que Streamlit lo configure
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ["PYTHONUTF8"] = "1"

from streamlit.web import cli as stcli
sys.argv = [
    "streamlit", "run", "scanner_raven_ai_pro.py",
    "--server.port", "8500",
    "--server.headless", "true",
    "--server.address", "0.0.0.0",
    "--server.enableCORS", "false",
    "--server.enableXsrfProtection", "false",
]
stcli.main()
