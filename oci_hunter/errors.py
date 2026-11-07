"""Exception types shared across the hunter."""


class Fatal(Exception):
    """Configuration / API error that makes further retries pointless."""
