from unittest import TestCase
from mock import patch, MagicMock

from knuto.kafka_user_topic import check_acl_allowed, AclNotAllowed


class Test_check_acl_allowed(TestCase):
    @patch("knuto.kafka_user_topic.globalconf")
    def test_allow_namespaced_topics(self, globalconf):
        logger = MagicMock()

        globalconf.allowed_non_namespaced_topics = []

        namespace = "foobar"
        topic = f"{namespace}-some-topic"
        acls = [
            {
                "resource": {"name": topic, "type": "topic", "patternType": "literal"},
                "operation": "Write",
            }
        ]

        # Should not Raise an exception there
        check_acl_allowed(logger, namespace, acls)

    @patch("knuto.kafka_user_topic.globalconf")
    def test_block_not_allowed_topics(self, globalconf):
        logger = MagicMock()

        globalconf.allowed_non_namespaced_topics = []

        topic = "non-namespaced-topic"
        acls = [
            {
                "resource": {"name": topic, "type": "topic", "patternType": "literal"},
                "operation": "Write",
            }
        ]

        with self.assertRaises(AclNotAllowed):
            check_acl_allowed(logger, "my-namespace", acls)

    @patch("knuto.kafka_user_topic.globalconf")
    def test_allow_configured_allowed_topics(self, globalconf):
        logger = MagicMock()

        topic = "non-namespaced-topic"

        globalconf.allowed_non_namespaced_topics = [topic, "other-topic"]

        acls = [
            {
                "resource": {"name": topic, "type": "topic", "patternType": "literal"},
                "operation": "Write",
            }
        ]

        # Should not Raise an exception there
        check_acl_allowed(logger, "my-namespace", acls)
