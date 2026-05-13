# Skills Repository Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert this repository from a Claude Code plugin marketplace layout into a pure root-level skills repository modeled after `anthropics/skills`.

**Architecture:** Each skill becomes a self-contained directory under `skills/<skill-name>/` containing `SKILL.md`, optional references, helper scripts, sample config, and a local README. Root-level `template/` and `spec/` describe how to add new skills. Claude Code plugin marketplace packaging is removed instead of shimmed.

**Tech Stack:** Markdown, shell file moves, Python helper scripts. User explicitly requested no tests; verification uses structural checks only.

---

## File Structure

Create:
- `skills/jenkins-skill/`
- `skills/kibana-log/`
- `template/SKILL.md`
- `template/bin/.gitkeep`
- `template/config-sample/.gitkeep`
- `spec/SKILL.md`
- `docs/superpowers/plans/2026-05-13-skills-repository-structure.md`

Move:
- `plugins/jenkins-skill/skills/jenkins-skill/SKILL.md` → `skills/jenkins-skill/SKILL.md`
- `plugins/jenkins-skill/skills/jenkins-skill/reference.md` → `skills/jenkins-skill/reference.md`
- `plugins/jenkins-skill/bin/jenkins-skill` → `skills/jenkins-skill/bin/jenkins-skill`
- `plugins/jenkins-skill/config-sample/index.json` → `skills/jenkins-skill/config-sample/index.json`
- `plugins/jenkins-skill/README.md` → `skills/jenkins-skill/README.md`
- `plugins/kibana-log/skills/kibana-log/SKILL.md` → `skills/kibana-log/SKILL.md`
- `plugins/kibana-log/bin/load_kibana_context.py` → `skills/kibana-log/bin/load_kibana_context.py`
- `plugins/kibana-log/config-sample/index.json` → `skills/kibana-log/config-sample/index.json`
- `plugins/kibana-log/config-sample/prod.json` → `skills/kibana-log/config-sample/prod.json`
- `plugins/kibana-log/config-sample/test.json` → `skills/kibana-log/config-sample/test.json`
- `plugins/kibana-log/README.md` → `skills/kibana-log/README.md`

Modify:
- `README.md` — root catalog and usage guide.
- `skills/jenkins-skill/README.md` — update paths from `plugins/jenkins-skill/...` to `skills/jenkins-skill/...`.
- `skills/kibana-log/README.md` — update paths from `plugins/kibana-log/...` to `skills/kibana-log/...`.
- `.gitignore` — remove `docs/superpowers/` ignore entry if present so spec/plan can be tracked.

Delete:
- `.claude-plugin/marketplace.json`
- `plugins/jenkins-skill/.claude-plugin/plugin.json`
- `plugins/jenkins-skill/package.json`
- `plugins/kibana-log/.claude-plugin/plugin.json`
- `plugins/kibana-log/package.json`
- empty `plugins/` tree after migration.

Do not create, restore, or run tests.

---

### Task 1: Move skill packages into root `skills/`

**Files:**
- Create/move: all paths listed under File Structure “Move”.
- Delete: empty plugin package directories after move.

- [ ] **Step 1: Create target directories**

Run:

```bash
mkdir -p \
  "skills/jenkins-skill/bin" \
  "skills/jenkins-skill/config-sample" \
  "skills/kibana-log/bin" \
  "skills/kibana-log/config-sample"
```

Expected: command exits 0.

- [ ] **Step 2: Move Jenkins skill files**

Run:

```bash
git mv "plugins/jenkins-skill/skills/jenkins-skill/SKILL.md" "skills/jenkins-skill/SKILL.md"
git mv "plugins/jenkins-skill/skills/jenkins-skill/reference.md" "skills/jenkins-skill/reference.md"
git mv "plugins/jenkins-skill/bin/jenkins-skill" "skills/jenkins-skill/bin/jenkins-skill"
git mv "plugins/jenkins-skill/config-sample/index.json" "skills/jenkins-skill/config-sample/index.json"
git mv "plugins/jenkins-skill/README.md" "skills/jenkins-skill/README.md"
```

Expected: each command exits 0.

- [ ] **Step 3: Move Kibana skill files**

Run:

```bash
git mv "plugins/kibana-log/skills/kibana-log/SKILL.md" "skills/kibana-log/SKILL.md"
git mv "plugins/kibana-log/bin/load_kibana_context.py" "skills/kibana-log/bin/load_kibana_context.py"
git mv "plugins/kibana-log/config-sample/index.json" "skills/kibana-log/config-sample/index.json"
git mv "plugins/kibana-log/config-sample/prod.json" "skills/kibana-log/config-sample/prod.json"
git mv "plugins/kibana-log/config-sample/test.json" "skills/kibana-log/config-sample/test.json"
git mv "plugins/kibana-log/README.md" "skills/kibana-log/README.md"
```

Expected: each command exits 0.

- [ ] **Step 4: Remove plugin packaging files**

Run:

```bash
git rm \
  ".claude-plugin/marketplace.json" \
  "plugins/jenkins-skill/.claude-plugin/plugin.json" \
  "plugins/jenkins-skill/package.json" \
  "plugins/kibana-log/.claude-plugin/plugin.json" \
  "plugins/kibana-log/package.json"
```

Expected: command exits 0.

- [ ] **Step 5: Remove empty plugin directories**

Run:

```bash
find plugins -type d -empty -delete
```

