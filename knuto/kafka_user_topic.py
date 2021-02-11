from argparse import ArgumentParser, Action

import kopf
from pykube import object_factory

from knuto.config import globalconf, state
from knuto.utils import _copy_object, _update_or_create, default_main


class AclNotAllowed(Exception):
    pass


def check_acl_allowed(logger, namespace, acls):
    logger.debug("Checking if ACLs given by user are permitted")
    idx = 0

    def log_and_raise(msg):
        logger.warning(msg)
        raise AclNotAllowed(msg)

    for acl in acls:
        logger.debug(f"ACL {idx}: {acl}")
        resource = acl["resource"]
        operation = acl["operation"]
        if resource["type"] not in ["group", "topic"]:
            log_and_raise(
                f"ACL {idx}: Only group and topic resources allowed, not {resource}"
            )

        if operation not in ["Read", "Write"]:
            log_and_raise(
                "ACL {idx}: Only Read and Write operations allowed, not {operation}"
            )

        if resource["patternType"] not in ["literal", "prefix"]:
            log_and_raise(
                f"Unsupported patternType {resource['patternType']}, operator needs upgrade?"
            )

        if (
            operation == "Read"
            and not globalconf.cross_namespace_read_enabled
            and not resource["name"].startswith(f"{namespace}-")
            and resource["name"] not in globalconf.read_allowed_non_namespaced_topics
        ):
            log_and_raise(
                f"ACL {idx}: resource name {resource['name']} does "
                f"neither begin with {namespace}- nor is it included in "
                "allowed non namespaced topics, operation Read not "
                "allowed."
            )

        if (
            operation == "Write"
            and not globalconf.cross_namespace_write_enabled
            and not resource["name"].startswith(f"{namespace}-")
            and resource["name"] not in globalconf.write_allowed_non_namespaced_topics
        ):
            log_and_raise(
                f"ACL {idx}: resource name {resource['name']} does "
                f"neither begin with {namespace}- nor is it included in "
                "allowed non namespaced topics, operation Write not "
                "allowed."
            )

        idx += 1


@kopf.on.create("kafka.strimzi.io", "v1beta1", "kafkausers")
def create_kafkauser(body, namespace, name, logger, **_):
    _update_or_create_kafkauser(
        body, namespace, name, logger, return_key="copied_to", logged_action="created"
    )


@kopf.on.update("kafka.strimzi.io", "v1beta1", "kafkausers")
def update_kafkauser(body, namespace, name, logger, **_):
    _update_or_create_kafkauser(
        body, namespace, name, logger, return_key="updated", logged_action="updated"
    )


def _update_or_create_kafkauser(
    body, namespace, name, logger, *, return_key, logged_action
):
    dst_namespace = globalconf.kafka_user_topic_destination_namespace

    try:
        check_acl_allowed(
            logger, namespace, body["spec"]["authorization"].get("acls", [])
        )
    except AclNotAllowed as e:
        return {"acl_not_allowed": str(e)}

    logger.info(
        f"KafkaUser {namespace}/{name} {logged_action}, copying change to {dst_namespace}"
    )
    new_kafkauser = _copy_kafkauser(body, namespace, name)
    _update_or_create(new_kafkauser)
    return {return_key: f"{dst_namespace}/{namespace}-{name}"}


@kopf.on.delete("kafka.strimzi.io", "v1beta1", "kafkausers")
def delete_kafkauser(body, namespace, name, logger, **_):
    dst_namespace = globalconf.kafka_user_topic_destination_namespace
    logger.info(
        f"KafkaUser {namespace}/{name} deleted, deleting copy in {dst_namespace}"
    )
    to_be_deleted = _copy_kafkauser(body, namespace, name)
    logger.debug(
        "Checking if {to_be_deleted.metadata['namespace']}/{to_be_deleted} exists"
    )
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
    new_kafkauser.annotations["knuto.niradynamics.se/created"] = "true"

    return new_kafkauser


@kopf.on.create("kafka.strimzi.io", "v1beta1", "kafkatopics")
def create_kafkatopic(body, namespace, name, logger, **_):
    return _update_or_create_kafkatopic(
        body, namespace, name, logger, return_key="copied_to", logged_action="created"
    )


@kopf.on.update("kafka.strimzi.io", "v1beta1", "kafkatopics")
def update_kafkatopic(body, namespace, name, logger, **_):
    return _update_or_create_kafkatopic(
        body, namespace, name, logger, return_key="updated", logged_action="updated"
    )


