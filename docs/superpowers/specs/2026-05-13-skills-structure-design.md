# Skills Repository Structure Design

## Goal

Convert this repository from a Claude Code plugin marketplace layout into a pure skills repository modeled after `anthropics/skills`.

## Scope

In scope:
- Move skill packages to root-level `skills/`.
- Move each skill's docs, helper scripts, and sample config under its own skill directory.
- Add a root-level `template/` for new skill packages.
- Add a root-level `spec/` summary for this repository's skill package convention.
- Rewrite root `README.md` as a skills catalog and usage guide.
- Remove Claude Code plugin marketplace packaging files.

Out of scope:
- Keeping Claude Code plugin marketplace compatibility.
- Adding or running tests.
- Changing helper behavior.
- Refactoring skill internals beyond path updates caused by the move.

## Target Layout

```text
.
├── README.md
├── LICENSE
├── spec/
│   └── SKILL.md
├── template/
│   ├── SKILL.md
│   ├── bin/.gitkeep
│   └── config-sample/.gitkeep
└── skills/
    ├── jenkins-skill/
    │   ├── SKILL.md
    │   ├── reference.md
    │   ├── README.md
    │   ├── bin/jenkins-skill
    │   └── config-sample/index.json
    └── kibana-log/
        ├── SKILL.md
        ├── README.md
        ├── bin/load_kibana_context.py
        └── config-sample/*.json
```

## Migration Rules

- `plugins/<name>/skills/<name>/SKILL.md` → `skills/<name>/SKILL.md`
- `plugins/<name>/skills/<name>/reference.md` → `skills/<name>/reference.md`
- `plugins/<name>/bin/*` → `skills/<name>/bin/*`
- `plugins/<name>/config-sample/*` → `skills/<name>/config-sample/*`
- `plugins/<name>/README.md` → `skills/<name>/README.md`

Delete after migration:
- `plugins/`
- `.claude-plugin/`
- `plugins/*/.claude-plugin/`
- `plugins/*/package.json`

## Skill Package Convention

Each skill package is self-contained:

```text
skills/<skill-name>/
├── SKILL.md
├── README.md
├── reference.md          # optional
├── bin/                  # optional helper scripts
└── config-sample/        # optional sample config
```

`SKILL.md` must contain YAML frontmatter with:
- `name`
- `description`

Supporting files stay inside the same skill directory so a user can copy one folder and get the complete skill.

## README Design

Root `README.md` becomes a catalog:
- purpose of the repository
- target layout
- available skills table
- how to use a skill by copying `skills/<name>`
- how to create a new skill from `template/`
- note that this repository is no longer a Claude Code plugin marketplace package

## Verification Without Tests

User requested not to test. Verification should use structural checks only:
- `find skills -maxdepth 3 -type f | sort`
- `find template spec -maxdepth 3 -type f | sort`
- `git status --short`
- manual inspection of moved paths and README references

No test commands should be run.
