# F5 mailbox outcome hardening

Reference disposition: retained contract/acceptance evidence; not an active implementation
sequence. Dated runtime counts and release proofs describe their original checkpoint.
Current engineering direction is in `docs/current/REENTRY.md`.


This checkpoint addresses two real mailbox-preview gaps before first persistence authority.

1. A high-impact outcome can co-exist with acknowledgement language in the same message. One clear high-impact class now wins over background acknowledgement/recruiter wording; conflicting high-impact classes remain `ambiguous`.
2. Gmail's metadata snippet can end before the decisive outcome phrase. The private runtime may therefore attach a bounded, whitelisted `gmail_search_signals` class label derived from Gmail server-side search without downloading a message body.

Public JAP validates signal labels fail-closed and feeds them into the deterministic classifier. Results remain `evidence_only`; the change adds no submission authority, lifecycle-state mutation, Gmail write, application submission action, or model/provider authority.

The motivating live examples are the HDI 2026-07-23 rejection (acknowledgement wording plus rejection) and the Capgemini 2026-06-21 rejection (decisive rejection text after the metadata snippet boundary).
