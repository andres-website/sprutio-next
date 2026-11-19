from tornado import web

from classes.core.FMLocale import FMLocale
from config import settings
from handlers.BaseHandler import BaseHandler, wrap_async_rpc, wrap_catch


class MainHandler(BaseHandler):

    @wrap_async_rpc
    @wrap_catch
    @web.authenticated
    def get(self):
        language = self.get_argument("language", None)
        if language is not None:
            secure_cookie = self.get_secure_cookie(settings.DEFAULT_COOKIE_TOKEN_NAME)
            auth_key = bytes.decode(secure_cookie)

            if language not in settings.LANGUAGES:
                language = settings.DEFAULT_LANGUAGE

            FMLocale.set_language(self, language, auth_key)
        # dev-режим фронта: /?dev=1 включает (cookie fm_dev), /?dev=0 выключает
        dev_arg = self.get_argument("dev", None)
        if dev_arg is not None:
            if dev_arg == "1":
                self.set_cookie("fm_dev", "1", expires_days=30)
            else:
                self.clear_cookie("fm_dev")
            dev = dev_arg == "1"
        else:
            dev = self.get_cookie("fm_dev") == "1"

        if self.application.options.debug:
            self.render("app.debug.html", language=self.get_current_language())
        else:
            self.render("app.html", language=self.get_current_language(), dev=dev,
                        logout_url=settings.LOGOUT_URL)
