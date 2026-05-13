# Agentic House Skills

A collection of self-contained Claude skills modeled after the structure of `anthropics/skills`.

This repository is a pure skills repository. It is not a Claude Code plugin marketplace package.

## Layout

```text
skills/<skill-name>/
├── SKILL.md
├── README.md
├── reference.md
├── bin/
└── config-sample/
```

Only `SKILL.md` is required. Other files are included when the skill needs human setup docs, longer references, helper scripts, or sample config.

## Skills

| Skill | Purpose |
| --- | --- |
| `jenkins-skill` | Trigger, monitor, and diagnose Jenkins builds using repository context and Jenkins parameter metadata. |
| `kibana-log` | Load Kibana index context and generate Discover links for application log investigation. |

## Use a Skill

Copy the skill directory you need:

```bash
cp -R skills/<skill-name> /path/to/your/skills/
```

Then load it using the skill mechanism supported by your Claude environment.

## Create a Skill

Start from the template:

```bash
cp -R template skills/new-skill
```

Update:
- `skills/new-skill/SKILL.md`
- optional `README.md`
- optional `reference.md`
- optional helper scripts under `bin/`
- optional sample config under `config-sample/`

## Package Convention

See `spec/SKILL.md`.
