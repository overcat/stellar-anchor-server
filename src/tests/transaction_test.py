"""This module tests `GET /transaction`."""
import json
from unittest.mock import patch

import pytest
from django.conf import settings
from stellar_sdk.keypair import Keypair
from stellar_sdk.transaction_envelope import TransactionEnvelope
from transaction.models import Transaction

from .helpers import mock_check_auth_success, mock_render_error_response


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_transaction_requires_param(
    mock_check,
    client,
    acc1_usd_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """Fails without parameters."""
    del mock_check
    acc1_usd_deposit_transaction_factory()
    acc2_eth_withdrawal_transaction_factory()

    response = client.get(f"/transaction", follow=True)
    content = json.loads(response.content)

    assert response.status_code == 400
    assert content.get("error")


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_transaction_id_filter_and_format(
    mock_check,
    client,
    acc1_usd_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """Succeeds with expected response if `id` provided."""
    del mock_check
    acc1_usd_deposit_transaction_factory()
    withdrawal = acc2_eth_withdrawal_transaction_factory()

    w_started_at = withdrawal.started_at.isoformat().replace("+00:00", "Z")
    w_completed_at = withdrawal.completed_at.isoformat().replace("+00:00", "Z")

    response = client.get(f"/transaction?id={withdrawal.id}", follow=True)
    content = json.loads(response.content)

    assert response.status_code == 200

    withdrawal_transaction = content.get("transaction")

    # Verifying the withdrawal transaction data:
    assert isinstance(withdrawal_transaction["id"], str)
    assert withdrawal_transaction["kind"] == "withdrawal"
    assert withdrawal_transaction["status"] == "completed"
    assert withdrawal_transaction["status_eta"] == 3600
    assert withdrawal_transaction["amount_in"] == "500.0"
    assert withdrawal_transaction["amount_out"] == "495.0"
    assert withdrawal_transaction["amount_fee"] == "3.0"
    assert withdrawal_transaction["started_at"] == w_started_at
    assert withdrawal_transaction["completed_at"] == w_completed_at
    assert (
        withdrawal_transaction["stellar_transaction_id"]
        == "17a670bc424ff5ce3b386dbfaae9990b66a2a37b4fbe51547e8794962a3f9e6a"
    )
    assert (
        withdrawal_transaction["external_transaction_id"]
        == "2dd16cb409513026fbe7defc0c6f826c2d2c65c3da993f747d09bf7dafd31094"
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


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_transaction_stellar_filter(
    mock_check,
    client,
    acc1_usd_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """Succeeds with expected response if `stellar_transaction_id` provided."""
    del mock_check
    acc1_usd_deposit_transaction_factory()
    withdrawal = acc2_eth_withdrawal_transaction_factory()

    response = client.get(
        f"/transaction?stellar_transaction_id={withdrawal.stellar_transaction_id}",
        follow=True,
    )
    content = json.loads(response.content)

    assert response.status_code == 200

    withdrawal_transaction = content.get("transaction")
    assert withdrawal_transaction["kind"] == "withdrawal"
    assert withdrawal_transaction["status"] == Transaction.STATUS.completed


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_transaction_external_filter(
    mock_check,
    client,
    acc1_usd_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """Succeeds with expected response if `external_transaction_id` provided."""
    del mock_check
    deposit = acc1_usd_deposit_transaction_factory()
    acc2_eth_withdrawal_transaction_factory()

    response = client.get(
        f"/transaction?external_transaction_id={deposit.external_transaction_id}",
        follow=True,
    )
    content = json.loads(response.content)

    assert response.status_code == 200

    withdrawal_transaction = content.get("transaction")
    assert withdrawal_transaction["kind"] == "deposit"
    assert (
        withdrawal_transaction["status"]
        == Transaction.STATUS.pending_user_transfer_start
    )


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_transaction_multiple_filters(
    mock_check,
    client,
    acc1_usd_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """Succeeds with expected response if multiple valid ids provided."""
    del mock_check
    acc1_usd_deposit_transaction_factory()
    withdrawal = acc2_eth_withdrawal_transaction_factory()

    response = client.get(
        (
            f"/transaction?id={withdrawal.id}"
            f"&external_transaction_id={withdrawal.external_transaction_id}"
            f"&stellar_transaction_id={withdrawal.stellar_transaction_id}"
        ),
        follow=True,
    )
    content = json.loads(response.content)

    assert response.status_code == 200

    withdrawal_transaction = content.get("transaction")

    # Verifying the withdrawal transaction data:
    assert isinstance(withdrawal_transaction["id"], str)
    assert withdrawal_transaction["kind"] == "withdrawal"
    assert withdrawal_transaction["status"] == Transaction.STATUS.completed


@pytest.mark.django_db
@patch("helpers.check_auth", side_effect=mock_check_auth_success)
def test_transaction_filtering_no_result(
    mock_check,
    client,
    acc1_usd_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """Succeeds with expected response if invalid combo of ids provided."""
    del mock_check
    deposit = acc1_usd_deposit_transaction_factory()
    withdrawal = acc2_eth_withdrawal_transaction_factory()

    response = client.get(
        (
            f"/transaction?id={deposit.id}"
            f"&external_transaction_id={withdrawal.external_transaction_id}"
            f"&stellar_transaction_id={withdrawal.stellar_transaction_id}"
        ),
        follow=True,
    )
    content = json.loads(response.content)

    assert response.status_code == 404
    assert content.get("error") is not None


@pytest.mark.django_db
@patch("helpers.render_error_response", side_effect=mock_render_error_response)
def test_transaction_authenticated_success(
    mock_render,
    client,
    acc1_usd_deposit_transaction_factory,
    acc2_eth_withdrawal_transaction_factory,
):
    """
    Succeeds with expected response if authentication required.
    Though it filters using the stellar transaction ID, the logic
    should apply in any case.
    """
    del mock_render
    client_address = "GDKFNRUATPH4BSZGVFDRBIGZ5QAFILVFRIRYNSQ4UO7V2ZQAPRNL73RI"
    client_seed = "SDKWSBERDHP3SXW5A3LXSI7FWMMO5H7HG33KNYBKWH2HYOXJG2DXQHQY"
    acc1_usd_deposit_transaction_factory()
    withdrawal = acc2_eth_withdrawal_transaction_factory()
    withdrawal.stellar_address = client_address
    withdrawal.save()

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
        f"/transaction?stellar_transaction_id={withdrawal.stellar_transaction_id}",
        follow=True,
        **header,
    )
    content = json.loads(response.content)

    assert response.status_code == 200

    withdrawal_transaction = content.get("transaction")
    assert withdrawal_transaction["kind"] == "withdrawal"
    assert withdrawal_transaction["status"] == Transaction.STATUS.completed


@pytest.mark.django_db
@patch("helpers.render_error_response", side_effect=mock_render_error_response)
def test_transaction_no_jwt(
    mock_render, client, acc2_eth_withdrawal_transaction_factory
):
    """Fails if required JWT is not provided."""
    del mock_render
    withdrawal = acc2_eth_withdrawal_transaction_factory()

    response = client.get(
        (
            f"/transaction?id={withdrawal.id}"
            f"&external_transaction_id={withdrawal.external_transaction_id}"
            f"&stellar_transaction_id={withdrawal.stellar_transaction_id}"
        ),
        follow=True,
    )
    content = json.loads(response.content)

    assert response.status_code == 400
    assert content == {"error": "JWT must be passed as 'Authorization' header"}
