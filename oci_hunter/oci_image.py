"""Ubuntu aarch64 image selection."""

from .errors import Fatal


def pick_image(compute, tenancy, prefix):
    """Pick the newest image whose display name starts with `prefix`.

    The list is sorted newest-first by the API, so the first match is the
    newest build of that flavor.
    """
    imgs = compute.list_images(
        tenancy,
        operating_system="Canonical Ubuntu",
        shape="VM.Standard.A1.Flex",
        sort_by="TIMECREATED",
        sort_order="DESC",
    ).data
    for img in imgs:
        if img.display_name.startswith(prefix):
            return img
    available = ", ".join(i.display_name for i in imgs if "aarch64" in i.display_name)
    raise Fatal(
        f"no image starting with '{prefix}' found in this region; "
        f"set IMAGE_PREFIX in .env to one of the available aarch64 images: "
        f"{available or '(no Ubuntu aarch64 images at all)'}"
    )
