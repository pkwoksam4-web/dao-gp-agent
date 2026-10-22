# DAO2 A/D 16-key status and lifecycle diagnostic

This directory preserves the original diagnostic output from GitHub Actions run `38880076711`, artifact `dao2-a-d-status-16-key-audit-v1` (artifact ID `12036928006`). No rerun was performed.

The artifact reports `PASS_DIAGNOSTIC_ONLY`: all 16 keys were classified `D_STATUS_VALID_TRADABLE`; 11/16 were ST; expected-axis conflicts and transport errors were both zero. The source archive SHA-256 and the SHA-256 of every extracted, unmodified output are recorded in `evidence_manifest.json` and `SHA256SUMS`.

This classifies the 16 keys using the frozen D status/lifecycle semantics. It does **not** recover any of the 16 unresolved A money-flow values, establish ST enrichment, or authorize changes to A or D. It is diagnostic evidence only.

Verify the extracted files with:

```sh
sha256sum -c SHA256SUMS
```
