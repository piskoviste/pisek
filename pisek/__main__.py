# pisek  - Tool for developing tasks for programming competitions.
#
# Copyright (c)   2019 - 2022 Václav Volhejn <vaclav.volhejn@gmail.com>
# Copyright (c)   2019 - 2022 Jiří Beneš <mail@jiribenes.com>
# Copyright (c)   2020 - 2022 Michal Töpfer <michal.topfer@gmail.com>
# Copyright (c)   2022        Jiří Kalvoda <jirikalvoda@kam.mff.cuni.cz>
# Copyright (c)   2023        Daniel Skýpala <daniel@honza.info>
# Copyright (c)   2024        Benjamin Swart <benjaminswart@email.cz>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import argcomplete
import argparse
import logging
import os
import sys
from typing import Optional

from pisek.user_errors import (
    UserError,
    TaskConfigError,
    TestingFailed,
    MissingFile,
    InvalidArgument,
    InvalidOperation,
)

from pisek.utils.util import clean_task_dir, log_level_mapper
from pisek.utils.text import eprint
from pisek.utils.colors import ColorSettings

from pisek.visualize import visualize
from pisek.init import init_task
from pisek.config.config_hierarchy import DEFAULT_CONFIG_FILENAME
from pisek.config.config_tools import export_config, update_and_replace_config
from pisek.version import print_version

from pisek.jobs.task_pipeline import TaskPipeline
from pisek.utils.pipeline_tools import (
    run_pipeline,
    PATH,
    locked_folder,
    assert_task_dir,
)
from pisek.utils.paths import INTERNALS_DIR

LOG_FILE = os.path.join(INTERNALS_DIR, "log")


@locked_folder
def test_task(args, **kwargs) -> None:
    return test_task_path(PATH, **vars(args), **kwargs)


def test_task_path(path, solutions: Optional[list[str]] = None, **env_args) -> None:
    return run_pipeline(path, TaskPipeline, solutions=solutions, **env_args)


def test_solutions(args) -> None:
    return test_task(args)


def test_generator(args) -> None:
    return test_task(args, solutions=[])


@locked_folder
def clean_directory() -> None:
    task_dir = PATH
    eprint(f"Cleaning directory: {os.path.abspath(task_dir)}")
    return clean_task_dir(task_dir)


