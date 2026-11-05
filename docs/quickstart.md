# Run a Windows release on Linux

The first Sidecar workflow starts with a Windows release that already runs under XboxXBERecomp. Build it in a Windows installation or VM using the project's documented `build.bat` and `release.bat` flow. The Sidecar does not install or bundle Windows or Visual Studio.

Copy or share the release folder onto Linux. Keep the Windows player, its `compiler` directory, and the `assets` directory together. Place the game files you legally own in `assets` as required by that title's instructions.

Install the Sidecar in a Python 3.11+ environment and register the release folder:

```sh
python3 -m pip install .
xbe-sidecar init /path/to/title-release --name "Title" --exe Title.exe --runner wine
xbe-sidecar doctor /path/to/title-release
xbe-sidecar setup /path/to/title-release
xbe-sidecar run /path/to/title-release
```

To use Proton, install `umu-launcher` and initialize with `--runner proton`. Sidecar uses `umu-run` so Proton can run outside Steam with the Steam Linux Runtime. If `umu-run` is not on `PATH`, set `UMU_RUN=/path/to/umu-run` or use `--runner-executable`. To pin a Proton build, add `--proton-path /path/to/Proton` (or a supported Proton codename). Otherwise umu selects its default Proton build and may download it and the required runtime on first launch.

Each title gets a separate prefix in `.sidecar/prefix` and timestamped output logs in `.sidecar/logs`. The prefix can be deleted to reset that title's Windows state; this does not delete the game files or executable. Back up saves/settings stored inside the prefix before resetting it.

This workflow runs the Windows release through Wine/Proton. It is not a native Linux game executable. `umu-run` manages its Proton/runtime cache under the user's data directory. A portable bundle containing pinned runner and runtime files is planned separately and must be verified for redistribution rights and host-library requirements.

Proton adapter details follow the [umu-run manual](https://github.com/Open-Wine-Components/umu-launcher/blob/main/docs/umu.1.scd), including its `WINEPREFIX`, `PROTONPATH`, and prefix-initialization behavior.
