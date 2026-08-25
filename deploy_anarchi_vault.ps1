<#
Safe deploy script for running a local Vault + cloudflared tunnel inside WSL2.
Notes:
- Designed to be run from PowerShell 7 on Windows and will write files into the WSL user's home (/home/ubuntu/anarchi-spine).
- Requires an environment variable VAULT_BROKER_TOKEN to be available inside WSL at runtime (used by the generated Python broker).
- Requires CLOUDFLARE_VAULT_TUNNEL_TOKEN to be set in WSL for cloudflared to run, or create the .env file in WSL manually.
- This script intentionally avoids capturing secrets in transcripts and fails fast if required secrets are missing.
- It writes docker-compose.vault.yml, broker-policy.hcl and anarchi_membrane_broker.py into WSL and then runs docker compose up.
#>

if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Host "PowerShell 7 or newer is required. Aborting." -ForegroundColor Red
    exit 1
}

# ---- Configuration (target the existing WSL2 Ubuntu instance and its current user home) ----
$wslUser = (wsl -e bash -lc 'whoami').Trim()
if (-not $wslUser) {
    Write-Host "Unable to detect active WSL user. Aborting." -ForegroundColor Red
    exit 1
}
$wslBaseDir = "/home/$wslUser/anarchi-asset-spine"
$composeFilename = 'docker-compose.vault.yml'
$policyFilename = 'vault/config/broker-policy.hcl'
$pythonFilename = 'anarchi_membrane_broker.py'

# ---- Safety: Do not log secrets ----
Write-Host "This script will use the existing WSL2 Ubuntu instance and write files into $wslBaseDir without creating a new WSL server." -ForegroundColor Cyan
Write-Host "Make sure you review the generated files before running in production. Secrets must be provided in the WSL environment or via a .env file placed into $wslBaseDir (not committed)." -ForegroundColor Yellow

# ---- Check required environment variables (on Windows side) ----
# Note: these are only used here to decide whether to proceed. The actual runtime expects these variables inside WSL.
if (-not $env:VAULT_BROKER_TOKEN) {
    Write-Host "WARNING: VAULT_BROKER_TOKEN is not set in the current Windows session." -ForegroundColor Yellow
    Write-Host "You must set this variable in WSL before running the generated Python broker (export VAULT_BROKER_TOKEN=...)" -ForegroundColor Yellow
}
if (-not $env:CLOUDFLARE_VAULT_TUNNEL_TOKEN) {
    Write-Host "WARNING: CLOUDFLARE_VAULT_TUNNEL_TOKEN is not set in the current Windows session." -ForegroundColor Yellow
    Write-Host "You must set this variable in WSL (or create a .env file in $wslBaseDir) before starting the cloudflared service." -ForegroundColor Yellow
}

# ---- Prepare docker-compose YAML (use explicit port mapping; avoid host network) ----
$dockerComposeYaml = @'
version: '3.8'

services:
  anarchi-vault:
    image: hashicorp/vault:1.15.0
    container_name: anarchi_vault
    restart: always
    environment:
      VAULT_LOCAL_CONFIG: |
        {
          "backend": { "file": { "path": "/vault/file" } },
          "listener": { "tcp": { "address": "0.0.0.0:8200", "tls_disable": 1 } },
          "default_lease_ttl": "1h",
          "max_lease_ttl": "24h",
          "ui": false
        }
    cap_add:
      - IPC_LOCK
    volumes:
      - ./vault/data:/vault/file
      - ./vault/config:/vault/config
    ports:
      - "127.0.0.1:8200:8200"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:8200/v1/sys/health"]
      interval: 10s
      timeout: 5s
      retries: 12

  anarchi-vault-tunnel:
    image: cloudflare/cloudflared:latest
    container_name: anarchi_vault_tunnel
    restart: always
    volumes:
      - ./cloudflare:/etc/cloudflared
    environment:
      - CLOUDFLARE_VAULT_TUNNEL_TOKEN
    command: tunnel run --token ${CLOUDFLARE_VAULT_TUNNEL_TOKEN}
'@

# ---- Broker policy HCL ----
$vaultPolicyHcl = @'
path "auth/token/create" {
  capabilities = ["create", "update"]
  allowed_parameters = {
    "ttl" = ["30s", "1m"]
    "num_uses" = ["1"]
    "explicit_max_ttl" = ["5m"]
    "policies" = ["anarchi-broker"]
    "meta" = []
  }
}

