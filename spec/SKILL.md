# Skill Package Convention

Each skill lives in `skills/<skill-name>/` and is self-contained.

Required:
- `SKILL.md` with YAML frontmatter containing `name` and `description`.

Optional:
- `README.md` for human setup and usage notes.
- `reference.md` or other reference files for longer material.
- `bin/` for helper scripts.
- `config-sample/` for sample local configuration.

A user should be able to copy one `skills/<skill-name>/` directory and get the complete skill package.
