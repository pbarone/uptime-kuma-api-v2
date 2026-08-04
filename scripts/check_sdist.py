"""Assert an sdist contains what it should and nothing it must not.

Two modes::

    python scripts/check_sdist.py                  # build a fresh sdist, check that
    python scripts/check_sdist.py dist/foo.tar.gz  # check an existing artifact

Pass the path when gating a release: that checks the exact tarball about to be
uploaded, rather than a second build of it that is only assumed to match.

Exits non-zero with an explanation on any violation.

Why this exists as a mechanism rather than a one-time manual check
-----------------------------------------------------------------
Nothing in ``MANIFEST.in`` structurally prevents a later broad
``recursive-include tests`` or ``graft tests`` from sweeping ``tests/.env`` and
``tests/.backups/**`` into a published artifact, and a file published to PyPI
cannot be withdrawn.

There is a second, quieter route to the same outcome. ``manifest_maker`` reads
an existing ``*.egg-info/SOURCES.txt`` back into the file list when no
revision-control plugin is installed (``add_defaults`` in
setuptools/command/egg_info.py). A tree that built once with a broad pattern
therefore keeps shipping those files even after the pattern is reverted, until
the stale egg-info is deleted. This was reproduced while writing this script: a
``MANIFEST.in`` holding nothing but the two ``include`` lines still produced a
111-member sdist carrying ``tests/.env`` and three credential-bearing
``tests/.backups/config_snapshot_*.json`` files, purely from a stale
``SOURCES.txt``. CI is safe from this because it builds a fresh checkout; a
local ``python -m build`` is not. Build mode deletes the egg-info first for that
reason -- a check that local build state can contaminate is not a check.

The tests/ rule is an allowlist, not a denylist of known-bad names, because the
failure being guarded against is a file nobody thought to enumerate.
"""

import fnmatch
import glob
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

# Present in the sdist or the build is wrong.
REQUIRED = [
    "CHANGELOG.md",
    "README.md",
    "LICENSE",
    "setup.py",
    "tests/uptime_kuma_test_case.py",
]

# Anything under tests/ that is not one of these is a violation. Allowlist
# rather than denylist: the risk is a file nobody listed, not a known-bad one.
ALLOWED_TESTS_EXACT = {"tests/uptime_kuma_test_case.py"}
ALLOWED_TESTS_GLOB = "tests/test_*.py"


def build_sdist(outdir):
    """Builds an sdist into outdir and returns its path."""
    for stale in glob.glob("*.egg-info"):
        print("removing stale " + stale + " so the check cannot inherit its SOURCES.txt")
        shutil.rmtree(stale)

    subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--outdir", outdir],
        check=True,
        stdout=subprocess.DEVNULL,
    )

    built = glob.glob(os.path.join(outdir, "*.tar.gz"))
    if len(built) != 1:
        raise SystemExit("FAIL expected exactly one sdist, got " + repr(built))
    return built[0]


def members(sdist_path):
    """Returns sdist member paths relative to the top-level directory."""
    with tarfile.open(sdist_path) as tar:
        return sorted(n.split("/", 1)[1] for n in tar.getnames() if "/" in n)


def check(names):
    """Returns a list of violation strings; empty means the sdist is clean."""
    failures = []

    for required in REQUIRED:
        if required in names:
            print("PASS present -> " + required)
        else:
            failures.append("missing from sdist -> " + required)

    allowed = set(fnmatch.filter(names, ALLOWED_TESTS_GLOB)) | ALLOWED_TESTS_EXACT
    unexpected = [n for n in names if n.startswith("tests/") and n not in allowed]
    for name in unexpected:
        failures.append(
            "unexpected file under tests/ -> " + name
            + " (allowed: " + ALLOWED_TESTS_GLOB + " and "
            + ", ".join(sorted(ALLOWED_TESTS_EXACT)) + ")"
        )
    if not unexpected:
        count = len(fnmatch.filter(names, ALLOWED_TESTS_GLOB))
        print("PASS no unexpected files under tests/ (" + str(count) + " test modules + the base class)")

    return failures


def main(argv):
    if len(argv) > 1:
        matches = sorted(glob.glob(argv[1]))
        if len(matches) != 1:
            print("FAIL expected exactly one sdist matching " + argv[1] + ", got " + repr(matches))
            return 1
        sdist_path = matches[0]
        print("checking existing artifact " + sdist_path)
        names = members(sdist_path)
    else:
        with tempfile.TemporaryDirectory() as outdir:
            sdist_path = build_sdist(outdir)
            names = members(sdist_path)

    print("sdist " + os.path.basename(sdist_path) + " has " + str(len(names)) + " members")

    failures = check(names)

    print("")
    if failures:
        for failure in failures:
            print("FAIL " + failure)
        print("")
        print("FAIL sdist contents check failed with " + str(len(failures)) + " violation(s)")
        return 1

    print("PASS sdist contents check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
