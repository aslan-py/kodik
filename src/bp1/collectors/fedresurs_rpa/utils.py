"""Helper functions for fedresurs_rpa."""

from datetime import datetime

from .models import ProxyConfig


def format_proxy_string(proxy: ProxyConfig | None) -> str | None:
    """Format proxy config to string."""
    if proxy is None:
        return None
    if proxy.username and proxy.password:
        return f"{proxy.server} ({proxy.username}:***)"
    return proxy.server


def validate_inn(inn: str) -> None:
    """Validate Russian INN (10 or 12 digits).

    Args:
        inn: INN string to validate.

    Raises:
        ValueError: If INN is invalid (not digits, wrong length, bad checksum).
    """
    if not inn.isdigit():
        raise ValueError("INN must contain only digits")

    if len(inn) not in (10, 12):
        raise ValueError("INN must be 10 or 12 digits")

    if len(inn) == 10:
        weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        checksum = sum(int(inn[i]) * weights[i] for i in range(9)) % 11 % 10
        if checksum != int(inn[9]):
            raise ValueError("Invalid INN checksum")
    else:
        weights1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        weights2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        check1 = sum(int(inn[i]) * weights1[i] for i in range(10)) % 11 % 10
        check2 = sum(int(inn[i]) * weights2[i] for i in range(11)) % 11 % 10
        if check1 != int(inn[10]) or check2 != int(inn[11]):
            raise ValueError("Invalid INN checksum")


def generate_filename(
    name: str,
    inn: str | None = None,
    timestamp: datetime | None = None,
) -> str:
    """Generate filename for saved HTML.

    Args:
        name: Company name.
        inn: Optional INN for filename.
        timestamp: Optional timestamp (uses current time if None).

    Returns:
        Filename string.
    """
    if timestamp is None:
        timestamp = datetime.now()

    date_str = timestamp.strftime("%Y%m%d_%H%M%S")

    if inn:
        safe_name = inn
    else:
        safe_name = "".join(c if c.isalnum() else "_" for c in name)[:50]

    return f"fedresurs_{safe_name}_{date_str}.html"
