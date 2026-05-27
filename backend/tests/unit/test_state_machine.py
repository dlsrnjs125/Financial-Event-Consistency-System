"""
Unit tests for State Machine
"""

from enum import Enum

import pytest


class TransactionStatus(Enum):
    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class InvalidStateTransition(Exception):
    pass


class TransactionStateMachine:
    ALLOWED_TRANSITIONS = {
        TransactionStatus.RECEIVED: {
            TransactionStatus.VALIDATED,
            TransactionStatus.FAILED,
        },
        TransactionStatus.VALIDATED: {
            TransactionStatus.PROCESSING,
            TransactionStatus.FAILED,
        },
        TransactionStatus.PROCESSING: {
            TransactionStatus.COMPLETED,
            TransactionStatus.FAILED,
        },
        TransactionStatus.COMPLETED: {TransactionStatus.SETTLED},
        TransactionStatus.SETTLED: set(),
        TransactionStatus.FAILED: set(),
        TransactionStatus.CANCELLED: set(),
    }

    def __init__(self, initial_status: TransactionStatus):
        self.current_status = initial_status

    def can_transition_to(self, next_status: TransactionStatus) -> bool:
        allowed = self.ALLOWED_TRANSITIONS.get(self.current_status, set())
        return next_status in allowed

    def transition_to(self, next_status: TransactionStatus) -> None:
        if not self.can_transition_to(next_status):
            allowed = [
                s.value
                for s in self.ALLOWED_TRANSITIONS.get(self.current_status, set())
            ]
            message = (
                f"Cannot transition from {self.current_status.value} "
                f"to {next_status.value}. Allowed: {allowed}"
            )
            raise InvalidStateTransition(message)
        self.current_status = next_status


class TestStateMachine:
    def test_normal_transaction_flow(self):
        """Test normal transaction flow"""
        sm = TransactionStateMachine(TransactionStatus.RECEIVED)

        sm.transition_to(TransactionStatus.VALIDATED)
        assert sm.current_status == TransactionStatus.VALIDATED

        sm.transition_to(TransactionStatus.PROCESSING)
        assert sm.current_status == TransactionStatus.PROCESSING

        sm.transition_to(TransactionStatus.COMPLETED)
        assert sm.current_status == TransactionStatus.COMPLETED

        sm.transition_to(TransactionStatus.SETTLED)
        assert sm.current_status == TransactionStatus.SETTLED

    def test_completed_cannot_go_back_to_processing(self):
        """Test that completed transaction cannot go back to processing"""
        sm = TransactionStateMachine(TransactionStatus.COMPLETED)

        with pytest.raises(InvalidStateTransition):
            sm.transition_to(TransactionStatus.PROCESSING)

    def test_failed_cannot_become_completed(self):
        """Test that failed transaction cannot become completed"""
        sm = TransactionStateMachine(TransactionStatus.FAILED)

        with pytest.raises(InvalidStateTransition):
            sm.transition_to(TransactionStatus.COMPLETED)

    def test_received_can_fail(self):
        """Test that received transaction can fail"""
        sm = TransactionStateMachine(TransactionStatus.RECEIVED)

        sm.transition_to(TransactionStatus.FAILED)
        assert sm.current_status == TransactionStatus.FAILED

    def test_settled_is_final_state(self):
        """Test that settled is a final state"""
        sm = TransactionStateMachine(TransactionStatus.SETTLED)

        with pytest.raises(InvalidStateTransition):
            sm.transition_to(TransactionStatus.COMPLETED)

        with pytest.raises(InvalidStateTransition):
            sm.transition_to(TransactionStatus.PROCESSING)

    def test_invalid_direct_transition_received_to_completed(self):
        """Test that RECEIVED cannot go directly to COMPLETED (skipping validation)"""
        sm = TransactionStateMachine(TransactionStatus.RECEIVED)

        with pytest.raises(InvalidStateTransition):
            sm.transition_to(TransactionStatus.COMPLETED)

    def test_can_transition_to(self):
        """Test can_transition_to method"""
        sm = TransactionStateMachine(TransactionStatus.VALIDATED)

        assert sm.can_transition_to(TransactionStatus.PROCESSING) is True
        assert sm.can_transition_to(TransactionStatus.FAILED) is True
        assert sm.can_transition_to(TransactionStatus.RECEIVED) is False
        assert sm.can_transition_to(TransactionStatus.COMPLETED) is False
