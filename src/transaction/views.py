"""This module defines the logic for the `/transaction` endpoint."""
import json
from urllib.parse import urlencode

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from django.conf import settings
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_exempt

from helpers import render_error_response, validate_sep10_token, validate_jwt_request
from .models import Transaction
from .serializers import TransactionSerializer


def _validate_limit(limit):
    limit = int(limit or settings.DEFAULT_PAGE_SIZE)
    if limit < 1:
        raise ValueError
    return limit


def _compute_qset_filters(req_params, translation_dict):
    """
    _compute_qset_filters translates the keys of req_params to the keys of translation_dict.
    If the key isn't present in filters_dict, it is discarded.
    """

    return {
        translation_dict[rp]: req_params[rp]
        for rp in filter(lambda i: i in translation_dict, req_params.keys())
    }


def _get_transaction_from_request(request):
    translation_dict = {
        "id": "id",
        "stellar_transaction_id": "stellar_transaction_id",
        "external_transaction_id": "external_transaction_id",
    }

    qset_filter = _compute_qset_filters(request.GET, translation_dict)
    if not qset_filter:
        raise AttributeError(
            "at least one of id, stellar_transaction_id, or external_transaction_id must be provided"
        )
    try:
        return Transaction.objects.get(**qset_filter)
    except Transaction.DoesNotExist as exc:
        raise exc


def _construct_more_info_url(request):
    qparams_dict = {}
    transaction_id = request.GET.get("id")
    if transaction_id:
        qparams_dict["id"] = transaction_id
    stellar_transaction_id = request.GET.get("stellar_transaction_id")
    if stellar_transaction_id:
        qparams_dict["stellar_transaction_id"] = stellar_transaction_id
    external_transaction_id = request.GET.get("external_transaction_id")
    if external_transaction_id:
        qparams_dict["external_transaction_id"] = external_transaction_id

    qparams = urlencode(qparams_dict)
    path = reverse("more_info")
    path_params = f"{path}?{qparams}"
    return request.build_absolute_uri(path_params)


@xframe_options_exempt
@api_view()
def more_info(request):
    """
    Popup to display more information about a specific transaction.
    See table: https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0024.md#4-customer-information-status
    """
    try:
        request_transaction = _get_transaction_from_request(request)
    except AttributeError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Transaction.DoesNotExist:
        return Response(
            {"error": "transaction not found"}, status=status.HTTP_404_NOT_FOUND
        )

    serializer = TransactionSerializer(
        request_transaction,
        context={"more_info_url": _construct_more_info_url(request)},
    )
    tx_json = json.dumps({"transaction": serializer.data})
    return render(
        request,
        "transaction/more_info.html",
        context={
            "tx_json": tx_json,
            "transaction": request_transaction,
            "asset_code": request_transaction.asset.code,
        },
    )


@validate_sep10_token()
@api_view()
def transactions(request):
    """
    Definition of the /transactions endpoint, in accordance with SEP-0024.
    See: https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0024.md#transaction-history
    """
    try:
        limit = _validate_limit(request.GET.get("limit"))
    except ValueError:
        return Response({"error": "invalid limit"}, status=status.HTTP_400_BAD_REQUEST)

    if not request.GET.get("asset_code") or not request.GET.get("account"):
        return Response(
            {"error": "asset_code and account are required fields"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    translation_dict = {
        "asset_code": "asset__code",
        "account": "stellar_account",
        "no_older_than": "started_at__gte",
        "kind": "kind",
    }

    qset_filter = _compute_qset_filters(request.GET, translation_dict)

    # Since the Transaction IDs are UUIDs, rather than in the chronological
    # order of their creation, we map the paging ID (if provided) to the
    # started_at field of a Transaction.
    paging_id = request.GET.get("paging_id")
    if paging_id:
        try:
            start_transaction = Transaction.objects.get(id=paging_id)
        except Transaction.DoesNotExist:
            return Response(
                {"error": "invalid paging_id"}, status=status.HTTP_400_BAD_REQUEST
            )
        qset_filter["started_at__lt"] = start_transaction.started_at

    transactions_qset = Transaction.objects.filter(**qset_filter)[:limit]
    serializer = TransactionSerializer(
        transactions_qset,
        many=True,
        context={"more_info_url": _construct_more_info_url(request)},
    )

    return Response({"transactions": serializer.data})


@validate_sep10_token()
@api_view()
def transaction(request):
    """
    Definition of the /transaction endpoint, in accordance with SEP-0024.
    See: https://github.com/stellar/stellar-protocol/blob/master/ecosystem/sep-0024.md#single-historical-transaction
    """
    try:
        request_transaction = _get_transaction_from_request(request)
    except AttributeError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Transaction.DoesNotExist:
        return Response(
            {"error": "transaction not found"}, status=status.HTTP_404_NOT_FOUND
        )
    serializer = TransactionSerializer(
        request_transaction,
        context={"more_info_url": _construct_more_info_url(request)},
    )
    return Response({"transaction": serializer.data})
