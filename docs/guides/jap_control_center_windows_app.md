# JAP Control Center — installed Windows app

The Windows app is the operator-facing shell for the existing JAP Product V1 Control Center. It deliberately does **not** duplicate the JAP runtime onto Windows. Windows owns installation, shortcuts and the native desktop window; WSL remains the runtime authority for Python, PostgreSQL connectivity, `.env`, private application documents and the exact Product V1 launcher.

## Why the WSL-backed design

The proven JAP runtime path already depends on:

- the canonical WSL checkout;
- its `.venv`;
- its private `.env` PostgreSQL configuration;
- `private_application_sources/`;
- an exact detached code checkout;
- native WSL Node 22/npm;
- `scripts/run_product_v1_live_demo.py`;
- loopback service `http://127.0.0.1:8780/`.

The Windows app preserves those boundaries instead of creating a second Windows-native database/runtime truth.

## Desktop presentation

The installed operator surface is a self-contained Windows x64 **WinForms + Microsoft WebView2** host. It renders the existing React Control Center inside a dedicated `JAP Control Center` window rather than opening a normal browser tab.

The desktop host contract is intentionally narrow:

- fixed product origin: `http://127.0.0.1:8780/`;
- start size: 1440×900;
- minimum size: 1180×720;
- no browser address bar or tabs;
- one desktop-host instance per user session;
- top-level navigation stays on `127.0.0.1:8780`;
- external HTTP/HTTPS/mail links are handed to the system browser;
- closing the window invokes the existing managed-PID-only stop path.

The host never reads `.env`, PostgreSQL credentials, CVs or application documents itself.

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

No administrator privileges or local .NET SDK are required. The desktop host is built in GitHub Actions as a self-contained `win-x64` bundle, published as an immutable versioned release, downloaded by the installer and verified by SHA-256 before adoption.

The installer also resolves the WSL distribution, verifies the configured repository identity, fetches public product code over HTTPS, records the exact `main` SHA and creates:

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
├── desktop-host\
│   ├── JAP.ControlCenter.Desktop.exe
│   ├── build-info.json
│   └── self-contained .NET/WebView2 host files
├── logs\
│   ├── runtime.stdout.log
│   └── runtime.stderr.log
└── state\
    ├── runtime.json
    └── webview2\
```

Secrets, PostgreSQL data, Candidate Facts, CV/application files and `private_application_sources/` are not copied to this directory.

## Runtime layout in WSL

The installed launcher keeps two distinct WSL paths:

1. canonical private/runtime checkout, normally `~/projects/job-application-pipeline`;
2. managed detached code worktree, normally `~/.local/share/jap-control-center/runtime`.

The managed worktree is pinned to the exact `main` SHA recorded by the installer/updater. The launcher refuses a dirty managed worktree, resets generated frontend dependency state when necessary, activates the canonical checkout's `.venv`, sources the canonical `.env`, selects native WSL Node 22/npm, binds `PRODUCT_V1_PRIVATE_DOCUMENT_ROOT` to the canonical `private_application_sources/`, and then invokes the existing fail-closed `scripts/run_product_v1_live_demo.py` path.

If a qualified frontend build already exists in the managed worktree, the launcher uses `--reuse-frontend`; otherwise the canonical launcher performs its normal frontend install/build before the readiness probes.

## Normal launch

Double-click **JAP Control Center**.

The desktop host:

1. starts the existing hidden PowerShell launcher with `-NoBrowser`;
2. that launcher proves or starts the managed WSL runtime on `127.0.0.1:8780`;
3. it reuses an already running endpoint only when its HTTP server identity is `DeepOceanProductV1/*`;
4. it fails closed if another process owns port 8780;
5. after readiness succeeds, WebView2 renders the loopback Control Center in the native window.

Runtime output is retained in `%LOCALAPPDATA%\JAP-Control-Center\logs`.

## Window close and stopping

Closing the native JAP window invokes **Stop JAP Control Center** automatically.

The stop action is fail-closed. The WSL runner will send a signal only when the recorded Linux PID:

- exists;
- has a command line containing `scripts/run_product_v1_live_demo.py`;
- has the managed worktree as its current working directory.

A manually started or unrelated process is not eligible for termination. The Start Menu stop shortcut remains available for explicit recovery/operator use.

## Updating

Product-code updates remain intentionally **explicit**. Normal app launch does not fetch or advance JAP code.

Choose **Update JAP Control Center** from the Start Menu. It fetches `main` over the read-only HTTPS transport and atomically stages the new exact SHA in `current.json`. That SHA is used on the next managed start.

The desktop shell has a separate immutable release/version contract. Changing its Windows host code requires a desktop-host version bump and a new checksum-verified release; ordinary JAP product-code updates do not rebuild the desktop shell.

## Product and privacy boundaries

The Windows app grants no additional JAP authority. In particular it does not:

- activate sources or market sensors;
- mutate ranking/Top-5 truth;
- approve application drafts;
- submit or send applications;
- copy `.env` or credentials to Windows;
- copy private CV/application documents to Windows;
- silently update the runtime on normal launch.

The existing Product V1 readiness chain remains authoritative:

`frontend build/reuse -> live preflight -> Application Workspace probe -> offline draft handoff -> loopback Control Center -> native WebView2 window`.
