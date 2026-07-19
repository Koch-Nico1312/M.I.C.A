from core.notification_center import NotificationCenter


def test_notification_center_persists_delivery_and_deduplicates(tmp_path):
    path = tmp_path / "notifications.json"
    center = NotificationCenter(path)
    deliveries = []

    first = center.publish(
        "Automation recovered",
        "Pulse is healthy again",
        "high",
        source="automation",
        dedup_key="pulse-recovered",
        deliver=lambda: deliveries.append("sent") or True,
    )
    second = center.publish(
        "Automation recovered",
        "Pulse is healthy again",
        "high",
        source="automation",
        dedup_key="pulse-recovered",
        deliver=lambda: deliveries.append("duplicate") or True,
    )

    restored = NotificationCenter(path).snapshot()
    assert first["status"] == "delivered"
    assert second["deduplicated"] is True
    assert deliveries == ["sent"]
    assert restored["counts"] == {"delivered": 1}


def test_notification_center_keeps_failed_delivery_for_recovery(tmp_path):
    center = NotificationCenter(tmp_path / "notifications.json")

    event = center.publish("Pulse failed", "Service unavailable", "urgent", deliver=lambda: False)

    assert event["status"] == "failed"
    assert event["error"] == "delivery backend unavailable"
