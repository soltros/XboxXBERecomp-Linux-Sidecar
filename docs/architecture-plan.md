# Architecture and delivery plan

## Goal

Build a Linux companion toolkit around XboxXBERecomp's supported Windows workflow. The toolkit prepares title projects, runs the Windows build tools and generated player inside a managed Wine or Proton environment, and keeps each title's Windows compatibility state self-contained and easy to launch.

The Sidecar is an orchestration and packaging layer. It is not a Linux port of XboxXBERecomp and does not replace its D3D12, XAudio2, Win32, or Xbox API implementations. The Windows player remains the program being run; Wine or Proton supplies the compatibility layer.

## User-facing workflows

### Build a title

1. Select or create a title workspace.
2. Verify the expected XboxXBERecomp project structure, SDK revision, build preset, and required host tools.
3. Ask the user to locate the required game files. Never download or include game content.
4. Initialize the selected Windows compatibility runner and title-specific prefix.
5. Invoke the project's documented Windows build pipeline with controlled paths and environment variables.
6. Capture logs, exit status, and produced player executable. Keep build output in the title workspace.
7. Launch the produced player in that same title environment.

### Run an existing player

1. Register a Windows player executable and its companion files.
2. Select a Wine or Proton runner and create or reuse a title-specific prefix.
3. Apply title launch options and documented environment overrides.
4. Launch the executable, preserve its exit status, and collect logs for support.

The MVP should support both workflows through one command-line interface and one shared title manifest.

## Proposed components

### Sidecar CLI and supervisor

A small Linux-native executable or script handles configuration, path validation, runner discovery, prefix creation, process supervision, log collection, updates, and cleanup. It should not emulate Windows APIs or inspect/modify generated game code.

Potential commands:

```text
sidecar init <title-dir>
sidecar build <title>
sidecar run <title>
sidecar runners
sidecar doctor <title>
```

Command names are provisional. Keep the initial interface scriptable and make all operations observable in logs.

### Title manifest

Store declarative project-specific settings in a versioned manifest, for example `sidecar.toml`:

- title name and workspace paths
- XboxXBERecomp source/revision and project build preset
- expected game image inputs (paths and hashes may be recorded locally)
- Windows player executable and working directory
- runner choice and pinned runner version
- prefix location and persistent user-data/save paths
- launch arguments, selected environment overrides, and display options
- optional known-good compatibility profile and notes

Do not put credentials or proprietary game data in the manifest. Validate paths and reject arbitrary shell fragments; model command arguments as arrays.

### Runner adapter

