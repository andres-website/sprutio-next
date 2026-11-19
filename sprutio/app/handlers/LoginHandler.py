from classes.core.FMLocale import FMLocale
from config import settings
from handlers.BaseHandler import BaseHandler, wrap_async_rpc, wrap_catch


class LoginHandler(BaseHandler):
    @wrap_async_rpc
    @wrap_catch
    def get(self):
        language = self.get_argument("language", None)
        if language is None:
            # форк: без явного выбора — язык браузера (Accept-Language), если он поддерживается
            language = settings.DEFAULT_LANGUAGE
            for part in self.request.headers.get("Accept-Language", "").split(","):
                code = part.split(";")[0].strip().lower()[:2]
                if code in settings.LANGUAGES:
                    language = code
                    break
        secure_cookie = self.get_secure_cookie(settings.DEFAULT_COOKIE_TOKEN_NAME)

        if language not in settings.LANGUAGES:
            language = settings.DEFAULT_LANGUAGE

        if secure_cookie is not None:
            auth_key = bytes.decode(secure_cookie)
            FMLocale.set_language(self, language, auth_key)
        else:
            FMLocale.set_language(self, language)

        if self.application.options.debug:
            self.render("login.html", language=language)
        else:
            self.render("login.html", language=language)
