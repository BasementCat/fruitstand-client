#!/usr/bin/env python

import logging
import argparse
import os
import sys
import json
import shlex
import subprocess
import time
import re
import platform
from threading import (
    Thread,
    Event
    )
import copy

logging.basicConfig(level = logging.ERROR)

args = {}
default_config = {
    "verbosity": 0,
    "url": "",
    "not_fruitstand": False,
    "no_config_file": False,
    "browser": "midori",
    "tags": {"id": platform.node()}
}
config = {}
logger = logging.getLogger()

candidate_config_file_name = "fruitstand-client.conf"
candidate_config_file_dirs = (
    "/etc/",
    os.path.expanduser("~/"),
    "./",
    "/"
    )
browsers = {
    "midori": "midori -e Fullscreen -a \"%s\""
}

stop_main = Event()
stop_app = Event()

def question(prompt, prompt_end = ": ", options = [], default = None, case_sensitive = False, empty = False):
    real_prompt = prompt

    if options:
        real_prompt += " (%s)" % (', '.join([str(o) for o in options]),)

    if default is not None:
        real_prompt += " [%s]" % (str(default),)

    real_prompt += prompt_end

    while True:
        answer = raw_input(real_prompt)
        if options:
            if not case_sensitive:
                answer = answer.lower()
            if answer in options:
                return answer
            elif not answer:
                if default is not None and default in options:
                    return default
        else:
            if answer:
                return answer
            else:
                if empty:
                    return answer
                elif default is not None:
                    return default

def parse_cli_args():
    global args, config

    parser = argparse.ArgumentParser(description = "Client for fruitstand", epilog = "The full version of most command line arguments may be specified in the config file.  To use some options, they may need to be supplied differently, these options each provide documentation on how to do so.")
    parser.add_argument("-f", "--config-file", help = "Specifies a config file to load.  Cannot be specified in the config file.")
    parser.add_argument("-F", "--no-config-file", help = "If specified, don't try to load any config file.  This will result in failure if required arguments are not present.", action = "store_true")
    parser.add_argument("-v", "--verbose", help = "Display more output.  If not specified, output is only displayed on error.  -v shows warnings, -vv shows info, -vvv shows debugging info.  Config usage: '\"verbosity\": 2'", action = "count")
    parser.add_argument("--configure", help = "Reconfigure the application.  Cannot be specified in the config file.", action = "store_true")
    parser.add_argument("--url", "-u", help = "Screen URL to load.  For a fruitstand installation, only the base URL needs to be specified - any additional URLs will be internally generated.  However, any web page that automatically refreshes in some fashion may be used here.")
    parser.add_argument("--not-fruitstand", help = "If --url points to an arbitrary URL that is not fruitstand, use this switch to disable additional communication that may lead to errors being logged.", action = "store_true")
    parser.add_argument("--browser", "-b", help = "Browser to use.  Either the name of a built in browser or a string specifying how to launch the browser.  Example: 'midori -e Fullscreen -a \"%%s\"' where '%%s' is replaced with your URL.  Please surround URL in double quotes.")
    parser.add_argument("--tag", "-t", help = "Tags for this screen, in \"tag-name=tag-value\" format.  The tag \"id\" is required but if it is not explicitly provided defaults to the system hostname.", action = "append")

    tags_raw = []
    args["tags"] = {}
    arg_defaults = {}
    for k,v in vars(parser.parse_args([])).items():
        arg_defaults[k] = v
    for k,v in vars(parser.parse_args()).items():
        if v == arg_defaults[k]:
            continue
        if k == "verbose":
            k = "verbosity"
        elif k == "tag" and v is not None:
            tags_raw = map(lambda t: re.split(r"\s*?=\s*?", t, 1), v)
        args[k] = v

    # parse tags
    for k,v in tags_raw:
        args["tags"][k] = v

    merge_args_into_config()
    apply_config()

def merge_args_into_config():
    global args, config

    for k,v in args.items():
        if k in ("config_file", "configure", "no_config_file") or v is None:
            continue
        if type(v) is list:
            config[k] += v
        elif type(v) is dict:
            config[k].update(v)
        else:
            config[k] = v

def apply_config():
    global config, logger

    if "verbosity" in config and config["verbosity"]:
        if config["verbosity"] >= 3:
            logger.setLevel(logging.DEBUG)
        elif config["verbosity"] >= 2:
            logger.setLevel(logging.INFO)
        elif config["verbosity"] >= 1:
            logger.setLevel(logging.DEBUG)