Define a narrow interface for `discover`, `install-or-select`, `create-prefix`, `run-command`, `diagnostics`, and `version`. Use Proton through `umu-run` as the default because the XboxXBERecomp player uses D3D12 and Proton includes VKD3D-Proton's D3D12-to-Vulkan translation. Keep plain Wine as an explicit fallback. UMU provides Proton's Steam Linux Runtime outside Steam and manages a Proton/runtime cache. Do not call a Proton script directly and assume the Steam Runtime setup is unnecessary. See the [umu-run manual](https://github.com/Open-Wine-Components/umu-launcher/blob/main/docs/umu.1.scd) and [VKD3D-Proton requirements](https://github.com/HansKristian-Work/vkd3d-proton/blob/master/README.md).

Allow user-managed runners initially. The product can later offer downloadable runner bundles if licensing, update security, and runtime dependencies are settled.

### Prefix and data manager

Use one Windows prefix per title and runner version. Keep it under the Sidecar's configurable data root, not inside a transient build directory. Separate:

- runner/runtime files (shareable and replaceable)
- title prefix (Windows registry, DLL overrides, installed prerequisites)
- title workspace/build output
- persistent title data (saves, settings, logs, crash reports)

Expose reset and backup operations. Prefix reset must not delete title assets, build outputs, or saves unless the user selects those separately.

### Build adapter

Wrap the exact XboxXBERecomp Windows build instructions for the selected revision. Prefer invoking documented tools and presets unchanged under the runner. Before automating, verify whether the build path requires Windows-only CMake, MSVC, Clang/LLD, Ghidra, or other tools and how each is distributed. Do not silently substitute Linux-native compilers or alter upstream build behavior.

Keep the build adapter replaceable: XboxXBERecomp's project template and toolchain may evolve. Record the upstream revision and make incompatible revisions fail with a helpful diagnostic.

### Launcher and diagnostics

The supervisor should set a controlled environment, set the correct Windows working directory, pass arguments without shell interpolation, forward signals, preserve process exit codes, and retain stdout/stderr. A `doctor` command should report host distro/kernel/architecture, runner path/version, runtime dependencies, prefix state, free disk space, project revision, and build-tool availability.

## Distribution strategy

The goal is an easy-to-run Linux package, but “single self-contained blob” is a packaging target to validate rather than an assumption. Wine and Proton have different dependency and redistribution models; Proton also commonly relies on Steam Runtime components. Evaluate these forms in order:

1. **MVP:** native Sidecar package plus UMU/Proton; retain system Wine as a selectable fallback.
2. **Portable bundle:** Sidecar plus a supported Wine build and required runtime libraries, subject to license and distribution review.
3. **Proton bundle/adapter:** use `umu-run` with a pinned Proton build and its runtime/container pieces, tested outside Steam on supported distributions.
4. **Single-file convenience:** optional self-extracting archive or AppImage-like launcher that unpacks a versioned runtime into the user's data directory. Keep runtime updates separate from title data and verify downloaded artifacts.

Never claim a runtime is self-contained until a clean-machine test confirms it has no undeclared host dependencies. Do not bundle Microsoft's redistributables or proprietary game files without a clear redistribution right.

The current UMU implementation uses XDG data directories for its Proton/runtime files and exposes `UMU_FOLDERS_PATH` to redirect its managed folders. This is a candidate for a preseeded per-title or shared runtime directory in the future bundle format; the Sidecar exposes that setting in the title manifest. An offline bundle still needs the matching UMU/Proton/Steam Runtime files and a clean-host dependency audit.

## Security and reliability requirements

- Treat project paths, manifest values, XBE-derived filenames, and runner output as untrusted input.
- Avoid shell command strings; pass argument vectors directly.
- Do not run builds as root.
- Keep prefixes private to the user and avoid exposing unrelated host directories when practical.
- Use checksums/signatures for Sidecar-managed runtime downloads and pin versions.
- Do not delete or reset prefixes automatically after a failed build.
- Make backups and destructive cleanup explicit.
- Report compatibility limitations rather than claiming perfect parity.

## Milestones

### 0. Feasibility spike

- Choose one representative title project and the upstream XboxXBERecomp revision.
- Follow upstream instructions manually on Linux with Wine and separately test the resulting player.
- Record every Windows tool, runtime dependency, environment variable, path assumption, and failure.
- Compare Wine and Proton viability for both build and run. Determine whether Proton can execute the build toolchain outside Steam with acceptable complexity.
- Define the first supported distro and a measurable “works” checklist.

#### Source review: upstream Windows build flow

The current upstream `templates/game/build.bat` does not only compile code. It:

1. Requires `assets/<GAME_XBE>`.
2. Finds Visual Studio through `vswhere.exe`, enters its developer environment with `VsDevCmd.bat`, and checks for Clang, CMake, Ninja, and Git. If C++ Clang/CMake components are missing, it offers to launch the Visual Studio Installer elevated.
3. Configures the Windows-only `release` CMake preset.
4. Builds `xbe_symbols`, which detects XDK exports from the XBE and writes `config/game.toml` using the matching SDK signatures.
5. Builds the actual Windows player and generated guest-code partitions.

The template's CMake logic also stages Windows `clang.exe` and `lld-link.exe`, title configs, SDK layouts, and generated-code headers into `out/build/release/compiler`. The Windows player uses those files on the player's first launch to recompile guest code from the user's XBE. The player itself links Win32, D3D12, DXGI, XAudio2, and other Windows libraries. Dependencies such as Zydis, toml++, ImGui, and SDL3 are fetched by CMake.

Consequences for Sidecar:

- Running `build.bat` under Wine is not sufficient by itself. The prefix needs the Visual Studio Build Tools discovery/layout and a Windows-target compiler/linker plus Windows SDK libraries. The installer elevation flow is not a sound unattended bootstrap path under Wine.
- The upstream `release` preset is conditioned on CMake detecting a Windows host. A Linux-side build driver cannot simply invoke that preset as-is.
- Build and run should be separate backends. The run backend can launch an existing Windows player and its compiler payload under Wine/Proton. The build backend must reproduce the batch stages and provide a compatible Windows-target toolchain.
- Do not silently use a Linux-native player build: that would change the requested artifact and return to the native-port work this project replaced.

#### Recommended implementation direction

1. Use a user-provided Windows installation/VM as the initial build backend and run the upstream `build.bat` unchanged there. This preserves the expected Visual Studio layout and Windows SDK/toolchain.
2. Place the resulting Windows release files in a Linux title workspace (a shared folder can avoid manual copying), then let Sidecar initialize an isolated Wine prefix and run the Windows player. The title assets remain user-provided.
3. Deliver this Wine run path first, including runner discovery, prefix setup, launch arguments, working directory, diagnostics, and logs. A user with an existing `.exe` should get value without configuring a VM.
4. Consider automating VM build/handoff later (for example, through a guest agent or shared-folder contract). Only pursue Linux-hosted Windows cross-compilation if it materially improves the workflow; it requires a CMake/toolchain overlay and remains unproven.

Primary source references: [upstream `build.bat`](https://github.com/TGP482/XboxXBERecomp/blob/main/templates/game/build.bat), [upstream `CMakePresets.json`](https://github.com/TGP482/XboxXBERecomp/blob/main/templates/game/CMakePresets.json), [upstream `XbeRecomp.cmake`](https://github.com/TGP482/XboxXBERecomp/blob/main/cmake/XbeRecomp.cmake), and [upstream game-template instructions](https://github.com/TGP482/XboxXBERecomp/blob/main/templates/game/README.md).

**Exit criteria:** repeatable manual build and launch on a clean Linux install, or a documented blocker that narrows the supported workflow.

### 1. CLI MVP

- Create a versioned title manifest and validation.
- Implement `runners`, `doctor`, `init`, `setup`, `build`, and `run`.
- Implement Wine runner discovery and per-title prefix management.
- Make `run` work for an existing Windows release before tying it to a Sidecar build.
- Build support documents the Windows VM handoff and validates the resulting files; upstream build execution remains inside Windows for the first milestone.
- Capture logs and preserve exit codes; add backup/reset commands.

**Exit criteria:** a user can prepare the known test title, build it from their own files, and launch it without manually editing Wine prefixes.

### 2. Compatibility and repeatability

- Add clean prefix setup and pinned per-title runner profiles.
- Test cold first-run, rebuild, relaunch, game saves, paths with spaces/non-ASCII, controller input, audio, fullscreen/windowed modes, crash logs, and shutdown.
- Publish a per-title compatibility report and troubleshooting guide.

**Exit criteria:** a documented reproducible result across at least two clean Linux installations in the supported distro family.

### 3. Proton adapter

- Define and implement Proton discovery and invocation with its required runtime environment.
- Test standalone use outside Steam and Steam-managed use, if both are intended.
- Pin versions and document Steam Runtime/pressure-vessel dependencies.

**Exit criteria:** same build/run test matrix passes for the supported Proton configuration, or Proton is explicitly marked experimental.

### 4. Portable runtime packaging

- Review component licenses and distribution obligations.
- Build signed/checksummed runtime bundles and an update/rollback path.
- Test from a clean user account with no system Wine/Proton installation.
- Add optional self-extracting or desktop-launcher packaging.

**Exit criteria:** clean-machine runtime dependency audit, install/uninstall/upgrade/rollback checks, and verified separation of runner, prefix, workspace, and saves.

### 5. Broader support and optional UI

- Add other distribution families, runner versions, title profiles, and a GUI only where repeated CLI workflows justify it.
- Maintain a compatibility database tied to precise game image hashes, upstream tool revisions, runner versions, and host environments.

## Initial decisions to record

- Repository name: `XboxXBERecomp-Linux-Sidecar` (provisional).
- Product scope: companion toolkit; upstream Windows XboxXBERecomp remains authoritative.
- First implementation: CLI, Wine baseline, one title, one distro family.
- Proton and bundled runtime: planned after feasibility and packaging review.
- Game files and generated title code: supplied/built locally by the user; excluded from this repository and releases.
- License: choose after confirming intended dependencies and contribution model.

## Risks and open questions

- Whether the full Windows build pipeline, especially reverse-engineering and compiler tools, runs reliably under Wine/Proton.
- Whether generated Windows players have title-specific runtime prerequisites or driver behavior that varies across Wine/Proton versions.
- Whether Proton can be distributed and supported as a standalone runtime without depending on Steam installation details.
- How much of the Windows build toolchain can be redistributed versus acquired by users.
- What the intended first title, upstream revision, Linux distro family, and packaging format are.
