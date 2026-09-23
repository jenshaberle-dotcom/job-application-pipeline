# JAP Control Center — installed Windows app

Status: current product-local Windows architecture

The installed JAP Control Center is a native Windows WebView2 shell around the local JAP Product runtime. Windows owns the installed desktop product, immutable product staging, update consent and transactional cutover. WSL remains the execution environment for Python and PostgreSQL access, but it is **not** a routine update authority.

## Canonical product boundary

The current generation starts at desktop version **1.0.62** and uses:

- install schema: `job_application_pipeline.windows_control_center_install.v3`;
- update generation: `cgkb_product_local_v1`;
- compatibility line: `cgkb-product-local-1`;
- release namespace: `jap-winapp-product-v<version>`;
- staging authority: the installed product-local update agent;
- consent authority: the running JAP Control Center;
- apply authority: the pre-staged isolated product helper.

Pre-1.0.62 installations require the explicit bootstrap bridge. They are not direct routine-update peers of this generation.

## Immutable release contract

Each product release binds one exact source SHA and publishes four required assets:

```text
JAP-Control-Center-Desktop-win-x64.zip
JAP-Control-Center-Desktop-win-x64.zip.sha256
JAP-Control-Center-Runtime.zip
JAP-Control-Center-Runtime.zip.sha256
```

The desktop archive contains the self-contained Windows host and `build-info.json`. The runtime archive contains the executable JAP source/runtime surface, `runtime-info.json`, the WSL runtime bridge, requirements and the already-built React `dist` with an exact `.jap-source-sha` marker.

Routine updates never build frontend assets, clone/fetch source, create a worktree or compile product code on the consumer machine.

## One-time install / bootstrap bridge

Run from the canonical WSL checkout after the target product release exists:

```bash
cd ~/projects/job-application-pipeline
bash scripts/install_jap_windows_control_center.sh
```

The bridge verifies the canonical repository identity and exact target source, downloads or consumes the immutable desktop and runtime release assets, verifies checksums and embedded identities, stages both under the managed per-user install root and performs a rollback-capable adoption.

The default Windows install root is:

```text
%LOCALAPPDATA%\JAP-Control-Center
```

After a successful bridge, `current.json` records the exact product source, desktop version, release namespace, update generation, WSL private-environment root and the WSL-visible immutable runtime-bundle path.

The bridge also deletes retired locally installed updater/launcher artifacts and stale updater state. Those retired components are migration cleanup targets only; they are not part of the current repository authority.

## Installed layout

```text
JAP-Control-Center\
├── current.json
├── Stop-JAP-Control-Center.ps1
├── desktop-host\
│   ├── JAP.ControlCenter.Desktop.exe
│   ├── build-info.json
│   └── self-contained .NET/WebView2 files
├── runtime\
│   ├── runtime-info.json
│   ├── requirements.txt
│   ├── src\
│   ├── scripts\
│   └── frontend\control-center\dist\
│       ├── index.html
│       └── .jap-source-sha
├── updates\
├── rollback\
├── logs\
└── state\
    ├── runtime.json
    ├── pending-update.json
    ├── accepted-update.json
    └── webview2\
```

Secrets, PostgreSQL data, CV/application files and `private_application_sources/` remain in the canonical WSL project/private environment and are not copied into the Windows product bundle.

## Runtime execution

The native desktop host reads the persisted installation contract and invokes the runtime bridge from the immutable runtime bundle through WSL. The bridge uses:

- canonical WSL `.venv` and private `.env`;
- canonical private application documents;
- executable product code from the immutable runtime bundle;
- the prebuilt source-bound React bundle;
- the exact installed source SHA.

The runtime bridge refuses mismatched repository/source metadata and mismatched frontend markers. It has no routine Git checkout/fetch path and no npm preparation/build action.

## Routine self-update

The current flow is:

```text
immutable product release
  -> product-local discovery
  -> download desktop + runtime archives
  -> checksum verification
  -> extraction into managed staging
  -> desktop/runtime identity verification
  -> pre-stage isolated apply helper
  -> tree-digest verification
  -> pending-update.json
  -> operator consent
  -> frozen accepted-update.json
  -> launch already-staged helper
  -> re-verify frozen staged trees
  -> atomic desktop + runtime cutover
  -> update current.json
  -> restart native host
  -> verify /app-info.json source_revision
  -> success cleanup
       or transactional desktop + runtime + current.json rollback
```

The key invariant is **stage before consent**. After the operator chooses Yes, the applier performs no release discovery, network download, archive extraction, Git operation, npm build, PowerShell updater invocation or WSL update mutation.

Choosing No snoozes the prompt for six hours. Before consent, a newer eligible release may supersede the pending desired state. After consent, the frozen accepted target cannot drift.

## Authority split

Routine update authority is intentionally separated:

1. hosted CI builds and qualifies exact-source desktop/runtime assets;
2. GitHub Release publishes one immutable product identity;
3. the installed product-local agent discovers, downloads, extracts and verifies;
4. the GUI owns explicit consent;
5. the isolated helper installs only the frozen staged target;
6. restart proof verifies the exact target runtime identity;
7. failure restores desktop, runtime and `current.json` together.

A CI runner, WSL checkout, Git command, npm build or operator PowerShell updater is not part of the routine product update authority.

## Product and privacy boundaries

The Windows application and updater do not gain application-submission authority. They do not:

- activate sources or market sensors;
- mutate ranking or Top-5 truth;
- approve or send applications;
- copy credentials to Windows;
- copy private CV/application documents to Windows;
- discover executable update material after consent.

The installed interactive runtime remains local-only on `127.0.0.1:8780`.
