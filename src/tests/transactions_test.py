"""This module tests the `/transactions` endpoint."""
import json
import urllib
from unittest.mock import patch

import pytest
from django.conf import settings
from stellar_sdk.keypair import Keypair
from stellar_sdk.transaction_envelope import TransactionEnvelope

from .helpers import mock_check_auth_success, mock_render_error_response


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_required_fields(mock_check, client, acc2_eth_withdrawal_transaction_factory):
    """Fails without required parameters."""
    del mock_check
    acc2_eth_withdrawal_transaction_factory()

    response = client.get(f"/transactions", follow=True)

    content = json.loads(response.content)
    assert response.status_code == 400
    assert content.get("error") is not None


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_required_account(mock_check, client, acc2_eth_withdrawal_transaction_factory):
    """Fails without `account` parameter."""
    del mock_check
    withdrawal = acc2_eth_withdrawal_transaction_factory()

    response = client.get(
        f"/transactions?asset_code={withdrawal.asset.code}", follow=True
    )

    content = json.loads(response.content)
    assert response.status_code == 400
    assert content.get("error") is not None


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_required_asset_code(
    mock_check, client, acc2_eth_withdrawal_transaction_factory
):
    """Fails without `asset_code` parameter."""
    del mock_check
    withdrawal = acc2_eth_withdrawal_transaction_factory()

    response = client.get(
        f"/transactions?account={withdrawal.stellar_account}", follow=True
    )

    content = json.loads(response.content)
    assert response.status_code == 400
    assert content.get("error") is not None


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_transactions_format(
    mock_check,
    client,
    acc2_eth_withdrawal_transaction_factory,
    acc2_eth_deposit_transaction_factory,
):
    """Response has correct length and status code."""
    del mock_check
    withdrawal = acc2_eth_withdrawal_transaction_factory()
    acc2_eth_deposit_transaction_factory()

    response = client.get(
        f"/transactions?asset_code={withdrawal.asset.code}&account={withdrawal.stellar_account}",
        follow=True,
    )
    content = json.loads(response.content)

    assert len(content.get("transactions")) == 2
    assert response.status_code == 200


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_transactions_order(
    mock_check,
    client,
    acc2_eth_withdrawal_transaction_factory,
    acc2_eth_deposit_transaction_factory,
):
    """Transactions are serialized in expected order."""
    del mock_check
    acc2_eth_deposit_transaction_factory()  # older transaction
    withdrawal = acc2_eth_withdrawal_transaction_factory()  # newer transaction

    response = client.get(
        f"/transactions?asset_code={withdrawal.asset.code}&account={withdrawal.stellar_account}",
        follow=True,
    )
    content = json.loads(response.content)

    # Withdrawal comes first, since transactions are ordered by -id
    withdrawal_transaction = content.get("transactions")[0]
    deposit_transaction = content.get("transactions")[1]

    assert withdrawal_transaction["kind"] == "withdrawal"
    assert deposit_transaction["kind"] == "deposit"


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_transactions_content(
    mock_check,
    client,
    acc2_eth_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """
    This expected response was adapted from the example SEP-0024 response on
    https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0024.md#transaction-history
    Some changes have been applied, to ensure the data we provide is in a consistent format and
    in accordance with design decisions from this reference implementation:

    - amounts are floats, so values like "500" are displayed as "500.0"
    - nullable fields are displayed, but with a null value
    """
    del mock_check
    deposit = acc2_eth_deposit_transaction_factory()
    withdrawal = acc2_eth_withdrawal_transaction_factory()

    d_started_at = deposit.started_at.isoformat().replace("+00:00", "Z")
    w_started_at = withdrawal.started_at.isoformat().replace("+00:00", "Z")
    w_completed_at = withdrawal.completed_at.isoformat().replace("+00:00", "Z")

    response = client.get(
        f"/transactions?asset_code={withdrawal.asset.code}&account={withdrawal.stellar_account}",
        follow=True,
    )
    content = json.loads(response.content)

    withdrawal_transaction = content.get("transactions")[0]
    deposit_transaction = content.get("transactions")[1]

    # Verifying the withdrawal transaction data:
    assert withdrawal_transaction["id"] == str(withdrawal.id)
    assert withdrawal_transaction["kind"] == withdrawal.kind
    assert withdrawal_transaction["status"] == withdrawal.status
    assert withdrawal_transaction["status_eta"] == 3600
    assert withdrawal_transaction["amount_in"] == str(withdrawal.amount_in)
    assert withdrawal_transaction["amount_out"] == str(withdrawal.amount_out)
    assert withdrawal_transaction["amount_fee"] == str(float(withdrawal.amount_fee))
    assert withdrawal_transaction["started_at"] == w_started_at
    assert withdrawal_transaction["completed_at"] == w_completed_at
    assert (
        withdrawal_transaction["stellar_transaction_id"]
        == withdrawal.stellar_transaction_id
    )
    assert (
        withdrawal_transaction["external_transaction_id"]
        == withdrawal.external_transaction_id
    )
    assert withdrawal_transaction["from_address"] is None
    assert withdrawal_transaction["to_address"] is None
    assert withdrawal_transaction["external_extra"] is None
    assert withdrawal_transaction["external_extra_text"] is None
    assert withdrawal_transaction["deposit_memo"] is None
    assert withdrawal_transaction["deposit_memo_type"] == withdrawal.deposit_memo_type
    assert (
        withdrawal_transaction["withdraw_anchor_account"]
        == withdrawal.withdraw_anchor_account
    )
    assert withdrawal_transaction["withdraw_memo"] == withdrawal.withdraw_memo
    assert withdrawal_transaction["withdraw_memo_type"] == withdrawal.withdraw_memo_type

    # Verifying the deposit transaction data:
    assert deposit_transaction["id"] == str(deposit.id)
    assert deposit_transaction["kind"] == deposit.kind
    assert deposit_transaction["status"] == deposit.status
    assert deposit_transaction["status_eta"] == deposit.status_eta
    assert deposit_transaction["amount_in"] == str(deposit.amount_in)
    assert deposit_transaction["amount_out"] == str(deposit.amount_out)
    assert deposit_transaction["amount_fee"] == str(float(deposit.amount_fee))
    assert deposit_transaction["started_at"] == d_started_at
    assert deposit_transaction["completed_at"] is None
    assert deposit_transaction["stellar_transaction_id"] is None
    assert (
        deposit_transaction["external_transaction_id"]
        == deposit.external_transaction_id
    )
    assert deposit_transaction["from_address"] is None
    assert deposit_transaction["to_address"] is None
    assert deposit_transaction["external_extra"] is None
    assert deposit_transaction["external_extra_text"] is None
    assert deposit_transaction["deposit_memo"] == deposit.deposit_memo
    assert deposit_transaction["deposit_memo_type"] == deposit.deposit_memo_type
    assert deposit_transaction["withdraw_anchor_account"] is None
    assert deposit_transaction["withdraw_memo"] is None
    assert deposit_transaction["withdraw_memo_type"] == deposit.withdraw_memo_type

    # stellar_account and asset should not be exposed:
    with pytest.raises(KeyError):
        assert withdrawal_transaction["stellar_account"]
    with pytest.raises(KeyError):
        assert withdrawal_transaction["asset"]
    with pytest.raises(KeyError):
        assert deposit_transaction["stellar_account"]
    with pytest.raises(KeyError):
        assert deposit_transaction["asset"]


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_paging_id(
    mock_check,
    client,
    acc2_eth_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """Only return transactions chronologically after a `paging_id`, if provided."""
    del mock_check
    acc2_eth_deposit_transaction_factory()
    withdrawal = acc2_eth_withdrawal_transaction_factory()

    response = client.get(
        (
            f"/transactions?asset_code={withdrawal.asset.code}"
            f"&account={withdrawal.stellar_account}"
            f"&paging_id={withdrawal.id}"
        ),
        follow=True,
    )
    content = json.loads(response.content)

    # By providing the paging_id = w.id, we're looking for entries older than `w`
    # which only leaves us with the deposit transaction.
    assert len(content.get("transactions")) == 1
    assert content.get("transactions")[0]["kind"] == "deposit"


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_kind_filter(
    mock_check,
    client,
    acc2_eth_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """Valid `kind` succeeds."""
    del mock_check
    acc2_eth_deposit_transaction_factory()
    withdrawal = acc2_eth_withdrawal_transaction_factory()

    response = client.get(
        (
            f"/transactions?asset_code={withdrawal.asset.code}"
            f"&account={withdrawal.stellar_account}"
            f"&kind=deposit"
        ),
        follow=True,
    )
    content = json.loads(response.content)

    # By providing the paging_id = w.id, we're looking for entries older than `w`
    # which only leaves us with the deposit transaction.
    assert len(content.get("transactions")) == 1
    assert content.get("transactions")[0]["kind"] == "deposit"


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_kind_filter_no_500(
    mock_check,
    client,
    acc2_eth_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """Invalid `kind` fails gracefully."""
    del mock_check
    acc2_eth_deposit_transaction_factory()
    withdrawal = acc2_eth_withdrawal_transaction_factory()

    response = client.get(
        (
            f"/transactions?asset_code={withdrawal.asset.code}"
            f"&account={withdrawal.stellar_account}&kind=somethingelse"
        ),
        follow=True,
    )
    content = json.loads(response.content)

    # By providing the paging_id = w.id, we're looking for entries older than `w`
    # which only leaves us with the deposit transaction.
    assert not content.get("transactions")


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_limit(
    mock_check,
    client,
    acc2_eth_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """Valid `limit` succeeds."""
    del mock_check
    acc2_eth_deposit_transaction_factory()
    withdrawal = acc2_eth_withdrawal_transaction_factory()  # newest

    response = client.get(
        f"/transactions?asset_code={withdrawal.asset.code}"
        f"&account={withdrawal.stellar_account}&limit=1",
        follow=True,
    )
    content = json.loads(response.content)

    # By providing the paging_id = w.id, we're looking for entries older than `w`
    # which only leaves us with the deposit transaction.
    assert len(content.get("transactions")) == 1
    assert content.get("transactions")[0]["kind"] == "withdrawal"


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_invalid_limit(
    mock_check,
    client,
    acc2_eth_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """Non-integer `limit` fails."""
    del mock_check
    acc2_eth_deposit_transaction_factory()
    withdrawal = acc2_eth_withdrawal_transaction_factory()  # newest

    response = client.get(
        (
            f"/transactions?asset_code={withdrawal.asset.code}"
            f"&account={withdrawal.stellar_account}&limit=string"
        ),
        follow=True,
    )
    content = json.loads(response.content)

    assert content.get("error") is not None
    assert response.status_code == 400


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_negative_limit(
    mock_check,
    client,
    acc2_eth_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """Negative `limit` fails."""
    del mock_check
    acc2_eth_deposit_transaction_factory()
    withdrawal = acc2_eth_withdrawal_transaction_factory()  # newest

    response = client.get(
        (
            f"/transactions?asset_code={withdrawal.asset.code}"
            f"&account={withdrawal.stellar_account}&limit=-1"
        ),
        follow=True,
    )
    content = json.loads(response.content)

    assert content.get("error") is not None
    assert response.status_code == 400


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_no_older_than_filter(
    mock_check,
    client,
    acc2_eth_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """Valid `no_older_than` succeeds."""
    del mock_check
    withdrawal_transaction = (
        acc2_eth_withdrawal_transaction_factory()
    )  # older transaction
    deposit_transaction = acc2_eth_deposit_transaction_factory()  # newer transaction

    urlencoded_datetime = urllib.parse.quote(deposit_transaction.started_at.isoformat())
    response = client.get(
        (
            f"/transactions?asset_code={withdrawal_transaction.asset.code}"
            f"&account={withdrawal_transaction.stellar_account}"
            f"&no_older_than={urlencoded_datetime}"
        ),
        follow=True,
    )
    content = json.loads(response.content)

    assert response.status_code == 200
    assert len(content.get("transactions")) == 1
    assert content.get("transactions")[0]["kind"] == "deposit"


@pytest.mark.django_db
@patch("helpers.render_error_response", side_effect=mock_render_error_response)
def test_transactions_authenticated_success(
    mock_render,
    client,
    acc2_eth_withdrawal_transaction_factory,
    acc2_eth_deposit_transaction_factory,
):
    """
    Response has correct length and status code, if the SEP 10 authentication
    token is required.
    """
    del mock_render
    client_address = "GDKFNRUATPH4BSZGVFDRBIGZ5QAFILVFRIRYNSQ4UO7V2ZQAPRNL73RI"
    client_seed = "SDKWSBERDHP3SXW5A3LXSI7FWMMO5H7HG33KNYBKWH2HYOXJG2DXQHQY"
    withdrawal = acc2_eth_withdrawal_transaction_factory()
    withdrawal.stellar_address = client_address
    withdrawal.save()
    acc2_eth_deposit_transaction_factory()

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

    # For testing, we make the key `HTTP_AUTHORIZATION`. This is the value that
    # we expect due to the middleware.
    header = {"HTTP_AUTHORIZATION": f"Bearer {encoded_jwt}"}

    response = client.get(
        f"/transactions?asset_code={withdrawal.asset.code}&account={withdrawal.stellar_account}",
        follow=True,
        **header,
    )
    content = json.loads(response.content)

    assert len(content.get("transactions")) == 2
    assert response.status_code == 200


@pytest.mark.django_db
@patch("helpers.render_error_response", side_effect=mock_render_error_response)
def test_transactions_no_jwt(
    mock_render, client, acc2_eth_withdrawal_transaction_factory
):
    """`GET /transactions` fails if a required JWT is not provided."""
    del mock_render
    withdrawal = acc2_eth_withdrawal_transaction_factory()
    response = client.get(
        f"/transactions?asset_code={withdrawal.asset.code}&account={withdrawal.stellar_account}",
        follow=True,
    )
    content = json.loads(response.content)
    assert response.status_code == 400
    assert content == {"error": "JWT must be passed as 'Authorization' header"}
