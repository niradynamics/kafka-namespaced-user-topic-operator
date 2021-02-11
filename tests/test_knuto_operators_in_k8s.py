"""
Runs integration tests with knuto operators running.
Activate by setting the environment variable KNUTO_INTEGRATION_TEST=1 or simply run
tox -e integration

Creates temporary test namespaces which contains the test resources and deletes namespaces after each test.
Running tests in minikube is recommended to avoid permission problems. Starting minikube is described at
https://minikube.sigs.k8s.io/docs/start/

The tests requires a strimzi operator running in the cluster to correctly handle CRDs.
The strimzi operator can be installed using the following two commands

helm repo add strimzi https://strimzi.io/charts/
helm install strimzi-operator strimzi/strimzi-kafka-operator

which are described in the strimzi documentation at
https://strimzi.io/docs/operators/master/deploying.html#deploying-cluster-operator-helm-chart-str
"""

import functools
import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Mapping, Sequence, Tuple

import jinja2
import pykube
import pytest
import yaml

INT_TEST_ENV_NAME = "KNUTO_INTEGRATION_TEST"

TEST_DATA_DIR = Path(__file__).parent / "test_data"

KAFKAUSER_BASE_YAML_FILE = TEST_DATA_DIR / "kafkauser_base.yaml"
KAFKATOPIC_BASE_YAML_FILE = TEST_DATA_DIR / "kafkatopic_base.yaml"
KAFKAUSER_ACL_BASE_YAML_FILE = TEST_DATA_DIR / "kafkauser_acl_base.yaml"
STRIMZI_SECRET_BASE_YAML_FILE = TEST_DATA_DIR / "strimzi_secret_base.yaml"
NAMESPACE_BASE_YAML_FILE = TEST_DATA_DIR / "namespace_base.yaml"

KAFKA_TEST_NAMESPACE = "integration-test-kafka-ns"
TEST_SOURCE_NAMESPACE = "integration-test-source-ns"

TEST_TOPIC_NAME = "test-topic-name"
TEST_USER_NAME = "test-user-name"
EXPECTED_KAFKA_USER_NAME = f"{TEST_SOURCE_NAMESPACE}-{TEST_USER_NAME}"
EXPECTED_KAFKA_TOPIC_NAME = f"{TEST_SOURCE_NAMESPACE}-{TEST_TOPIC_NAME}"

INTEGRATION_TESTS_ENABLED = os.getenv(INT_TEST_ENV_NAME)

integration_test_skipif = pytest.mark.skipif(
    not INTEGRATION_TESTS_ENABLED,
    reason=f"Integration tests disabled. Activate by setting environment variable {INT_TEST_ENV_NAME}",
)

user_acl_condition_table_params = pytest.mark.parametrize(
    "operation,topic_prefix,operator_args,expect_success",
    [
        ("Read", TEST_SOURCE_NAMESPACE, "", True),
        ("Read", "other-namespace", "", False),
        ("Read", "other-namespace", "--enable-cross-namespace-read", True),
        (
            "Read",
            "some-prefix",
            f"--read-allowed-non-namespaced-topics some-prefix-{TEST_TOPIC_NAME}",
            True,
        ),
        ("Write", TEST_SOURCE_NAMESPACE, "", True),
        ("Write", "other-namespace", "", False),
        ("Write", "other-namespace", "--enable-cross-namespace-write", True),
        (
            "Write",
            "some-prefix",
            f"--write-allowed-non-namespaced-topics some-prefix-{TEST_TOPIC_NAME}",
            True,
        ),
    ],
)


@integration_test_skipif
@user_acl_condition_table_params
def test_create_user_acl(
    api, *, operation, topic_prefix, operator_args, expect_success
):
    with user_topic_operator_test_context(operator_args):
        assert not _check_if_kafkauser_created(api)

        acls = [(operation, f"{topic_prefix}-{TEST_TOPIC_NAME}")]
        user_with_acls = _create_kafka_user(
            namespace=TEST_SOURCE_NAMESPACE, name=TEST_USER_NAME, acls=acls
        )
        _apply_object(user_with_acls)

        assert expect_success == _check_if_kafkauser_created(api)