Expected: command exits 0. `plugins/` may disappear if empty.

- [ ] **Step 6: Structural check only**

Run:

```bash
find skills -maxdepth 3 -type f | sort
```

Expected output includes:

```text
skills/jenkins-skill/README.md
skills/jenkins-skill/SKILL.md
skills/jenkins-skill/bin/jenkins-skill
skills/jenkins-skill/config-sample/index.json
skills/jenkins-skill/reference.md
skills/kibana-log/README.md
skills/kibana-log/SKILL.md
skills/kibana-log/bin/load_kibana_context.py
skills/kibana-log/config-sample/index.json
skills/kibana-log/config-sample/prod.json
skills/kibana-log/config-sample/test.json
```

Do not run tests.

---

### Task 2: Add root template and spec

**Files:**
- Create: `template/SKILL.md`
- Create: `template/bin/.gitkeep`
- Create: `template/config-sample/.gitkeep`
- Create: `spec/SKILL.md`

- [ ] **Step 1: Create template directories**

Run:

```bash
mkdir -p "template/bin" "template/config-sample" "spec"
```

Expected: command exits 0.

- [ ] **Step 2: Write `template/SKILL.md`**

Create `template/SKILL.md` with:

```markdown
---
name: example-skill
description: Use when the user needs this example skill's workflow or reference material.
---

# Example Skill

## Overview

Describe what this skill helps Claude do and when it should be used.

## Workflow

1. Gather the minimum required context.
2. Apply the skill-specific process.
3. Report results and next steps.

## References

Keep heavy reference material in separate files next to this `SKILL.md` when needed.
```

- [ ] **Step 3: Add `.gitkeep` files**

Run:

```bash
: > "template/bin/.gitkeep"
: > "template/config-sample/.gitkeep"
```

Expected: command exits 0.

- [ ] **Step 4: Write `spec/SKILL.md`**

Create `spec/SKILL.md` with:

```markdown
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
```

- [ ] **Step 5: Structural check only**

Run:

```bash
find template spec -maxdepth 3 -type f | sort
```

Expected output:

```text
spec/SKILL.md
template/SKILL.md
template/bin/.gitkeep
template/config-sample/.gitkeep
```

Do not run tests.

---

### Task 3: Rewrite root README as skills catalog

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace root README content**

Replace `README.md` with:

```markdown
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
```

- [ ] **Step 2: Structural check only**

Run:

```bash
grep -n "Claude Code plugin marketplace\|plugins/\|skills/<skill-name>\|jenkins-skill\|kibana-log" README.md
```

Expected:
- `Claude Code plugin marketplace` appears only in the sentence saying this is not a marketplace package.
- `plugins/` does not appear.
- `jenkins-skill` and `kibana-log` appear in the skills table.

Do not run tests.

---

### Task 4: Update skill-local README path references

**Files:**
- Modify: `skills/jenkins-skill/README.md`
- Modify: `skills/kibana-log/README.md`

- [ ] **Step 1: Update Jenkins README paths**

In `skills/jenkins-skill/README.md`, replace:

```text
plugins/jenkins-skill/config-sample/index.json
```

with:

```text
skills/jenkins-skill/config-sample/index.json
```

Remove any local plugin development section that tells users to run `claude --plugin-dir ... plugins/jenkins-skill`.

- [ ] **Step 2: Update Kibana README paths**

In `skills/kibana-log/README.md`, replace any `plugins/kibana-log/` path prefix with `skills/kibana-log/`.

Remove any local plugin development section that tells users to run `claude --plugin-dir ... plugins/kibana-log`.

- [ ] **Step 3: Structural text check only**

Run:

```bash
grep -R -n "plugins/jenkins-skill\|plugins/kibana-log\|plugin-dir" skills README.md spec template || true
```

Expected: no output.

Do not run tests.

---

### Task 5: Remove `docs/superpowers/` ignore and verify final structure

**Files:**
- Modify: `.gitignore`
- Verify: repository tree and git status.

- [ ] **Step 1: Update `.gitignore`**

If `.gitignore` contains:

```text
docs/superpowers/
```

remove that line. Keep other ignore entries unchanged.

- [ ] **Step 2: Verify root structure only**

Run:

```bash
find . -maxdepth 2 -type d | sort
```

Expected output includes:

```text
./docs
./docs/superpowers
./skills
./skills/jenkins-skill
./skills/kibana-log
./spec
./template
```

Expected output does not include:

```text
./plugins
./.claude-plugin
```

Do not run tests.

- [ ] **Step 3: Verify skill files only**

Run:

```bash
find skills template spec -maxdepth 3 -type f | sort
```

Expected output includes all moved skill files and template/spec files. It must not include `.claude-plugin` or `package.json`.

Do not run tests.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected:
- file moves from `plugins/` to `skills/`
- deletions for `.claude-plugin/marketplace.json` and plugin package metadata
- new `template/`, `spec/`, and `docs/superpowers/...` files
- no unrelated changes

Do not run tests.

---

## Self-Review

- Spec coverage: root-level `skills/`, self-contained packages, `template/`, `spec/`, root README catalog, and removal of marketplace packaging are all covered.
- User constraint: every task says do not run tests; verification commands are structural only.
- Placeholder scan: no TODO/TBD/fill-later steps remain.
- Path consistency: all target paths use `skills/<skill-name>/`; legacy `plugins/` appears only in source migration commands and cleanup checks.
