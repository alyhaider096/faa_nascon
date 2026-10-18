"""Independent Section 5.3 oracle; never imports production signing code."""
import hashlib
import hmac
import json


SIGNED_FIELDS = {
    "stream/key": ("action", "player_id", "status", "stream_key"),
    "costream/session": ("active_host", "handoff_occurred", "layout", "participant_count", "session_id", "status"),
    "qr": ("entity_id", "short_url", "target_route"),
    "guest/cart-merge": ("cart_merged", "guest_token", "registered_user_id", "total_items", "write_rejection_code"),
    "moderation/test": ("chat_room_id", "flagged_count", "kicked_users", "queue_depth"),
}


def sign(salt: str, entity_id: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    message = (entity_id + "|" + canonical).encode("utf-8")
    return hmac.new(salt.encode("utf-8"), message, hashlib.sha256).hexdigest()


def signed_payload(route: str, response: dict) -> dict:
    """Extract only the contract's signed keys, failing on missing fields.

    Callers supply flagged_count explicitly for moderation because the source
    response example omits it; do not silently infer it from another count.
    """
    values = dict(response)
    if route == "guest/cart-merge":
        values["total_items"] = response["active_cart"]["total_items"]
        values["registered_user_id"] = response["active_cart"]["user_id"]
    elif route == "moderation/test":
        values["queue_depth"] = response["dlq_status"]["queue_depth"]
    return {key: values[key] for key in SIGNED_FIELDS[route]}