def _update_or_create_kafkatopic(
    body, namespace, name, logger, *, return_key, logged_action
):
    dst_namespace = globalconf.kafka_user_topic_destination_namespace

    topic_name = body["spec"].get("topicName", name)
    if not topic_name.startswith(f"{namespace}-"):
        logger.error(
            f"KafkaTopic {namespace}/{name}'s topicName or name not prefixed with {namespace}-, not copying!"
        )
        return {"policy_violation": f"Topic name should be prefixed with {namespace}-"}

    logger.info(
        f"KafkaTopic {namespace}/{name} {logged_action}, copying change to {dst_namespace}"
    )
    new_kafkatopic = _copy_kafkatopic(body, namespace, name)
    _update_or_create(new_kafkatopic)

    return {return_key: f"{dst_namespace}/{namespace}-{name}"}


@kopf.on.delete("kafka.strimzi.io", "v1beta1", "kafkatopics")
def delete_kafkatopic(body, namespace, name, logger, **_):
    dst_namespace = globalconf.kafka_user_topic_destination_namespace
    if not globalconf.kafka_topic_deletion_enabled:
        logger.warning(
            f"KafkaTopic {namespace}/{name} deleted, deletion not enabled, not deleting copy in {dst_namespace}"
        )
        return {
            "not_deleting": f"Deletion of KafkaTopic not enabled for namespace {namespace}"
        }

    logger.info(
        f"KafkaTopic {namespace}/{name} deleted, deleting copy in {dst_namespace}"
    )
    to_be_deleted = _copy_kafkatopic(body, namespace, name)
    logger.debug(
        "Checking if {to_be_deleted.metadata['namespace']}/{to_be_deleted} exists"
    )
    if to_be_deleted.exists():
        logger.info("Deleting {to_be_deleted.metadata['namespace']}/{to_be_deleted}")
        to_be_deleted.delete()


def _copy_kafkatopic(body, namespace, name):
    dst_namespace = globalconf.kafka_user_topic_destination_namespace
    new_obj = _copy_object(body)
    new_obj["metadata"]["namespace"] = dst_namespace
    KafkaTopic = object_factory(state.api, "kafka.strimzi.io/v1beta1", "KafkaTopic")
    new_kafkatopic = KafkaTopic(state.api, new_obj)
    new_kafkatopic.annotations["knuto.niradynamics.se/source"] = f"{namespace}/{name}"
    new_kafkatopic.annotations["knuto.niradynamics.se/created"] = "true"

    return new_kafkatopic


class StoreTopicDestinationNamespace(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        globalconf.kafka_user_topic_destination_namespace = values


class StoreTopicDeletionEnabled(Action):
    def __init__(self, *args, **kwargs):
        kwargs["nargs"] = 0
        super(StoreTopicDeletionEnabled, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        globalconf.kafka_topic_deletion_enabled = True


class StoreEnableCrossNamespaceRead(Action):
    def __init__(self, *args, **kwargs):
        kwargs["nargs"] = 0
        super(StoreEnableCrossNamespaceRead, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        globalconf.cross_namespace_read_enabled = True


class StoreEnableCrossNamespaceWrite(Action):
    def __init__(self, *args, **kwargs):
        kwargs["nargs"] = 0
        super(StoreEnableCrossNamespaceWrite, self).__init__(*args, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        globalconf.cross_namespace_write_enabled = True


class StoreReadAllowedCrossNamespaceTopics(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        globalconf.read_allowed_non_namespaced_topics = values


class StoreWriteAllowedNonNamespacedTopics(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        globalconf.write_allowed_non_namespaced_topics = values


def main():
    program_args = ArgumentParser()
    program_args.add_argument(
        "--kafka-user-topic-destination-namespace",
        action=StoreTopicDestinationNamespace,
    )
    program_args.add_argument(
        "--enable-topic-deletion", action=StoreTopicDeletionEnabled
    )
    program_args.add_argument(
        "--enable-cross-namespace-read",
        action=StoreEnableCrossNamespaceRead,
        help="Use this flag to enable reads from all other namespaces.",
    )
    program_args.add_argument(
        "--read-allowed-non-namespaced-topics",
        nargs="*",
        action=StoreReadAllowedCrossNamespaceTopics,
        help="List of topics which has not been prefixed with the namespace, "
        "that are allowed to create kafka users with read permissions for.",
    )

    program_args.add_argument(
        "--enable-cross-namespace-write",
        action=StoreEnableCrossNamespaceWrite,
        help="Use this flag to enable writes to all other namespaces.",
    )
    program_args.add_argument(
        "--write-allowed-non-namespaced-topics",
        nargs="*",
        action=StoreWriteAllowedNonNamespacedTopics,
        help="List of topics which has not been prefixed with the namespace, "
        "that are allowed to create kafka users with write permissions for.",
    )

    return default_main([program_args])


if __name__ == "__main__":
    main()
