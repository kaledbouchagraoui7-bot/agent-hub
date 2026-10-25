# Workspace Check

The workspace template may have been updated. Compare the current workspace with the reference template and selectively apply beneficial structural changes.

## Rules

- Preserve all existing user content and customizations.
- **Conditional notification**: Only notify or mention this update to the user if you actually find changes worth applying. If the workspace is already in sync or no meaningful differences exist, simply delete this file without bothering the user.
- Start a background job via `x agent run` — do NOT block the current chat session.
- After starting the background job, delete this file.

## References

- Reference template: <SOURCE>
- Current workspace: <TARGET>
