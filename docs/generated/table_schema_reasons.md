| Reason | Meaning |
| :--- | :--- |
| `duplicate-identity` | It's defined more than once, so Protostar can't tell which copy to update. |
| `unsafe-pin` | The update would move your pinned hook to an older or unrelated revision. |
| `shared-structure` | It shares YAML anchors with content Protostar doesn't manage. |
| `unowned` | It was in your file before Protostar managed it. |
| `different-group` | This dependency is already in another group. Keep its current placement or add it to this group too. |
| `diverged` | You and the update both changed it. |
| `type-mismatch` | You and the update changed it to different kinds of value. |
| `deleted-ancestor` | You deleted it, and the update changed it. |
| `retracted` | You edited it, and the update no longer includes it. |
| `proposed` | Protostar adds it; your file doesn't have it yet. |
| `preserved` | You changed it, and the update is still Protostar's version. |
