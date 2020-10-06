knuto
=====
Kafka Namespaced User/Topic Operator

Current chart version is `0.9.0`





## Chart Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| image | string | `"niradynamics/knuto:94f0e50"` | Which knuto docker image to install |
| kafkauser_source_namespaces.dev.deletion_enabled | bool | `true` |  |
| kafkauser_source_namespaces.latest.deletion_enabled | bool | `false` |  |
| kafkauser_source_namespaces.production.deletion_enabled | bool | `false` |  |
| kafkauser_source_namespaces.dev.cross_namespace_read_allowed | bool | `false` | Set to true if it should be allowed to create users with read access from all topics. |
| kafkauser_source_namespaces.latest.cross_namespace_read_allowed | bool | `false` | Set to true if it should be allowed to create users with read access from all topics. |
| kafkauser_source_namespaces.production.cross_namespace_read_allowed | bool | `false` | Set to true if it should be allowed to create users with read access from all topics. |
| kafkauser_source_namespaces.dev.read_allowed_non_namespaced_topics | list of strings | [] | Topics not prefixed with "dev-" which is still allowed to create users with read permissions to. |
| kafkauser_source_namespaces.latest.read_allowed_non_namespaced_topics | list of strings | [] | Topics not prefixed with "latest-" which is still allowed to create users with read permissions to. |
| kafkauser_source_namespaces.production.read_allowed_non_namespaced_topics | list of strings | [] | Topics not prefixed with "production-" which is still allowed to create users with read permissions to. |
| kafkauser_source_namespaces.dev.cross_namespace_write_allowed | bool | `false` | Set to true if it should be allowed to create users with write access to all topics. |
| kafkauser_source_namespaces.latest.cross_namespace_write_allowed | bool | `false` | Set to true if it should be allowed to create users with write access to all topics. |
| kafkauser_source_namespaces.production.cross_namespace_write_allowed | bool | `false` | Set to true if it should be allowed to create users with write access to all topics. |
| kafkauser_source_namespaces.dev.write_allowed_non_namespaced_topics | list of strings | [] | Topics not prefixed with "dev-" which is still allowed to create users with write permissions to. |
| kafkauser_source_namespaces.latest.write_allowed_non_namespaced_topics | list of strings | [] | Topics not prefixed with "latest-" which is still allowed to create users with write permissions to. |
| kafkauser_source_namespaces.production.write_allowed_non_namespaced_topics | list of strings | [] | Topics not prefixed with "production-" which is still allowed to create users with write permissions to. |
| secret_type_to_bootstrap_server | object | `{"scram-sha-512":"production-kafka-bootstrap.kafka.svc.cluster.local:9092"}` | Mapping of secret type to the DNS name an port of the Kafka service. Used to construct kafka-client.properties in Secrets placed in the namespaces configured in kafkauser_source_namespaces |
| strimzi_namespace | string | `"kafka"` | The namespace in which the Strimzi User and Topic operator listens for KafkaUser and KafkaTopic CRDs. |
