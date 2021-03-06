import argparse
from bson.json_util import dumps, loads
import datetime
from document import Layer, Interface
import pkg_resources
import motor
import ui

import tornado.auth
import tornado.escape
import tornado.httpclient
import tornado.ioloop
import tornado.template
import tornado.web
from tornado import gen
from config import Config
import logging


def dump(s):
    return dumps(s, indent=2)


class LaunchPadAPIMixin(object):
    _APIBASE = "https://api.launchpad.net/1.0/"

    @gen.coroutine
    def lp_client(self, url):
        http_client = tornado.httpclient.HTTPClient()
        url = self._APIBASE + url
        try:
            response = http_client.fetch(url, headers={"Accept": "text/json"})
            raise gen.Return(response)
        except tornado.httpclient.HTTPError:
            raise gen.Return(False)
        finally:
            http_client.close()

    @gen.coroutine
    def check_lp_group_membership(self, username, groups):
        if isinstance(groups, str):
            groups = [groups]

        for group in groups:
            url = "{}/+member/{}/".format(group, username)
            result = yield self.lp_client(url)
            if result is not False:
                raise gen.Return(True)

        raise gen.Return(False)


class RequestBase(tornado.web.RequestHandler, LaunchPadAPIMixin):
    def get_current_user(self):
        user = self.get_secure_cookie("u")
        if user:
            return loads(user.decode("utf-8"))
        return None

    @property
    def db(self):
        return self.settings['db']

    @property
    def metrics(self):
        return getattr(self.settings['db'], "metrics")

    @gen.coroutine
    def add_metric(self, data):
        data.update({
            "remote_ip": self.request.remote_ip,
            "timestamp": datetime.datetime.utcnow()
        })
        if self.current_user:
            data["username"] = self.current_user["username"]
        yield self.metrics.insert(data, w=0)


class RestBase(RequestBase):
    @property
    def db(self):
        return getattr(self.settings['db'], self.collection)

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

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

    @gen.coroutine
    def verify_write_permissions(self, document, user=None):
        if user is None:
            user = self.get_current_user()["username"]
        owners = document.get("owner", [])
        if not owners:
            # XXX: backwards compat
            raise gen.Return(True)
        users = [o for o in owners if not o.startswith("~")]
        if user in users:
            raise gen.Return(True)

        groups = [o for o in owners if o.startswith("~")]
        # Include admin groups which always pass test
        groups += self.settings.get("admin_lp_group", [])
        raise gen.Return(self.check_lp_group_membership(user, groups))


class MainHandler(RequestBase):
    @gen.coroutine
    def get(self):
        interfaces = yield Interface.find(self.db.interfaces)
        layers = yield Layer.find(self.db.layers)
        self.render("index.html",
                    site=self.settings['site'],
                    current_user=self.get_current_user(),
                    interfaces=interfaces,
                    layers=layers
                    )


def get_schema_by_kind(kind):
    klass = None
    schema = None
    if kind == "interface":
        klass = Interface
    elif kind == "layer":
        klass = Layer
    schema = klass.schema
    return klass, schema


class EditHandler(RequestBase):
    @tornado.web.addslash
    @gen.coroutine
    def get(self, kind, oid):
        klass, schema = get_schema_by_kind(kind)
        db = getattr(self.db, kind + "s")
        if oid == "+":
            # "+" is out token for "add new"
            obj = klass()
        else:
            obj = yield klass.load(db, oid)
        self.render("editor.html",
                    site=self.settings['site'],
                    schema=schema,
                    entity=obj,
                    dumps=dumps,
                    kind=kind)


class SchemaHandler(RestBase):
    @tornado.web.addslash
    def get(self, kind):
        _, schema = get_schema_by_kind(kind)
        self.write(dump(schema))


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

    @tornado.web.authenticated
    @tornado.web.addslash
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        # XXX: assumes encoding :-/
        body = loads(self.request.body.decode("utf-8"))
        if not isinstance(body, list):
            body = [body]
        user = self.get_current_user()["username"]
        # validate the user can modify each record before changing any
        # XXX: this could be a race (vs out of band modification)
        # but this will be redone with proper database acls
        documents = []
        for item in body:
            id = item['id']
            document = yield self.factory.load(self.db, id)
            if not (yield self.verify_write_permissions(document, user)):
                raise tornado.web.HTTPError(401,
                                            "Launchpad user not authorized")
            document.update(item)
            documents.append(document)
        for document in documents:
            yield document.save(self.db, user=user)
            yield self.add_metric({"kind": self.collection,
                                   "action": "update",
                                   "item": document['id']})
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

    @tornado.web.authenticated
    @tornado.web.addslash
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self, id):
        # XXX: assumes encoding :-/
        body = loads(self.request.body.decode("utf-8"))
        document = yield self.factory.load(self.db, id)
        user = self.get_current_user()["username"]
        if not (yield self.verify_write_permissions(document, user)):
            raise tornado.web.HTTPError(401,
                                        "Launchpad user not authorized")
        document.update(body)
        yield document.save(self.db, user=user)
        yield self.add_metric({"kind": self.collection,
                               "action": "update",
                               "item": document['id']})
        self.finish()

    @tornado.web.authenticated
    @tornado.web.addslash
    @gen.coroutine
    def delete(self, id):
        document = yield self.factory.load(self.db, id)
        user = self.get_current_user()["username"]
        if not (yield self.verify_write_permissions(document, user)):
            raise tornado.web.HTTPError(401,
                                        "Launchpad user not authorized")
        if document:
            yield document.remove(self.db)
            yield self.add_metric({"kind": self.collection,
                                   "action": "delete",
                                   "item": document['id']})


