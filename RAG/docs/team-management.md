---
title: Team Management
product_area: teams
---

# Team Management

Manage team members, roles, and permissions in your Helix organization.

## Roles

| Role | Permissions |
|------|------------|
| **Owner** | Full access. Can delete organization. Billing management. |
| **Admin** | Manage members, projects, settings. Cannot delete org. |
| **Developer** | Create/edit pipelines, trigger builds, view logs. |
| **Viewer** | Read-only access to projects and build logs. |

## Inviting Members

1. Go to **Organization → Members**.
2. Click **Invite Member**.
3. Enter their email address.
4. Select a role.
5. They'll receive an email invitation valid for 7 days.

## Managing Permissions

### Project-level Permissions
Override organization roles at the project level:
- **Project Settings → Members → Manage Roles**
- A Developer at org level can be an Admin for specific projects.

### Branch Protection
Restrict who can push to protected branches:
1. **Project Settings → Branches → Protected Branches**.
2. Set allowed roles for push and merge.

## API Token Scopes

When creating API tokens for team automation:
- `read:projects` — list projects
- `write:pipelines` — create/edit pipelines
- `admin:members` — manage team membership

## Audit Log

All member actions are logged:
- **Organization → Settings → Audit Log**
- Filter by user, action type, or date range.
- Logs retained for 90 days on Pro, 365 days on Enterprise.
