# Package Layout

Generated bundle layout:

```text
<package-name>/
├─ README.md
├─ INSTALL.ps1
├─ CHECK.ps1
├─ manifest.json
├─ customer-settings.template.json
├─ configs/
│  ├─ openclaw.fragment.json
│  ├─ models.sanitized.json
│  └─ auth-profiles.sanitized.json
└─ workspaces/
   ├─ <agent-id-1>/
   └─ <agent-id-2>/
```

Safe merge strategy:

- Add or replace only `agents.list` entries for target agents.
- Add or replace only channel accounts for target agents.
- Add or replace only `bindings` for target agents.
- Avoid copying unknown top-level fields from source config.
