import json
import threading
import traceback

from classes.core import FM
from config.server import COOKIE_EXPIRE
from config.settings import DEFAULT_COOKIE_TOKEN_NAME
from helpers import random_hash

from cryptography.fernet import Fernet


def _new_session_secret(password):
    """форк: пароль в redis хранится зашифрованным ключом сессии; ключ — только в подписанной cookie
    (HttpOnly, Secure)."""
    key = Fernet.generate_key()
    return key.decode("ascii"), Fernet(key).encrypt(password.encode("utf-8")).decode("ascii")


def _set_session_cookie(request, token, key):
    request.set_secure_cookie(DEFAULT_COOKIE_TOKEN_NAME, token + "|" + key, COOKIE_EXPIRE,
                              httponly=True, secure=True, samesite="Lax")


class FMAuth:
    @staticmethod
    def authenticate_by_pam(request, username, password):
        rpc_request = FM.BaseAction.get_rpc_request()

        result = rpc_request.request('main/authenticate', login=username, password=password)
        answer = FM.BaseAction.process_result(result)

        if not answer.get('Error', False) and answer.get('data').get('status', False):
            try:
                redis = request.redis.get(threading.currentThread())
                """:type : connectors.RedisConnector.RedisConnector"""
                token = 'FM::session::' + username + '::' + random_hash()
                key, password_enc = _new_session_secret(password)
                params = {
                    "server": "localhost",
                    "user": username,
                    "password_enc": password_enc
                }
                redis.set(token, json.dumps(params))
                _set_session_cookie(request, token, key)
                return token
            except Exception as e:
                request.application.logger.error(
                    "Error in FMAuth: %s, traceback = %s" % (str(e), traceback.format_exc()))
                return False

        return False

    @staticmethod
    def authenticate_by_token(request, token):
        redis = request.redis.get(threading.currentThread())
        """:type : connectors.RedisConnector.RedisConnector"""
        if redis.exists(str(token)):
            try:
                params = json.loads(redis.get(token))
                if "password" in params:
                    # внешний токен (панель хостинга) содержит пароль — переводим его в формат сессии форка
                    key, params["password_enc"] = _new_session_secret(params.pop("password"))
                    redis.set(token, json.dumps(params))
                    _set_session_cookie(request, token, key)
                else:
                    raw = request.get_raw_session_cookie()
                    key = raw.split("|", 1)[1] if raw and "|" in raw else None
                    if key is None:
                        return False
                    _set_session_cookie(request, token, key)
                return token
            except Exception as e:
                request.application.logger.error(
                    "Error in FMAuth: %s, traceback = %s" % (str(e), traceback.format_exc()))
                return False

        return False

    @staticmethod
    def logout(request):
        try:
            token = request.get_secure_cookie(DEFAULT_COOKIE_TOKEN_NAME)
            redis = request.redis.get(threading.currentThread())
            """:type : connectors.RedisConnector.RedisConnector"""

            redis.delete(request.get_current_user() + '::session')
            redis.delete(token)

            request.clear_cookie("token")
            request.clear_cookie("locale")
        except Exception as e:
            request.application.logger.error(
                "Error in FMAuth: %s, traceback = %s" % (str(e), traceback.format_exc()))
            return False
