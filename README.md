# Kafka Namespaced User Topic Operator (KNUTO)

## What is this?

This is a Kubernetes operator that will complement the [Strimzi](https://strimzi.io)
Kafka User and Topic operators by enabling User and Topic operator to work with multiple
namespaces.

The Strimzi operators by design does not handle multiple namespaces, but will only work with [[KafkaUser]] and [[KafkaTopic]]
[CRD]s in one namespace. One of the main resons for this is that the operators are bidirectional - if a user is created
in Kafka, the corresponding [KafkaUser] [CRD] will be created in Kubernetes, but there's no way to know which namespace
this [KafkaUser] should be created in.

The Kafka Namespaced User Topic Operator (from here on referered to as KNUTO) works around this by applying some
conventions when it comes to naming of Kafka users and topics, and by copying [KafkaUser], [KafkaTopic] and Secrets between
namespaces.

## Rationale

One common way of organizing a Kubernetes cluster used by an organization is to use multiple namespaces. For example,
there can be one namespace per team, or there can be a development namespace, a staging namespace and a production
namespace.

With Strimzi Kafka Operator, it is possible to configure one Kafka cluster per namespace, but this may not always
be desired, as multiple namespaces might want to use the data in one Kafka cluster, and there is a certain overhead
in running multiple Kafka clusters.

Note however that one Kafka cluster per namespace *is* a safer option when it comes to
separation of environments. Sharing a Kafka cluster means that an application in namespace A that misbehaves will also
cause problems for applications in namespace B talking to the same Kafka cluster. Your requirements should decide
which setup you use.

For an example usecase where we have two namespaces, *staging* and *production*, and both should share the same
Kafka cluster, the desired functionality is that applications deployed to both namespaces can add [KafkaUser]
and [KafkaTopic] [CRD]s together with the rest of their manifests to gain access to Kafka, and these [CRD]s should
be picked up by Strimzi so users with credentials as well as topics can be created.

## Conventions

KNUTO works with the assumption that topics and users are prepended with the namespace name in which they are defined.
So in our example with the *staging* and *production* namespaces, any topic that is **written** by an application in
the *staging* namespace should have a name that starts with "*staging-*". The same goes for users.

On the permissions/ACL side, it is assumed that a [KafkaUser] in any namespace is allowed to **read** data in all topics
in the Kafka cluster, but only a [KafkaUser] in the namespace associated with a topic (i.e where the topic name is prefixed
with the namespace name) is allowed to **write** to a topic.

This works well in a staging/production scenario, where for example an application in *staging* can read the
production data from a topic prefixed *production-*, but it can not write to any production topic, prohibiting
modification of the production environment.

## How it works

For every namespace that shares a Kafka cluster, KNUTO is configured to watch for [KafkaUser] and [KafkaTopic] [CRD]s being added.

### Handling [KafkaUser]

When a [KafkaUser] [CRD] is added to a namespace managed by KNUTO (but not by Strimzi), KNUTO will check that the access control rules follows conventions as outlined above,
and if they pass the test, add a few annotations and copy the [CRD] to the namespace managed by Strimzi User operator.

Once Strimzi has created the user, KNUTO will detect the creation of the Secret with credentials, modify this
Secret slightly to add a configuration file that can be used directly by the Kafka libraries for Java, and copy
it to the namespace in which the [KafkaUser] was created.

Currently, KNUTO only support SCRAM-SHA-512 credentials, and will log a warning and ignore Secrets with other forms of authentication.

A [KafkaUser] created with the name "*test*" in the "*staging*" namespace will be named "*staging-test*" in Kafka. The secret
generated in "*staging*" will be named "*test-kafka-config*" and will have two entries:

* password, which is the SCRAM-SHA-512 password.
* "kafka-client.properties" which can be read in a as a [Properties](https://docs.oracle.com/javase/9/docs/api/java/util/Properties.html)
  and passed to a Kafka Consumer or Producer. It contains the following properties:
  * sasl.mechanism
  * security.protocol=SASL_PLAINTEXT
  * sasl.jaas.config with username and password.
  * bootstrap.servers as configured when deploying KNUTO for the namespace.

The naming of objects in Kubernets are slightly confusing:

* [KafkaUser] in source namespace (in our example, "*staging"*) should be named after the service using it, without namespace prefix.
* [KafkaUser] in Kafka namespace gets prefixed with the source namespace.
* Secret in Kafka namespace also gets prefixed with the source namespace.
* Secret when created in the source namespace is not prefixed with namespace, but suffixed with "*-kafka-config*".

The idea is that the manifests/helm chart for applications can be slightly less complex, as the name of the [KafkaUser], and the
name of the secret to mount will be the same regardless of namespace.

If the [KafkaUser] is removed from the source namespace, it will be removed from the namespace managed by Strimzi as well, effectively
removing the user from Kafka.

### Handling [KafkaTopic]

When a [KafkaTopic] [CRD] is added to a namespace managed by KNUTO (but not by Strimzi), KNUTO will check that the
name of the topic is prefixed with the name of the namespace. This differs from the naming of KafkaUser as explained above,
which is because applications explicitly need to configure which topics to write to inside the code, while the
handling of users is usually within the Kafka library.

If the [KafkaTopic] created pass the test, it will be copied into the namespace managed by Strimzi, and Strimzi will create
the topic inside Kafka, and update the [KafkaTopic] in the Strimzi-managed namespace with the status. The original [KafkaTopic] in the
source namespace (i.e the one managed by KNUTO) will not be updated.

If a [KafkaTopic] is removed from the KNUTO-managed namespace, the behaviour depends on a per-namespace setting for Knuto:

* The default behaviour is to remove the KafkaTopic from the namespace handled by Strimzi. This will make Strimzi
  remove the topic from Kafka, effectively removing all the data stored on the topic.
* KNUTO can be configured to **not** remove the KafkaTopic from the Strimzi-managed namespace. This serves as
  protection against unintended removal of data, and is a useful setting for production topics.

## Installation

KNUTO comes with a Helm Chart, see [charts/knuto](./charts/knuto) and the [values.yaml documentation](./charts/knuto/README.md)



[CRD]: https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/
[KafkaTopic]: https://strimzi.io/docs/master/#type-[KafkaTopic]-reference
[KafkaUser]: https://strimzi.io/docs/master/#type-[KafkaUser]-reference