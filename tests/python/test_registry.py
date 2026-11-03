import unittest

from nova_agents.registry import agent_catalog, agent_ids, validate_agent_registry
from nova_agents.version import APP_NAME, APP_VERSION, RELEASE_CHANNEL


class RegistryTests(unittest.TestCase):
    def test_registry_has_unique_stable_ids_and_required_metadata(self):
        validate_agent_registry()
        profiles = agent_catalog()
        ids = [profile["id"] for profile in profiles]
        self.assertEqual(ids, list(agent_ids()))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {"reaction", "chat", "browser", "research"})
        for profile in profiles:
            self.assertTrue(profile["name"])
            self.assertTrue(profile["description"])
            self.assertTrue(profile["enabled"])

    def test_catalog_is_a_copy_not_mutable_internal_state(self):
        profiles = agent_catalog()
        profiles[0]["name"] = "Changed by caller"
        self.assertEqual(agent_catalog()[0]["name"], "Reaction Agent")

    def test_development_version_is_explicit(self):
        self.assertEqual(APP_NAME, "NOVA")
        self.assertEqual(APP_VERSION, "0.5.0-alpha")
        self.assertEqual(RELEASE_CHANNEL, "development")


if __name__ == "__main__":
    unittest.main()
