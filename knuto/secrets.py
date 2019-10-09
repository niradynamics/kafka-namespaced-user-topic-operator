import base64
import kopf
from kopf.clients.auth import login_pykube, get_pykube_api
from pykube import Secret
from .config import globalconf
from .utils import _copy_object, main

login_pykube()
api = get_pykube_api()


@kopf.on.create("", "v1", "secrets", labels={"strimzi.io/kind":"KafkaUser"})
def kafka_secret(body, namespace, name, logger, **kwargs):
    new_obj = _copy_object(body)

    if "-" not in name:
        logger.debug("Skipping secret as it doesn't have a "-" in its name")
        return

    (dst_namespace, dst_name) = name.split("-", maxsplit=1)

    if dst_namespace not in globalconf.conf.get_list("knuto.source_namespaces"):
        logger.info("Skipping as its name prefix is not in our list of destination namespaces")

    if "password" in new_obj["data"]:
        secret_type = "scram-sha-512"
    else:
        logger.warning(f"Unable to work on secret {namespace}/{name}, unrecognized secret type")
        return

    broker_bootstrap_servers = globalconf.conf.get(f"knuto.broker-bootstrap-servers.{secret_type}")

    if secret_type == "scram-sha-512":
        password = base64.b64decode(body["data"]["password"])
        kafka_client_properties = f"""sasl.mechanism=SCRAM-SHA-256
security.protocol=SASL_PLAINTEXT
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required \
  username="{name}" \
  password="{password}";
bootstrap.servers={broker_bootstrap_servers}
""".encode("ascii")
        new_obj["data"]["kafka-client.properties"] = base64.b64encode(kafka_client_properties).decode("ascii")

        new_secret = Secret(api, new_obj)
        # Deleting to ensure we don't react on the secret we're creating
        del new_secret.labels["strimzi.io/kind"]

        new_secret.annotations["knuto.niradynamics.se/source"] = f"{namespace}/{name}"
        new_secret.metadata["name"] = f"{dst_name}-kafka-config"
        new_secret.metadata["namespace"] = dst_namespace
        logger.info("Creating %(namespace)s/%(name)s with a kafka-client.properties with SCRAM-SHA-256 configuration" % new_secret.metadata)
        new_secret.create()
        return {"copied_to": f"{new_namespace}/{new_name}"}



