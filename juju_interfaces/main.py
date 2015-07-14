from bson.json_util import dumps, loads
from document import Layer, Interface
from tornado import gen
import pkg_resources
import motor
import os
import tornado.auth
import tornado.escape
import tornado.ioloop
import tornado.template
import tornado.web
from json import load


def dump(s):
    return dumps(s, indent=2)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html",
                    links=['/api/v1/interfaces/',
                           '/api/v1/interface/mysql/',
                           '/api/v1/layers/',
                           '/api/v1/layer/charmhelpers/'],
                    site=self.settings['site'])


class RestBase(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("u")

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    @property
    def db(self):
        return getattr(self.settings['db'], self.collection)


class RestCollection(RestBase):
    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        cursor = self.db.find({"id": {"$exists": True}})
        response = []
        while (yield cursor.fetch_next):
            document = cursor.next_object()
            response.append(Interface(document))
        # Iteration complete
        self.write(dump(response))
        self.finish()


class InterfacesHandler(RestCollection):
    factory = Interface
    collection = "interfaces"


class LayersHandler(RestCollection):
    factory = Layer
    collection = "layers"


class RestResource(RestBase):
    @tornado.web.addslash
    @tornado.web.asynchronous
    @gen.coroutine
    def get(self, id):
        document = yield self.factory.load(self.db, id)
        self.write(dump(document))
        self.finish()

    #@tornado.web.authenticated
    @tornado.web.addslash
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self, id):
        # XXX: assumes encoding :-/
        body = loads(self.request.body.decode("utf-8"))
        document = yield self.factory.load(self.db, id)
        document.update(body)
        yield document.save(self.db)
        self.finish()

    #@tornado.web.authenticated
    @tornado.web.addslash
    @gen.coroutine
    def delete(self, id):
        document = yield self.factory.load(self.db, id)
        if document:
            yield document.remove(self.db)


class InterfaceHandler(RestResource):
    factory = Interface
    collection = "interfaces"


class LayerHandler(RestResource):
    factory = Layer
    collection = "layers"


def load_oauth(key_fn):
    if not os.path.exists(key_fn):
        print("You need to set up a valid key file for auth.\n"
              "See http://www.tornadoweb.org/en/stable/auth.html#google"
              "for the default. By default this should live in"
              " ~/.juju-interfaces.key.")
    return load(open(key_fn))


class GoogleOAuth2LoginHandler(tornado.web.RequestHandler,
                               tornado.auth.GoogleOAuth2Mixin):
    @property
    def site(self):
        return self.settings["site"] + "auth/google"

    @tornado.gen.coroutine
    def get(self):
        if self.get_argument('code', False):
            user = yield self.get_authenticated_user(
                redirect_uri=self.site,
                code=self.get_argument('code'))
            # Save the user with e.g. set_secure_cookie
            self.set_secure_cookie("u", user)
        else:
            yield self.authorize_redirect(
                redirect_uri=self.site,
                client_id=self.settings['google_oauth']['key'],
                scope=['profile', 'email'],
                response_type='code',
                extra_params={'approval_prompt': 'auto'})


def main():
    db = motor.MotorClient().test
    settings = dict(
        site="http://bcsaller.dyndns.org:8888",
        autoreload=True,
        debug=True,
        login_url="/login",
        template_path=pkg_resources.resource_filename(__name__, "."),
        static_path=pkg_resources.resource_filename(__name__, "static"),
        cookie_secret="52e714bd-d35f-4c22-8815-f19aaf9b11d9",
        google_oauth=load_oauth(os.path.expanduser("~/.juju-interfaces.key")),
        db=db)

    application = tornado.web.Application([
        (r"/api/v1/interfaces/?", InterfacesHandler),
        (r"/api/v1/interface/([\w\d_]+)/?", InterfaceHandler),
        (r"/api/v1/layers/?", LayersHandler),
        (r"/api/v1/layer/([\w\d_]+)/?", LayerHandler),
        (r"/login/", GoogleOAuth2LoginHandler),
        (r"/", MainHandler),
    ], **settings)

    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()
