knuto
=====
Kafka Namespaced User/Topic Operator

Current chart version is `0.7.0`





## Chart Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| image | string | `"036535796760.dkr.ecr.eu-west-1.amazonaws.com/erfor/knuto:f83fdc4"` | Which knuto docker image to install |
| kafkauser_source_namespaces.dev.deletion_enabled | bool | `true` |  |
| kafkauser_source_namespaces.latest.deletion_enabled | bool | `false` |  |
| kafkauser_source_namespaces.production.deletion_enabled | bool | `false` |  |
| secret_type_to_bootstrap_server | object | `{"scram-sha-512":"production-kafka-bootstrap.kafka.svc.cluster.local:9092"}` | MApping of secret type to the DNS name an port of the Kafka service. Used to construct kafka-client.properties in Secrets placed in the namespaces configured in kafkauser_source_namespaces |
| strimzi_namespace | string | `"kafka"` | The namespace in which the Strimzi User and Topic operator listens for KafkaUser and KafkaTopic CRDs. |
