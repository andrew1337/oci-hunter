"""Instance launch, lookup and error classification."""

import time

from oci.core.models import (
    CreateVnicDetails,
    InstanceOptions,
    InstanceSourceViaImageDetails,
    LaunchInstanceDetails,
    LaunchInstanceShapeConfigDetails,
)
from oci.exceptions import ServiceError

from .config import APP_DIR
from .errors import Fatal
from .logging import log

INSTANCE_NAME = "free-tier-hunter"


def launch_instance(compute, cfg, ad, subnet_id, image_id, pubkey):
    return compute.launch_instance(
        LaunchInstanceDetails(
            compartment_id=cfg["tenancy"],
            availability_domain=ad,
            shape=cfg["shape"],
            shape_config=LaunchInstanceShapeConfigDetails(
                ocpus=cfg["ocpus"], memory_in_gbs=cfg["mem_gb"]
            ),
            display_name=INSTANCE_NAME,
            source_details=InstanceSourceViaImageDetails(
                image_id=image_id,
                boot_volume_size_in_gbs=cfg["boot_gb"],
                boot_volume_vpus_per_gb=10,
            ),
            create_vnic_details=CreateVnicDetails(
                subnet_id=subnet_id,
                assign_public_ip=True,
                display_name=f"{INSTANCE_NAME}-vnic",
            ),
            metadata={"ssh_authorized_keys": pubkey},
            instance_options=InstanceOptions(are_legacy_imds_endpoints_disabled=True),
            is_pv_encryption_in_transit_enabled=True,
        )
    ).data


def wait_public_ip(compute, vnet, tenancy, instance_id, timeout=300):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            for att in compute.list_vnic_attachments(
                tenancy, instance_id=instance_id
            ).data:
                vnic = vnet.get_vnic(att.vnic_id).data
                if vnic.public_ip:
                    return vnic.public_ip
        except ServiceError as exc:
            log(f"vnic lookup failed: {exc.message}")
        time.sleep(10)
    return None


def find_existing_instance(compute, tenancy):
    for inst in compute.list_instances(tenancy, display_name=INSTANCE_NAME).data:
        if inst.lifecycle_state != "TERMINATED":
            return inst
    return None


def classify_error(exc):
    """Bucket a ServiceError into ratelimit / capacity / server / fatal."""
    code = exc.code or ""
    msg = (exc.message or "").lower()
    if exc.status == 429:
        return "ratelimit"
    if "capacity" in msg:
        return "capacity"
    if code in ("QuotaExceeded", "LimitExceeded"):
        return "fatal"
    if exc.status >= 500:
        return "server"
    return "fatal"


def retry_after_seconds(exc, default):
    """Best-effort Retry-After extraction from a 429 ServiceError.

    Returns `default` when the header is absent or unparseable."""
    try:
        raw = (exc.headers or {}).get("Retry-After")
    except AttributeError:
        return default
    if raw is None:
        return default
    try:
        return max(0, int(float(raw)))
    except (TypeError, ValueError):
        return default


def load_pubkey(cfg):
    """SSH public key: SSH_PUBKEY env, SSH_KEY_FILE (.pub is read from the
    sibling private key path), or a mounted /app/ssh_key.pub."""
    if cfg["ssh_pubkey"]:
        log("using SSH_PUBKEY from environment")
        return cfg["ssh_pubkey"]
    if cfg["ssh_key_file"]:
        # The value is the private key name; the .pub sits next to it.
        pub = (
            APP_DIR / (cfg["ssh_key_file"] + ".pub")
            if not cfg["ssh_key_file"].endswith(".pub")
            else APP_DIR / cfg["ssh_key_file"]
        )
        if not pub.is_file():
            raise Fatal(
                f"SSH_KEY_FILE set but {pub} not found (mount the "
                f"key pair into the container)"
            )
        log(f"using ssh key from {pub.name}")
        return pub.read_text(encoding="utf-8").strip()
    path = APP_DIR / "ssh_key.pub"
    if path.is_file():
        log(f"using ssh key from {path.name}")
        return path.read_text(encoding="utf-8").strip()
    raise Fatal(
        "no SSH public key found (set SSH_KEY_FILE in .env to the "
        "private key file name mounted into the container, or set "
        "SSH_PUBKEY)"
    )
