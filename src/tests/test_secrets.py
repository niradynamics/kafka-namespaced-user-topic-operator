from unittest import TestCase
from mock import patch, MagicMock

import base64

from knuto.secrets import (
    _should_copy,
    kafka_secret_create,
    kafka_secret,
    _source_namespace_for_secret,
)


class Test_should_copy(TestCase):
    @patch("knuto.secrets.globalconf")
    def test_correct_namespace(self, globalconf):
        logger = MagicMock()

        globalconf.kafka_user_topic_source_namespaces = set(
            ["latest", "ingestion-latest"]
        )

        self.assertTrue(
            _should_copy(
                "latest-something",
                "kafka",
                "latest",
                {"data": {"password": "pw"}},
                logger,
            )
        )

        self.assertTrue(
            _should_copy(
                "ingestion-latest-something",
                "kafka",
                "ingestion-latest",
                {"data": {"password": "pw"}},
                logger,
            )
        )

        self.assertFalse(
            _should_copy(
                "ingestion-latest-something",
                "kafka",
                None,
                {"data": {"password": "pw"}},
                logger,
            )
        )

        self.assertFalse(
            _should_copy(
                "wrong-something",
                "kafka",
                "wrong",
                {"data": {"password": "pw"}},
                logger,
            )
        )

    @patch("knuto.secrets.globalconf")
    def test_scram_secret(self, globalconf):
        logger = MagicMock()

        globalconf.kafka_user_topic_source_namespaces = set(["ingestion-latest"])

        self.assertFalse(
            _should_copy(
                "ingestion-latest-something",
                "kafka",
                "ingestion-latest",
                {"data": {}},
                logger,
            )
        )


class Test_kafka_secret_create(TestCase):
    @patch("knuto.secrets._update_or_create")
    @patch("knuto.secrets._load_kafkauser")
    @patch("knuto.secrets.globalconf")
    @patch("knuto.secrets._source_namespace_for_secret")
    @patch("knuto.secrets._should_copy")
    def test_create(
        self,
        _should_copy,
        _source_namespace_for_secret,
        globalconf,
        _load_kafkauser,
        _update_or_create,
    ):
        logger = MagicMock()

        _source_namespace_for_secret.return_value = "ns-with-dash"
        _should_copy.return_value = True
        globalconf.secret_type_to_hostname = {"scram-sha-512": "broker"}
        _load_kafkauser.return_value = MagicMock()

        secret_obj = {
            "metadata": {
                "namespace": "kafka",
                "name": "ns-with-dash-test",
                "labels": {"strimzi.io/kind": "KafkaUser"},
            },
            "data": {"password": base64.b64encode("pass".encode("utf-8"))},
        }

        ret = kafka_secret_create(secret_obj, "kafka", "ns-with-dash-test", logger)

        _source_namespace_for_secret.assert_called_with(
            "kafka", "ns-with-dash-test", logger
        )
        _should_copy.assert_called_with(
            "ns-with-dash-test", "kafka", "ns-with-dash", secret_obj, logger
        )
        _load_kafkauser.assert_called_with("ns-with-dash", "test")
        _update_or_create.assert_called_once()

        secret_created = _update_or_create.call_args.args[0]

        # This test is not a unit test per se, as it also tests a bit of _create_new_secret
        self.assertEqual(secret_created.namespace, "ns-with-dash")
        self.assertEqual(secret_created.name, "test-kafka-config")
        self.assertEqual(
            secret_created.annotations,
            {"knuto.niradynamics.se/source": "kafka/ns-with-dash-test"},
        )
        self.assertTrue("kafka-client.properties" in secret_created.obj["data"])

        self.assertEqual(ret, {"copied_to": "ns-with-dash/test-kafka-config"})


class Test_kafka_secret(TestCase):
    @patch("knuto.secrets.globalconf")
    @patch("knuto.secrets._update_or_create")
    @patch("knuto.secrets._should_copy")
    @patch("knuto.secrets._source_namespace_for_secret")
    def test_update(
        self, _source_namespace_for_secret, _should_copy, _update_or_create, globalconf
    ):
        _should_copy.return_value = True
        _source_namespace_for_secret.return_value = "ns"
        globalconf.secret_type_to_hostname = {"scram-sha-512": "broker"}

        logger = MagicMock()

        secret_obj = {
            "metadata": {
                "namespace": "kafka",
                "name": "ns-test",
                "labels": {"strimzi.io/kind": "KafkaUser"},
            },
            "data": {"password": base64.b64encode("pass".encode("utf-8"))},
        }

        ret = kafka_secret(secret_obj, "kafka", "ns-test", logger)

        self.assertEqual(ret, {"updated": "ns/test-kafka-config"})


class Test_Source_Namespace_For_Secret(TestCase):
    @patch("knuto.secrets._load_kafkauser")
    def test_with_correct_annotation(self, _load_kafkauser):
        logger = MagicMock()
        _load_kafkauser.return_value = MagicMock()
        _load_kafkauser.return_value.annotations = {
            "knuto.niradynamics.se/source": "ns-with-dash/test"
        }

        ret = _source_namespace_for_secret("kafka", "ns-with-dash-test", logger)

        _load_kafkauser.assert_called_with("kafka", "ns-with-dash-test")

        self.assertEqual(ret, "ns-with-dash")

    @patch("knuto.secrets._load_kafkauser")
    def test_with_no_annotation(self, _load_kafkauser):
        logger = MagicMock()
        _load_kafkauser.return_value = MagicMock()
        _load_kafkauser.return_value.annotations = {}

        ret = _source_namespace_for_secret("kafka", "ns-with-dash-test", logger)

        self.assertEqual(ret, None)
