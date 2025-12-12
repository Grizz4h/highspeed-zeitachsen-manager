import os
import sys

# damit Imports relativ zum Tool-Ordner funktionieren
TOOL_DIR = os.path.dirname(__file__)
sys.path.insert(0, TOOL_DIR)

def render():
    # hier importierst du dein altes Streamlit-"app"
    import app_timeaxis  # noqa: F401
    # Wenn dein altes app.py direkt Streamlit Code "oben" ausführt, reicht der Import.
    # Besser wäre: app_timeaxis.main() – siehe Schritt 3.
