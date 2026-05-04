---
title: Build Pipelines
product_area: builds
---

# Build Pipelines

Build pipelines automate your CI/CD workflow in Helix.

## Creating a Pipeline

1. Go to **Project → Pipelines → New Pipeline**.
2. Select your source repository.
3. Choose a pipeline template or start from scratch.
4. Configure build steps.
5. Set triggers (push, PR, schedule).

## Pipeline Configuration

```yaml
# helix-pipeline.yml
name: main-build
trigger:
  branches: [main, develop]
  events: [push, pull_request]

steps:
  - name: install
    run: npm install
  - name: test
    run: npm test
  - name: build
    run: npm run build
  - name: deploy
    run: helix deploy --env production
    only: [main]
```

## Build Status

| Status | Description |
|--------|-------------|
| **Queued** | Build is waiting for a runner. |
| **Running** | Build is actively executing. |
| **Passed** | All steps completed successfully. |
| **Failed** | One or more steps failed. |
| **Cancelled** | Build was manually cancelled. |
| **Timed Out** | Build exceeded the 30-minute timeout. |

## Viewing Build Logs

1. Click on any build in the pipeline history.
2. Select a step to see its logs.
3. Logs are retained for 30 days (Pro) or 90 days (Enterprise).

## Environment Variables

Set build-time variables:
- **Project Settings → Variables**
- Mark sensitive values as **Protected** — they won't appear in logs.
- Variables are injected as environment variables during build.

## Caching

Speed up builds with dependency caching:
```yaml
cache:
  paths:
    - node_modules/
    - .pip-cache/
  key: ${BRANCH}-${CHECKSUM:package-lock.json}
```

## Parallel Builds

Run steps in parallel for faster pipelines:
```yaml
steps:
  - group: test-suite
    parallel:
      - name: unit-tests
        run: npm run test:unit
      - name: integration-tests
        run: npm run test:integration
      - name: lint
        run: npm run lint
```

## Build Artifacts

Save build outputs:
- Artifacts are stored for 7 days by default.
- Download from the build detail page.
- Access programmatically via the Helix API.
