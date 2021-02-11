from mock import patch, MagicMock
import pytest

from knuto.kafka_user_topic import check_acl_allowed, AclNotAllowed


TEST_SOURCE_NS = "test-source-ns"
TEST_TOPIC_NAME = "test-topic-name"


@pytest.mark.parametrize(
    "operation,target_ns,cross_ns,non_ns_topics,expect_ok",
    [
        ("Write", TEST_SOURCE_NS, False, [], True),
        ("Write", "other-namespace", True, [], True),
        ("Write", "some-prefix", False, [], False),
        (
            "Write",
            "some-prefix",
            False,
            [f"some-prefix-{TEST_TOPIC_NAME}"],
            True,
        ),
        ("Read", TEST_SOURCE_NS, False, [], True),
        ("Read", "other-namespace", True, [], True),
        ("Read", "some-prefix", False, ["other-topic"], False),
        (
            "Read",
            "some-prefix",
            False,
            [f"some-prefix-{TEST_TOPIC_NAME}", "other-topic"],
            True,
        ),
    ],
)
@patch("knuto.kafka_user_topic.globalconf")
def test_acl_rules(
    globalconf, *, operation, target_ns, cross_ns, non_ns_topics, expect_ok
):
    logger = MagicMock()

    if operation == "Write":
        globalconf.cross_namespace_write_enabled = cross_ns
        globalconf.write_allowed_non_namespaced_topics = non_ns_topics
    else:
        globalconf.cross_namespace_read_enabled = cross_ns
        globalconf.read_allowed_non_namespaced_topics = non_ns_topics

    topic = f"{target_ns}-{TEST_TOPIC_NAME}"
    acls = _get_acls(operation, topic)

    if expect_ok:
        check_acl_allowed(logger, TEST_SOURCE_NS, acls)
    else:
        with pytest.raises(AclNotAllowed):
            check_acl_allowed(logger, TEST_SOURCE_NS, acls)


def _get_acls(operation, topic):
    return [
        {
            "resource": {"name": topic, "type": "topic", "patternType": "literal"},
            "operation": operation,
        }
    ]
