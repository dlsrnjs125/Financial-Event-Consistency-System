"""Repository for account persistence operations."""

from sqlalchemy.orm import Session

from app.models.account import Account


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_account_no(self, account_no: str) -> Account | None:
        return (
            self.session.query(Account)
            .filter(Account.account_no == account_no)
            .one_or_none()
        )

    def get_by_account_no_for_update(self, account_no: str) -> Account | None:
        return (
            self.session.query(Account)
            .filter(Account.account_no == account_no)
            .with_for_update()
            .one_or_none()
        )

    def get_by_id_for_update(self, account_id: int) -> Account | None:
        return (
            self.session.query(Account)
            .filter(Account.id == account_id)
            .with_for_update()
            .one_or_none()
        )

    def update_balance(self, account: Account, new_balance: int) -> Account:
        account.balance = new_balance
        self.session.flush()
        return account
