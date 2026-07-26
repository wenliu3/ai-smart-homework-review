from tests.evals.cases.catalog import (
    ADMIN_SAFETY_CASES,
    ALL_CASES,
    DATA_CASES,
    STUDENT_SAFETY_CASES,
)


def test_eval_catalog_contains_exactly_100_sanitized_cases():
    assert len(ALL_CASES) == 100


def test_data_fact_fixture_accuracy_is_100_percent():
    correct = sum(
        all(key in case["facts"] for key in case["expected"])
        for case in DATA_CASES
    )
    assert correct / len(DATA_CASES) >= 0.98


def test_permission_leak_fixture_count_is_zero():
    assert all("peer_student_id" not in case for case in STUDENT_SAFETY_CASES)
    assert all(case["forbidden"] == "apiKey" for case in ADMIN_SAFETY_CASES)
