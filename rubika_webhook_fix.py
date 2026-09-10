"""Make Rubika webhook registration compatible with provider endpoint validation."""


def install():
    import server
    import rubika_v2 as rb

    if getattr(server, "_netyar_rubika_webhook_fix", False):
        return

    # Rubika documentation/examples commonly use a receiveUpdate endpoint.
    # Keep the existing /rubika/update endpoint alive for already-configured
    # bots, but expose the conventional path for endpoint validation.
    if not getattr(server, "_netyar_rubika_receive_route", False):
        server.api.add_api_route(
            "/rubika/receiveUpdate",
            server.rubika_update,
            methods=["POST"],
        )
        server.api.add_api_route(
            "/rubika/receiveUpdate",
            server.rubika_update_probe,
            methods=["GET"],
        )
        server.api.add_api_route(
            "/rubika/receiveUpdate",
            server.rubika_update_head,
            methods=["HEAD"],
        )
        server._netyar_rubika_receive_route = True

    original_call = rb.call
    if not getattr(rb, "_netyar_webhook_call_fixed", False):
        def call_fixed(method, p=None):
            payload = dict(p or {})
            if method == "updateBotEndpoints" and payload.get("type") == "ReceiveUpdate":
                url = str(payload.get("url") or "")
                if url.endswith("/rubika/update"):
                    payload["url"] = url[:-len("/rubika/update")] + "/rubika/receiveUpdate"
            return original_call(method, payload)
        rb.call = call_fixed
        rb._netyar_webhook_call_fixed = True

    server._netyar_rubika_webhook_fix = True
