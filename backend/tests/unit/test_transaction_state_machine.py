"""Unit tests for the Phase 3 transaction state machine."""

import pytest

from app.domain.exceptions import InvalidStateTransition
from app.domain.transaction_state_machine import TransactionStateMachine
from app.domain.transaction_status import TransactionStatus


@pytest.mark.parametrize(
    ("current_status", "next_status"),
    [
        (TransactionStatus.RECEIVED, TransactionStatus.VALIDATED),
        (TransactionStatus.RECEIVED, TransactionStatus.FAILED),
        (TransactionStatus.VALIDATED, TransactionStatus.PROCESSING),
        (TransactionStatus.VALIDATED, TransactionStatus.FAILED),
        (TransactionStatus.PROCESSING, TransactionStatus.COMPLETED),
        (TransactionStatus.PROCESSING, TransactionStatus.FAILED),
        (TransactionStatus.COMPLETED, TransactionStatus.SETTLED),
        (TransactionStatus.COMPLETED, TransactionStatus.CANCELLED),
    ],
)
def test_allowed_transitions_succeed(current_status, next_status):
    TransactionStateMachine.validate_transition(current_status, next_status)


@pytest.mark.parametrize(
    ("current_status", "next_status"),
    [
        (TransactionStatus.COMPLETED, TransactionStatus.PROCESSING),
        (TransactionStatus.FAILED, TransactionStatus.COMPLETED),
        (TransactionStatus.SETTLED, TransactionStatus.CANCELLED),
        (TransactionStatus.RECEIVED, TransactionStatus.COMPLETED),
        (TransactionStatus.CANCELLED, TransactionStatus.COMPLETED),
        (TransactionStatus.SETTLED, TransactionStatus.PROCESSING),
    ],
)
def test_forbidden_transitions_raise_invalid_state_transition(
    current_status, next_status
):
    with pytest.raises(InvalidStateTransition) as exc_info:
        TransactionStateMachine.validate_transition(current_status, next_status)

    assert exc_info.value.current_status == current_status
    assert exc_info.value.next_status == next_status


def test_can_transition_accepts_string_status_values():
    assert TransactionStateMachine.can_transition("RECEIVED", "VALIDATED") is True
    assert TransactionStateMachine.can_transition("COMPLETED", "PROCESSING") is False


def test_allowed_next_statuses_returns_documented_transition_targets():
    assert TransactionStateMachine.allowed_next_statuses(
        TransactionStatus.RECEIVED
    ) == frozenset({TransactionStatus.VALIDATED, TransactionStatus.FAILED})
    assert TransactionStateMachine.allowed_next_statuses(
        TransactionStatus.COMPLETED
    ) == frozenset({TransactionStatus.SETTLED, TransactionStatus.CANCELLED})
    assert (
        TransactionStateMachine.allowed_next_statuses(TransactionStatus.SETTLED)
        == frozenset()
    )


@pytest.mark.parametrize(
    "status",
    [
        TransactionStatus.FAILED,
        TransactionStatus.CANCELLED,
        TransactionStatus.SETTLED,
    ],
)
def test_is_terminal_status_returns_true_for_terminal_statuses(status):
    assert TransactionStateMachine.is_terminal_status(status) is True


@pytest.mark.parametrize(
    "status",
    [
        TransactionStatus.RECEIVED,
        TransactionStatus.VALIDATED,
        TransactionStatus.PROCESSING,
        TransactionStatus.COMPLETED,
    ],
)
def test_is_terminal_status_returns_false_for_non_terminal_statuses(status):
    assert TransactionStateMachine.is_terminal_status(status) is False


def test_cancel_is_allowed_only_before_settlement_from_completed():
    assert TransactionStateMachine.can_cancel(TransactionStatus.COMPLETED) is True


@pytest.mark.parametrize(
    "status",
    [
        TransactionStatus.RECEIVED,
        TransactionStatus.VALIDATED,
        TransactionStatus.PROCESSING,
        TransactionStatus.FAILED,
        TransactionStatus.CANCELLED,
        TransactionStatus.SETTLED,
    ],
)
def test_cancel_is_not_allowed_from_non_completed_statuses(status):
    assert TransactionStateMachine.can_cancel(status) is False


def test_settled_cancel_raises_invalid_state_transition():
    with pytest.raises(InvalidStateTransition):
        TransactionStateMachine.validate_cancel_allowed(TransactionStatus.SETTLED)


@pytest.mark.parametrize("unknown_status", ["UNKNOWN", "", "completed"])
def test_unknown_status_string_raises_value_error(unknown_status):
    with pytest.raises(ValueError):
        TransactionStateMachine.allowed_next_statuses(unknown_status)
