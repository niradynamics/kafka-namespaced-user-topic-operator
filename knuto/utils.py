import argparse
import asyncio
import inspect
import os
from copy import deepcopy

import kopf
import pyhocon

from knuto.config import globalconf

def _copy_object(obj):
    new_obj = deepcopy(obj)
    for key in ["resourceVersion", "selfLink", "uid", "creationTimestamp", "generation"]:
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
def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--config", "-c", default=os.path.join(script_dir, "knuto.conf"))
    argparser.add_argument("--verbose", "-v", default=False, action='store_true')
    argparser.add_argument("namespace")

    args = argparser.parse_args()

    globalconf.conf = pyhocon.ConfigFactory.parse_file(args.config)
    kopf.configure(verbose=args.verbose)

    run_kopf(args.namespace)


def _update_or_create(obj):
    if obj.exists():
        obj.update()
    else:
        obj.create()
