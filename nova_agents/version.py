"""Application version metadata for the NOVA Alpha 0.5 development line."""

APP_NAME = "NOVA"
APP_VERSION = "0.5.0-alpha"
RELEASE_CHANNEL = "development"
BUILD_LABEL = "Alpha 0.5 · Orchestrator Consolidation"


def version_info() -> dict[str, str]:
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "channel": RELEASE_CHANNEL,
        "build": BUILD_LABEL,
    }
