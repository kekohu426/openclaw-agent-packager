#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

ROOT_FILES = {
    '.clawignore',
    'AGENTS.md',
    'HEARTBEAT.md',
    'IDENTITY.md',
    'MEMORY.md',
    'SOUL.md',
    'TOOLS.md',
    'USER.md',
}
DIRS_ALWAYS = {'config', 'discoveries', 'data'}
SKIP_DIR_NAMES = {'sessions', '.git', '.openclaw', 'node_modules', '__pycache__', '.next', 'dist', 'build'}
SKIP_FILE_NAMES = {'cookies.youtube.txt'}
SKIP_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.log', '.pyc', '.zip'}
SKILL_TEXT_FILES = {
    'SKILL.md',
    'README.md',
    'AGENTS.md',
    'SOUL.md',
    'TOOLS.md',
    'USER.md',
    'HEARTBEAT.md',
    'IDENTITY.md',
    'MEMORY.md',
}
SKILL_ALLOWED_EXTS = {'.json', '.yaml', '.yml', '.md', '.txt', '.ps1', '.sh', '.py', '.mjs', '.js', '.ts'}
MODEL_SECRET_KEYS = {'apiKey', 'api_key', 'key'}
AUTH_SECRET_KEYS = {'key', 'apiKey', 'api_key', 'token'}
CHANNEL_SECRET_KEYS = {
    'appId',
    'appSecret',
    'encryptKey',
    'verificationToken',
    'botToken',
    'token',
    'secret',
    'webhookSecret',
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def mask_value(key: str) -> str:
    return f'REPLACE_WITH_{key.upper()}'


def sanitize_secret_object(obj: Any, secret_keys: set[str]) -> Any:
    if isinstance(obj, dict):
        data = deepcopy(obj)
        for key, value in list(data.items()):
            if key in secret_keys and value not in (None, ''):
                data[key] = mask_value(key)
            else:
                data[key] = sanitize_secret_object(value, secret_keys)
        return data
    if isinstance(obj, list):
        return [sanitize_secret_object(item, secret_keys) for item in obj]
    return obj


def collect_secret_values(obj: Any, secret_keys: set[str]) -> dict[str, Any]:
    if not isinstance(obj, dict):
        return {}
    found: dict[str, Any] = {}
    for key, value in obj.items():
        if key in secret_keys and value not in (None, ''):
            found[key] = value
    return found


def sanitize_models(models: dict[str, Any]) -> dict[str, Any]:
    return sanitize_secret_object(models, MODEL_SECRET_KEYS)


def sanitize_auth(auth: dict[str, Any]) -> dict[str, Any]:
    return sanitize_secret_object(auth, AUTH_SECRET_KEYS)


def should_skip_file(path: Path) -> bool:
    return path.name in SKIP_FILE_NAMES or path.suffix.lower() in SKIP_SUFFIXES


def copy_tree_slim(source: Path, target: Path) -> int:
    count = 0
    for path in source.rglob('*'):
        rel = path.relative_to(source)
        if any(part in SKIP_DIR_NAMES for part in rel.parts):
            continue
        if path.is_file() and not should_skip_file(path):
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            count += 1
    return count


def copy_skills_slim(source: Path, target: Path) -> int:
    count = 0
    if not source.exists():
        return count
    for skill_dir in source.iterdir():
        if not skill_dir.is_dir() or skill_dir.name in SKIP_DIR_NAMES:
            continue
        for path in skill_dir.rglob('*'):
            rel = path.relative_to(source)
            if any(part in SKIP_DIR_NAMES for part in rel.parts):
                continue
            if path.is_dir():
                continue
            if path.name in SKILL_TEXT_FILES or path.suffix.lower() in SKILL_ALLOWED_EXTS:
                if should_skip_file(path):
                    continue
                dest = target / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
                count += 1
    return count


def copy_workspace(source: Path, target: Path, include_memory: bool) -> list[str]:
    copied: list[str] = []
    if not source.exists():
        return copied

    for name in ROOT_FILES:
        path = source / name
        if path.exists() and path.is_file():
            dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied.append(name)

    for dirname in sorted(DIRS_ALWAYS):
        path = source / dirname
        if path.exists() and path.is_dir():
            file_count = copy_tree_slim(path, target / dirname)
            copied.append(f'{dirname}/ ({file_count} files)')

    if include_memory:
        path = source / 'memory'
        if path.exists() and path.is_dir():
            file_count = copy_tree_slim(path, target / 'memory')
            copied.append(f'memory/ ({file_count} files)')

    skills_path = source / 'skills'
    if skills_path.exists() and skills_path.is_dir():
        file_count = copy_skills_slim(skills_path, target / 'skills')
        copied.append(f'skills/ ({file_count} files)')

    return copied


def make_install_ps1(agent_ids: list[str], external_mode: bool) -> str:
    agent_list = ', '.join([f"'{agent_id}'" for agent_id in agent_ids])
    external_literal = '$true' if external_mode else '$false'
    template = r'''param(
  [string]$SettingsPath = (Join-Path $PSScriptRoot 'customer-settings.json'),
  [switch]$RestartGateway
)

$ErrorActionPreference = 'Stop'

function Read-Json([string]$Path) {
  Get-Content -Raw -Encoding UTF8 $Path | ConvertFrom-Json
}

function Write-Json([string]$Path, $Object) {
  $json = $Object | ConvertTo-Json -Depth 100
  [System.IO.File]::WriteAllText($Path, $json, [System.Text.UTF8Encoding]::new($false))
}

function Ensure-Property($Object, [string]$PropertyName, $DefaultValue) {
  if (-not $Object.PSObject.Properties[$PropertyName]) {
    $Object | Add-Member -NotePropertyName $PropertyName -NotePropertyValue $DefaultValue
  }
  return $Object.$PropertyName
}

function Set-DynamicProperty($Object, [string]$PropertyName, $Value) {
  if ($Object.PSObject.Properties[$PropertyName]) {
    $Object.$PropertyName = $Value
  } else {
    $Object | Add-Member -NotePropertyName $PropertyName -NotePropertyValue $Value
  }
}

function Merge-SecretValues($Target, $Overrides) {
  if ($null -eq $Target -or $null -eq $Overrides) {
    return $Target
  }
  foreach ($prop in $Overrides.PSObject.Properties) {
    if ($null -eq $prop.Value -or $prop.Value -eq '') {
      continue
    }
    Set-DynamicProperty $Target $prop.Name $prop.Value
  }
  return $Target
}

function Test-PlaceholderValue([string]$Value) {
  return $Value -like 'REPLACE_WITH_*'
}

function Find-OpenClawCmd([string]$TargetOpenClaw) {
  $root = Split-Path (Split-Path $TargetOpenClaw -Parent) -Parent
  if (-not $root) {
    return $null
  }
  $cmdPath = Join-Path $root 'app\openclaw.cmd'
  if (Test-Path $cmdPath) {
    return $cmdPath
  }
  return $null
}

if (!(Test-Path $SettingsPath)) {
  Copy-Item (Join-Path $PSScriptRoot 'customer-settings.template.json') $SettingsPath -Force
  Write-Host 'Generated customer-settings.json. Review it and rerun INSTALL.ps1.'
  exit 1
}

$settings = Read-Json $SettingsPath
$targetOpenClaw = $settings.targetOpenClaw
$targetConfigPath = Join-Path $targetOpenClaw 'openclaw.json'
$externalMode = __EXTERNAL_MODE__

if (!(Test-Path $targetOpenClaw)) { throw "Target OpenClaw directory missing: $targetOpenClaw" }
if (!(Test-Path $targetConfigPath)) { throw "Target config missing: $targetConfigPath" }

$fragment = Read-Json (Join-Path $PSScriptRoot 'configs\openclaw.fragment.json')
$target = Read-Json $targetConfigPath
$backupPath = "$targetConfigPath.delivery-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item $targetConfigPath $backupPath -Force

$targetAgents = Ensure-Property $target 'agents' ([pscustomobject]@{ list = @() })
$targetChannels = Ensure-Property $target 'channels' ([pscustomobject]@{})
$null = Ensure-Property $target 'bindings' @()

$modelsPath = Join-Path $PSScriptRoot 'configs\models.sanitized.json'
$authPath = Join-Path $PSScriptRoot 'configs\auth-profiles.sanitized.json'

foreach($agentId in @(__AGENT_LIST__)) {
  $agentConfig = $fragment.agents.list | Where-Object { $_.id -eq $agentId } | Select-Object -First 1
  if ($null -eq $agentConfig) { continue }

  $workspaceTarget = $settings.agents.$agentId.workspace
  if ([string]::IsNullOrWhiteSpace($workspaceTarget)) {
    throw "Missing workspace path in settings for agent: $agentId"
  }

  $agentConfig.workspace = $workspaceTarget
  $targetAgents.list = @($targetAgents.list | Where-Object { $_.id -ne $agentId }) + @($agentConfig)

  $workspacePackageDir = Join-Path $PSScriptRoot ("workspaces\" + $agentId)
  if (Test-Path $workspacePackageDir) {
    New-Item -ItemType Directory -Force $workspaceTarget | Out-Null
    Copy-Item (Join-Path $workspacePackageDir '*') $workspaceTarget -Recurse -Force
  }

  $agentDir = Join-Path $targetOpenClaw ("agents\" + $agentId + "\agent")
  New-Item -ItemType Directory -Force $agentDir | Out-Null

  if (Test-Path $modelsPath) {
    $models = Read-Json $modelsPath
    foreach ($providerProp in $settings.models.providerKeys.PSObject.Properties) {
      if ($models.providers.PSObject.Properties[$providerProp.Name]) {
        foreach ($keyName in @('apiKey', 'api_key', 'key')) {
          if ($models.providers.$($providerProp.Name).PSObject.Properties[$keyName] -and -not (Test-PlaceholderValue ([string]$providerProp.Value))) {
            $models.providers.$($providerProp.Name).$keyName = $providerProp.Value
          }
        }
      }
    }
    Write-Json (Join-Path $agentDir 'models.json') $models
  }

  if (Test-Path $authPath) {
    $auth = Read-Json $authPath
    foreach ($profileProp in $settings.authProfiles.profileKeys.PSObject.Properties) {
      if ($auth.profiles.PSObject.Properties[$profileProp.Name]) {
        foreach ($keyName in @('key', 'apiKey', 'api_key', 'token')) {
          if ($auth.profiles.$($profileProp.Name).PSObject.Properties[$keyName] -and -not (Test-PlaceholderValue ([string]$profileProp.Value))) {
            $auth.profiles.$($profileProp.Name).$keyName = $profileProp.Value
          }
        }
      }
    }
    Write-Json (Join-Path $agentDir 'auth-profiles.json') $auth
  }

  foreach ($channelName in @('feishu', 'telegram')) {
    if (-not $fragment.channels.PSObject.Properties[$channelName]) {
      continue
    }
    $channelFragment = $fragment.channels.$channelName
    if (-not $channelFragment.accounts.PSObject.Properties[$agentId]) {
      continue
    }

    $channelTarget = Ensure-Property $targetChannels $channelName ([pscustomobject]@{ accounts = [pscustomobject]@{} })
    $channelAccounts = Ensure-Property $channelTarget 'accounts' ([pscustomobject]@{})
    $channelAccount = $channelFragment.accounts.$agentId

    $channelSettings = $null
    if ($settings.agents.$agentId.channels.PSObject.Properties[$channelName]) {
      $channelSettings = $settings.agents.$agentId.channels.$channelName
    }

    if ($null -ne $channelSettings -and $channelSettings.PSObject.Properties['enabled']) {
      $channelAccount.enabled = [bool]$channelSettings.enabled
    }

    if ($externalMode -and $null -ne $channelSettings -and $channelSettings.PSObject.Properties['accountSecrets']) {
      $channelAccount = Merge-SecretValues $channelAccount $channelSettings.accountSecrets
    }

    Set-DynamicProperty $channelAccounts $agentId $channelAccount
  }

  $target.bindings = @($target.bindings | Where-Object { $_.agentId -ne $agentId -and -not ($_.match -and $_.match.accountId -eq $agentId) }) + @($fragment.bindings | Where-Object { $_.agentId -eq $agentId })
}

Write-Json $targetConfigPath $target
Write-Host "Install complete. Config backup: $backupPath"

if ($RestartGateway) {
  $openClawCmd = Find-OpenClawCmd $targetOpenClaw
  if ($openClawCmd) {
    & $openClawCmd gateway restart --json | Out-Host
  } else {
    Write-Host 'OpenClaw executable not found automatically. Restart the gateway manually.'
  }
}
'''
    return template.replace('__AGENT_LIST__', agent_list).replace('__EXTERNAL_MODE__', external_literal)


def make_check_ps1() -> str:
    return """$ErrorActionPreference = 'Stop'
if (!(Test-Path (Join-Path $PSScriptRoot 'configs\\openclaw.fragment.json'))) { throw 'Missing configs/openclaw.fragment.json' }
if (!(Test-Path (Join-Path $PSScriptRoot 'customer-settings.template.json'))) { throw 'Missing customer-settings.template.json' }
if (!(Test-Path (Join-Path $PSScriptRoot 'INSTALL.ps1'))) { throw 'Missing INSTALL.ps1' }
Write-Host 'Package structure check passed.'
"""


def build_settings_template(
    agent_ids: list[str],
    target_openclaw: str,
    model_providers: dict[str, Any],
    auth_profiles: dict[str, Any],
    channel_secrets_by_agent: dict[str, dict[str, dict[str, Any]]],
    external_mode: bool,
) -> dict[str, Any]:
    agents: dict[str, Any] = {}
    workspace_parent = str(Path(target_openclaw).parent / 'workspaces')
    for agent_id in agent_ids:
        channels: dict[str, Any] = {
            'feishu': {'enabled': True},
            'telegram': {'enabled': False},
        }
        if external_mode:
            for channel_name, secrets in channel_secrets_by_agent.get(agent_id, {}).items():
                channels.setdefault(channel_name, {'enabled': True})
                channels[channel_name]['accountSecrets'] = {
                    key: mask_value(key) for key in sorted(secrets.keys())
                }

        agents[agent_id] = {
            'workspace': str(Path(workspace_parent) / agent_id),
            'channels': channels,
        }

    provider_keys = {
        provider_name: 'REPLACE_WITH_API_KEY'
        for provider_name in sorted(model_providers.keys())
        if isinstance(model_providers.get(provider_name), dict)
        and any(secret_key in model_providers[provider_name] for secret_key in MODEL_SECRET_KEYS)
    }
    profile_keys = {
        profile_name: 'REPLACE_WITH_API_KEY'
        for profile_name in sorted(auth_profiles.keys())
        if isinstance(auth_profiles.get(profile_name), dict)
        and any(secret_key in auth_profiles[profile_name] for secret_key in AUTH_SECRET_KEYS)
    }

    return {
        'targetOpenClaw': target_openclaw,
        'agents': agents,
        'models': {'providerKeys': provider_keys},
        'authProfiles': {'profileKeys': profile_keys},
        'packageMode': 'external' if external_mode else 'internal-migration',
    }


def build_readme(package_name: str, external_mode: bool) -> str:
    mode_text = (
        'Mode: external/customer-safe package. Channel account secrets are removed and must be filled in customer-settings.json.\n'
        if external_mode
        else 'Mode: internal migration package. Existing channel account secrets are kept for fast install/testing.\n'
    )
    return (
        f'# {package_name}\n\n'
        'Slim package by default: excludes memory, sessions, node_modules, caches, logs, and bulky outputs.\n'
        'Add `--include-memory` only when memory transfer is required.\n\n'
        f'{mode_text}\n'
        'Quick steps:\n'
        '1. Unzip the bundle anywhere.\n'
        '2. Run `powershell -ExecutionPolicy Bypass -File .\\CHECK.ps1`.\n'
        '3. Copy `customer-settings.template.json` to `customer-settings.json` if you need to adjust defaults.\n'
        '4. Run `powershell -ExecutionPolicy Bypass -File .\\INSTALL.ps1 -RestartGateway`.\n'
        '5. If Feishu replies with `access not configured`, complete pairing approval on the target OpenClaw instance.\n\n'
        'The installer only merges:\n'
        '- `agents.list` entries for packaged agents\n'
        '- `bindings` for packaged agents\n'
        '- `channels.<name>.accounts.<agentId>` for packaged agents\n'
        '- packaged workspace files into the configured workspace path\n'
        '- packaged `models.json` and optional `auth-profiles.json`\n'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description='Build an OpenClaw agent delivery package')
    parser.add_argument('--source-openclaw', required=True)
    parser.add_argument('--workspace-root', required=True)
    parser.add_argument('--agents', nargs='+', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--package-name', required=True)
    parser.add_argument('--target-openclaw', required=True)
    parser.add_argument('--include-memory', action='store_true')
    parser.add_argument('--external', action='store_true', help='Strip channel secrets for customer-safe distribution')
    parser.add_argument('--zip', action='store_true')
    args = parser.parse_args()

    source_openclaw = Path(args.source_openclaw)
    workspace_root = Path(args.workspace_root)
    output_root = Path(args.output_dir) / args.package_name

    if output_root.exists():
        shutil.rmtree(output_root)
    (output_root / 'configs').mkdir(parents=True)
    (output_root / 'workspaces').mkdir(parents=True)

    openclaw = read_json(source_openclaw / 'openclaw.json')
    merged_fragment: dict[str, Any] = {'agents': {'list': []}, 'bindings': [], 'channels': {}}
    merged_models: dict[str, Any] = {'providers': {}}
    merged_auth: dict[str, Any] = {'version': 1, 'profiles': {}}
    channel_secrets_by_agent: dict[str, dict[str, dict[str, Any]]] = {}
    manifest: dict[str, Any] = {
        'package_name': args.package_name,
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'agents': args.agents,
        'source_openclaw': str(source_openclaw),
        'workspace_root': str(workspace_root),
        'target_openclaw_example': args.target_openclaw,
        'include_memory': args.include_memory,
        'external': args.external,
    }

    for agent_id in args.agents:
        agent = next((item for item in openclaw.get('agents', {}).get('list', []) if item.get('id') == agent_id), None)
        if not agent:
            raise SystemExit(f'Agent not found: {agent_id}')
        agent = deepcopy(agent)
        agent['workspace'] = str(Path(args.target_openclaw).parent / 'workspaces' / agent_id)
        merged_fragment['agents']['list'].append(agent)

        for binding in openclaw.get('bindings', []):
            if binding.get('agentId') == agent_id:
                merged_fragment['bindings'].append(deepcopy(binding))

        channels = openclaw.get('channels', {})
        for channel_name in ('feishu', 'telegram'):
            channel = channels.get(channel_name)
            if not isinstance(channel, dict):
                continue
            accounts = channel.get('accounts', {})
            if agent_id not in accounts:
                continue

            account = deepcopy(accounts[agent_id])
            if args.external:
                secret_values = collect_secret_values(account, CHANNEL_SECRET_KEYS)
                if secret_values:
                    channel_secrets_by_agent.setdefault(agent_id, {})[channel_name] = secret_values
                account = sanitize_secret_object(account, CHANNEL_SECRET_KEYS)
            merged_fragment.setdefault('channels', {}).setdefault(channel_name, {}).setdefault('accounts', {})[agent_id] = account

        source_agent_dir = source_openclaw / 'agents' / agent_id / 'agent'
        if source_agent_dir.exists():
            models_path = source_agent_dir / 'models.json'
            if models_path.exists():
                models = read_json(models_path)
                for provider_name, provider_cfg in models.get('providers', {}).items():
                    merged_models['providers'][provider_name] = deepcopy(provider_cfg)
            auth_path = source_agent_dir / 'auth-profiles.json'
            if auth_path.exists():
                auth = read_json(auth_path)
                for profile_name, profile_cfg in auth.get('profiles', {}).items():
                    merged_auth['profiles'][profile_name] = deepcopy(profile_cfg)

        source_workspace = workspace_root / agent_id
        copied = copy_workspace(source_workspace, output_root / 'workspaces' / agent_id, args.include_memory)
        manifest.setdefault('workspace_files', {})[agent_id] = copied
        if not source_workspace.exists():
            manifest.setdefault('warnings', []).append(
                f"Workspace not found for {agent_id}: {source_workspace}"
            )

    write_json(output_root / 'configs' / 'openclaw.fragment.json', merged_fragment)
    write_json(output_root / 'configs' / 'models.sanitized.json', sanitize_models(merged_models))
    if merged_auth.get('profiles'):
        write_json(output_root / 'configs' / 'auth-profiles.sanitized.json', sanitize_auth(merged_auth))
    write_json(output_root / 'manifest.json', manifest)
    write_json(
        output_root / 'customer-settings.template.json',
        build_settings_template(
            args.agents,
            args.target_openclaw,
            merged_models.get('providers', {}),
            merged_auth.get('profiles', {}),
            channel_secrets_by_agent,
            args.external,
        ),
    )

    (output_root / 'INSTALL.ps1').write_text(make_install_ps1(args.agents, args.external), encoding='utf-8')
    (output_root / 'CHECK.ps1').write_text(make_check_ps1(), encoding='utf-8')
    (output_root / 'README.md').write_text(build_readme(args.package_name, args.external), encoding='utf-8')

    if args.zip:
        zip_path = Path(args.output_dir) / f'{args.package_name}.zip'
        if zip_path.exists():
            zip_path.unlink()
        with ZipFile(zip_path, 'w', ZIP_DEFLATED) as archive:
            for path in output_root.rglob('*'):
                archive.write(path, path.relative_to(output_root.parent))
        print(zip_path)
    else:
        print(output_root)


if __name__ == '__main__':
    main()
