"""Application version metadata for the NOVA Beta 0.6 development line."""

APP_NAME = "NOVA"
APP_VERSION = "0.6.0-beta"
RELEASE_CHANNEL = "beta"
BUILD_LABEL = "Beta 0.6 · Desktop Control & Multi-Agent Architecture"


def version_info() -> dict[str, str]:
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "channel": RELEASE_CHANNEL,
        "build": BUILD_LABEL,
    }
