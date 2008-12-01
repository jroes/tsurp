# TODO:
# * Tell people somewhere on the front page that they can e-mail photos
# * Report the KeyError bug with memcache (tsurp.com/P)
# * Properly determine content-type
# * Use GAE's image.resize() to reduce network traffic

import random
import logging
import wsgiref.handlers
import os
import traceback
import email
import mimetypes

from google.appengine.api import users, memcache, mail, datastore_errors
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import template
from google.appengine.runtime import apiproxy_errors
import urllib

from url56 import from_url56, to_url56, InvalidURLError
from imagestore import Image, ImageStore

ADMIN_ADDRESS = 'jroes@jroes.net'
CONTACT_ADDRESS = 'contact@tsurp.com'
ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.jpe', '.bmp',
                      '.png', '.gif', '.tif', '.tiff')
IMAGE_URL = 'http://tsurp.com/%s'

# T-mobile images
BAD_FILES = ('dottedline350.gif', 'dottedline600.gif', 
             'tmobilelogo.gif', 'tmobilespace.gif')

class Index(webapp.RequestHandler):
    def get(self):
        try:
            self.response.headers['Content-Type'] = 'text/html'
            write_template(self.response, 'index.html', None)
        except Exception, e:
            self.error(500)
            logging.error('%s: %s' % (self.__class__.__name__,
                          traceback.print_exc()))

class ImageFile(webapp.RequestHandler):
    def get(self, image_id):
        try:
            image = memcache.get(image_id)
            if image is None:
                image = Image.get_by_id(from_url56(image_id))
                memcache.add(image_id, image)

            if image and image.image:
                self.response.headers['Content-Type'] = "image/%s" % str(image.ext)
                self.response.out.write(image.image)
            else:
                self.error(404)
        except InvalidURLError, e:
            self.error(404)
        except datastore_errors.BadKeyError, e:
            self.error(404)
        except Exception, e:
            self.error(404)
            logging.error('%s: %s' % (self.__class__.__name__,
                          traceback.print_exc()))

class ImagePage(webapp.RequestHandler):
    def get(self, image_id):
        try:
            image = memcache.get(image_id)
            if image is None:
                image = Image.get_by_id(from_url56(image_id))
                memcache.add(image_id, image)

            if not image:
                self.error(404)
                return

            extra_header_values = {
                'title': 'tsurp: ' + image.title,
                }
        
            values = {
                'image_url': '/img/' + image_id,
                'this_url': self.request.url
                }
        
            write_template(self.response, 'image.html', values, 
                           extra_header_values)
        except InvalidURLError, e:
            self.error(404)
        except datastore_errors.BadKeyError, e:
            self.error(404)
        except Exception, e:
            self.error(404)
            logging.error('%s: %s' % (self.__class__.__name__,
                          traceback.print_exc()))

class UserImages(webapp.RequestHandler):
    def get(self, user_nickname):
        try:
            
            extra_header_values = {
                'title': 'tsurp: %s''s images' % user_nickname
                }

            user_nickname = urllib.unquote(user_nickname)

            images = db.GqlQuery("SELECT * FROM Image WHERE author_nickname = :1", user_nickname)

            if not images or not isinstance(images, db.GqlQuery):
                self.error(404)
                return

            images_table = "<table id='images_table'>"
            rowcount = 0
            rows = "<tr>"
            for img in images:
                # 5 images per row
                if (rowcount % 5) == 0 and rowcount > 0:
                    rows += "</tr><tr>"
                    
                image_url = "/%s" % to_url56(img.key().id())
                image_src_url = "/img%s" % image_url
                rows += "<td>"
                rows += "<a href='%s'>" % image_url
                rows += "<img src='%s' /></a>" % image_src_url
                rows += "</td>"
                rowcount += 1
            images_table += rows
            images_table += "</tr></table>"

            values = {
                'images_table': images_table,
                'username': user_nickname
                }

            write_template(self.response, 'userimages.html', values, 
                           extra_header_values)
        except Exception, e:
            self.error(404)
            logging.error('%s: %s' % (self.__class__.__name__,
                          traceback.print_exc()))

