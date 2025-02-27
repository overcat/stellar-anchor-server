"""This module tests the `/withdraw` endpoint."""
import json
from unittest.mock import patch

import pytest
from django.conf import settings
from helpers import format_memo_horizon
from stellar_sdk.keypair import Keypair
from stellar_sdk.transaction_envelope import TransactionEnvelope
from transaction.management.commands.watch_transactions import process_withdrawal
from transaction.models import Transaction

from .helpers import mock_check_auth_success, mock_render_error_response


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_withdraw_success(mock_check, client, acc1_usd_withdrawal_transaction_factory):
    """`GET /withdraw` succeeds with no optional arguments."""
    del mock_check
    acc1_usd_withdrawal_transaction_factory()
    response = client.get(f"/withdraw?asset_code=USD", follow=True)
    content = json.loads(response.content)
    assert response.status_code == 403
    assert content["type"] == "interactive_customer_info_needed"


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_withdraw_invalid_asset(
    mock_check, client, acc1_usd_withdrawal_transaction_factory
):
    """`GET /withdraw` fails with an invalid asset argument."""
    del mock_check
    acc1_usd_withdrawal_transaction_factory()
    response = client.get(f"/withdraw?asset_code=ETH", follow=True)
    content = json.loads(response.content)
    assert response.status_code == 400
    assert content == {"error": "invalid operation for asset ETH"}


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_withdraw_no_asset(mock_check, client):
    """`GET /withdraw fails with no asset argument."""
    del mock_check
    response = client.get(f"/withdraw", follow=True)
    content = json.loads(response.content)
    assert response.status_code == 400
    assert content == {"error": "'asset_code' is required"}


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_withdraw_interactive_no_txid(
    mock_check, client, acc1_usd_withdrawal_transaction_factory
):
    """
    `GET /withdraw/interactive_withdraw` fails with no transaction_id.
    """
    del mock_check
    acc1_usd_withdrawal_transaction_factory()
    response = client.get(f"/withdraw/interactive_withdraw?", follow=True)
    content = json.loads(response.content)
    assert response.status_code == 400
    assert content == {"error": "no 'transaction_id' provided"}


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_withdraw_interactive_no_asset(
    mock_check, client, acc1_usd_withdrawal_transaction_factory
):
    """
    `GET /withdraw/interactive_withdraw` fails with no asset_code.
    """
    del mock_check
    acc1_usd_withdrawal_transaction_factory()
    response = client.get(
        f"/withdraw/interactive_withdraw?transaction_id=2", follow=True
    )
    content = json.loads(response.content)
    assert response.status_code == 400
    assert content == {"error": "invalid 'asset_code'"}


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_withdraw_interactive_invalid_asset(
    mock_check, client, acc1_usd_withdrawal_transaction_factory
):
    """
    `GET /withdraw/interactive_withdraw` fails with invalid asset_code.
    """
    del mock_check
    acc1_usd_withdrawal_transaction_factory()
    response = client.get(
        f"/withdraw/interactive_withdraw?transaction_id=2&asset_code=ETH", follow=True
    )
    content = json.loads(response.content)
    assert response.status_code == 400
    assert content == {"error": "invalid 'asset_code'"}


# TODO: Decompose the below tests, since they call the same logic. The issue: Pytest complains
# about decomposition when passing fixtures to a helper function.


@pytest.mark.django_db
@patch(
    "transaction.management.commands.watch_transactions.stream_transactions",
    return_value=[{}],
)
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_withdraw_interactive_failure_no_memotype(
    mock_check, mock_transactions, client, acc1_usd_withdrawal_transaction_factory
):
    """
    `GET /withdraw/interactive_withdraw` fails with no `memo_type` in Horizon response.
    """
    del mock_check, mock_transactions
    acc1_usd_withdrawal_transaction_factory()
    response = client.get(f"/withdraw?asset_code=USD", follow=True)
    content = json.loads(response.content)
    assert response.status_code == 403
    assert content["type"] == "interactive_customer_info_needed"

    transaction_id = content["id"]
    url = content["url"]
    response = client.post(
        url, {"amount": 20, "bank_account": "123456", "bank": "Bank"}
    )
    assert response.status_code == 200
    assert (
        Transaction.objects.get(id=transaction_id).status
        == Transaction.STATUS.pending_user_transfer_start
    )


