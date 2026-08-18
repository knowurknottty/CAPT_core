# CAPT-UPG-011 Repair Contract

Acceptance requires the authenticated `steer_deliberation` command itself to cause a durable RuntimeService/EventStore Cohort transition: persist the directive, advance the active epoch, make prior contributions stale for current quorum, surface the directive into the next governed deliberation/model input, preserve state across restart, enforce idempotency/conflict handling, and keep capability/lease expansion as a separate authorization path.
