#import "../template.typ": *

= Deploy Target Setup <appendix-deploy-setup>

This appendix documents the complete procedure for configuring a deployment target server for the DESMET evaluation framework's Build & Deploy stage. The setup prioritises security --- the target server may host other production services, so the deploy user must be strictly isolated.

== Architecture

The deployment architecture separates concerns across three layers:

- *Local machine* (evaluation harness): commits and pushes build artifacts to a git repository
- *GitHub* (artifact transport): hosts the deploy repository with per-platform branches
- *Target server* (runtime): pulls branches via SSH, runs containers via Docker Compose, serves via reverse proxy

SSH access to the target server is restricted to a private network (Tailscale VPN), while HTTP traffic from end users routes through Cloudflare to the server's public IP. This separation ensures deploy operations are never exposed to the public internet.

== Step 1: Create a Restricted Deploy User

A dedicated user with no sudo access is created to isolate all deploy operations from the rest of the system.

#figure(
  ```bash
  adduser --disabled-password --gecos '' desmet
  usermod -aG docker desmet
  mkdir -p /opt/desmet
  chown desmet:desmet /opt/desmet
  ```,
  caption: [Creating the deploy user and workspace directory],
)

The user is added to the `docker` group to allow container management. This would normally grant root-equivalent access (via `docker run -v /:/host`), but is mitigated by the restricted shell installed in Step 4.

== Step 2: SSH Key Authentication

An Ed25519 key pair is generated on the local machine for deploy access:

#figure(
  ```bash
  ssh-keygen -t ed25519 -f ~/.ssh/desmet_deploy -N "" -C "desmet-deploy"
  ```,
  caption: [Generating the deploy SSH key pair (local machine)],
)

The public key is installed on the server:

#figure(
  ```bash
  mkdir -p /home/desmet/.ssh
  echo "PUBLIC_KEY_CONTENT" > /home/desmet/.ssh/authorized_keys
  chown -R desmet:desmet /home/desmet/.ssh
  chmod 700 /home/desmet/.ssh
  chmod 600 /home/desmet/.ssh/authorized_keys
  ```,
  caption: [Installing the deploy public key on the server],
)

== Step 3: SSH Daemon Hardening

The SSH daemon is configured to prevent the deploy user from establishing tunnels, forwarding ports, or using agent forwarding. This eliminates lateral movement vectors if the deploy key is compromised.

#figure(
  ```
  Match User desmet
      AllowTcpForwarding no
      X11Forwarding no
      PermitTunnel no
      AllowAgentForwarding no
  ```,
  caption: [SSH hardening rules added to `sshd_config`],
)

If the server uses an `AllowUsers` directive, `desmet` must be added to the list. The SSH daemon is then restarted to apply the changes.

The deploy tool also passes `-o IdentitiesOnly=yes` in all SSH commands to prevent the SSH agent from offering unrelated keys, which avoids "too many authentication failures" errors on servers with strict retry limits.

== Step 4: Restricted Shell

The default shell for the deploy user is replaced with a whitelist-based script that permits only the commands required by the deploy pipeline. This is the primary security control that makes Docker group membership safe.

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Allowed*], [*Blocked*],
    ),
    [`git pull`, `fetch`, `clone`, `status` (within `/opt/desmet`)], [`git push`, any git operation outside `/opt/desmet`],
    [`docker compose up/down/ps/logs/build/restart/stop/start`], [`docker run`, `docker exec`, `docker rm`],
    [`docker ps` (read-only)], [All other `docker` subcommands],
    [`curl` (for health checks)], [`wget`, `nc`, other network tools],
    [`mkdir -p` (within `/opt/desmet`)], [`rm`, `cat`, `chmod`, `chown`, all other commands],
    [`whoami`, `id`], [Interactive shell access],
  ),
  caption: [Restricted shell command whitelist],
)

The script is installed at `/usr/local/bin/desmet-shell` and set as the user's login shell via `usermod -s`. Any command not matching the whitelist is rejected with an error message listing permitted operations.

== Step 5: GitHub Deploy Key

A separate SSH key pair is generated _on the server_ so that the deploy user can pull from the private deploy repository:

#figure(
  ```bash
  sudo -u desmet ssh-keygen -t ed25519 -f /home/desmet/.ssh/id_ed25519 \
      -N "" -C "desmet-server"
  ```,
  caption: [Generating the server-side GitHub deploy key],
)

The public key is added as a _read-only deploy key_ on the GitHub repository (Settings #sym.arrow Deploy keys). Read-only access is sufficient since the server only pulls --- all pushes originate from the local machine.

== Step 6: Reverse Proxy

Nginx routes platform-specific subdomains to unique container ports using a `map` block:

#figure(
  ```nginx
  map $host $desmet_port {
      langgraph-desmet.example.com     8001;
      crewai-desmet.example.com        8002;
      openai-agents-desmet.example.com 8003;
      google-adk-desmet.example.com    8004;
      agent-framework-desmet.example.com 8005;
  }

  server {
      listen 443 ssl;
      server_name *-desmet.example.com;

      ssl_certificate     /path/to/origin-cert.pem;
      ssl_certificate_key /path/to/origin-key.pem;

      location / {
          proxy_pass http://127.0.0.1:$desmet_port;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
      }
  }
  ```,
  caption: [Nginx configuration for subdomain-based routing],
)

Adding a new platform requires only a new `map` entry and a DNS A record --- no new `server` block. If using Cloudflare, a proxied Origin Certificate provides TLS termination without renewal overhead.

== Step 7: Environment Variables

The evaluation harness reads deploy configuration from environment variables, set in the project's `.env` file:

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Variable*], [*Example*], [*Purpose*],
    ),
    [`DEPLOY_HOST`], [`100.x.x.x`], [Server IP (Tailscale or public)],
    [`DEPLOY_PORT`], [`2222`], [SSH port (defaults to 22)],
    [`DEPLOY_USER`], [`desmet`], [SSH username],
    [`DEPLOY_KEY_PATH`], [`~/.ssh/desmet_deploy`], [Path to private key],
    [`DEPLOY_REPO`], [`git\@github.com:user/repo.git`], [Deploy repository URL (SSH format)],
    [`DEPLOY_BASE_PATH`], [`/opt/desmet`], [Server-side workspace root],
  ),
  caption: [Deploy stage environment variables],
)

The `DEPLOY_REPO` URL uses SSH format because the server pulls from GitHub using its deploy key. Local pushes from the evaluation harness are automatically converted to HTTPS with token authentication, so no additional GitHub credentials are required on the local machine beyond an authenticated `gh` CLI.

The management console's configuration panel displays the deploy target status (configured, partially configured, or not configured) based on whether these environment variables are set.

== Verification

Once all steps are complete, the setup can be verified from the local machine:

#figure(
  ```bash
  # Test SSH access
  ssh desmet-deploy "whoami"

  # Test Docker access
  ssh desmet-deploy "docker ps"

  # Test GitHub access from server
  ssh desmet-deploy "ssh -T git@github.com 2>&1"

  # Test public endpoint (expect 502 --- no container running yet)
  curl -sI https://langgraph-desmet.example.com
  ```,
  caption: [Verification commands for the deploy target],
)

A 502 response from the public endpoint is expected before any deployment has occurred, confirming that DNS, Cloudflare, and nginx are correctly configured and awaiting a backend service.
