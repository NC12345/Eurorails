# ferry_small_city as a composite type rather than is_ferry boolean

Dublin (`r10_c22`) and Belfast (`r7_c25`) are both small cities and ferry terminals. We added a `ferry_small_city` type to the node type enum rather than adding an `is_ferry: bool` field to `small_city` nodes. All behavioral dispatch in rendering and future movement logic uses `if/elif` on `type`; a dedicated composite type keeps that dispatch pattern consistent and avoids scattering `is_ferry` checks across unrelated code paths.

## Considered Options

- **`ferry_small_city` type (chosen)** — single dispatch point, self-documenting, consistent with how all other node variants are handled.
- **`is_ferry: bool` on `small_city` nodes** — rejected because it splits identity across two fields, requiring every piece of movement/rendering logic to check both `type` and `is_ferry`.
