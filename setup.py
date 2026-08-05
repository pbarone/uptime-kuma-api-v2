from setuptools import setup
from codecs import open
import os

# An inherited `setup.py publish` shortcut was removed here. It ran
# `rm dist/*`, `python setup.py sdist` and `twine upload dist/*`, which uploaded
# a locally built artifact straight to PyPI -- bypassing the tag/__version__
# check, `twine check`, and `scripts/check_sdist.py`. That made it the one path
# by which a stale `*.egg-info/SOURCES.txt` could publish `tests/.env` and the
# credential-bearing `tests/.backups/**` snapshots, since a local build reads
# that stale manifest while CI's fresh checkout cannot. It was also broken on
# Windows (`rm`). Releases go through the tag-triggered publish workflow, which
# is gated; see the release flow in CONTRIBUTING.md.

info = {}
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "uptime_kuma_api", "__version__.py"), "r", "utf-8") as f:
    exec(f.read(), info)

with open("README.md", "r", "utf-8") as f:
    readme = f.read()

setup(
    name="uptime-kuma-api2",
    version=info["__version__"],
    description="A python wrapper for the Uptime Kuma WebSocket API (v2 support)",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/pbarone/uptime-kuma-api2",
    project_urls={
        "Source": "https://github.com/pbarone/uptime-kuma-api2",
        "Changelog": "https://github.com/pbarone/uptime-kuma-api2/blob/main/CHANGELOG.md",
        "Issues": "https://github.com/pbarone/uptime-kuma-api2/issues",
    },
    author=info["__author__"],
    author_email="pbarone@users.noreply.github.com",
    license=info["__license__"],
    packages=["uptime_kuma_api"],
    python_requires=">=3.8, <4",
    install_requires=[
        "python-socketio[client]>=5.0.0",
        "packaging",
        # api.py imports requests at module scope for the status-page HTTP
        # fetch. It resolves in practice via python-socketio's [client] extra,
        # which declares requests>=2.21.0 - but relying on that leaves a
        # load-bearing import undeclared and invisible to dependency scanning.
        # The floor matches the extra's, so no install that resolves today
        # stops resolving.
        "requests>=2.21.0"
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries"
    ]
)
