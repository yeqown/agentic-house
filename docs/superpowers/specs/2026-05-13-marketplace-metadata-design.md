# Marketplace Metadata Design

## Purpose

Restore Claude Code marketplace compatibility while keeping the repository's flat skills catalog structure.

## Current State

The repository currently stores skills at the top level under `skills/<skill-name>/`. This matches the skill package convention where each skill directory is self-contained and copyable. The repository no longer contains Claude Code plugin marketplace metadata.

## Target Structure

```text
.claude-plugin/
└── marketplace.json

skills/
├── jenkins-skill/
└── kibana-log/

spec/
template/
README.md
```

Skill source directories stay under top-level `skills/`. The marketplace metadata points to those directories instead of moving or duplicating them.

## Marketplace Metadata

Add `.claude-plugin/marketplace.json` using the upstream `anthropics/skills` shape:

- top-level package name and owner metadata
- repository description and version metadata
- `plugins` array
- each plugin includes `name`, `description`, `source`, `strict`, and `skills`

Plugins are grouped by domain:

- `ci-cd-skills` contains `./skills/jenkins-skill`
- `observability-skills` contains `./skills/kibana-log`

Each plugin uses `source: "./"` because skills remain in this repository root, and `strict: false` to match the upstream marketplace examples.

## Documentation Updates

Update `README.md` to describe the repository as a skills catalog with Claude Code marketplace metadata. Remove wording that says the repository is not a plugin marketplace package.

Keep `spec/SKILL.md` focused on the skill package convention. No change is needed unless marketplace metadata references become useful there later.

## Scope

In scope:

- create `.claude-plugin/marketplace.json`
- update root README wording and layout notes
- validate JSON syntax
- verify marketplace paths reference existing skill directories

Out of scope:

- moving skill directories
- duplicating skills under another directory
- changing skill behavior
- changing helper scripts or configuration samples

## Testing

Verification should include:

- JSON parse check for `.claude-plugin/marketplace.json`
- path existence check for every skill path listed in marketplace metadata
- repository search to confirm README no longer claims this is not a marketplace package
