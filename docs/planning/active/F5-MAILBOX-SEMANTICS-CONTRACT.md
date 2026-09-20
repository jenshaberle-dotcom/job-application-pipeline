# F5 mailbox semantics contract

`contracts/f5_mailbox_semantics_v1.json` is the canonical provider-neutral semantics contract for bounded F5 mailbox evidence.

Authority is intentionally one-way:

- **job-application-pipeline owns classification semantics and Product interpretation**;
- the private runtime may discover and normalize bounded Gmail evidence, but its preview audit is non-authoritative;
- runtime keeps an exact mirror of this contract only for operator acceptance and must prove that mirror matches public JAP `main`;
- any semantic change must update this canonical contract and the public classifier tests first, then update the runtime mirror.

The corpus contains no private mailbox content or employer-specific production rule. It captures structural cases such as strong acknowledgement subjects, truncated metadata plus bounded lifecycle signals, conflicting signals, Initiativbewerbung semantics and non-application noise.

This contract is an anti-drift boundary: a second implementation is allowed only as a non-authoritative projection that satisfies the same canonical cases.
