# JAP Control Center — installed Windows app

The Windows app is the operator-facing shell for the existing JAP Product V1 Control Center. It deliberately does **not** duplicate the JAP runtime onto Windows. Windows owns installation, shortcuts, process launch and browser opening; WSL remains the runtime authority for Python, PostgreSQL connectivity, `.env`, private application documents and the exact Product V1 launcher.

## Why the WSL-backed design

The proven JAP demo/runtime path already depends on:

- the canonical WSL checkout;
- its `.venv`;
- its private `.env` PostgreSQL configuration;
- `private_application_sources/`;
- an exact detached code checkout;
- `scripts/run_product_v1_live_demo.py`;
- loopback service `http://127.0.0.1:8780/`.

The Windows app preserves those boundaries instead of creating a second Windows-native database/runtime truth.

## One-time installation

From the canonical WSL checkout:

```bash
cd ~/projects/job-application-pipeline
bash scripts/install_jap_windows_control_center.sh
```

The Windows installer defaults to:

```text
%LOCALAPPDATA%\JAP-Control-Center
```

No administrator privileges are required. The installer resolves the default WSL distribution, verifies the configured repository origin, fetches `origin/main`, records its exact SHA and creates:

- Desktop shortcut: **JAP Control Center**;
- Start Menu: **JAP Control Center**;
- Start Menu: **Update JAP Control Center**;
- Start Menu: **Stop JAP Control Center**.

## Installed layout

```text
JAP-Control-Center\
├── current.json
├── JAP-Control-Center.ps1
├── Update-JAP-Control-Center.ps1
├── Stop-JAP-Control-Center.ps1
├── run-jap-control-center-wsl.sh
├── logs\
│   ├── runtime.stdout.log
│   └── runtime.stderr.log
└── state\
    └── runtime.json
```

Secrets, PostgreSQL data, Candidate Facts, CV/application files and `private_application_sources/` are not copied to this directory.

## Runtime layout in WSL

The installed launcher keeps two distinct WSL paths:

1. canonical private/runtime checkout, normally `~/projects/job-application-pipeline`;
2. managed detached code worktree, normally `~/.local/share/jap-control-center/runtime`.

The managed worktree is pinned to the exact `origin/main` SHA recorded by the installer/updater. The launcher refuses a dirty managed worktree. It activates the canonical checkout's `.venv`, sources the canonical `.env`, binds `PRODUCT_V1_PRIVATE_DOCUMENT_ROOT` to the canonical `private_application_sources/`, and then invokes the existing fail-closed `scripts/run_product_v1_live_demo.py` path.

If a qualified frontend build already exists in the managed worktree, the launcher uses `--reuse-frontend`; otherwise the canonical launcher performs its normal frontend install/build before the readiness probes.

## Normal launch

Double-click **JAP Control Center**.

The launcher:

1. checks `127.0.0.1:8780`;
2. reuses an already running endpoint only when its HTTP server identity is `DeepOceanProductV1/*`;
3. fails closed if another process owns port 8780;
4. starts the managed WSL runtime hidden;
5. waits for the JAP endpoint to become healthy;
6. opens `http://127.0.0.1:8780/` in the default browser.

Runtime output is retained in `%LOCALAPPDATA%\JAP-Control-Center\logs`.

## Updating

Updates are intentionally **explicit** in v1. The normal app launch does not fetch or advance code.

Choose **Update JAP Control Center** from the Start Menu. It fetches `origin/main` and atomically stages the new exact SHA in `current.json`. That SHA is used on the next managed start.

This differs from the mature PED release installer on purpose: JAP is currently still moving quickly on `main` and does not yet have a stable immutable Windows-app release channel. Once JAP has a stable release bundle/manifest contract, the installer can adopt PED-style release download, checksum verification and automatic stable-version updates without changing the WSL/private-runtime boundary.

## Stopping

Choose **Stop JAP Control Center** from the Start Menu.

The stop action is fail-closed. The WSL runner will send a signal only when the recorded Linux PID:

- exists;
- has a command line containing `scripts/run_product_v1_live_demo.py`;
- has the managed worktree as its current working directory.

A manually started or unrelated process is not eligible for termination.

## Product and privacy boundaries

The Windows app itself grants no additional JAP authority. In particular it does not:

- activate sources or market sensors;
- mutate ranking/Top-5 truth;
- approve application drafts;
- submit or send applications;
- copy `.env` or credentials to Windows;
- copy private CV/application documents to Windows;
- silently update the runtime on normal launch.

The existing Product V1 demo readiness chain remains authoritative:

`frontend build/reuse -> live preflight -> Application Workspace probe -> offline draft handoff -> loopback Control Center`.
