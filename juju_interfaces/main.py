import argparse
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
from config import Config
import logging


def dump(s):
    return dumps(s, indent=2)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html",
                    links=['/api/v1/interfaces/',
                           '/api/v1/interface/pgsql/',
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

    def parse_search_query(self):
        result = {}
        q = self.get_query_arguments("q")
        for query in q:
            if ":" in query:
                k, v = query.split(":", 1)
                result[k] = v
            else:
                result[self.factory.pk] = query
        return result


class RestCollection(RestBase):
    @tornado.web.asynchronous
    @gen.coroutine
    def get(self):
        q = self.parse_search_query()
        response = []
        for iface in (yield Interface.find(self.db, **q)):
            response.append(iface)
        # Iteration complete
        self.write(dump(response))
        self.finish()

    #@tornado.web.authenticated
    @tornado.web.addslash
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        # XXX: assumes encoding :-/
        body = loads(self.request.body.decode("utf-8"))
        if not isinstance(body, list):
            body = [body]
        for item in body:
            id = item['id']
            document = yield self.factory.load(self.db, id)
            document.update(item)
            yield document.save(self.db)
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


def setup():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=8888)
    parser.add_argument('-l', '--log-level', default=logging.INFO)
    parser.add_argument('-d', '--database', type=str, default="test")
    parser.add_argument('-c', '--config', type=Config.load,
                        default=pkg_resources.resource_filename(
                            __name__, "config.json"))

    options = parser.parse_args()
    logging.basicConfig(level=options.log_level)
    return options


def main():
    options = setup()
    db = getattr(motor.MotorClient(), options.database)
    settings = options.config
    settings.update(dict(
        autoreload=True,
        debug=True,
        login_url="/login",
        template_path=pkg_resources.resource_filename(__name__, "."),
        static_path=pkg_resources.resource_filename(__name__, "static"),
        google_oauth=load_oauth(os.path.expanduser("~/.juju-interfaces.key")),
        db=db))

    application = tornado.web.Application([
        (r"/api/v1/interfaces/?", InterfacesHandler),
        (r"/api/v1/interface/([\-\w\d_]+)/?", InterfaceHandler),
        (r"/api/v1/layers/?", LayersHandler),
        (r"/api/v1/layer/([\w\d_]+)/?", LayerHandler),
        (r"/login/", GoogleOAuth2LoginHandler),
        (r"/", MainHandler),
    ], **settings)

    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()
