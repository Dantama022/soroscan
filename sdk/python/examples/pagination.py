"""
Pagination examples for the SoroScan SDK.

Demonstrates how ``Paginator`` and ``AsyncPaginator`` remove manual page
bookkeeping when walking large event result sets. Both examples use the same
filters and page size so the sync and async helpers are easy to compare.

Set ``SOROSCAN_API_KEY`` when querying a protected deployment.
"""

import asyncio

from soroscan import AsyncSoroScanClient, SoroScanClient
from soroscan.pagination import AsyncPaginator, Paginator

CONTRACT_ID = "CCAAA111222333444555666777888999AAABBBCCCDDDEEEFFF"
PAGE_SIZE = 25


def paginate_events_sync() -> int:
    """Walk every event page using the synchronous paginator."""
    with SoroScanClient() as client:
        paginator = Paginator(
            client.get_events,
            contract_id=CONTRACT_ID,
            event_type="transfer",
            ordering="-timestamp",
            page_size=PAGE_SIZE,
        )

        total_events = 0
        for page in paginator:
            total_events += len(page.results)
            print(
                f"[sync] page {paginator.current_page_number}: "
                f"{len(page.results)} events "
                f"(running total {total_events}/{page.count})"
            )

        print(f"[sync] finished after {paginator.current_page_number} page(s)")
        return total_events


async def paginate_events_async() -> int:
    """Walk every event page using the asynchronous paginator."""
    async with AsyncSoroScanClient() as client:
        paginator = AsyncPaginator(
            client.get_events,
            contract_id=CONTRACT_ID,
            event_type="transfer",
            ordering="-timestamp",
            page_size=PAGE_SIZE,
        )

        total_events = 0
        async for page in paginator:
            total_events += len(page.results)
            print(
                f"[async] page {paginator.current_page_number}: "
                f"{len(page.results)} events "
                f"(running total {total_events}/{page.count})"
            )

        print(f"[async] finished after {paginator.current_page_number} page(s)")
        return total_events


def main() -> None:
    sync_total = paginate_events_sync()
    async_total = asyncio.run(paginate_events_async())

    print(f"\nProcessed {sync_total} events synchronously")
    print(f"Processed {async_total} events asynchronously")


if __name__ == "__main__":
    main()
