"""
pytest configuration for Intelli-Credit test suite.
"""
import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest


@pytest.fixture(scope="session")
def rule_engine():
    """Shared RuleEngine instance for all unit tests."""
    from services.reasoning.rule_engine import RuleEngine
    engine = RuleEngine()
    return engine


@pytest.fixture(scope="session")
def project_root():
    return PROJECT_ROOT
