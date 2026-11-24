import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

"""NOVA Python regression tests.

Enforces strict isolated sandbox mode across all tests to prevent
any live desktop or browser execution on the host machine.
"""
import os

os.environ["NOVA_TEST_MODE"] = "1"
os.environ["NOVA_SANDBOX_MODE"] = "1"
os.environ["NOVA_HEADLESS"] = "1"
