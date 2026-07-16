# ADR 0012 — Deterministic parallel semantic-audit manifests

**Status:** accepted

The bilingual semantic audit is partitioned by Card GUID into three deterministic
worker manifests.  A card is eligible when it has pending source coverage or a
pending/uncertain semantic decision/check.  Pending source coverage is weighted
first; semantic work is the fallback weight.  A GUID is never split between
workers.

The partition uses descending weight, GUID tie-breaking, and assignment to the
least-loaded worker (worker number as the final tie-break).  Manifests carry the
raw ledger SHA-256, schema version, source fingerprint, and a canonical card
fingerprint so stale worker inputs fail closed.

Manifest creation takes an advisory snapshot lock, verifies the ledger hash is
unchanged before writing, and writes only under `scratch/parallel/manifests/`.
Workers may write review bundles only below their own
`scratch/parallel/worker_N/` directory and may run `apply-review --dry-run`; a
single coordinator applies reviewed bundles to the canonical ledger.

Existing bundles whose GUIDs are no longer open are recorded as completed or
superseded.  An open GUID already present in a bundle is deferred rather than
assigned again, preventing duplicate semantic review.