@integration_test_skipif
@user_acl_condition_table_params
def test_update_user_acl(
    api, *, operation, topic_prefix, operator_args, expect_success
):
    with user_topic_operator_test_context(operator_args):
        user_without_acls = _create_kafka_user(
            namespace=TEST_SOURCE_NAMESPACE, name=TEST_USER_NAME, acls=[]
        )
        _apply_object(user_without_acls)
        assert _check_if_kafkauser_created(api)

        acls = [(operation, f"{topic_prefix}-{TEST_TOPIC_NAME}")]
        updated_user = _create_kafka_user(
            namespace=TEST_SOURCE_NAMESPACE, name=TEST_USER_NAME, acls=acls
        )
        _apply_object(updated_user)

        assert expect_success == _check_if_kafkauser_has_acls(api, acls)


@integration_test_skipif
def test_create_topic(api):
    with user_topic_operator_test_context():
        assert not _check_if_kafkatopic_created(api)
        topic = _create_kafka_topic(
            namespace=TEST_SOURCE_NAMESPACE, name=TEST_TOPIC_NAME
        )
        _apply_object(topic)

        assert _check_if_kafkatopic_created(api)


@integration_test_skipif
def test_create_secret(api):
    """
    Uses user_topic operator to create KafkaUser in kafka namespace.
    KafkaUser must exist before secret is created to avoid race condition
    and a failed secret copy operation.
    Stubs strimzi by putting a secret for that user in kafka namespace.
    Expects secrets operator to copy user secret into source namespace.
    """
    with secrets_operator_test_context():
        assert not _check_if_knuto_secret_created(api)

        user = _create_kafka_user(
            namespace=TEST_SOURCE_NAMESPACE, name=TEST_USER_NAME, acls=[]
        )
        strimzi_secret = _create_strimzi_secret(
            namespace=KAFKA_TEST_NAMESPACE,
            name=f"{TEST_SOURCE_NAMESPACE}-{TEST_USER_NAME}",
        )
        _apply_object(user)
        assert _check_if_kafkauser_created(api)

        _apply_object(strimzi_secret)
        assert _check_if_knuto_secret_created(api)


def _retry(fun, *, n, sleep_s):
    """Retries a function up to N times until it returns truthy value"""
    assert n

    @functools.wraps(fun)
    def wrapper(*args, **kwargs):
        res = None
        for _ in range(n):
            res = fun(*args, **kwargs)
            if res:
                return res
            time.sleep(sleep_s)

        return res

    return wrapper


def _retry_3(fun):
    """Retries a function up to 3 times with a 1 second sleep in between"""
    return _retry(fun, n=3, sleep_s=1)


def _retry_5(fun):
    """Retries a function up to 5 times with a 1 second sleep in between"""
    return _retry(fun, n=5, sleep_s=1)


@pytest.fixture
def api():
    config = pykube.KubeConfig.from_file()
    return pykube.HTTPClient(config)


@contextmanager
def user_topic_operator_test_context(extra_params=""):
    params = f"--kafka-user-topic-destination-namespace {KAFKA_TEST_NAMESPACE} {extra_params} -- {TEST_SOURCE_NAMESPACE}"
    with _temporary_kubernetes_test_namespace(), _run_knuto_operator(
        module="knuto.kafka_user_topic", params=params
    ) as op:
        yield op


@contextmanager
def secrets_operator_test_context(extra_params=""):
    secrets_params = f"--secret-type-to-bootstrap-server scram-sha-512=SERVER --kafka-user-topic-source-namespace {TEST_SOURCE_NAMESPACE} {extra_params} {KAFKA_TEST_NAMESPACE}"

    with user_topic_operator_test_context(), _run_knuto_operator(
        module="knuto.secrets", params=secrets_params
    ) as op:
        yield op


@contextmanager
def _temporary_kubernetes_test_namespace():
    _apply_object(_create_namespace(KAFKA_TEST_NAMESPACE))
    _apply_object(_create_namespace(TEST_SOURCE_NAMESPACE))
    try:
        yield
    finally:
        _delete_namespace_with_resources(KAFKA_TEST_NAMESPACE)
        _delete_namespace_with_resources(TEST_SOURCE_NAMESPACE)


