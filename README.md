# agentic-house

Internal Claude Code marketplace for the `jenkins-skill` plugin.

## Install marketplace

Add this repository as a Claude Code marketplace:

```text
/plugin marketplace add git@github.com:yeqown/agentic-house.git
```

## Install plugin

After the marketplace is added:

```text
/plugin install jenkins-skill@agentic-house
/reload-plugins
```

## Update plugin

```text
/plugin marketplace update agentic-house
/plugin update jenkins-skill@agentic-house
/reload-plugins
```

## Repository layout

- marketplace metadata lives at `.claude-plugin/marketplace.json`
- plugin content lives at `plugins/jenkins-skill`

## Plugin runtime

The plugin itself still uses `JENKINS_SKILL_HOME` and documents runtime setup in:

- `plugins/jenkins-skill/README.md`
