import argparse
import asyncio
import inspect
import os
from copy import deepcopy
from typing import Mapping

import pykube
import kopf

import logging

from .config import globalconf, state

logger = logging.getLogger(__name__)


def _copy_object(obj: Mapping):
    """
    Performs a deep copy of a Mapping.
    Converts to a basic dict to avoid problems with kopf Body mapping type.
    Pykube expects json-serializable types, i.e. basic types.
    """
    new_obj = deepcopy(dict(obj))
    for key in [
        "resourceVersion",
        "selfLink",
        "uid",
        "creationTimestamp",
        "generation",
        "finalizers",
        "ownerReferences",
    ]:
        if key in new_obj["metadata"]:
            del new_obj["metadata"][key]

    return new_obj


def run_kopf(namespace):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(kopf.operator(standalone=True, namespace=namespace))


script_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))


# This script dir is used from multiple functions
def default_main(program_argparsers):
    argparser = argparse.ArgumentParser(parents=program_argparsers, add_help=False)
    argparser.add_argument("--verbose", "-v", default=False, action="store_true")
    argparser.add_argument("namespace", help="Namespace to watch for changes")

    args = argparser.parse_args()

    kopf.configure(verbose=args.verbose)

    print(f"globalconf: {globalconf.current_values()}")

    kopf.login_via_pykube(logger=logger)
    state.api = pykube.HTTPClient(_get_pykube_config())

    run_kopf(args.namespace)


def _get_pykube_config():
    try:
        config = pykube.KubeConfig.from_service_account()
        logger.debug("Pykube is configured in cluster with service account.")
    except FileNotFoundError:
        config = pykube.KubeConfig.from_file()
        logger.debug("Pykube is configured via kubeconfig file.")

    return config


def _update_or_create(obj):
    if obj.exists():
        logger.info("Update object %s" % repr(obj))
        obj.update()
    else:
        logger.info("Create object %s" % repr(obj))
        obj.create()