def _main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Tool for developing tasks for programming competitions. "
            "Full documentation is at https://github.com/kasiopea-org/pisek"
        )
    )

    def add_cms_import_arguments(parser):
        parser.add_argument(
            "--description",
            "-d",
            type=str,
            help="create the dataset with the description DESCRIPTION",
        )

        parser.add_argument(
            "--time-limit",
            "-t",
            type=float,
            help="override the time limit when importing to TIME_LIMIT seconds",
        )

    def add_argument_dataset(parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--dataset",
            "-d",
            type=str,
            help="use the dataset with the description DESCRIPTION",
        )

        group.add_argument(
            "--active-dataset",
            "-a",
            action="store_true",
            help="use active dataset",
        )

    # ------------------------------- pisek -------------------------------

    parser.add_argument(
        "--clean",
        "-c",
        action="store_true",
        help="clean directory beforehand",
    )
    parser.add_argument(
        "--plain",
        "-p",
        action="store_true",
        help="do not use ANSI escape sequences",
    )
    parser.add_argument(
        "--no-jumps",
        action="store_true",
        help="do not use ANSI cursor movement & clear sequences",
    )
    parser.add_argument(
        "--no-colors",
        action="store_true",
        help="do not use ANSI color sequences",
    )
    parser.add_argument(
        "--pisek-dir",
        help="pisek directory for higher level settings",
        type=str,
    )
    parser.add_argument(
        "--config-filename",
        help="override name of the configuration file",
        default=DEFAULT_CONFIG_FILENAME,
        type=str,
    )

    subparsers = parser.add_subparsers(
        help="subcommand to run", dest="subcommand", required=True
    )

    # ------------------------------- pisek version -------------------------------

    parser_version = subparsers.add_parser("version", help="print current version")

    # ------------------------------- pisek test -------------------------------

    parser_test = subparsers.add_parser("test", help="test task")
    test_subparsers = parser_test.add_subparsers(help="testing target", dest="target")
    test_all = test_subparsers.add_parser("all", help="test all")
    test_gen = test_subparsers.add_parser("generator", help="test only generator")
    test_sols = test_subparsers.add_parser(
        "solutions", help="test generator & given solutions"
    )
    test_sols.add_argument(
        "solutions", type=str, help="name of the solutions to test", nargs="+"
    )

    parser_test.add_argument(
        "--jobs",
        "-j",
        type=int,
        help="how many jobs to run in parallel",
    )
    parser_test.add_argument(
        "--verbosity",
        "-v",
        action="count",
        default=0,
        help="be more verbose (enter multiple times for even more verbosity)",
    )
    parser_test.add_argument(
        "--file-contents",
        "-C",
        action="store_true",
        help="show file contents on error",
    )
    parser_test.add_argument(
        "--time-limit",
        "-t",
        type=float,
        help="override time limit for solutions to TIME_LIMIT seconds",
    )
    parser_test.add_argument(
        "--full", "-f", action="store_true", help="don't stop on first failure"
    )
    parser_test.add_argument(
        "--strict",
        action="store_true",
        help="interpret warnings as failures (for final check)",
    )
    parser_test.add_argument(
        "--repeat",
        "-n",
        type=int,
        default=1,
        help="test task REPEAT times giving generator different seeds. (Changes seeded inputs only.)",
    )
    parser_test.add_argument(
        "--all-inputs",
        "-a",
        action="store_true",
        help="test each solution on all inputs",
    )
    parser_test.add_argument(
        "--testing-log",
        "-T",
        action="store_true",
        help="write test results to testing_log.json",
    )

    # ------------------------------- pisek clean -------------------------------

    parser_clean = subparsers.add_parser("clean", help="clean task directory")

    # ------------------------------- pisek init -------------------------------

    parser_task = subparsers.add_parser("init", help="create a task skeleton")

    # ------------------------------- pisek config -------------------------------

    parser_config = subparsers.add_parser("config", help="manage task config")
    config_subparsers = parser_config.add_subparsers(
        help="subcommand to run", dest="config_subcommand", required=True
    )
    config_subparsers.add_parser(
        "update", help="update config to newest version (replaces the config)"
    )
    parser_export = config_subparsers.add_parser(
        "export", help="creates an organization independent config"
    )
    parser_export.add_argument(
        "filename", help="name of the exported configuration file"
    )

    # ------------------------------- pisek visualize -------------------------------

    parser_visualize = subparsers.add_parser(
        "visualize", help="show solution statistics and closeness to limit"
    )
    parser_visualize.add_argument(
        "--filter",
        "-f",
        choices=("slowest", "all"),
        default="slowest",
        type=str,
        help="which inputs to show (slowest/all)",
    )
    parser_visualize.add_argument(
        "--bundle",
        "-b",
        action="store_true",
        help="don't group inputs by test",
    )
    parser_visualize.add_argument(
        "--solutions",
        "-s",
        default=None,
        type=str,
        nargs="*",
        help="visualize only solutions with a name or source in SOLUTIONS",
    )
    parser_visualize.add_argument(
        "--filename",
        default="testing_log.json",
        type=str,
        help="read testing log from FILENAME",
    )
    parser_visualize.add_argument(
        "--limit",
        "-l",
        default=None,
        type=float,
        help="visualize as if the time limit was LIMIT seconds",
    )
    parser_visualize.add_argument(
        "--segments",
        "-S",
        type=int,
        help="print bars SEGMENTS characters wide",
    )

    # ------------------------------- pisek cms -------------------------------

    parser_cms = subparsers.add_parser("cms", help="import task into CMS")
    subparsers_cms = parser_cms.add_subparsers(
        help="subcommand to run", dest="cms_subcommand", required=True
    )

    parser_cms_create = subparsers_cms.add_parser("create", help="create a new task")
    add_cms_import_arguments(parser_cms_create)

    parser_cms_update = subparsers_cms.add_parser(
        "update", help="update the basic properties of an existing task"
    )

    parser_cms_add = subparsers_cms.add_parser(
        "add", help="add a dataset to an existing task"
    )
    add_cms_import_arguments(parser_cms_add)
    parser_cms_add.add_argument(
        "--no-autojudge",
        action="store_true",
        help="disable background judging for the new dataset",
    )

    parser_cms_submit = subparsers_cms.add_parser(
        "submit", help="submit reference solutions for evaluation using CMS"
    )
    parser_cms_submit.add_argument(
        "--username",
        "-u",
        type=str,
        required=True,
        help="submit as the user with username USERNAME",
    )

    parser_cms_testing_log = subparsers_cms.add_parser(
        "testing-log",
        help="generate a testing log for reference solutions submitted to CMS",
    )
    add_argument_dataset(parser_cms_testing_log)

    parser_cms_check = subparsers_cms.add_parser(
        "check",
        help="check if reference solutions scored as expected in CMS",
    )
    add_argument_dataset(parser_cms_check)

    argcomplete.autocomplete(parser)
    args = parser.parse_args(argv)

    if args.pisek_dir is None and "PISEK_DIRECTORY" in os.environ:
        args.pisek_dir = os.path.join(os.getcwd(), os.environ["PISEK_DIRECTORY"])
    ColorSettings.set_state(not args.plain and not args.no_colors)

    # Taskless subcommands
    if args.subcommand == "version":
        return print_version()
    elif args.subcommand == "init":
        return init_task(args.config_filename, args.no_jumps)

    # !!! Ensure this is always run before clean_directory !!!
    assert_task_dir(PATH, args.pisek_dir, args.config_filename)

    if args.clean:
        clean_directory()

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    open(LOG_FILE, "w").close()
    logging.basicConfig(
        filename=LOG_FILE,
        encoding="utf-8",
        level=log_level_mapper(os.getenv("LOG_LEVEL", "info")),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.subcommand == "test":
        if args.target == "generator":
            return test_generator(args)
        elif args.target == "solutions":
            return test_solutions(args)
        elif args.target is None or args.target == "all":
            return test_task(args, solutions=None)
        else:
            assert False, "Unknown command"

    elif args.subcommand == "config":
        if args.config_subcommand == "update":
            return update_and_replace_config(PATH, args.pisek_dir, args.config_filename)
        elif args.config_subcommand == "export":
            return export_config(
                PATH,
                args.pisek_dir,
                args.config_filename,
                os.path.join(PATH, args.filename),
            )
        else:
            assert False, "Unknown command"

    elif args.subcommand == "cms":
        args, unknown_args = parser.parse_known_args()

        try:
            import pisek.cms as cms
        except ImportError as err:
            err.add_note("Failed to locate CMS installation")
            raise

        from logging import StreamHandler
        from sys import stdout

        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, StreamHandler) and handler.stream is stdout:
                root_logger.removeHandler(handler)

        if args.cms_subcommand == "create":
            return cms.create(args)
        elif args.cms_subcommand == "update":
            return cms.update(args)
        elif args.cms_subcommand == "add":
            return cms.add(args)
        elif args.cms_subcommand == "submit":
            return cms.submit(args)
        elif args.cms_subcommand == "testing-log":
            return cms.testing_log(args)
        elif args.cms_subcommand == "check":
            return cms.check(args)
        else:
            assert False, "Unknown command"

    elif args.subcommand == "clean":
        return clean_directory()
    elif args.subcommand == "visualize":
        return visualize(PATH, **vars(args))
    else:
        assert False, "Unknown command"


def main(argv: list[str]) -> int:
    try:
        _main(argv)
    except TestingFailed:
        return 1
    except (TaskConfigError, MissingFile, InvalidArgument, InvalidOperation) as e:
        print(ColorSettings.colored(str(e), "red"))
        return 2
    except UserError:
        raise NotImplementedError()
    except KeyboardInterrupt:
        eprint("\rStopping...")
        return 130

    return 0


def main_wrapped() -> int:
    return main(sys.argv[1:])


if __name__ == "__main__":
    exit(main_wrapped())
