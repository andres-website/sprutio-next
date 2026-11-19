import concurrent.futures
import json
import logging
import os
import threading
import traceback

import tornado.escape
import tornado.ioloop
import tornado.locale
import tornado.web

from config import server
from config.settings import DEFAULT_LOCALE, DEFAULT_LANGUAGE, DEFAULT_COOKIE_TOKEN_NAME
from core import FM


# Обработчики FM блокирующие (ходят в RPC синхронно) и исполняются в пуле потоков.
# В оригинале (форк tornado 4.3 от Beget) каждый запрос шёл в новом Thread и вызывал finish()
# прямо из него. В tornado 6 (asyncio) IOStream нельзя трогать из чужого потока, поэтому
# finish()/flush() из рабочего потока выполняются синхронно в потоке IOLoop (см. _on_loop).
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=int(os.getenv("FM_APP_WORKERS", "64")),
                                                  thread_name_prefix="fm-req")


class BaseHandler(tornado.web.RequestHandler):
    def __init__(self, application, request, **kwargs):
        self._fm_loop = None
        self._fm_worker = None
        super(BaseHandler, self).__init__(application=application, request=request, **kwargs)

    def _on_loop(self, fn, *args):
        """Выполнить fn в потоке IOLoop и дождаться результата (если вызвано из рабочего потока)."""
        if self._fm_worker is None or threading.current_thread() is not self._fm_worker:
            return fn(*args)
        done = concurrent.futures.Future()

        def callback():
            try:
                fn(*args)
                done.set_result(None)
            except BaseException as e:  # пробрасываем в рабочий поток, как было в оригинале
                done.set_exception(e)

        self._fm_loop.add_callback(callback)
        return done.result()

    def finish(self, chunk=None):
        return self._on_loop(super(BaseHandler, self).finish, chunk)

    # --- сессия (форк): cookie "token" = "<ключ redis>|<ключ шифрования пароля>" ---------------------
    def get_raw_session_cookie(self):
        raw = super(BaseHandler, self).get_secure_cookie(DEFAULT_COOKIE_TOKEN_NAME)
        return raw.decode("utf-8") if raw is not None else None

    def get_secure_cookie(self, name, value=None, max_age_days=31, min_version=None):
        """Для cookie сессии отдаёт только ключ redis — остальной код оригинала работает без изменений."""
        raw = super(BaseHandler, self).get_secure_cookie(name, value, max_age_days, min_version)
        if name == DEFAULT_COOKIE_TOKEN_NAME and raw is not None and b"|" in raw:
            raw = raw.split(b"|", 1)[0]
        return raw

    def flush(self, include_footers=False):
        return self._on_loop(super(BaseHandler, self).flush, include_footers)

    def initialize(self):
        pass

    def data_received(self, chunk):
        pass

    @property
    def config(self):
        return self.application.config

    @property
    def redis(self):
        return self.application.redis

    def json(self, data=None, code=200):
        self.set_status(code)
        self.set_header("Content-Type", "application/json; charset=UTF-8")

        if isinstance(data, dict) and data.get("error", False):
            self.set_status(500)

        try:
            answer = json.dumps(data, ensure_ascii=False)
        except TypeError:
            self.set_status(500)
            self.application.logger.error(
                "login:" + self.get_current_user() + ' -- Traceback:' + traceback.format_exc())
            answer = {
                "error": True,
                "message": "Serialization error"
            }

        self.write(answer)

    def on_finish(self):
        self.redis.close_current()

    def _handle_request_exception(self, e):
        self.application.logger.error("Handled exception in app.py: " + str(e) + "Traceback:" + traceback.format_exc())
        if isinstance(e, tornado.web.HTTPError):
            if e.status_code == 403:
                self.set_status(e.status_code)
                self.application.logger.error("login: None -- Traceback:" + traceback.format_exc())
                self.write('Error %s' % e.status_code)
                self.redirect(self.get_login_url())
            elif e.status_code in [404, 500, 503]:
                self.set_status(e.status_code)
                self.write('Error %s' % e.status_code)
        else:
            self.application.logger.error(
                "login:" + self.get_current_user() + ' -- Traceback:' + traceback.format_exc())
            self.set_status(500)
            self.write(json.dumps({'message': str(e)}, ensure_ascii=False))

        if not self._finished:
            self.finish()

    def get_post(self, key, default=None):

        body = self.request.body.decode('utf-8')

        if body == '':
            return default

        try:
            data = json.loads(body)
        except ValueError:
            self.application.logger.error(
                "JSON DECODE ERROR login:" + self.get_current_user() + ' -- Traceback:' + traceback.format_exc())
            return default

        if isinstance(data, dict):
            return data.get(key, default)
        else:
            return default

    def get_current_language(self):

        redis = self.redis.get(threading.currentThread())
        secure_cookie = self.get_secure_cookie(DEFAULT_COOKIE_TOKEN_NAME)

        if secure_cookie is None:
            return DEFAULT_LANGUAGE

        auth_key = bytes.decode(secure_cookie)
        params = redis.get(auth_key)

        if params is None:
            return DEFAULT_LANGUAGE

        params = json.loads(params)
        redis.expire(auth_key, 86400)

        return params.get("language", DEFAULT_LANGUAGE)

    def get_current_user(self):
        redis = self.redis.get(threading.currentThread())
        secure_cookie = self.get_secure_cookie("token")

        if secure_cookie is None:
            return None

        auth_key = bytes.decode(secure_cookie)
        params = redis.get(auth_key)

        if params is None:
            return None

        params = json.loads(params)
        redis.expire(auth_key, server.REDIS_DEFAULT_EXPIRE)

        return params.get("user", None)

    def get_error(self, e, msg=""):
        self.application.logger.error(
            "Error in FM Main: %s, %s, traceback = %s" % (msg, str(e), traceback.format_exc()))

        result = {
            "error": True,
            "message": msg,
        }

        if self.application.options.debug:
            result['traceback'] = traceback.format_exc()
            result['message'] += ' ' + str(e)

        return result

    def get_action(self, name, *args, **kwargs):
        action = FM.ActionsProvider.get_action(action_name=name, request=self, *args, **kwargs)
        return action

    def get_beget_path(self):
        login = self.get_current_user()
        return '/home/' + login[0] + '/' + login

    def get_current_host(self):
        redis = self.redis.get(threading.currentThread())
        secure_cookie = self.get_secure_cookie("token")

        if secure_cookie is None:
            raise tornado.web.HTTPError(403, "Authentication Failed")

        auth_key = bytes.decode(secure_cookie)
        params = redis.get(auth_key)

        if params is None:
            raise tornado.web.HTTPError(403, "Authentication Failed")

        redis.expire(auth_key, 86400)
        params = json.loads(params)

        return params['server']

    def get_current_password(self):

        redis = self.redis.get(threading.currentThread())
        secure_cookie = self.get_secure_cookie("token")

        if secure_cookie is None:
            raise tornado.web.HTTPError(403, "Authentication Failed")

        auth_key = bytes.decode(secure_cookie)
        params = redis.get(auth_key)

        if params is None:
            raise tornado.web.HTTPError(403, "Authentication Failed")

        redis.expire(auth_key, 86400)
        params = json.loads(params)

        if "password_enc" in params:
            from cryptography.fernet import Fernet, InvalidToken
            raw = self.get_raw_session_cookie() or ""
            key = raw.split("|", 1)[1] if "|" in raw else None
            if key is None:
                raise tornado.web.HTTPError(403, "Authentication Failed")
            try:
                return Fernet(key.encode("ascii")).decrypt(params["password_enc"].encode("ascii")).decode("utf-8")
            except (InvalidToken, ValueError):
                raise tornado.web.HTTPError(403, "Authentication Failed")

        return params['password']  # старые сессии до обновления

    def get_user_locale(self):
        try:
            locale = bytes.decode(self.get_secure_cookie("locale"))
            if locale:
                return tornado.locale.get(locale)
        except:
            return tornado.locale.get(DEFAULT_LOCALE)

    def is_ajax(self):
        if 'X-Requested-With' in self.request.headers:
            if self.request.headers['X-Requested-With'] == 'XMLHttpRequest':
                return True
        return False


def wrap_catch(method):
    def catch(*args, **kwargs):

        self = args[0]
        try:
            return method(*args, **kwargs)

        except Exception as e:
            msg = "Catched Error in FM Main request thread"
            logger = logging.getLogger('tornado.application')
            logger.error("Error in FM Main: %s, %s, traceback = %s" % (msg, str(e), traceback.format_exc()))

            self.redis.close(threading.currentThread())
            self._handle_request_exception(e)

    return catch


def wrap_async_rpc(method):
    async def run(*args, **kwargs):

        self = args[0]
        self._fm_loop = tornado.ioloop.IOLoop.current()

        def work():
            self._fm_worker = threading.current_thread()
            try:
                return method(*args, **kwargs)
            finally:
                self._fm_worker = None

        try:
            await self._fm_loop.run_in_executor(_EXECUTOR, work)

        except Exception as e:
            msg = "Catched Error in FM Main request thread"
            logger = logging.getLogger('tornado.application')
            logger.error("Error in FM Main: %s, %s, traceback = %s" % (msg, str(e), traceback.format_exc()))

            if not self._finished:
                self._handle_request_exception(e)

    return run
