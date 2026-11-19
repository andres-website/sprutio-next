from config.settings import DEFAULT_COOKIE_TOKEN_NAME
from core import FM


class Logout(FM.BaseAction):
    def __init__(self, request, **kwargs):
        super(Logout, self).__init__(request=request, **kwargs)

    def run(self):

        # форк: при выходе сессия удаляется из redis по cookie сессии
        auth_key = self.request.get_secure_cookie(DEFAULT_COOKIE_TOKEN_NAME)
        redis = self.redis.get_current()

        redis_key = 'FM::session_state::' + self.request.get_current_user()
        redis.delete(redis_key)
        redis.delete(auth_key)

        self.request.clear_cookie("authkey")
        self.request.clear_cookie("locale")

        answer = {
            "message": "bye!"
        }

        return answer