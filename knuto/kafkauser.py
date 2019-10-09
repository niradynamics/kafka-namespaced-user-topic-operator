import kopf
from kopf.clients.auth import login_pykube, get_pykube_api
from pykube import object_factory

from .utils import _copy_object, _update_or_create
from .config import globalconf
from .utils import main  # makes the main function available when creating endpoints in setup.py

login_pykube()
api = get_pykube_api()

KafkaUser = object_factory(api, "kafka.strimzi.io/v1beta1", "KafkaUser")

@kopf.on.create("kafka.strimzi.io", "v1beta1", "kafkausers")
def create_fn(body, namespace, name, logger, **kwargs):
    dst_namespace = globalconf.conf.get("knuto.strimzi_namespace")
    logger.info(f"KafkaUser {namespace}/{name} created, creating copy in {dst_namespace}")
    new_kafkauser = _copy_kafkauser(body, namespace, name, logger)
    _update_or_create(new_kafkauser)

    return {'copied_to': f"{dst_namespace}/{namespace}-{name}"}


@kopf.on.update("kafka.strimzi.io", "v1beta1", "kafkausers")
def update_fn(body, namespace, name, logger, **kwargs):
    dst_namespace = globalconf.conf.get("knuto.strimzi_namespace")
    logger.info(f"KafkaUser {namespace}/{name} updated, updating copy in {dst_namespace}")
    new_kafkauser = _copy_kafkauser(body, namespace, name, logger)
    _update_or_create(new_kafkauser)

    return {'updated': f"{dst_namespace}/{namespace}-{name}"}


def _copy_kafkauser(body, namespace, name, logger):
    new_obj = _copy_object(body)
    new_obj["metadata"]["namespace"] = dst_namespace
    new_obj["metadata"]["name"] = f"{namespace}-{name}"
    new_kafkauser = KafkaUser(api, new_obj)
    new_kafkauser.annotations["knuto.niradynamics.se/source"] = f"{namespace}/{name}"

    return new_kafkauser

