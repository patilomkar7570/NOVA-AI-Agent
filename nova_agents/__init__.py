"""NOVA's Router, AI Planner, Orchestrator and active specialists."""
from .orchestrator import Orchestrator
from .memory import SharedMemory
from .registry import agent_catalog, agent_ids
from .version import APP_VERSION

__version__ = APP_VERSION

__all__ = ["Orchestrator", "SharedMemory", "agent_catalog", "agent_ids", "__version__"]
