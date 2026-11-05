# XboxXBERecomp Linux Sidecar

A companion toolkit for building and running XboxXBERecomp projects on Linux while keeping the upstream Windows toolchain and Windows game executable intact.

The Sidecar aims to provide a managed Wine or Proton environment, per-title configuration, and repeatable build and launch workflows. It does not reimplement the Xbox runtime or translate the generated game executable into a native Linux binary. Users supply their own legally acquired game files and build their own game code locally.

## Project status

Planning and repository bootstrap. No launcher or sandbox implementation exists yet. See [the architecture plan](docs/architecture-plan.md) for scope, design, and milestones.

## Intended workflows

1. **Build and run:** prepare a title project in the layout XboxXBERecomp expects, run its supported Windows build tools in an isolated Wine or Proton environment, then launch the resulting Windows player in that environment.
2. **Run an existing build:** register an already-built XboxXBERecomp Windows player and launch it with the same managed runtime, prefix, settings, and per-title data directories.

## Principles

- Preserve compatibility with upstream XboxXBERecomp rather than maintaining a hard fork.
- Keep generated game code, game assets, saves, and runtime state out of the toolkit distribution.
- Keep title prefixes and configuration isolated from one another.
- Make the runner selectable and diagnosable: Wine first, with Proton as a supported runner where its runtime requirements can be met cleanly.
- Treat compatibility as something demonstrated per title and runner version; do not promise that every game runs perfectly.
- Start with a command-line MVP. Add a graphical manager only after the build and launch contracts are stable.

## Planned first use

The initial implementation should target one Linux distribution family and one known XboxXBERecomp title project. It should establish the runtime layout, per-title prefix lifecycle, build invocation, launch invocation, logging, and recovery behavior before broadening support.

## License

License selection is pending. The project should not bundle XboxXBERecomp source, Windows binaries, Wine/Proton binaries, or game files until their redistribution terms and the project's own license are documented.
