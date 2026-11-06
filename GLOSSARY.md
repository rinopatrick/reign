# GLOSSARY.md — Reign domain language

## Import
A file uploaded by the user and parsed locally. Never fetches from a bank.

## Sync
Manual re-import of a statement file. There is no server sync and no cloud.

## Preview
A read-only inspection of what an import file would create. Writes zero rows.

## Dedupe
Skipping rows whose statement fingerprint already exists in the account.

## Format
One named bank CSV layout plus its detector, for example bca or bsi.
