import argparse
import asyncio
import inspect
import os
from copy import deepcopy

import kopf
from kopf.clients.auth import login_pykube, get_pykube_api

from .config import globalconf, state

def _copy_object(obj):
    new_obj = deepcopy(obj)
    for key in ["resourceVersion", "selfLink", "uid", "creationTimestamp", "generation", "finalizers"]:
        if key in new_obj["metadata"]:
            del new_obj["metadata"][key]

    return new_obj


def run_kopf(namespace):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    kopf.login()                    # tokens & certs

    loop.run_until_complete(kopf.operator(
        standalone=True,
        namespace=namespace
    ))


script_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

# This script dir is used from multiple functions
def default_main(program_argparsers):
    argparser = argparse.ArgumentParser(parents=program_argparsers, add_help=False)
    argparser.add_argument("--verbose", "-v", default=False, action='store_true')
    argparser.add_argument("namespace", help="Namespace to watch for changes")

    args = argparser.parse_args()

    kopf.configure(verbose=args.verbose)


    print(f"globalconf: {globalconf.current_values()}")

    login_pykube()
    state.api = get_pykube_api()

    run_kopf(args.namespace)


def _update_or_create(obj):
    if obj.exists():
        obj.update()
    else:
        obj.create()