@pytest.mark.django_db
@patch(
    "transaction.management.commands.watch_transactions.stream_transactions",
    return_value=[{"memo_type": "not_hash"}],
)
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_withdraw_interactive_failure_incorrect_memotype(
    mock_check, mock_transactions, client, acc1_usd_withdrawal_transaction_factory
):
    """
    `GET /withdraw/interactive_withdraw` fails with incorrect `memo_type` in Horizon response.
    """
    del mock_check, mock_transactions
    acc1_usd_withdrawal_transaction_factory()
    response = client.get(f"/withdraw?asset_code=USD", follow=True)
    content = json.loads(response.content)
    assert response.status_code == 403
    assert content["type"] == "interactive_customer_info_needed"

    transaction_id = content["id"]
    url = content["url"]
    response = client.post(
        url, {"amount": 20, "bank_account": "123456", "bank": "Bank"}
    )
    assert response.status_code == 200
    assert (
        Transaction.objects.get(id=transaction_id).status
        == Transaction.STATUS.pending_user_transfer_start
    )


@pytest.mark.django_db
@patch(
    "transaction.management.commands.watch_transactions.stream_transactions",
    return_value=[{"memo_type": "hash"}],
)
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_withdraw_interactive_failure_no_memo(
    mock_check, mock_transactions, client, acc1_usd_withdrawal_transaction_factory
):
    """
    `GET /withdraw/interactive_withdraw` fails with no `memo` in Horizon response.
    """
    del mock_check, mock_transactions
    acc1_usd_withdrawal_transaction_factory()
    response = client.get(f"/withdraw?asset_code=USD", follow=True)
    content = json.loads(response.content)
    assert response.status_code == 403
    assert content["type"] == "interactive_customer_info_needed"

    transaction_id = content["id"]
    url = content["url"]
    response = client.post(
        url, {"amount": 20, "bank_account": "123456", "bank": "Bank"}
    )
    assert response.status_code == 200
    assert (
        Transaction.objects.get(id=transaction_id).status
        == Transaction.STATUS.pending_user_transfer_start
    )


@pytest.mark.django_db
@patch(
    "transaction.management.commands.watch_transactions.stream_transactions",
    return_value=[{"memo_type": "hash", "memo": "wrong_memo"}],
)
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_withdraw_interactive_failure_incorrect_memo(
    mock_check, mock_transactions, client, acc1_usd_withdrawal_transaction_factory
):
    """
    `GET /withdraw/interactive_withdraw` fails with incorrect `memo` in Horizon response.
    """
    del mock_check, mock_transactions
    acc1_usd_withdrawal_transaction_factory()
    response = client.get(f"/withdraw?asset_code=USD", follow=True)
    content = json.loads(response.content)
    assert response.status_code == 403
    assert content["type"] == "interactive_customer_info_needed"

    transaction_id = content["id"]
    url = content["url"]
    response = client.post(
        url, {"amount": 20, "bank_account": "123456", "bank": "Bank"}
    )
    assert response.status_code == 200
    assert (
        Transaction.objects.get(id=transaction_id).status
        == Transaction.STATUS.pending_user_transfer_start
    )


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_withdraw_interactive_success_transaction_unsuccessful(
    mock_check, client, acc1_usd_withdrawal_transaction_factory
):
    """
    `GET /withdraw/interactive_withdraw` changes transaction to `pending_stellar`
    with unsuccessful transaction.
    """
    del mock_check
    acc1_usd_withdrawal_transaction_factory()
    response = client.get(f"/withdraw?asset_code=USD", follow=True)
    content = json.loads(response.content)
    assert response.status_code == 403
    assert content["type"] == "interactive_customer_info_needed"

    transaction_id = content["id"]
    url = content["url"]
    response = client.post(
        url, {"amount": 50, "bank_account": "123456", "bank": "Bank"}
    )
    assert response.status_code == 200
    transaction = Transaction.objects.get(id=transaction_id)
    assert transaction.status == Transaction.STATUS.pending_user_transfer_start

    withdraw_memo = transaction.withdraw_memo
    mock_response = {
        "memo_type": "hash",
        "memo": format_memo_horizon(withdraw_memo),
        "successful": False,
        "id": "c5e8ada72c0e3c248ac7e1ec0ec97e204c06c295113eedbe632020cd6dc29ff8",
        "envelope_xdr": "AAAAAEU1B1qeJrucdqkbk1mJsnuFaNORfrOAzJyaAy1yzW8TAAAAZAAE2s4AAAABAAAAAAAAAAAAAAABAAAAAAAAAAEAAAAAoUKq+1Z2GGB98qurLSmocHafvG6S+YzKNE6oiHIXo6kAAAABVVNEAAAAAACnUE2lfwuFZ+G+dkc+qiL0MwxB0CoR0au324j+JC9exQAAAAAdzWUAAAAAAAAAAAA=",
    }
    process_withdrawal(mock_response, transaction)
    assert (
        Transaction.objects.get(id=transaction_id).status
        == Transaction.STATUS.pending_stellar
    )


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_withdraw_interactive_success_transaction_successful(
    mock_check, client, acc1_usd_withdrawal_transaction_factory
):
    """
    `GET /withdraw/interactive_withdraw` changes transaction to `completed`
    with successful transaction.
    """
    del mock_check
    acc1_usd_withdrawal_transaction_factory()
    response = client.get(f"/withdraw?asset_code=USD", follow=True)
    content = json.loads(response.content)
    assert response.status_code == 403
    assert content["type"] == "interactive_customer_info_needed"

    transaction_id = content["id"]
    url = content["url"]
    response = client.post(
        url, {"amount": 50, "bank_account": "123456", "bank": "Bank"}
    )
    assert response.status_code == 200
    transaction = Transaction.objects.get(id=transaction_id)
    assert transaction.status == Transaction.STATUS.pending_user_transfer_start

    withdraw_memo = transaction.withdraw_memo
    mock_response = {
        "memo_type": "hash",
        "memo": format_memo_horizon(withdraw_memo),
        "successful": True,
        "id": "c5e8ada72c0e3c248ac7e1ec0ec97e204c06c295113eedbe632020cd6dc29ff8",
        "envelope_xdr": "AAAAAEU1B1qeJrucdqkbk1mJsnuFaNORfrOAzJyaAy1yzW8TAAAAZAAE2s4AAAABAAAAAAAAAAAAAAABAAAAAAAAAAEAAAAAoUKq+1Z2GGB98qurLSmocHafvG6S+YzKNE6oiHIXo6kAAAABVVNEAAAAAACnUE2lfwuFZ+G+dkc+qiL0MwxB0CoR0au324j+JC9exQAAAAAdzWUAAAAAAAAAAAA=",
    }
    process_withdrawal(mock_response, transaction)

    assert transaction.status == Transaction.STATUS.completed
    assert transaction.completed_at


