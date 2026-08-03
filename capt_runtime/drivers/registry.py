"""DriverRegistry (M0-B, ADR-0120/0121).

Registration is NOT authorization. A driver descriptor grants no execution
authority. Capability grants remain CAPT-owned. A driver must not self-register
as authoritative.

The registry enforces:
- duplicate driver-ID rejection,
- immutable descriptor identity (driverId+driverVersion),
- version compatibility checks against the contract schema version,
- a registration audit event (returned to the caller to persist),
- disable/unregister behavior,
- health status,
- trust classification (always 'untrusted' for external drivers),
- driver implementation digest (package identity where practical).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..contracts import CONTRACT_SCHEMA_VERSION, digest, require


class DriverRegistryError(Exception):
    pass


class DuplicateDriverId(DriverRegistryError):
    pass


class IncompatibleDriverVersion(DriverRegistryError):
    pass


class DriverNotRegistered(DriverRegistryError):
    pass


class SpoofedDriverIdentity(DriverRegistryError):
    pass


class DriverRegistry(object):
    def __init__(self) -> None:
        # driverId -> registration record
        self._drivers: Dict[str, Dict[str, Any]] = {}
        self._audit: List[Dict[str, Any]] = []

    # -- registration ------------------------------------------------------

    def register(
        self,
        descriptor: Dict[str, Any],
        package_identity: Optional[str] = None,
        registered_by: str = "system",
    ) -> Dict[str, Any]:
        """Register a driver. Returns an audit event for CAPT to persist.

        The descriptor is validated against the contract. Duplicate IDs, spoofed
        identity (mismatched digest), and incompatible versions are rejected.
        """
        require("ExecutionDriverDescriptor", descriptor)
        driver_id = descriptor["driverId"]
        version = descriptor["driverVersion"]

        if driver_id in self._drivers:
            raise DuplicateDriverId(
                "driver %r already registered; duplicate IDs rejected" % driver_id
            )

        # Compatibility: the driver must declare support for the current contract
        # schema version family. We require the descriptor to NOT be writeCapable
        # (M0-B: no write-capable driver). The read-only CAPABILITY operations a
        # driver may be granted are enforced later, at work-order dispatch time
        # (host.dispatch rejects RepositoryWrite etc.), not at registration — the
        # descriptor's supportedOperations are driver-lifecycle ops
        # (describe/submit/inspect/cancel/resume/reconcile), a different vocabulary.
        if descriptor.get("writeCapable", False):
            raise IncompatibleDriverVersion("M0-B drivers must not be writeCapable")

        # Identity digest: bind the descriptor content so a later mutation of the
        # stored record without re-registration is detectable (spoof guard).
        identity_digest = digest(descriptor)

        record = {
            "driverId": driver_id,
            "driverVersion": version,
            "descriptor": descriptor,
            "identityDigest": identity_digest,
            "packageIdentity": package_identity,
            "contractSchemaVersion": CONTRACT_SCHEMA_VERSION,
            "trustClassification": "untrusted",
            "health": "unknown",
            "enabled": True,
            "registeredAt": descriptor.get("registeredAt"),
            "registeredBy": registered_by,
        }
        self._drivers[driver_id] = record

        event = {
            "eventType": "DriverRegistered",
            "driverId": driver_id,
            "driverVersion": version,
            "trustClassification": "untrusted",
            "identityDigest": identity_digest,
            "packageIdentity": package_identity,
            "authority": "registration_only",
            "registeredBy": registered_by,
        }
        self._audit.append(event)
        return event

    # -- queries -----------------------------------------------------------

    def get(self, driver_id: str) -> Dict[str, Any]:
        rec = self._drivers.get(driver_id)
        if rec is None:
            raise DriverNotRegistered("driver %r not registered" % driver_id)
        return rec

    def is_registered(self, driver_id: str) -> bool:
        return driver_id in self._drivers

    def list_drivers(self) -> List[str]:
        return sorted(self._drivers.keys())

    def health(self, driver_id: str) -> str:
        return self.get(driver_id)["health"]

    def set_health(self, driver_id: str, health: str) -> None:
        self.get(driver_id)  # raises if absent
        self._drivers[driver_id]["health"] = health

    # -- lifecycle ---------------------------------------------------------

    def disable(self, driver_id: str, reason: str = "") -> Dict[str, Any]:
        rec = self.get(driver_id)
        rec["enabled"] = False
        event = {
            "eventType": "DriverDisabled",
            "driverId": driver_id,
            "reason": reason,
            "authority": "registration_only",
        }
        self._audit.append(event)
        return event

    def unregister(self, driver_id: str, reason: str = "") -> Dict[str, Any]:
        self.get(driver_id)  # raises if absent
        del self._drivers[driver_id]
        event = {
            "eventType": "DriverUnregistered",
            "driverId": driver_id,
            "reason": reason,
            "authority": "registration_only",
        }
        self._audit.append(event)
        return event

    # -- spoof / integrity -------------------------------------------------

    def verify_identity(self, driver_id: str, descriptor: Dict[str, Any]) -> None:
        """Reject a driver that presents a descriptor whose digest differs from
        the one recorded at registration (identity spoofing)."""
        rec = self.get(driver_id)
        if digest(descriptor) != rec["identityDigest"]:
            raise SpoofedDriverIdentity(
                "driver %r descriptor digest mismatch; identity spoof rejected"
                % driver_id
            )

    def drain_audit(self) -> List[Dict[str, Any]]:
        events = list(self._audit)
        self._audit.clear()
        return events
