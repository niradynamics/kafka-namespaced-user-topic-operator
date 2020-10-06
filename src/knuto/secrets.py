import base64
import kopf
from argparse import ArgumentParser, Action, ArgumentError
from pykube import Secret, object_factory
from .config import globalconf, state
from .utils import _copy_object, _update_or_create, default_main

SOURCE_ANNOTATION = "knuto.niradynamics.se/source"


@kopf.on.create("", "v1", "secrets", labels={"strimzi.io/kind": "KafkaUser"})
def kafka_secret_create(body, namespace, name, logger, **kwargs):
    new_obj = _copy_object(body)

    source_namespace = _source_namespace_for_secret(namespace, name, logger)

    if not _should_copy(name, namespace, source_namespace, body, logger):
        return

    new_secret = _create_new_secret(name, namespace, source_namespace, new_obj)

    # What we do here is to find the KafkaUser in the source namespace, and then let that adopt
    # the newly created secret. This gives us automatic deletion of the secret in the source namespace
    # if the KafkaUser is removed in the source namespace.
    corresponding_kafkauser = _load_kafkauser(
        new_secret.metadata["namespace"], name[len(source_namespace) + 1 :]
    )

    kopf.adopt([new_secret.obj], corresponding_kafkauser.obj)

    logger.info(
        f"Creating {new_secret.metadata['namespace']}/{new_secret} with a kafka-client.properties with SCRAM-SHA-256 configuration"
        % new_secret.metadata
    )
    _update_or_create(new_secret)

    return {"copied_to": f"{new_secret.metadata['namespace']}/{new_secret}"}


def _load_kafkauser(namespace, name):
    KafkaUser = object_factory(state.api, "kafka.strimzi.io/v1beta1", "KafkaUser")

    kafkauser = KafkaUser(
        state.api, {"metadata": {"namespace": namespace, "name": name}}
    )
    kafkauser.reload()

    return kafkauser


def _source_namespace_for_secret(namespace, name, logger):
    """Load the KafkaUser in the namespace handled by strimzi that corresponds to the newly created/updated
    secret, and check its annotations to find the namespace it was originally created in"""

    kafkauser = _load_kafkauser(namespace, name)

    if not SOURCE_ANNOTATION in kafkauser.annotations:
        logger.info(
            f"Skipping secret {namespace}/{name} has no {SOURCE_ANNOTATION} annotation"
        )
        return None

    source_namespace = kafkauser.annotations[SOURCE_ANNOTATION].split("/")[0]

    return source_namespace


@kopf.on.update("", "v1", "secrets", labels={"strimzi.io/kind": "KafkaUser"})
def kafka_secret(body, namespace, name, logger, **kwargs):
    new_obj = _copy_object(body)

    source_namespace = _source_namespace_for_secret(namespace, name, logger)

    if not _should_copy(name, namespace, source_namespace, body, logger):
        return

    new_secret = _create_new_secret(name, namespace, source_namespace, new_obj)

    logger.info(
        f"Updating {new_secret.metadata['namespace']}/{new_secret} with a kafka-client.properties with SCRAM-SHA-256 configuration"
        % new_secret.metadata
    )
    _update_or_create(new_secret)

    return {"updated": f"{new_secret.metadata['namespace']}/{new_secret}"}


def _should_copy(name, namespace, source_namespace, obj, logger):
    if source_namespace is None:
        return False

    if not source_namespace in globalconf.kafka_user_topic_source_namespaces:
        logger.info(
            f"Skipping as Secret's source namespace {{source_namespace}} is not in our list of destination namespaces"
        )
        return False

    if "password" in obj["data"]:
        return True
    else:
        logger.warning(
            f"Unable to work on secret {namespace}/{name}, unrecognized secret type"
        )

    return False


def _create_new_secret(name, strimzi_namespace, destination_namespace, secret_copy):

    dst_name = name[len(destination_namespace) + 1 :]

    # Slightly silly, but we'll only reach this point if _should_copy already said it's there
    # Later on, we'll handle more types, so this is future extension point.
    secret_type = None
    if "password" in secret_copy["data"]:
        secret_type = "scram-sha-512"

    broker_bootstrap_servers = globalconf.secret_type_to_hostname_map[secret_type]

    if secret_type == "scram-sha-512":
        password = base64.b64decode(secret_copy["data"]["password"]).decode("utf-8")
        kafka_client_properties = f"""sasl.mechanism=SCRAM-SHA-512
security.protocol=SASL_PLAINTEXT
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required \
username="{name}" \
password="{password}";
bootstrap.servers={broker_bootstrap_servers}
""".encode(
            "ascii"
        )
        new_secret = Secret(state.api, secret_copy)
        new_secret.obj["data"]["kafka-client.properties"] = base64.b64encode(
            kafka_client_properties
        ).decode("ascii")

        # Deleting to ensure we don't react on the secret we're creating
        del new_secret.labels["strimzi.io/kind"]

        new_secret.annotations[
            "knuto.niradynamics.se/source"
        ] = f"{strimzi_namespace}/{name}"
        new_secret.metadata["name"] = f"{dst_name}-kafka-config"
        new_secret.metadata["namespace"] = destination_namespace

        return new_secret


class BootstrapServerArgumentAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not "=" in values:
            raise ArgumentError(
                "Invalid value, should be on the form secret-type=bootstrapserver-dns-name:port"
            )
        (secret_type, server_addr) = values.split("=")
        globalconf.secret_type_to_hostname_map[secret_type] = server_addr


class TopicSourceNamespaceAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        globalconf.kafka_user_topic_source_namespaces.add(values)


def main():
    program_args = ArgumentParser()
    program_args.add_argument(
        "--secret-type-to-bootstrap-server",
        action=BootstrapServerArgumentAction,
        default={},
    )
    program_args.add_argument(
        "--kafka-user-topic-source-namespace",
        action=TopicSourceNamespaceAction,
        default=set([]),
    )

    return default_main([program_args])
