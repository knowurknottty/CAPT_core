"""UPG-081 regression: shared effective IP policy across supported egress hosts."""
from __future__ import annotations

import ipaddress

import pytest

from capt_runtime.media_adapter_contract import _trusted_origin
from capt_runtime.tools.backends.ssh import SSHNetworkPolicy, _network_allows


@pytest.mark.parametrize("ip", [
    "64:ff9b::a9fe:a9fe",      # NAT64 -> cloud metadata 169.254.169.254
    "2002:a9fe:a9fe::1",       # 6to4 -> cloud metadata 169.254.169.254
    "64:ff9b::7f00:1",         # NAT64 -> loopback
    "2002:0a00:0005::1",       # 6to4 -> private RFC1918
])
def test_media_origin_rejects_encoded_nonpublic_ipv4(ip):
    with pytest.raises(ValueError, match="PRIVATE_IP"):
        _trusted_origin(f"https://[{ip}]")


@pytest.mark.parametrize("ip", [
    "64:ff9b::a9fe:a9fe",
    "2002:a9fe:a9fe::1",
])
def test_ssh_public_policy_rejects_embedded_metadata_ip(ip):
    assert not _network_allows(SSHNetworkPolicy(), ipaddress.ip_address(ip))


def test_explicit_private_ssh_policy_is_still_allowed():
    policy = SSHNetworkPolicy(
        allowed_destination_classes=("public",),
        allowed_cidrs=("64:ff9b::/96", "169.254.0.0/16"),
    )
    assert _network_allows(policy, ipaddress.ip_address("64:ff9b::a9fe:a9fe"))


@pytest.mark.parametrize("ip", [
    "8.8.8.8", "2001:4860:4860::8888", "64:ff9b::0808:0808",
])
def test_public_traffic_remains_admissible(ip):
    if ip != "64:ff9b::0808:0808":
        assert _network_allows(SSHNetworkPolicy(), ipaddress.ip_address(ip))
    assert _trusted_origin(f"https://[{ip}]" if ":" in ip else f"https://{ip}")
