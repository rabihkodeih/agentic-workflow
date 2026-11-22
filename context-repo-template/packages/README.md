Software packages and libraries developed inside this workspace, one folder per package: `packages/<name>/`.

- Self-contained: own manifest (`pyproject.toml`, `package.json`, `Cargo.toml`, ...), own `README.md`, own tests. Run its tools from its folder; no imports across packages except through the manifest.
- Register each package in `AGENTS.md` "Code" with its unit-test command.
- Code changes follow `dev-workflow.md`; worktrees are of the workspace repo (`<parent>/<workspace>-worktrees/<branch>`).
- Not copied into cloned workspaces. A package that several workspaces need, or that a team will share, graduates to its own repo next to the workspace (`git subtree split -P packages/<name> -b <name>` keeps its history), and its `AGENTS.md` row moves to "Outside".
