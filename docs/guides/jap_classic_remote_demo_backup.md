# JAP Classic remote demo backup

Status: branch-local demo backup only  
Scope: remote browser operation of the existing local JAP Classic runtime

## Intent

This path does **not** make JAP Classic a cloud product. The product runtime, PostgreSQL,
private application documents, provider integration and all application logic stay on the
home machine. The only remote component is an authenticated HTTPS bridge to the already
existing local browser surface on \`http://127.0.0.1:8780\`.

The normal product path remains local-only. This backup is opt-in and is intentionally
kept off \`main\` unless a later explicit product decision says otherwise.

## Network boundary

\`\`\`text
remote browser
  -> HTTPS
  -> Cloudflare Access
  -> Cloudflare Tunnel
  -> http://127.0.0.1:8780
  -> existing JAP Classic React/Python runtime
  -> existing local PostgreSQL / files / provider path
\`\`\`

There is no router port-forward, no public PostgreSQL endpoint and no JAP bind to
\`0.0.0.0\`.

## One-time Cloudflare setup

Use a **remotely managed named tunnel**, not a Quick Tunnel.

1. Put the demo hostname on a domain managed by Cloudflare.
2. In Zero Trust, create a self-hosted Access application for the exact demo hostname.
   Limit access to the intended operator identity and require the desired MFA policy.
3. Create a Cloudflare Tunnel.
4. Add one Published application route:
   - hostname: the demo hostname, for example \`jap-demo.example.com\`
   - service: \`http://127.0.0.1:8780\`
5. Enable **Protect with Access** for the tunnel route so \`cloudflared\` validates the
   Access token at the connector boundary.
6. Install current \`cloudflared\` on the Windows JAP machine and ensure
   \`cloudflared.exe\` is on \`PATH\`.
7. Copy the remotely-managed tunnel token. Do not commit it and do not place it in a
   repository file.

Cloudflare documents the hostname-to-local-service route explicitly for Tunnel. Access
must be created before publishing the route; otherwise the hostname can be reachable
without authentication.

## Start for a demo

1. Start JAP Classic normally and wait until the local UI is ready.
2. Open a fresh PowerShell window.
3. Put the hostname in the process environment:

\`\`\`powershell
$env:JAP_DEMO_REMOTE_HOSTNAME = "jap-demo.example.com"
\`\`\`

4. Load the tunnel token without writing it to command history:

\`\`\`powershell
$secureToken = Read-Host "Cloudflare tunnel token" -AsSecureString
$tokenPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $env:JAP_DEMO_CLOUDFLARE_TUNNEL_TOKEN =
        [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPtr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPtr)
}
Remove-Variable secureToken, tokenPtr -ErrorAction SilentlyContinue
\`\`\`

5. Start the backup bridge from this branch:

\`\`\`powershell
.\scripts\windows\Start-JAP-Classic-Remote-Demo.ps1
\`\`\`

The launcher refuses to report READY unless all of these are true:

- JAP answers locally on \`127.0.0.1:8780/healthz\`;
- \`cloudflared\` exists;
- a tunnel token is present only in process environment;
- the tunnel process stays alive;
- an unauthenticated HTTPS request to the public \`/healthz\` endpoint is challenged
  or blocked by Cloudflare Access;
- an unauthenticated public HTTP 200 causes an immediate fail-closed stop.

The token is passed to \`cloudflared\` through its documented \`TUNNEL_TOKEN\` environment
variable, not as a command-line argument.

## Stop after the demo

\`\`\`powershell
.\scripts\windows\Start-JAP-Classic-Remote-Demo.ps1 -Stop
Remove-Item Env:\JAP_DEMO_CLOUDFLARE_TUNNEL_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:\JAP_DEMO_REMOTE_HOSTNAME -ErrorAction SilentlyContinue
\`\`\`

The stop path only terminates the exact \`cloudflared\` PID and executable path recorded
by this launcher. It does not scan for or kill unrelated tunnel processes.

## Demo acceptance check

From a device outside the home network:

1. open \`https://<demo-hostname>/\`;
2. verify Cloudflare Access authentication appears before JAP content;
3. authenticate;
4. verify the same Control Center data visible locally;
5. open the target job/application workflow;
6. exercise the demo path through document generation and browser download;
7. log out or use a private window to confirm the unauthenticated Access gate again.

If a browser-only operation depends on a desktop-specific Windows action, record that as a
bounded demo incompatibility. Do not broaden this backup into a second cloud architecture.

## Explicit non-goals

- no cloud database;
- no multi-user JAP;
- no cloud worker or container deployment;
- no change to JAP product authority;
- no router port-forward;
- no RDP;
- no public local-network bind;
- no Quick Tunnel / anonymous \`trycloudflare.com\` demo;
- no credential or tunnel token in Git.
