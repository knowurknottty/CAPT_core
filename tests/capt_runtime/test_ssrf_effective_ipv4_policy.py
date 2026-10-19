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

@pytest.mark.parametrize("host", [
    "2130706433", "0x7f000001", "0X7F000001",
    "127.1", "0x7f.1", "017700000001", "127.000.0.1",
    "127.0.0.1.", "0x7f000001.", "0xA9FEA9FE",
])
def test_legacy_numeric_hosts_cannot_bypass_origin_admission(host):
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        _trusted_origin(f"https://{host}")


@pytest.mark.parametrize("url", [
    "https://%31%32%37.0.0.1",
    "https://127%2e0%2e0%2e1",
    "https://example.com\\evil.test",
    "https://@example.com",
])
def test_percent_encoded_or_ambiguous_authority_rejected(url):
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        _trusted_origin(url)


def test_valid_hostname_with_numeric_label_remains_allowed():
    assert _trusted_origin("https://123.example.com") == "123.example.com"

@pytest.mark.parametrize("host", [
    "１２７.０.０.１",
    "①②⑦.0.0.1",
    "１２７．０．０．１",
    "127。0。0。1",
    "𝟏𝟐𝟕.𝟎.𝟎.𝟏",
])
def test_unicode_numeric_host_variants_fail_closed(host):
    # Some client IDNA/UTS46 stacks normalize these names to loopback.
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        _trusted_origin("https://" + host)


def test_localhost_subdomains_do_not_bypass_loopback_gate():
    with pytest.raises(ValueError, match="LOCALHOST"):
        _trusted_origin("https://foo.localhost")
    with pytest.raises(ValueError, match="LOCALHOST"):
        _trusted_origin("https://localhost.")