def _delete_namespace_with_resources(namespace):
    for resource in ["kafkauser", "kafkatopic", "secrets"]:
        subprocess.run(f"kubectl -n {namespace} delete {resource} --all", shell=True)
    subprocess.run(f"kubectl delete namespace {namespace}", shell=True)


@_retry_3
def _check_if_kafkauser_created(api) -> bool:
    kafkausers = _get_kafkausers(api, KAFKA_TEST_NAMESPACE)
    return any(user.name == EXPECTED_KAFKA_USER_NAME for user in kafkausers)


def _get_kafkausers(api, namespace):
    kafkauser_type = pykube.object_factory(api, "kafka.strimzi.io/v1beta1", "KafkaUser")
    return list(kafkauser_type.objects(api, namespace=namespace))


@_retry_3
def _check_if_kafkauser_has_acls(api, acls) -> bool:
    kafkausers = _get_kafkausers(api, KAFKA_TEST_NAMESPACE)
    return any(
        all(
            _create_kafka_user_acl(acl[0], acl[1])
            in user.obj["spec"]["authorization"]["acls"]
            for acl in acls
        )
        for user in kafkausers
    )


@_retry_3
def _check_if_kafkatopic_created(api) -> bool:
    kafkatopics = _get_kafkatopics(api, KAFKA_TEST_NAMESPACE)
    return any(topic.name == EXPECTED_KAFKA_TOPIC_NAME for topic in kafkatopics)


def _get_kafkatopics(api, namespace):
    kafkatopic_type = pykube.object_factory(
        api, "kafka.strimzi.io/v1beta1", "KafkaTopic"
    )
    return list(kafkatopic_type.objects(api, namespace=namespace))


@_retry_5
def _check_if_knuto_secret_created(api):
    secrets = list(pykube.objects.Secret.objects(api, namespace=TEST_SOURCE_NAMESPACE))
    expected_secret_name = f"{TEST_USER_NAME}-kafka-config"
    return any(secret.name == expected_secret_name for secret in secrets)


def _apply_object(obj: Mapping):
    """Apply a config with kubectl"""
    data = yaml.dump(obj)
    subprocess.run(f"kubectl apply -f -", shell=True, check=True, text=True, input=data)


@contextmanager
def _run_knuto_operator(*, module, params):
    proc = subprocess.Popen(
        f"python -m {module} {params}",
        shell=True,
    )
    try:
        yield proc
    finally:
        proc.terminate()
        proc.wait(timeout=3)

        if proc.returncode is None:
            print("Forcefully killing operator")
            proc.kill()


def _create_namespace(name) -> Mapping:
    return _render_obj(NAMESPACE_BASE_YAML_FILE, name=name)


def _render_obj(template_path: Path, **kwargs) -> Mapping:
    """Instantiates a yaml template and returns it as an object."""
    text = jinja2.Template(template_path.read_text()).render(**kwargs)
    return yaml.load(text, Loader=yaml.FullLoader)


def _create_kafka_user(*, namespace, name, acls: Sequence[Tuple[str, str]]) -> Mapping:
    obj = _render_obj(KAFKAUSER_BASE_YAML_FILE, namespace=namespace, name=name)
    obj["spec"]["authorization"]["acls"] = list(
        _create_kafka_user_acl(acl[0], acl[1]) for acl in acls
    )
    return obj


def _create_kafka_topic(*, namespace, name) -> Mapping:
    topic_name = f"{namespace}-{name}"
    return _render_obj(KAFKATOPIC_BASE_YAML_FILE, namespace=namespace, name=topic_name)


def _create_kafka_user_acl(operation, name) -> Mapping:
    return _render_obj(KAFKAUSER_ACL_BASE_YAML_FILE, name=name, operation=operation)


def _create_strimzi_secret(*, namespace, name) -> Mapping:
    return _render_obj(STRIMZI_SECRET_BASE_YAML_FILE, namespace=namespace, name=name)