@pytest.mark.django_db
def test_withdraw_authenticated_success(
    client, acc1_usd_withdrawal_transaction_factory
):
    """`GET /withdraw` succeeds with the SEP 10 authentication flow."""
    client_address = "GDKFNRUATPH4BSZGVFDRBIGZ5QAFILVFRIRYNSQ4UO7V2ZQAPRNL73RI"
    client_seed = "SDKWSBERDHP3SXW5A3LXSI7FWMMO5H7HG33KNYBKWH2HYOXJG2DXQHQY"
    acc1_usd_withdrawal_transaction_factory()

    # SEP 10.
    response = client.get(f"/auth?account={client_address}", follow=True)
    content = json.loads(response.content)

    envelope_xdr = content["transaction"]
    envelope_object = TransactionEnvelope.from_xdr(envelope_xdr, network_passphrase=settings.STELLAR_NETWORK_PASSPHRASE)
    client_signing_key = Keypair.from_secret(client_seed)
    envelope_object.sign(client_signing_key)
    client_signed_envelope_xdr = envelope_object.to_xdr()

    response = client.post(
        "/auth",
        data={"transaction": client_signed_envelope_xdr},
        content_type="application/json",
    )
    content = json.loads(response.content)
    encoded_jwt = content["token"]
    assert encoded_jwt

    header = {"HTTP_AUTHORIZATION": f"Bearer {encoded_jwt}"}
    response = client.get(f"/withdraw?asset_code=USD", follow=True, **header)
    content = json.loads(response.content)
    assert response.status_code == 403
    assert content["type"] == "interactive_customer_info_needed"


@pytest.mark.django_db
@patch("helpers.render_error_response", side_effect=mock_render_error_response)
def test_withdraw_no_jwt(mock_render, client, acc1_usd_withdrawal_transaction_factory):
    """`GET /withdraw` fails if a required JWT isn't provided."""
    del mock_render
    acc1_usd_withdrawal_transaction_factory()
    response = client.get(f"/withdraw?asset_code=USD", follow=True)
    content = json.loads(response.content)
    assert response.status_code == 400
    assert content == {"error": "JWT must be passed as 'Authorization' header"}
