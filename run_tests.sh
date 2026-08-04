#!/bin/bash
#
# Runs the full inherited integration suite against throwaway Uptime Kuma
# containers, one server version at a time.
#
# DISPOSABLE LOCAL DOCKER HOST ONLY. This script binds host port 3001 and
# claims the container name "uptimekuma", so it will collide with any Uptime
# Kuma already running there. It also runs the inherited integration tests,
# which delete every monitor, notification, proxy, tag, status page, docker
# host, maintenance and API key on the instance they connect to. That is safe
# here only because each instance is a fresh container this script created and
# destroys, and it is why the target must never be a server you care about.
#
# Usage: ./run_tests.sh [uptime-kuma-version]
#   With no argument, iterates the matrix below.
#
# Requires bash: uses arrays and [[ ]]. Do not switch the shebang back to sh.

version="$1"
if [ -n "$version" ]
then
  versions=("$version")
else
  # 2.5.0  - current release; the version this tree is live-verified against
  # 2.1.0  - the incident -> incidents status page rename boundary
  # 2.0.0  - first version on the >= 2.0 gate path
  # 1.23.x / 1.22.x - the 1.23 and 1.22 gate boundaries
  # 1.21.3 - oldest supported server; the pre-1.22 payload path, which is the
  #          one most at risk of silent regression
  versions=(2.5.0 2.1.0 2.0.0 1.23.2 1.23.0 1.22.1 1.22.0 1.21.3)
fi

for version in "${versions[@]}"
do
  echo "Starting uptime kuma $version..."
  docker run -d -it --rm -p 3001:3001 --name uptimekuma "louislam/uptime-kuma:$version" > /dev/null

  readiness_timeout="${READINESS_TIMEOUT:-60}"
  readiness_started_at=$SECONDS

  while [[ "$(curl -s -L --max-time 1 -o /dev/null -w ''%{http_code}'' 127.0.0.1:3001)" != "200" ]]
  do
    readiness_elapsed=$((SECONDS - readiness_started_at))
    if (( readiness_elapsed >= readiness_timeout ))
    then
      echo "Timed out waiting for uptime kuma $version after ${readiness_elapsed}s."
      echo "Stopping uptime kuma..."
      docker stop uptimekuma > /dev/null
      exit 1
    fi
    sleep 0.5
  done

  echo "Running tests..."
  python -m unittest discover -s tests

  echo "Stopping uptime kuma..."
  docker stop uptimekuma > /dev/null
  sleep 1

  echo ''
done
