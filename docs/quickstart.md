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

To use Proton, initialize the workspace with `--runner proton`. Set `PROTON=/path/to/proton` if the Proton script is not discoverable in a Steam library. Proton outside Steam is experimental; `doctor` reports when a Steam runtime may be missing.

Each title gets a separate prefix in `.sidecar/prefix` and timestamped output logs in `.sidecar/logs`. The prefix can be deleted to reset that title's Windows state; this does not delete the game files or executable. Back up saves/settings stored inside the prefix before resetting it.

This workflow runs the Windows release through Wine/Proton. It is not a native Linux game executable. A portable bundle containing a pinned Wine/Proton runtime is planned separately and must be verified for redistribution rights and host-library requirements.