path "secret/data/organizations/+/credentials/*" {
  capabilities = ["read"]
  min_wrapping_ttl = "10s"
  max_wrapping_ttl = "60s"
}
'@

# ---- Python membrane broker (fixed Vault URL and /v1 API paths; require VAULT_BROKER_TOKEN) ----
$membraneBrokerPy = @'
import os
import sys
import hashlib
import hmac
import time
import secrets
import requests

# Use VAULT_ADDR environment variable if present. Default is loopback with Vault port.
VAULT_ADDR = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
VAULT_MASTER_TOKEN = os.getenv("VAULT_BROKER_TOKEN")
if not VAULT_MASTER_TOKEN:
    print("[AnarchI Membrane] ERROR: VAULT_BROKER_TOKEN is not set. Set the environment variable and retry.", file=sys.stderr)
    sys.exit(2)

# NOTE: MEMBRANE_SALT is process-ephemeral by design. If persistent cross-process validation is required, store/retrieve the salt securely.
MEMBRANE_SALT = secrets.token_bytes(64)

class AnarchiMembraneBarrier:
    def __init__(self):
        if not VAULT_MASTER_TOKEN:
            print("[AnarchI Membrane] Critical Error: Missing secure token root context.", file=sys.stderr)
            sys.exit(1)

    def generate_ephemeral_handle(self, user_identity, membership_tag, requested_capability):
        headers = {"X-Vault-Token": VAULT_MASTER_TOKEN}
        meta_payload = {
            "policies": ["anarchi-broker"],
            "meta": {
                "identity_substrate": user_identity,
                "membership_tag": membership_tag,
                "capability": requested_capability,
                "salt_nonce": secrets.token_hex(16)
            },
            "ttl": "45s",
            "num_uses": 1
        }
        try:
            # Vault HTTP API requires the /v1 prefix
            res = requests.post(f"{VAULT_ADDR}/v1/auth/token/create", json=meta_payload, headers=headers, timeout=5)
            if res.status_code != 200:
                print(f"[AnarchI Membrane] Inner Core Isolation rejection: {res.status_code} {res.text}", file=sys.stderr)
                return None
            j = res.json()
            if not ("auth" in j and "client_token" in j["auth"]):
                print(f"[AnarchI Membrane] Unexpected Vault response: {j}", file=sys.stderr)
                return None
            raw_vault_token = j["auth"]["client_token"]
            blind_handle = hmac.new(
                MEMBRANE_SALT,
                f"{raw_vault_token}:{user_identity}:{time.time()}".encode(),
                hashlib.sha256
            ).hexdigest()
            return {
                "handle": f"ANARCHI-HANDLE-{blind_handle}",
                "internal_token_ref": raw_vault_token,
                "expires_at": time.time() + 45.0
            }
        except Exception as e:
            print(f"[AnarchI Membrane] Critical loop failure: {e}", file=sys.stderr)
            return None

    def execute_blind_publish(self, active_context, target_platform, asset_payload):
        if time.time() > active_context.get("expires_at", 0):
            print("[AnarchI Membrane] Action Aborted: Temporal execution barrier threshold exceeded.")
            return False
        headers = {"X-Vault-Token": active_context.get("internal_token_ref")}
        try:
            lookup_res = requests.get(f"{VAULT_ADDR}/v1/auth/token/lookup-self", headers=headers, timeout=5)
            if lookup_res.status_code != 200:
                print("[AnarchI Membrane] Authorization Rejected: Token replay prevented or lease expired.")
                return False
            metadata = lookup_res.json().get("data", {}).get("meta", {})
            print(f"[AnarchI Membrane] Execution Validated: {metadata.get('identity_substrate')} saturated with capability {metadata.get('capability')}")
            return True
        except Exception as e:
            print(f"[AnarchI Membrane] Runtime loop exception: {e}", file=sys.stderr)
            return False