def load_config():
    global args, config

    if "no_config_file" not in args or not args["no_config_file"]:
        candidate_file = None

        if "config_file" in args and args["config_file"] is not None:
            candidate_file = args["config_file"]
        else:
            for dir_ in candidate_config_file_dirs:
                candidate_file = os.path.join(dir_, candidate_config_file_name)
                logger.debug("Looking for config file: %s", candidate_file)
                if os.path.exists(candidate_file):
                    if os.path.isfile(candidate_file):
                        break
                    else:
                        logger.debug("Candidate config file %s is not a file", candidate_file)
                else:
                    logger.debug("Candidate config file %s does not exist", candidate_file)
                candidate_file = None

        if candidate_file:
            if not (os.path.exists(candidate_file) and os.path.isfile(candidate_file)):
                logger.error("Selected config file %s does not exist or is not a file", candidate_file)
                if "configure" in args and args["configure"]:
                    configure_app()
                else:
                    sys.exit(1)
        else:
            logger.error("No config file could be found (looked in %s for %s)", ", ".join(candidate_config_file_dirs), candidate_config_file_name)
            if "configure" in args and args["configure"]:
                args["config_file"] = os.path.join(candidate_config_file_dirs[0], candidate_config_file_name)
                configure_app()
            else:
                logger.error("To start the configuration process, relaunch with --configure")
                sys.exit(1)

        logger.info("Loading config from %s", candidate_file)

        with open(candidate_file, "r") as fp:
            config.update(json.load(fp))

        if "config_file" not in args or not args["config_file"]:
            args["config_file"] = candidate_file

    # In case the user wants to re-configure, let's do that
    if "configure" in args and args["configure"]:
        configure_app()

    merge_args_into_config()

    # The user may have specified not to load a config file.  If we get to this point
    # and can assume that the user does actually want to run the app, sanity checking
    # is required
    if "no_config_file" in args and args["no_config_file"]:
        if not (config["url"]):
            logger.error("--url is required")
            sys.exit(1)

    apply_config()

def configure_app():
    global args, config

    print "Hello!  Answer the following questions to configure fruitstand-client."

    config["verbosity"] = question("Pick a verbosity level - usually you won't need to change this and you can always override it with the command line", options = [0, 1, 2, 3], default = config["verbosity"])
    config["url"] = question("URL of your fruitstand installation", default = config["url"])
    config["not_fruitstand"] = True if question("Is this URL a fruitstand installation?", options = ["y", "n"], default = "n" if config["not_fruitstand"] else "y" ) == "n" else False
    print "Configured browsers:\n\t" + "\n\t".join(browsers.keys()) + "\n"
    config["browser"] = question("Browser to use.  Use a configured browser or see --help on how to specify a browser command", default = config["browser"])

    print "Now we'll configure tags.  Tags are a method of classifying screens for fruitstand to determine what content to send them and how to manage them."
    done_with_tags = False
    while not done_with_tags:
        del_tags = []
        add_tags = {}
        for k,v in config["tags"].items():
            op = question("Existing tag: '%s' = '%s' - (K)eep, (R)emove, (A)dd new, (D)one" % (k, v), options = ["k", "r", "a", "d"], default = "k")
            if op == "k":
                continue
            elif op == "r":
                del_tags.append(k)
            elif op == "a":
                n_t, n_v = re.split(r"\s*?=\s*?", question("New tag - format is \"tag-name=tag-value\""), 1)
                add_tags[n_t] = n_v
            elif op == "d":
                done_with_tags = True
                break
        for k in del_tags:
            del(config["tags"][k])
        config["tags"].update(add_tags)

    while True:
        filen = question("Save configuration to", default = args["config_file"])

        if os.path.exists(filen):
            if question("The file %s already exists, overwrite it?" % (filen,), options = ["y", "n"]) != "y":
                continue

        with open(filen, "w") as fp:
            json.dump(config, fp, sort_keys = True, indent = 4)

        break

    print "All done!  To reconfigure, just relaunch with --configure."

    sys.exit(0)

def stop(stop_do_poll_thread = False, do_stop_main = False, do_stop_app = False):
    if do_stop_main:
        stop_main.set()
    if do_stop_app:
        stop_app.set()

def main():
    parse_cli_args()
    load_config()
    logger.debug("Setting up browser string and finding browser")
    qs = "?"
    for k,v in config["tags"].items():
        if config["not_fruitstand"] or k == "id":
            qs += "&%s=%s" % (k, v)
    browser_string = (browsers[config["browser"]] if config["browser"] in browsers else config["browser"]) % (config["url"] + qs,)
    logger.debug("Raw browser string: %s", browser_string)
    browser_args = shlex.split(browser_string)
    logger.debug("Raw browser command: %s", repr(browser_args))
    if not os.path.exists(browser_args[0]):
        real_command = subprocess.check_output("which %s" % (browser_args[0],), shell = True).strip()
        if not real_command:
            logger.error("Can't find browser: %s", browser_args[0])
        browser_args[0] = real_command
    logger.debug("Final browser command: %s", repr(browser_args))

    while not stop_main.is_set():
        logger.info("Running '%s'", " ".join(browser_args))
        browser = subprocess.Popen(browser_args)
        try:
            while browser.poll() is None and not stop_main.wait(1):
                pass
        except KeyboardInterrupt:
            stop(True, True, True)

        if browser.poll() is None:
            if browser.returncode == 0:
                logger.info("Browser exited with return code 0")
            else:
                logger.error("Browser exited with unexpected return code %d", browser.returncode)

        if stop_main.is_set():
            if browser.poll() is None:
                logger.info("Stopping browser - SIGTERM")
                browser.terminate()
                time.sleep(1)
                if browser.poll() is None:
                    logger.error("Browser ignored SIGTERM, sending SIGKILL")
                    browser.kill()

if __name__ == "__main__":
    while not stop_app.is_set():
        args = {}
        config = copy.deepcopy(default_config)
        main()
    logger.info("Bye")
