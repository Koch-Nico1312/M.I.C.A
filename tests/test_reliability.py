from core.reliability import build_reliability_report


def test_reliability_report_has_expected_shape():
    report = build_reliability_report()

    assert report["status"] in {"ok", "degraded", "blocked"}
    assert isinstance(report["checks"], list)
    assert isinstance(report["counts"], dict)
    assert isinstance(report["recommendations"], list)

