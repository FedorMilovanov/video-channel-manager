# Recovery evidence bundle

Retain these files after a successful channel-closing recovery:

1. original signed comment plan;
2. original apply journal after it reaches `completed`;
3. fresh YouTube inventory snapshot;
4. fresh comment audit JSON and Markdown;
5. final coverage certificate.

The certificate binds the other JSON artifacts by SHA-256. The audit proves current channel coverage; the signed plan and journal prove which reviewed operations were attempted; verify-only proves that recovery did not repeat writes.
