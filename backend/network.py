"""Fixed-provider JSON transport with bounded responses and no credential logging."""
import json
import re
import socket
import urllib.error
import urllib.request


class ServiceError(Exception):
    def __init__(self, code, uncertain=False):
        super().__init__(code)
        self.code, self.uncertain = code, uncertain


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ProviderHTTP:
    def post(self, url, token, body, timeout=45):
        if not url.startswith(("https://api.openai.com/v1/responses", "https://graph.facebook.com/v")):
            raise ServiceError("provider_endpoint_rejected")
        request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode(),
                                         headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
                                         method="POST")
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ServiceError("provider_response_too_large", True)
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            # Persist only a numeric provider error code, never its echoed request or credentials.
            suffix = ""
            try:
                detail = json.loads(error.read(8192)).get("error", {}).get("code", "")
                if re.fullmatch(r"[0-9]{1,12}", str(detail)):
                    suffix = "_code_" + str(detail)
            except Exception:
                pass
            raise ServiceError("provider_http_" + str(error.code) + suffix, error.code >= 500 or error.code == 408) from None
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError):
            raise ServiceError("provider_network_or_timeout", True) from None
        except (ValueError, TypeError):
            raise ServiceError("provider_invalid_response", True) from None