if __name__ == "__main__":
    print("[AnarchI Engine] Executing structural reverse-engineering isolation test...")
    barrier = AnarchiMembraneBarrier()
    context = barrier.generate_ephemeral_handle(
        user_identity="usr:anar-core:identity:77x9",
        membership_tag="membership:adforge:intelligence_tier_3",
        requested_capability="capability:publish_marketing_artifact_z"
    )
    if context:
        print(f"\n[OBFUSCATED BLIND STRING EXPOSED TO CLIENT EXTERNAL RUNTIME]:\n{context['handle']}\n")
        barrier.execute_blind_publish(context, "META-ADS", {"artifact_digest": "ADF-BODY-LIMB-006"})
'@

# ---- Write files into WSL by piping content into 'cat > file' on the WSL side (safer than fragile heredocs) ----
Write-Host "Creating WSL target directory structure inside the existing Ubuntu instance: $wslBaseDir" -ForegroundColor Cyan
wsl -u $wslUser -- bash -c "mkdir -p '$wslBaseDir' && mkdir -p '$wslBaseDir/vault/config' && mkdir -p '$wslBaseDir/cloudflare'"

Write-Host "Writing docker-compose to WSL: $composeFilename" -ForegroundColor Cyan
$dockerComposeYaml | wsl -u $wslUser -- bash -lc "cat > $wslBaseDir/$composeFilename"

Write-Host "Writing Vault policy to WSL: $policyFilename" -ForegroundColor Cyan
$vaultPolicyHcl | wsl -u $wslUser -- bash -lc "cat > $wslBaseDir/$policyFilename"

Write-Host "Writing Python membrane broker to WSL: $pythonFilename" -ForegroundColor Cyan
$membraneBrokerPy | wsl -u $wslUser -- bash -lc "cat > $wslBaseDir/$pythonFilename"

# ---- If user provided CLOUDFLARE token on Windows, optionally write .env into WSL (warning: this stores secret on disk) ----
if ($env:CLOUDFLARE_VAULT_TUNNEL_TOKEN) {
    Write-Host "Detected CLOUDFLARE_VAULT_TUNNEL_TOKEN in current session. Writing a .env file into WSL (this writes the token to disk)." -ForegroundColor Yellow
    $envFile = "CLOUDFLARE_VAULT_TUNNEL_TOKEN=$($env:CLOUDFLARE_VAULT_TUNNEL_TOKEN)" + "`n"
    $envFile | wsl -u $wslUser -- bash -lc "cat > $wslBaseDir/.env"
    Write-Host "Wrote $wslBaseDir/.env (make sure this file is gitignored in your WSL workspace)." -ForegroundColor Yellow
}

# ---- Start docker-compose in WSL ----
Write-Host "Starting docker compose stack inside WSL..." -ForegroundColor Green
wsl -u $wslUser -- bash -lc "cd $wslBaseDir && docker compose -f $composeFilename up -d"

# ---- Wait for Vault to be healthy (simple loop with reasonable timeout) ----
Write-Host "Waiting for Vault to report healthy/unsealed status (up to 120s)..." -ForegroundColor Cyan
$waitStart = Get-Date
$healthy = $false
while ((Get-Date) - $waitStart -lt (New-TimeSpan -Seconds 120)) {
    try {
        $resp = wsl -u $wslUser -- bash -lc "curl -s -o /dev/null -w \"%{http_code}\" http://127.0.0.1:8200/v1/sys/health || echo 000"
        if ($resp -eq '200') { $healthy = $true; break }
    } catch { }
    Start-Sleep -Seconds 5
}
if (-not $healthy) {
    Write-Host "Vault did not become healthy within timeout. You may need to unseal Vault and/or inspect container logs." -ForegroundColor Red
    Write-Host "To view logs: wsl -u $wslUser -- bash -lc 'docker logs anarchi_vault'" -ForegroundColor DarkGray
    exit 3
}

Write-Host "Vault is up. IMPORTANT: Vault is NOT auto-unsealed by this script. Unseal and write the policy inside the container or enable auto-unseal in production." -ForegroundColor Green
Write-Host "To register the broker policy inside the Vault container run (inside WSL or the container):" -ForegroundColor DarkGray
Write-Host "  vault policy write anarchi-broker /vault/config/broker-policy.hcl" -ForegroundColor DarkGray

Write-Host "Done. Generated files are in WSL: $wslBaseDir. Review the files and ensure VAULT_BROKER_TOKEN and CLOUDFLARE_VAULT_TUNNEL_TOKEN are set inside WSL before running the Python broker or relying on cloudflared." -ForegroundColor Green
