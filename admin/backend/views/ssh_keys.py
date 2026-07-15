from __future__ import annotations

from flask import Blueprint, jsonify, request

from admin.backend.api_contract import error_response
from pilot.core.ssh_keys import AuthorizedKeysStore, SSHKey, SSHKeyError

ssh_keys_bp = Blueprint("ssh_keys", __name__)


def _serialize(key: SSHKey) -> dict:
    return {"fingerprint": key.fingerprint, "type": key.key_type, "comment": key.comment}


@ssh_keys_bp.route("/", methods=["GET"])
def list_keys():
    return jsonify({"keys": [_serialize(key) for key in AuthorizedKeysStore().list()]})


@ssh_keys_bp.route("/", methods=["POST"])
def add_key():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("malformed_request", "Expected a JSON object.", 400)
    public_key = str(data.get("public_key", "")).strip()
    if not public_key:
        return error_response("invalid_ssh_key", "A public key is required.", 422)
    try:
        key = AuthorizedKeysStore().add(public_key)
    except SSHKeyError as error:
        return error_response("invalid_ssh_key", str(error), 422)
    return jsonify({"ok": True, "key": _serialize(key)})


@ssh_keys_bp.route("/", methods=["DELETE"])
def remove_key():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("malformed_request", "Expected a JSON object.", 400)
    fingerprint = str(data.get("fingerprint", "")).strip()
    if not fingerprint:
        return error_response("invalid_fingerprint", "A fingerprint is required.", 422)
    try:
        AuthorizedKeysStore().remove(fingerprint)
    except SSHKeyError as error:
        return error_response("ssh_key_removal_rejected", str(error), 409)
    return jsonify({"ok": True})