class InterfaceHandler(RestResource):
    factory = Interface
    collection = "interfaces"


class LayerHandler(RestResource):
    factory = Layer
    collection = "layers"


class MetricsHandler(RequestBase):
    @property
    def metrics(self):
        return getattr(self.settings['db'], "metrics")

    @tornado.web.addslash
    @tornado.web.asynchronous
    @gen.coroutine
    def post(self):
        body = loads(self.request.body.decode("utf-8"))
        body.update({"kind": "build"})
        yield self.add_metric(body)
        self.finish()


class LaunchpadAuthHandler(tornado.web.RequestHandler,
                           tornado.auth.OpenIdMixin,
                           LaunchPadAPIMixin):
    _OPENID_ENDPOINT = "https://login.launchpad.net/+openid"

    @gen.coroutine
    def get(self):
        if self.get_argument("openid.mode", None):
            user = yield self.get_authenticated_user()
            if not user:
                raise tornado.web.HTTPError(500, "Launchpad auth failed")
            self.set_secure_cookie("u", tornado.escape.json_encode(user))
            self.redirect("/")
            return
        self.authenticate_redirect()

    def _on_authentication_verified(self, future, response):
        if response.error or b"is_valid:true" not in response.body:
            future.set_exception(tornado.auth.AuthError(
                "Invalid OpenID response: %s" % (response.error or
                                                 response.body)))
            return

        # Make sure we got back at least an email from attribute exchange
        ax_ns = None
        for name in self.request.arguments:
            if name.startswith("openid.ns.") and \
                    self.get_argument(name) == "http://openid.net/srv/ax/1.0":
                ax_ns = name[10:]
                break

        def get_ax_arg(key):
            if not ax_ns:
                return None
            base = "openid." + ax_ns
            count = base + ".count." + key
            # XXX: this is a hack, getting the .1 key
            path = base + ".value." + key + ".1"

            ct = self.get_argument(count, None)
            if not ct:
                return None
            return self.get_argument(path, None)

        user = {}
        for key in ["fullname", "username", "email", "locale"]:
            result = get_ax_arg(key)
            if result is not None:
                user[key] = result

        claimed_id = self.get_argument("openid.claimed_id", None)
        if claimed_id:
            user["claimed_id"] = claimed_id
        future.set_result(user)


def setup():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=9999)
    parser.add_argument('-l', '--log-level', default=logging.INFO)
    parser.add_argument('-d', '--database-name', type=str, default="test")
    parser.add_argument('--database', type=str, default="localhost")
    parser.add_argument('-c', '--config', type=Config.load,
                        default=pkg_resources.resource_filename(
                            __name__, "config.json"))

    options = parser.parse_args()
    logging.basicConfig(level=options.log_level)
    return options


def main():
    options = setup()
    db = getattr(motor.MotorClient(host=options.database),
                 options.database_name)
    settings = options.config
    settings.update(dict(
        autoreload=True,
        debug=True,
        login_url="/login",
        template_path=pkg_resources.resource_filename(__name__, "."),
        static_path=pkg_resources.resource_filename(__name__, "static"),
        db=db,
        ui_modules=ui))

    application = tornado.web.Application([
        (r"/api/v1/interfaces/?", InterfacesHandler),
        (r"/api/v1/interface/([\-\w\d_]+)/?", InterfaceHandler),
        (r"/api/v1/layers/?", LayersHandler),
        (r"/api/v1/layer/([\-\w\d_]+)/?", LayerHandler),
        (r"/api/v1/schema/(interface|layer)/?", SchemaHandler),
        (r"/api/v1/metrics/?", MetricsHandler),
        (r"/login/", LaunchpadAuthHandler),
        (r"/(interface|layer)/([\-\w\d_]+|\+)/?", EditHandler),
        (r"/", MainHandler),
    ], **settings)

    application.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    main()
