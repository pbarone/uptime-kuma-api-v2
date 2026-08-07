<#
.SYNOPSIS
    Run a live_test_* script against a throwaway Uptime Kuma container on a
    remote Docker host, then destroy the container.

.DESCRIPTION
    Some verification can only be done against a real server: whether a version
    gate is correct, what a server does with a field the library withholds, how a
    payload round-trips. This starts a disposable container for exactly that, runs
    one script against it, and removes it again.

    Two properties are the point of it existing rather than doing this by hand.

    1. The container is destroyed in a finally block, including on the path where
       the script raised or readiness timed out. A forgotten container on a shared
       host holding a bound port is the failure mode this prevents.
    2. The Docker host address and SSH user are read from the gitignored root
       .env and are NEVER printed. Every line of output passes through a
       sanitizer that replaces them with the <docker-host> and <user>
       placeholders, so a captured transcript can be pasted into an issue or a
       spec without scrubbing.

    The container runs with no volume, so removing it destroys all of its state.
    It is bootstrapped by the script under test -- need_setup() / setup() / login()
    -- with a password this runner generates per run rather than a committed one.

.PARAMETER Script
    The script to run, relative to the repository root. Must exist.

.PARAMETER Image
    Container image. Defaults to the 1.23.2 image used for v1 verification.

.PARAMETER Port
    Host port to publish on. Defaults to 3023. Port 3001 is refused outright --
    see the note in the code.

.PARAMETER Name
    Container name. Defaults to kuma-disposable-<port>.

.PARAMETER Username
    Admin username to bootstrap with. Defaults to admin.

.PARAMETER Password
    Admin password to bootstrap with. Defaults to a freshly generated value.
    Uptime Kuma requires at least 6 characters.

.PARAMETER TimeoutSeconds
    How long to wait for the container to answer before giving up. Defaults to
    120. On timeout the container is removed and the runner exits non-zero.

.PARAMETER KeepContainer
    Leave the container running after the script finishes, for debugging. You are
    then responsible for removing it. The name is printed so you can.

.PARAMETER Python
    Python executable. Defaults to the repository virtualenv.

.EXAMPLE
    pwsh -File scripts/run_disposable_kuma.ps1 -Script tests/live_test_v2_only_fields_v1.py

    Probe every version-gated monitor field against a 1.23.2 server. This is the
    run recorded in .kiro/specs/v2-only-fields-rule/v1-verification-results.md.

.EXAMPLE
    pwsh -File scripts/run_disposable_kuma.ps1 `
        -Script tests/live_test_conditions_v1.py -Port 3024

    A second script on a different port, so it can run alongside the first.

.NOTES
    Requires the root .env to define DOCKER-HOST and DOCKER-USER, key-based SSH
    to that host, and Docker on it. This is maintainer tooling: scripts/ ships in
    neither the wheel nor the sdist, and CI never runs it.

    Output is ASCII only. The Windows console defaults to cp1252 and raises
    UnicodeEncodeError on check marks and box-drawing characters, which has
    crashed scripts mid-run here before. Use PASS / FAIL / ->.

    The script under test is expected to read UPTIME_KUMA_V1_URL,
    UPTIME_KUMA_V1_USERNAME and UPTIME_KUMA_V1_PASSWORD, which this runner sets
    for the child process only. Those keys are deliberately distinct from the
    UPTIME_KUMA_* keys in tests/.env that point at a real 2.x instance, so a
    script that creates and deletes monitors cannot reach it by misconfiguration.
    There is deliberately no option to change that prefix: making it settable
    would hand back exactly the accident the split key names exist to prevent.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Script,

    [string]$Image = 'louislam/uptime-kuma:1.23.2',
    [int]$Port = 3023,
    [string]$Name,
    [string]$Username = 'admin',
    [string]$Password,
    [int]$TimeoutSeconds = 120,
    [switch]$KeepContainer,
    [string]$Python = '.venv\Scripts\python.exe'
)

$ErrorActionPreference = 'Continue'

# ---------------------------------------------------------------------------
# Preconditions, all checked before anything is started
# ---------------------------------------------------------------------------

if (-not (Test-Path $Script)) {
    Write-Output "FAIL: script not found -> $Script"
    Write-Output "      Paths are relative to the repository root; run this from there."
    exit 1
}

if (-not (Test-Path $Python)) {
    Write-Output "FAIL: python not found -> $Python"
    Write-Output "      Pass -Python if your interpreter is elsewhere."
    exit 1
}

# 3001 is the conventional Uptime Kuma port and is where a real instance is
# expected to be. Publishing a throwaway container there would either collide
# with it or, worse, succeed on a host where it is not running and then be
# indistinguishable from it in tests/.env. Refused rather than warned about.
if ($Port -eq 3001) {
    Write-Output "FAIL: port 3001 is refused."
    Write-Output "      It is the default Uptime Kuma port and where a real instance lives."
    Write-Output "      Pick a free port, e.g. -Port 3023."
    exit 1
}

if (-not (Test-Path '.env')) {
    Write-Output "FAIL: no .env at the repository root."
    Write-Output "      It must define DOCKER-HOST and DOCKER-USER. It is gitignored."
    exit 1
}

$vals = @{}
Get-Content '.env' | Where-Object { $_ -match '=' } | ForEach-Object {
    $parts = $_ -split '=', 2
    $vals[$parts[0].Trim()] = $parts[1].Trim()
}

$dockerHost = $vals['DOCKER-HOST']
$dockerUser = $vals['DOCKER-USER']

if (-not $dockerHost -or -not $dockerUser) {
    Write-Output "FAIL: DOCKER-HOST and/or DOCKER-USER missing from .env"
    exit 1
}

if (-not $Name) { $Name = "kuma-disposable-$Port" }

if (-not $Password) {
    # Generated per run rather than defaulted to a literal, so no credential --
    # however throwaway -- is committed. Uptime Kuma requires 6+ characters.
    $chars = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'.ToCharArray()
    $Password = -join (1..20 | ForEach-Object { $chars | Get-Random })
}

$sshTarget = "$dockerUser@$dockerHost"

# ---------------------------------------------------------------------------
# Output sanitizing. Nothing below writes a raw line.
# ---------------------------------------------------------------------------

function Hide-Target([string]$text) {
    if (-not $text) { return $text }
    $text = $text -replace [regex]::Escape($dockerHost), '<docker-host>'
    $text = $text -replace [regex]::Escape($dockerUser), '<user>'
    return $text
}

function Write-Clean($lines) {
    foreach ($line in $lines) { Write-Output (Hide-Target ([string]$line)) }
}

function Invoke-Remote([string]$command) {
    ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new `
        $sshTarget $command 2>&1
}

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

