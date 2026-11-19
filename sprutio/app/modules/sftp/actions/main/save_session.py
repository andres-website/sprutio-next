import json

from core import FM


class SaveSession(FM.BaseAction):
    def __init__(self, request, order, session, **kwargs):
        super(SaveSession, self).__init__(request=request, **kwargs)

        self.order = order
        self.session = session

    def run(self):

        result = self.set_redis_session_data()
        return result

    def set_redis_session_data(self):

        redis_key = 'FM::session_state::' + self.request.get_current_user()
        redis = self.redis.get_current()

        session = {}
        if redis.exists(redis_key):
            try:
                session = json.loads(redis.get(redis_key))
            except ValueError:
                session = {}
        if not isinstance(session, dict):
            session = {}

        # форк: сохраняем каждую панель отдельно — состояние второй панели не теряется
        for side in ('Left', 'Right'):
            if not isinstance(session.get(side), dict):
                session[side] = {'type': FM.Modules.HOME}

        session[self.order] = self.session
        redis.set(redis_key, json.dumps(session))

        return {
            "message": "session saved"
        }
