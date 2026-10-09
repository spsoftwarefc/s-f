# PQ-07P — retained archive and publisher verification join

Work order committed first at `103f002d57d52038eefa614eb244b6a8ff1f380e`, parent `3b3ea3687b5fa4db74b380d73bdf588d37ccf036`.

This isolated read-only adapter reuses `read_retained` and operator-pinned `authenticate_publisher`. It rejects incorrect external manifest/policy/digest pins, rehashes retained source bytes, copies the **exact** retained bytes into a private path before verification, and verifies source commit/tree and all no-authorization flags in returned publisher evidence. Tests include false publisher acceptance, wrong tree, tampered retained bytes and wrong manifest pin. It does not install, publish, rebuild from a tag, verify actual independent retention custody, or fetch a real attestation.

The existing `setuptools>=68` package build prerequisite remains a reproducibility blocker; preview workflow version pins alone cannot close it. PQ-07 live NO-GO; PQ-08 NOT STARTED; SF-R10 UNMET.
