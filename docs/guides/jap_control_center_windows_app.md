# JAP Control Center — installed Windows app

The Windows app is the operator-facing shell for the existing JAP Product V1 Control Center. It deliberately does **not** duplicate the JAP runtime onto Windows. Windows owns installation, the native desktop window and update consent; WSL remains the runtime authority for Python, PostgreSQL connectivity, `.env`, private application documents and the exact Product V1 launcher.

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

The installer also resolves the WSL distribution, verifies the configured repository identity, fetches public product code over HTTPS, records the exact `main` SHA and creates only the operator surfaces that belong to the application:

- Desktop shortcut: **JAP Control Center**;
- Start Menu: **JAP Control Center**;
- Start Menu: **Stop JAP Control Center**.

There is deliberately no separately launchable update program or update shortcut. Update discovery and consent live inside the main JAP Control Center window.

## Installed layout

```text
JAP-Control-Center\
├── current.json
├── JAP-Control-Center.ps1
├── Stop-JAP-Control-Center.ps1
├── Apply-JAP-Control-Center-Update.ps1   # internal helper, not an operator surface
├── run-jap-control-center-wsl.sh
├── desktop-host\
│   ├── JAP.ControlCenter.Desktop.exe
│   ├── build-info.json
│   └── self-contained .NET/WebView2 host files
├── logs\
│   ├── runtime.stdout.log
│   ├── runtime.stderr.log
│   └── desktop-host-update.log
└── state\
    ├── runtime.json
    ├── pending-update.json
    ├── accepted-update.json
    └── webview2\
```

`Apply-JAP-Control-Center-Update.ps1` is an implementation detail used after explicit consent because a running Windows executable cannot safely replace its own files. It has no shortcut and is not intended to be invoked by the operator.

Secrets, PostgreSQL data, Candidate Facts, CV/application files and `private_application_sources/` are not copied to this directory.

## Runtime layout in WSL

The installed launcher keeps two distinct WSL paths:

1. canonical private/runtime checkout, normally `~/projects/job-application-pipeline`;
2. managed detached code worktree, normally `~/.local/share/jap-control-center/runtime`.

The managed worktree is pinned to the exact `main` SHA recorded by the installer/updater. The launcher refuses a dirty managed worktree, resets generated frontend dependency state when necessary, activates the canonical checkout's `.venv`, sources the canonical `.env`, selects native WSL Node 22/npm, binds `PRODUCT_V1_PRIVATE_DOCUMENT_ROOT` to the canonical `private_application_sources/`, and then invokes the existing fail-closed `scripts/run_product_v1_live_demo.py` path.

Generated frontend state is source-bound. A `dist` bundle can be reused only when its `.jap-source-sha` marker matches the exact installed pin. The generated `app-info.json` publishes the same source revision to the local desktop shell.

## Normal launch

Double-click **JAP Control Center**.

The desktop host:

1. starts the existing hidden PowerShell launcher with `-NoBrowser`;
2. that launcher proves or starts the managed WSL runtime on `127.0.0.1:8780`;
3. an already running JAP endpoint is reusable only when both its `DeepOceanProductV1/*` server identity and `/app-info.json` source revision match `current.json.pinned_sha` exactly;
4. a managed stale JAP runtime from an older installed source is stopped and replaced;
5. an unrelated process on port 8780 remains fail-closed and is never killed;
6. after readiness succeeds, WebView2 renders the loopback Control Center in the native window.

Runtime output is retained in `%LOCALAPPDATA%\JAP-Control-Center\logs`.

## Window close and stopping

Closing the native JAP window invokes **Stop JAP Control Center** automatically.

The stop action is fail-closed. The WSL runner will send a signal only when the recorded Linux PID:

- exists;
- has a command line containing `scripts/run_product_v1_live_demo.py`;
- has the managed worktree as its current working directory.

A manually started or unrelated process is not eligible for termination. The Start Menu stop shortcut remains available for explicit recovery/operator use.

## Integrated self-update

Normal app launch does not fetch or advance JAP code. The local JAP runner stages a checksum-verified compatible release and writes bounded pending-update metadata. The running JAP Control Center polls that local pending state and owns the complete user-facing update interaction.

The operator flow is:

```text
JAP Control Center
  -> "Update available"
  -> Yes: freeze the exact offered target
  -> main window closes
  -> hidden internal applier verifies and installs the staged target
  -> JAP Control Center restarts
```

Choosing **No** snoozes the prompt for six hours. During the snooze, a newer compatible v1 release may replace the pending desired state. Once the operator chooses **Yes**, the exact displayed release is frozen in `accepted-update.json`; a newer release appearing during application of that update is not silently substituted.

The compatibility line uses the `latest_direct` policy: supported v1 releases are direct upgrade targets from older supported v1 releases. Breaking changes require an explicit compatibility bridge rather than silently reusing the v1 line.

The separate historical `Update JAP Control Center` Start Menu entry and installed `Update-JAP-Control-Center.ps1` operator wrapper are removed when WINAPP-018 or later is installed.

## Product and privacy boundaries

The Windows app grants no additional JAP authority. In particular it does not:

- activate sources or market sensors;
- mutate ranking/Top-5 truth;
- approve application drafts;
- submit or send applications;
- copy `.env` or credentials to Windows;
- copy private CV/application documents to Windows;
- silently update the runtime on normal launch.

The installed interactive start is local-only; the broader external employer-origin/demo qualification probe remains a separate explicit validation path rather than a dependency of every desktop launch.
