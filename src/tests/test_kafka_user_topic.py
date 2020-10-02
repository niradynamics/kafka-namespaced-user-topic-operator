from unittest import TestCase
from mock import patch, MagicMock

from knuto.kafka_user_topic import check_acl_allowed, AclNotAllowed


class Test_check_acl_allowed(TestCase):
    @patch("knuto.kafka_user_topic.globalconf")
    def test_allow_write_to_cross_namespaced_topics(self, globalconf):
        logger = MagicMock()

        globalconf.cross_namespace_write_enabled = True
        globalconf.write_allowed_non_namespaced_topics = []

        namespace = "foobar"
        topic = f"other-namespace-some-topic"
        acls = self._get_acls("Write", topic)

        # Should not Raise an exception there
        check_acl_allowed(logger, namespace, acls)

    @patch("knuto.kafka_user_topic.globalconf")
    def test_allow_write_to_namespaced_topics(self, globalconf):
        logger = MagicMock()

        globalconf.cross_namespace_write_enabled = False
        globalconf.write_allowed_non_namespaced_topics = []

        namespace = "foobar"
        topic = f"{namespace}-some-topic"
        acls = self._get_acls("Write", topic)

        # Should not Raise an exception there
        check_acl_allowed(logger, namespace, acls)

    @patch("knuto.kafka_user_topic.globalconf")
    def test_block_write_to_not_allowed_topics(self, globalconf):
        logger = MagicMock()

        globalconf.cross_namespace_write_enabled = False
        globalconf.write_allowed_non_namespaced_topics = []

        topic = "non-namespaced-topic"
        acls = self._get_acls("Write", topic)

        with self.assertRaises(AclNotAllowed):
            check_acl_allowed(logger, "my-namespace", acls)

    @patch("knuto.kafka_user_topic.globalconf")
    def test_allow_write_to_configured_allowed_topics(self, globalconf):
        logger = MagicMock()

        topic = "non-namespaced-topic"

        globalconf.cross_namespace_write_enabled = False
        globalconf.write_allowed_non_namespaced_topics = [topic, "other-topic"]

        acls = self._get_acls("Write", topic)

        # Should not Raise an exception there
        check_acl_allowed(logger, "my-namespace", acls)

    @patch("knuto.kafka_user_topic.globalconf")
    def test_allow_read_to_cross_namespaced_topics(self, globalconf):
        logger = MagicMock()

        globalconf.cross_namespace_read_enabled = True
        globalconf.read_allowed_non_namespaced_topics = []

        namespace = "foobar"
        topic = f"other-namespace-some-topic"
        acls = self._get_acls("Read", topic)

        # Should not Raise an exception there
        check_acl_allowed(logger, namespace, acls)

    @patch("knuto.kafka_user_topic.globalconf")
    def test_allow_read_to_namespaced_topics_with_only_namespace_read(self, globalconf):
        logger = MagicMock()

        globalconf.cross_namespace_read_enabled = False
        globalconf.read_allowed_non_namespaced_topics = []

        namespace = "foobar"
        topic = f"{namespace}-some-topic"
        acls = self._get_acls("Read", topic)

        # Should not Raise an exception there
        check_acl_allowed(logger, namespace, acls)

    @patch("knuto.kafka_user_topic.globalconf")
    def test_block_read_to_not_allowed_topics_with_only_namespace_read(
        self, globalconf
    ):
        logger = MagicMock()

        globalconf.cross_namespace_read_enabled = False
        globalconf.read_allowed_non_namespaced_topics = []

        topic = "non-namespaced-topic"
        acls = self._get_acls("Read", topic)

        with self.assertRaises(AclNotAllowed):
            check_acl_allowed(logger, "my-namespace", acls)

    @patch("knuto.kafka_user_topic.globalconf")
    def test_allow_read_to_configured_allowed_topics_with_only_namespace_read(
        self, globalconf
    ):
        logger = MagicMock()

        topic = "non-namespaced-topic"

        globalconf.cross_namespace_read_enabled = False
        globalconf.read_allowed_non_namespaced_topics = [topic, "other-topic"]

        acls = self._get_acls("Read", topic)

        # Should not Raise an exception there
        check_acl_allowed(logger, "my-namespace", acls)

    @staticmethod
    def _get_acls(operation, topic):
        return [
            {
                "resource": {"name": topic, "type": "topic", "patternType": "literal"},
                "operation": operation,
            }
        ]