Write-Output "== disposable Uptime Kuma =="
Write-Output "  image     $Image"
Write-Output "  container $Name"
Write-Output "  address   http://<docker-host>:$Port/"
Write-Output "  script    $Script"
Write-Output ""

Write-Output "== starting =="
# rm -f first so a container left behind by an interrupted earlier run does not
# make this one fail on the name.
Write-Clean (Invoke-Remote "docker rm -f $Name 2>/dev/null; docker run -d --name $Name -p ${Port}:3001 $Image")
if ($LASTEXITCODE -ne 0) {
    Write-Output "FAIL: could not start the container (ssh/docker exit $LASTEXITCODE)"
    exit 1
}

$exitCode = 1
try {
    Write-Output ""
    Write-Output "== waiting for readiness (max ${TimeoutSeconds}s) =="
    $ready = $false
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $probe = Invoke-WebRequest -Uri "http://${dockerHost}:$Port" `
                -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
            if ($probe.StatusCode -eq 200) { $ready = $true; break }
        }
        catch {
            Start-Sleep -Seconds 3
        }
    }

    if (-not $ready) {
        Write-Output "FAIL: not ready within ${TimeoutSeconds}s -- removing the container."
        Write-Output "      A bad image tag, a bound port or a container that exits on"
        Write-Output "      startup all land here. Try: -TimeoutSeconds 240, or a free port."
        exit 1
    }
    Write-Output "  PASS ready"

    Write-Output ""
    Write-Output "== running $Script =="
    $env:UPTIME_KUMA_V1_URL = "http://${dockerHost}:$Port/"
    $env:UPTIME_KUMA_V1_USERNAME = $Username
    $env:UPTIME_KUMA_V1_PASSWORD = $Password

    $output = & $Python $Script 2>&1
    $exitCode = $LASTEXITCODE
    Write-Clean $output

    Write-Output ""
    if ($exitCode -eq 0) {
        Write-Output "== PASS -> $Script exited 0 =="
    }
    else {
        Write-Output "== FAIL -> $Script exited $exitCode =="
    }
}
finally {
    # Always clears the credentials from this process, and always deals with the
    # container -- including on the readiness-timeout and script-raised paths.
    $env:UPTIME_KUMA_V1_URL = $null
    $env:UPTIME_KUMA_V1_USERNAME = $null
    $env:UPTIME_KUMA_V1_PASSWORD = $null

    Write-Output ""
    if ($KeepContainer) {
        Write-Output "== keeping $Name as requested =="
        Write-Output "  remove it with: ssh <user>@<docker-host> 'docker rm -f $Name'"
    }
    else {
        Write-Output "== removing $Name =="
        Write-Clean (Invoke-Remote "docker rm -f $Name")
    }
}

exit $exitCode
