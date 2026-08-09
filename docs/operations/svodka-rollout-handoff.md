# Svodka rollout handoff

This file exists to prevent the production rollout from being lost when implementation-only work closes.

The supported production sequence is: current-main quality proof -> read-only preflight -> exact reviewed release -> isolated ledger init -> one exact manual canary -> verified provider receipt -> scheduled strict-next publisher -> autonomous scheduled proof.

No production-complete claim is valid before the final scheduled proof is recorded.
