# This file is taken from the Zipline project with minor modifications:
# github.com/quantopian/zipline
#
# Copyright 2016 Quantopian, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from contextlib import contextmanager
from glob import glob
import os
from os.path import abspath, basename, dirname, exists, isfile
from shutil import move, rmtree
from subprocess import check_call

HERE = dirname(abspath(__file__))
SLIDER_ROOT = dirname(HERE)
TEMP_LOCATION = "/tmp/slider-doc"
TEMP_LOCATION_GLOB = TEMP_LOCATION + "/*"


@contextmanager
def removing(path):
    try:
        yield
    finally:
        rmtree(path)


def ensure_not_exists(path):
    if not exists(path):
        return
    if isfile(path):
        os.unlink(path)
    else:
        rmtree(path)


def main():
    old_dir = os.getcwd()
    print("Moving to %s." % HERE)
    os.chdir(HERE)

    try:
        print("Building docs with 'make html'")
        check_call(["make", "html"])

        print("Clearing temp location '%s'" % TEMP_LOCATION)
        rmtree(TEMP_LOCATION, ignore_errors=True)

        with removing(TEMP_LOCATION):
            print("Copying built files to temp location.")
            move("build/html", TEMP_LOCATION)

            print("Moving to '%s'" % SLIDER_ROOT)
            os.chdir(SLIDER_ROOT)

            print("Checking out gh-pages branch.")
            check_call(
                ["git", "branch", "-f", "--track", "gh-pages", "origin/gh-pages"]
            )
            check_call(["git", "checkout", "gh-pages"])
            check_call(["git", "reset", "--hard", "origin/gh-pages"])

            print("Copying built files:")
            for file_ in glob(TEMP_LOCATION_GLOB):
                base = basename(file_)

                print("%s -> %s" % (file_, base))
                ensure_not_exists(base)
                move(file_, ".")
    finally:
        os.chdir(old_dir)

    print()
    print("Updated documentation branch in directory %s" % SLIDER_ROOT)
    print("If you are happy with these changes, commit and push to gh-pages.")


if __name__ == "__main__":
    main()
