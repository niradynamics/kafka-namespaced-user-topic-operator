
import os
import inspect
import asyncio
import argparse
import kopf
import pyhocon

from . config import globalconf
from . import secrets

script_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))


def run_kopf():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    kopf.login()                    # tokens & certs

    loop.run_until_complete(kopf.operator(
        standalone=True,
        namespace=globalconf.conf.get("knuto.strimzi_watched_namespace")
    ))


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--config", "-c", default=os.path.join(script_dir, "knuto.conf"))
    argparser.add_argument("--verbose", "-v", default=False, action='store_true')

    args = argparser.parse_args()

    globalconf.conf = pyhocon.ConfigFactory.parse_file(args.config)
    kopf.configure(verbose=args.verbose)

    run_kopf()

