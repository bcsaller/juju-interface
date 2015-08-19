import tornado.web


class Menu(tornado.web.UIModule):
    menu = {"interfaces": '/api/v1/interfaces/',
            "layers": '/api/v1/layers/',
            }

    def render(self, site):
        return self.render_string(
            "menu.html",
            menu=self.menu,
            site=site)


class SSO(tornado.web.UIModule):
    def render(self, user):
        return self.render_string(
            "signon.html",
            current_user=user
        )


class Overview(tornado.web.UIModule):
    def render(self, collection, kind):
        return self.render_string(
            "interfaces.html",
            collection=collection,
            kind=kind
        )
