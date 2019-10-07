import kopf
from kopf.clients.auth import login_pykube, get_pykube_api
from pykube import object_factory

from .utils import _copy_object
from .config import globalconf

login_pykube()
api = get_pykube_api()

KafkaUser = object_factory(api, "kafka.strimzi.io/v1beta1", "KafkaUser")

@kopf.on.create("kafka.strimzi.io", "v1beta1", "kafkausers")
def create_fn(body, namespace, name, logger, **kwargs):
    dst_namespace = globalconf.conf.get("knuto.strimzi_watched_namespace")
    if namespace == dst_namespace:
        logger.info(f"Not doing anything for KafkaUser {namespace}/{name}")
        return
    if namespace in globalconf.conf.get_list("knuto.source_namespaces"):
        logger.info(f"KafkaUser {namespace}/{name} is in a namespace we watch, creating copy in {dst_namespace}")
        new_obj = _copy_object(body)
        new_obj["metadata"]["namespace"] = dst_namespace
        new_obj["metadata"]["name"] = f"{namespace}-{name}"
        new_kafkauser = KafkaUser(api, new_obj)
        new_kafkauser.annotations["knuto.niradynamics.se/source"] = f"{namespace}/{name}"
        new_kafkauser.create()
        return {'copied_to': f"{dst_namespace}/{namespace}-{name}"}


@kopf.on.update("kafka.strimzi.io", "v1beta1", "kafkausers")
def update_fn(spec, status, namespace, logger, **kwargs):
    logger.info(f"Saw an update of {spec} in {namespace}")



