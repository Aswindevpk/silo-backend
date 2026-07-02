# Database Schema Architectural Analysis — Silo

This document presents a comprehensive evaluation of the database schema proposed in [database_schema.md](file:///Users/aswin/Developer/Silo/silo-backend/docs/database_schema.md). The analysis covers structural completeness, data integrity safeguards, performance optimizations, and SaaS compliance.

---

## 1. Structural Completeness & Feature Coverage

The schema covers all target specifications required to implement the **Silo Core Engine**:

| Business Requirement | Schema Component | Verification |
| --- | --- | --- |
| **Multi-Tenancy** | `Workspace` & `WorkspaceMember` | Users can create/join multiple workspaces. Permissions (`Role`) are scoped per workspace membership. |
| **Onboarding & Expansion** | `WorkspaceInvitation` | Validates email-target tokens and tracks invitation lifecycle. |
| **Async Channels** | `Channel` | Models Workspace boundaries and isolates private groups with `allowed_members`. |
| **Threaded Discussions** | `Topic` & `Reply` | Models parent threads with reply cascades, matching the wireframe requirements. |
| **Voice Signaling** | `CallSession` | Tracks 2-member calling history (ringing, completed, duration). |
| **SaaS Monetization** | `WorkspaceSubscription` | Integrates Stripe statuses, billing periods, and auto-renew flags. |

---

## 2. Integrity & Deletion Safeguards

### Cascade Deletion Analysis
A major vulnerability in relational SaaS schemas is cascade-deleting users causing wide-scale historical data deletion. The schema safely handles this:

* **Safe SET_NULL Relationships**: 
  - `Workspace.created_by`, `Channel.created_by`, `Topic.created_by`, `Reply.created_by`, and `CallSession.caller/receiver` all use `on_delete=models.SET_NULL, null=True`. 
  - If a user leaves the company and their user profile is purged, the messages, channels, and logs remain in the system marked as `None` (Anonymous/Deleted), preserving historical threads.
* **Hard Cascade Deletions**: 
  - `WorkspaceMember` uses `on_delete=models.CASCADE`. If a Workspace or a User is hard-deleted, the junction member record is deleted, which is correct.
  - `Reply.topic` and `Topic.channel` use `on_delete=models.CASCADE`. If an admin deletes a channel or thread, the child items are swept cleanly.

---

## 3. Performance & Scalability Index

### ⚡ Query Optimizations Included:
1. **Sidebar Thread Sorting**:
   - Adding `last_reply_at = models.DateTimeField(db_index=True)` on the `Topic` model is crucial. Sidebars must load rapidly, sorted by the latest active thread. Indexing this field avoids full-table scans.
2. **Elimination of `COUNT(*)` Overhead**:
   - `replies_count = models.PositiveIntegerField(default=0)` on the `Topic` model avoids executing heavy aggregation joins (`COUNT` queries) on the `Reply` table every time the channel feed loads.
3. **Invitation Constraints**:
   - `unique_together = ('workspace', 'email')` prevents database bloating if users trigger duplicate invitations repeatedly.

---

## 4. WebRTC Signaling and WebSocket Compatibility

* **Stateless Handshakes**: The WebSocket starts unauthenticated, preventing raw WebSocket HTTP 403 handshakes when using load balancers or proxy caching.
* **Dynamic Grouping**: The `channel_layer` group routing maps directly to `channel_{id}` in Redis, allowing real-time socket events (e.g., `new_reply` or `incoming_call` signaling) to be dispatched instantly to matching subscribers.

---

## 5. Summary Recommendation for Deployment

The schema is robust and ready for implementation. We recommend dividing the models into three Django apps for modularity:
1. **`apps.workspaces`**: Models `Workspace`, `WorkspaceMember`, `WorkspaceInvitation`, and `WorkspaceSubscription`.
2. **`apps.chats`**: Models `Channel`, `Topic`, and `Reply`.
3. **`apps.calls`**: Models `CallSession` (and signaling routing).
