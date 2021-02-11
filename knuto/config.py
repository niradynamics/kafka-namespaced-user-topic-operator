#


class globalconf:
    kafka_user_topic_destination_namespace = None
    kafka_user_topic_source_namespaces = set([])
    secret_type_to_hostname_map = {}
    kafka_topic_deletion_enabled = False

    cross_namespace_read_enabled = False
    read_allowed_non_namespaced_topics = []

    cross_namespace_write_enabled = False
    write_allowed_non_namespaced_topics = []

    @classmethod
    def current_values(cls):
        pairs = []
        for name in [
            n for n in dir(cls) if not n.startswith("__") and not n == "current_values"
        ]:
            val = getattr(cls, name)
            pairs.append(f"{name}={val}")

        return ",".join(pairs)


class state:
    api = None
