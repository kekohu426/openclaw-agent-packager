---
name: openclaw-agent-packager
description: Package one or more OpenClaw agents from an existing source instance into a customer-installable delivery bundle with sanitized configs, workspace files, README, and Windows installer scripts. Use when asked to package an agent, migrate agents between OpenClaw instances, build a delivery bundle, generate INSTALL.ps1, create customer handoff materials, or support single-agent or multi-agent deployment.
---

# OpenClaw Agent Packager

Use this skill to turn one or more working agents from a source OpenClaw instance into a reusable delivery bundle.

## Quick Start

1. Identify the source OpenClaw state directory and workspace root.
2. Choose one or more agent ids.
3. Run `scripts/build_package.py`.
4. Review the generated `README.md`, `INSTALL.ps1`, and `customer-settings.template.json`.
5. Test the package in a separate target OpenClaw instance before distributing it.

## When To Use

- Package a single agent such as `sysmon` for customer delivery.
- Package several cooperating agents into one bundle.
- Migrate agents from one OpenClaw instance to another.
- Generate a Windows-first installation bundle with automatic config merge.
- Create a sanitized customer package while keeping secrets out of distributed files.

## Workflow

### 1. Gather source inputs

Collect:

- Source OpenClaw state directory, usually something like `C:\Users\<user>\.openclaw`
- Workspace root, usually something like `C:\Users\<user>\clawd`
- One or more agent ids
- Target OpenClaw data path example for the customer

### 2. Build the package

Run:

```powershell
python scripts/build_package.py \
  --source-openclaw "C:\Users\ke'ko\.openclaw" \
  --workspace-root "C:\Users\ke'ko\clawd" \
  --agents sysmon lead-ecom \
  --output-dir "C:\Users\ke'ko\Desktop" \
  --package-name "openclaw-delivery-suite" \
  --target-openclaw "D:\openclaw\latest\data\.openclaw"
```

### 3. Validate the output

Check that the bundle contains:

- `README.md`
- `INSTALL.ps1`
- `CHECK.ps1`
- `manifest.json`
- `customer-settings.template.json`
- `workspaces/<agent-id>/...`
- `configs/openclaw.fragment.json`
- `configs/models.sanitized.json`
- `configs/auth-profiles.sanitized.json`

### 4. Test on a target instance

Always test on a different OpenClaw instance from the source.

Verify:

- The target instance still starts.
- The merged config is schema-compatible.
- The migrated agents appear in the target config.
- Channel bindings work.
- Feishu pairing can complete.

## Safety Rules

- Do not blindly copy the whole source `openclaw.json`.
- Merge only compatible fields for the target instance.
- Prefer `agents.list`, `channels.*.accounts`, and `bindings`.
- Avoid migrating unknown top-level fields from older source configs.
- Exclude runtime artifacts like `sessions`, logs, caches, cookies, and screenshots.
- Do not exclude executable workspace content such as `scripts/`, `tests/`, `knowledge/`, `agent-config.json`, `README.md`, or operational `memory/` config files.
- Sanitize API keys in customer-facing config templates.
- Keep raw secret-bearing files only for local testing, never for external distribution.

## Known Migration Failure Modes

- Packaging only identity files while omitting executable workspace files like `scripts/` makes the target agent reply but fail to actually run tasks.
- Omitting operational `memory/` files like `memory/users.json` or `memory/*/accounts.txt` breaks agents that treat memory as live config.
- Migrating channel account config without restarting the gateway leaves the target instance on stale runtime config.
- If the target reports `gateway token mismatch`, the service install is out of sync with the active config and may need `openclaw gateway install --force` from the intended state directory.
- Agent-local `agent-config.json` can drift from global `openclaw.json`; packaged bundles should keep them aligned.

## Multi-Agent Packaging Guidance

When packaging multiple agents:

- Build one shared bundle, not many unrelated zips.
- Deduplicate shared model providers and auth profiles.
- Keep one combined `manifest.json`.
- Generate one combined installer.
- Keep per-agent workspaces under `workspaces/<agent-id>/`.

## Notes On Feishu

- A Feishu bot can be connected yet still reject messages if the sender is not paired.
- If the target instance replies with `access not configured`, run pairing approval on the target instance.
- Pairing success is separate from channel startup success.

## Resources

### `scripts/build_package.py`

Creates a delivery bundle for one or more agents.

### `references/package-layout.md`

Describes the generated bundle structure and merge strategy.
