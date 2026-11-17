from dataclasses import dataclass, field


@dataclass
class Event:
    order_id: str
    version: int
    status: str


@dataclass
class OrderState:
    applied_version: int = 0
    status: str = "NOT_CREATED"
    pending: dict = field(default_factory=dict)


class OrderProcessor:
    def __init__(self):
        self.orders = {}

    def receive_event(self, event):
        if event.order_id not in self.orders:
            self.orders[event.order_id] = OrderState()

        order = self.orders[event.order_id]
        expected_version = order.applied_version + 1

        print(
            f"Received {event.order_id}, "
            f"version {event.version}, status {event.status}"
        )

        if event.version < expected_version:
            print(
                f"Duplicate or old event ignored: "
                f"version {event.version}"
            )
            return

        if event.version > expected_version:
            order.pending[event.version] = event
            print(
                f"Version {event.version} is pending. "
                f"Waiting for version {expected_version}."
            )
            return

        self.apply_event(order, event)
        self.apply_pending_events(order)

    def apply_event(self, order, event):
        order.applied_version = event.version
        order.status = event.status
        print(
            f"Applied version {event.version}. "
            f"New status: {event.status}"
        )

    def apply_pending_events(self, order):
        next_version = order.applied_version + 1

        while next_version in order.pending:
            event = order.pending.pop(next_version)
            self.apply_event(order, event)
            next_version = order.applied_version + 1

    def print_state(self, order_id):
        order = self.orders[order_id]

        print(
            f"Current state for {order_id}: "
            f"version={order.applied_version}, "
            f"status={order.status}, "
            f"pending={list(order.pending.keys())}"
        )


class FencedOrderStore:
    def __init__(self):
        self.latest_token = 0
        self.status = "NOT_CREATED"

    def update_order(self, worker_name, fencing_token, status):
        if fencing_token < self.latest_token:
            print(
                f"REJECTED: {worker_name} used old token "
                f"{fencing_token}. Latest token is "
                f"{self.latest_token}."
            )
            return

        self.latest_token = fencing_token
        self.status = status

        print(
            f"ACCEPTED: {worker_name} used token "
            f"{fencing_token}. New status: {status}"
        )

    def print_state(self):
        print(
            f"Final worker-protected state: "
            f"token={self.latest_token}, status={self.status}"
        )


def test_correct_ordering():
    print("\n=== TEST 1: Out-of-order and duplicate events ===")

    processor = OrderProcessor()

    processor.receive_event(
        Event("ORDER-100", 2, "PAID")
    )

    processor.receive_event(
        Event("ORDER-100", 1, "CREATED")
    )

    processor.receive_event(
        Event("ORDER-100", 2, "PAID")
    )

    processor.print_state("ORDER-100")


def test_missing_event():
    print("\n=== TEST 2: Missing event ===")

    processor = OrderProcessor()

    processor.receive_event(
        Event("ORDER-200", 2, "PAID")
    )

    processor.print_state("ORDER-200")

    print(
        "The order did not jump to PAID because version 1 "
        "is missing."
    )


def test_stale_worker():
    print("\n=== TEST 3: Stale worker and fencing tokens ===")

    store = FencedOrderStore()

    store.update_order(
        "worker-A",
        1,
        "PAID"
    )

    store.update_order(
        "worker-B",
        2,
        "SHIPPED"
    )

    store.update_order(
        "worker-A",
        1,
        "CANCELLED"
    )

    store.print_state()


if __name__ == "__main__":
    test_correct_ordering()
    test_missing_event()
    test_stale_worker()

