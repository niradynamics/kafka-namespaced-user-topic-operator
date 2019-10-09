from argparse import ArgumentParser, Action

import kopf
from pykube import object_factory

from .utils import _copy_object, _update_or_create, default_main
from .config import globalconf, state


@kopf.on.create("kafka.strimzi.io", "v1beta1", "kafkausers")
def create_fn(body, namespace, name, logger, **kwargs):
    dst_namespace = globalconf.kafka_user_topic_destination_namespace
    logger.info(f"KafkaUser {namespace}/{name} created, creating copy in {dst_namespace}")
    new_kafkauser = _copy_kafkauser(body, namespace, name)
    _update_or_create(new_kafkauser)

    return {'copied_to': f"{dst_namespace}/{namespace}-{name}"}


@kopf.on.update("kafka.strimzi.io", "v1beta1", "kafkausers")
def update_fn(body, namespace, name, logger, **kwargs):
    dst_namespace = globalconf.kafka_user_topic_destination_namespace
    logger.info(f"KafkaUser {namespace}/{name} updated, updating copy in {dst_namespace}")
    new_kafkauser = _copy_kafkauser(body, namespace, name)
    _update_or_create(new_kafkauser)

    return {'updated': f"{dst_namespace}/{namespace}-{name}"}


@kopf.on.delete("kafka.strimzi.io", "v1beta1", "kafkausers", optional=True)
def delete_fn(body, namespace, name, logger, **kwargs):
    dst_namespace = globalconf.kafka_user_topic_destination_namespace
    logger.info(f"KafkaUser {namespace}/{name} deleted, deleting copy in {dst_namespace}")
    to_be_deleted = _copy_kafkauser(body, namespace, name)
    logger.debug("Checking if {to_be_deleted.metadata['namespace']}/{to_be_deleted} exists")
    if to_be_deleted.exists():
        logger.info("Deleting {to_be_deleted.metadata['namespace']}/{to_be_deleted}")
        to_be_deleted.delete()


def _copy_kafkauser(body, namespace, name):
    dst_namespace = globalconf.kafka_user_topic_destination_namespace
    new_obj = _copy_object(body)
    new_obj["metadata"]["namespace"] = dst_namespace
    new_obj["metadata"]["name"] = f"{namespace}-{name}"
    KafkaUser = object_factory(state.api, "kafka.strimzi.io/v1beta1", "KafkaUser")
    new_kafkauser = KafkaUser(state.api, new_obj)
    new_kafkauser.annotations["knuto.niradynamics.se/source"] = f"{namespace}/{name}"

    return new_kafkauser


class StoreTopicDestinationNamespace(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        globalconf.kafka_user_topic_destination_namespace = values


def main():
    program_args = ArgumentParser()
    program_args.add_argument("--kafka-user-topic-destination-namespace", action=StoreTopicDestinationNamespace)

    return default_main([program_args])
