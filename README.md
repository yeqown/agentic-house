# Agentic House Skills

A collection of self-contained Claude skills with Claude Code marketplace metadata.

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
| `jenkins` | Trigger, monitor, and diagnose Jenkins builds using repository context and Jenkins parameter metadata. |
| `kibana` | Load Kibana index context and generate Discover links for application log investigation. |

## Install or Update Skills

Add this repository as a Claude Code plugin marketplace:

```text
/plugin marketplace add yeqown/agentic-house
```

Then install or update skills from the marketplace through Claude Code's plugin UI.

```text
# update
/plugin marketplace update yeqown/agentic-house

# install skill
```

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