class UploadImageFromWeb(webapp.RequestHandler):
    def post(self):
        try:
            if not isinstance(self.request.get('img'), str):
                self.redirect('/')
            image = db.Blob(self.request.get('img'))
            ext = self.request.POST.get('img').filename.split('.')[-1]
            author = users.get_current_user()
            title = self.request.get('title')

            image_id = ImageStore.add(image, ext=ext,
                                      author=author, title=title)

            memcache.add(image_id, image)
            self.redirect('/' + image_id)
        except Exception, e:
            self.error(500)
            logging.error('%s: %s' % (self.__class__.__name__,
                                     traceback.print_exc()))

class UploadImageFromMail(webapp.RequestHandler):
    def post(self):
        try:
            sender = self.request.GET.get("from", "")
            if not sender or sender == '':
                self.error(500)
                return

            recipient = self.request.GET.get("to", "")
            if recipient == ADMIN_ADDRESS:
                mail.send_mail(sender=CONTACT_ADDRESS,
                               to=ADMIN_ADDRESS,
                               subject="mail to contact@tsurp.com from %s" % sender,
                               body=self.request.body)
                return
                
            message = email.message_from_string(self.request.body)

            for part in message.walk():
                if part.get_content_maintype() == 'multipart':
                    continue

                filename = part.get_filename()
                if filename and filename not in BAD_FILES:
                    ext = mimetypes.guess_extension(part.get_content_type())
                
                    if ext in ALLOWED_EXTENSIONS:
                        image = db.Blob(part.get_payload(decode=True))

                        ext = ext.replace('.', '')
                        # turn .jpe's into jpgs, there's no content/type: jpe
                        if ext == 'jpe': ext = 'jpg'
                        
                        image_id = ImageStore.add(image, ext=ext,
                                                  author=users.User(sender))
                        memcache.add(image_id, image)

                        url = IMAGE_URL % image_id
                        mail.send_mail(sender=CONTACT_ADDRESS,
                                       to=sender,
                                       subject="tsurp: %s" % url,
                                       body=url)
                        logging.debug('sent image url %s to %s' % (url, sender))
                    else:
                        logging.debug('invalid ext for %s: %s' % (filename,
                                                                  ext))

        except apiproxy_errors.OverQuotaError, e:
            self.error(500)
            logging.debug('lost message for %s, over quota: %s.' % (sender, e))
            # We should add to a queue in the datastore here
        except Exception, e:
            self.error(500)
            logging.error('%s: %s' % (self.__class__.__name__,
                                     traceback.print_exc()))

def get_login_listitems():
    user = users.get_current_user()
    if user:
        items = "<li><a href=""/user/%s"">my images</a></li>" % user.nickname()
        items += "<li><a href=""%s"">logout</a>" % users.create_logout_url("/")
        return items
    else:
        items = "<li><a href=""%s"">login (google acct)</a></li>" % users.create_login_url("/")
        items += "<li><a href=""%s"">register</a>" % users.create_login_url("/")
        return items

def write_template(response, file, values, 
                   extra_header_values=None, extra_footer_values=None):

    header_values = {
        'title': 'tsurp'
        }
    
    login_listitems = get_login_listitems()

    footer_values = {
        'login_listitems': login_listitems
        }

    path = os.path.join(os.path.dirname(__file__), file)

    if extra_header_values:
        header_values.update(extra_header_values)
    response.out.write(template.render('header.html', header_values))

    response.out.write(template.render(path, values))

    if extra_footer_values:
        footer_values.update(extra_footer_values)
    response.out.write(template.render('footer.html', footer_values))

def real_main():
    application = webapp.WSGIApplication(
        [('/', Index),
         ('/user/(.*)', UserImages),
         ('/u/img/web', UploadImageFromWeb),
         ('/u/img/mail', UploadImageFromMail),
         ('/img/(.*)', ImageFile),
         ('/(.*)', ImagePage)
         ],
        debug=True)
    wsgiref.handlers.CGIHandler().run(application)

def profile_main():
    # This is the main function for profiling 
    # We've renamed our original main() above to real_main()
    try:
        import cProfile, pstats, StringIO
        prof = cProfile.Profile()
        prof = prof.runctx("real_main()", globals(), locals())
        stream = StringIO.StringIO()
        stats = pstats.Stats(prof, stream=stream)
        stats.sort_stats("time")  # Or cumulative
        stats.print_stats(80)  # 80 = how many to print
        # The rest is optional.
        # stats.print_callees()
        # stats.print_callers()
        logging.info("Profile data:\n%s", stream.getvalue())
    except:
        return

if __name__ == "__main__":
    # Profile one percent of requests
    if random.randint(1, 100) == 1:
        profile_main()
    else:
        real_main()
