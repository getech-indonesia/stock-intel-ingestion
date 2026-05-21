from app.scrapers.corporate_action import fetch_idx_corporate_action


def fetch_and_build_corporate_action(
    ca_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    start: int = 0,
    length: int = 9999,
) -> dict:
    return fetch_idx_corporate_action(
        ca_type=ca_type,
        date_from=date_from,
        date_to=date_to,
        start=start,
        length=length,
    )