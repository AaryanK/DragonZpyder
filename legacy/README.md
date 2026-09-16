# Legacy DragonZpyder program

The original single-file desktop assistant was removed from the current runnable tree during the P1 containment slice.

It remains available in Git history for forensic/reference purposes, but it must not be restored into startup, imported by the modern package, or used as a source of credentials. The historical program mixed desktop control, messaging, telephony, local credential files and provider-specific behavior without the governed execution boundaries required by the current product.

Provider credential revocation/rotation is an operational task separate from source containment. Deleting a value from the current tree does not revoke a credential and does not erase historical copies.
