import sys
from pathlib import Path

# Make `import monitor` and `import app` work without setting PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
