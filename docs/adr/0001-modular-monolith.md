# ADR 0001: Use a modular monolith

## Status

Accepted.

## Context

The product will eventually run audits, metadata edits, uploads, background workers, and several interfaces. Starting with microservices would multiply deployment, queue, authentication, and observability complexity before the domain is stable.

## Decision

Use one repository and one Python package with strict internal modules and adapter contracts. Persist operation boundaries so long-running jobs can later move to workers without changing exchange formats or domain rules.

## Consequences

Development and local PowerShell use stay simple. Modules can be extracted later only when real scaling or deployment boundaries justify it.
