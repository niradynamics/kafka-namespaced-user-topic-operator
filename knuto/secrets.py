import base64
import kopf
from kopf.clients.auth import login_pykube, get_pykube_api
from pykube import Secret
from .config import globalconf
from .utils import _copy_object, _update_or_create
from .utils import main  # makes the main function available when creating endpoints in setup.py

login_pykube()
api = get_pykube_api()


@kopf.on.create("", "v1", "secrets", labels={"strimzi.io/kind": "KafkaUser"})
def kafka_secret_create(body, namespace, name, logger, **kwargs):
    new_obj = _copy_object(body)

    if not _should_copy(name, namespace, new_obj, logger):
        return

    new_secret = _create_new_secret(name, namespace, new_obj)

    logger.info(
            f"Creating {new_secret.metadata['namespace']}/{new_secret} with a kafka-client.properties with SCRAM-SHA-256 configuration" % new_secret.metadata)
    _update_or_create(new_secret)

    return {"copied_to": f"{new_secret.metadata['namespace']}/{new_secret}"}


@kopf.on.create("", "v1", "secrets", labels={"strimzi.io/kind": "KafkaUser"})
def kafka_secret(body, namespace, name, logger, **kwargs):
    new_obj = _copy_object(body)

    if not _should_copy(name, namespace, new_obj, logger):
        return

    new_secret = _create_new_secret(name, namespace, new_obj)

    logger.info(
            f"Updating {new_secret.metadata['namespace']}/{new_secret} with a kafka-client.properties with SCRAM-SHA-256 configuration" % new_secret.metadata)
    _update_or_create(new_secret)

    return {"updated": f"{new_secret.metadata['namespace']}/{new_secret}"}



def _should_copy(name, namespace, obj, logger):
    if "-" not in name:
        logger.debug("Skipping secret as it doesn't have a \"-\" in its name")
        return False

    (dst_namespace, dst_name) = name.split("-", maxsplit=1)

    if dst_namespace not in globalconf.conf.get_list("knuto.source_namespaces"):
        logger.info(f"Skipping as Secret's name prefix ({dst_namespace} is not in our list of destination namespaces")
        return False

    if "password" in obj["data"]:
        return True
    else:
        logger.warning(f"Unable to work on secret {namespace}/{name}, unrecognized secret type")

    return False


def _create_new_secret(name, source_namespace, secret_copy):

    (dst_namespace, dst_name) = name.split("-", maxsplit=1)

    # Slightly silly, but we'll only reach this point if _should_copy already said it's there
    # Later on, we'll handle more types, so this is future extension point.
    secret_type = None
    if "password" in secret_copy["data"]:
        secret_type = "scram-sha-512"

    broker_bootstrap_servers = globalconf.conf.get(f"knuto.broker-bootstrap-servers.{secret_type}")

    if secret_type == "scram-sha-512":
        password = base64.b64decode(secret_copy["data"]["password"])
        kafka_client_properties = f"""sasl.mechanism=SCRAM-SHA-256
    security.protocol=SASL_PLAINTEXT
    sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required \
      username="{name}" \
      password="{password}";
    bootstrap.servers={broker_bootstrap_servers}
    """.encode("ascii")
        new_secret = Secret(api, secret_copy)
        new_secret.obj["data"]["kafka-client.properties"] = base64.b64encode(kafka_client_properties).decode("ascii")

        new_secret = Secret(api, secret_copy)
        # Deleting to ensure we don't react on the secret we're creating
        del new_secret.labels["strimzi.io/kind"]

        new_secret.annotations["knuto.niradynamics.se/source"] = f"{source_namespace}/{name}"
        new_secret.metadata["name"] = f"{dst_name}-kafka-config"
        new_secret.metadata["namespace"] = dst_namespace

        return new_secret
