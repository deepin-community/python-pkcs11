#!/usr/bin/env python3
"""Test runner for python-pkcs11.

This program sets up a test environment for python-pkcs11, utilizing SoftHSM 2
with a custom config and state file in a temporary directory, executes the test
suite, and then cleans up after itself.

It reuses the logic from the project's Travis configuration.

Copyright (c) 2023 Faidon Liambotis <paravoid@debian.org>
License: MIT
"""

import contextlib
import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import typing
import unittest

try:
    import pytest

    WITH_PYTEST = True
except ImportError:
    WITH_PYTEST = False


@contextlib.contextmanager
def softhsm_testenv(base_dir: str | None = None) -> typing.Generator[None, None, None]:
    """Context manager to execute a piece of code in a softhsm2 environment.

    Executes with a temporary config file and state directory, as to not affect
    the system copy.
    """

    tmpdir = tempfile.TemporaryDirectory(prefix="pkcs11-testenv.", dir=base_dir)
    tmpdir_path = pathlib.Path(tmpdir.name)

    print(f"Creating temporary directory for SoftHSM 2: {tmpdir_path}")

    softhsm_token_dir = tmpdir_path / "softhsm2"
    softhsm_token_dir.mkdir()

    softhsm_config = tmpdir_path / "softhsm2.conf"
    softhsm_config.write_text(
        textwrap.dedent(
            f"""
            directories.tokendir = {softhsm_token_dir}
            objectstore.backend = file
            log.level = INFO
            """
        )
    )

    # Inject variables to the subprocess & unittest environment
    # softhsm2 expects SOFTHSM2_CONF, while the unit tests expect PKCS11_*
    os.environ["SOFTHSM2_CONF"] = str(softhsm_config)
    os.environ["PKCS11_MODULE"] = "/usr/lib/softhsm/libsofthsm2.so"
    os.environ["PKCS11_TOKEN_LABEL"] = "TEST"
    os.environ["PKCS11_TOKEN_PIN"] = "1234"
    os.environ["PKCS11_TOKEN_SO_PIN"] = "5678"

    # Initialize a new token
    print("Initializing a new token with softhsm2-util")
    sys.stdout.flush()
    subprocess.run(
        [
            "softhsm2-util",
            "--init-token",
            "--free",
            "--label",
            os.environ["PKCS11_TOKEN_LABEL"],
            "--pin",
            os.environ["PKCS11_TOKEN_PIN"],
            "--so-pin",
            os.environ["PKCS11_TOKEN_SO_PIN"],
        ],
        check=True,
    )

    print("Running in the test environment...")
    sys.stdout.flush()
    yield
    sys.stdout.flush()
    print("Done")

    # Delete the token. This is not necessary since we nuke the directory
    # anyway, but acts as an additional safeguard that SoftHSM still works
    print("Deleting the token from SoftHSM 2")
    sys.stdout.flush()
    subprocess.run(
        [
            "softhsm2-util",
            "--delete-token",
            "--token",
            os.environ["PKCS11_TOKEN_LABEL"],
        ],
        check=True,
    )

    # Cleanup the tmpdir (the garbage collector would do this anyway)
    print(f"Removing temporary directory {tmpdir_path}")
    tmpdir.cleanup()


def run_testsuite_with_softhsm() -> int:
    """Execute the testsuite with the SoftHSM as the module."""

    with softhsm_testenv(base_dir="tests"):
        if WITH_PYTEST:
            return pytest.main()
        else:
            testprogram = unittest.main(module=None, verbosity=1, exit=False)
            return not testprogram.result.wasSuccessful()


if __name__ == "__main__":
    sys.exit(run_testsuite_with_softhsm())
