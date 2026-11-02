"""
Root conftest.py — adds project root to sys.path so that
`from src.data.parser_bi5 import ...` works without `pip install -e .`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
