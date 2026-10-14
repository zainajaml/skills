# Semantic conflicts

A conflict is a disagreement about **behavior**, not about text in files. The upstream and destination code never share files, so Git cannot detect these conflicts. You must.

## Detect

For every unit that touches a feature the destination already has, compare four behaviors:

1. **Original upstream behavior:** the code at the checkpoint (`git show <checkpoint>:<path>`).
2. **Existing destination behavior:** what the migrated code does now, including local improvements made after migration (`git log` in the destination since the migration, without `Lovable-Upstream:` trailers).
3. **New upstream behavior:** the code at the unit's last commit.
4. **Required final behavior:** what the product should do after the sync.

| Pattern | Meaning | Action |
| --- | --- | --- |
| 1 = 2, and 3 differs | Destination unchanged since migration | Not a conflict: apply the upstream change in the destination's style |
| 1 ≠ 2, and 3 = 1 | Only the destination changed | Not a conflict: nothing to sync for this behavior |
| 1 ≠ 2, 3 ≠ 1, and the changes are independent | Both changed different aspects | Merge: apply only the upstream change and keep the destination change |
| 1 ≠ 2, 3 ≠ 1, and the changes overlap | Both changed the same aspect differently | **Conflict** |
| 3 needs something the destination removed on purpose (a Supabase capability, a retired flow) | Architecture decision | **Conflict** |
| 3 weakens security or authorization relative to 2 | Security regression | **Conflict**; always needs approval |

Common cases: login or session flows (the destination has its own auth), validation rules made stricter or looser on one side, data representation (cents vs decimals), permissions, renamed or merged screens, and features retired during migration.

## Decide

- Destination architecture decisions are kept by default: the auth design, module boundaries, API envelope, security controls.
- Never overwrite a local improvement just because upstream changed.
- If the required final behavior is clear from evidence (upstream fixes a bug that the destination also has), propose `adapt` and record it with `--needs-approval no`.
- If intent is ambiguous, the change is visible to users, or security is involved, ask the user. Record `--needs-approval yes`.

Resolutions (`sync_state.py conflict --resolution`):

| Resolution | Meaning | Unit status afterwards |
| --- | --- | --- |
| `adapt` | Implement upstream behavior in a way compatible with the destination's choices | `verified` once implemented and tested |
| `preserve` | Keep the destination behavior; upstream change not applied | `retained-local` (decision + `--user-approved`) |
| `decline` | The user does not want this upstream change | `declined` (decision + `--user-approved`) |
| `defer` | Decide later | `deferred`; the checkpoint stops before it |

A conflict marked `--needs-approval yes` can be resolved only with `--user-approved`. Record approvals only when the user actually gave them.

## Report each conflict

```text
Conflict C1 — unit U3 (Login flow)
Affected feature:     Sign-in and post-login redirect
Upstream change:      Redirects to /dashboard after login; adds "remember me" (30-day session)
Existing destination: Backend issues 15-min access + rotating refresh cookie; redirect honors ?next=
Reason:               A 30-day session conflicts with the destination's token lifetime policy
Proposal:             adapt — keep ?next= (default /dashboard); implement "remember me" as a longer refresh-token lifetime (max 30 days) in the auth module
Expected impact:      Backend auth config + login DTO, frontend checkbox; existing sessions unaffected
Approval required:    yes (authentication behavior)
```

Record it:

```bash
python3 <skill>/scripts/sync_state.py conflict --id C1 --unit U3 --feature "Sign-in redirect" \
  --upstream-change "..." --existing "..." --reason "..." --proposal "..." --impact "..." --needs-approval yes
# after the user decides:
python3 <skill>/scripts/sync_state.py conflict --id C1 --resolution adapt --user-approved --status resolved
```

Conflicts never block unrelated units. Continue with the other units, and let the checkpoint stop at the first unresolved commit.
