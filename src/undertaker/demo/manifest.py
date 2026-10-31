"""Expected cause per demo workflow id; the eval scores against this."""

MANIFEST: dict[str, str] = {
    "order-1042": "retry-loop",
    "order-1043": "heartbeat",
    "order-1044": "lost-activity",
    "order-1045": "orphaned",
    "order-1046": "broken-code",
    "order-1047": "changed-code",
    "order-1048": "waiting-signal",
    "order-1049": "long-sleep",
    "order-1050": "undead-child",
    "order-1050-box": "orphaned",
    "inventory-nightly": "alive",
    "proof-dough": "alive",
}
COMPLETED = ["order-1001", "order-1002", "order-1003"]
