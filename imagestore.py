from google.appengine.api import memcache
from google.appengine.ext import db
from url56 import from_url56, to_url56

class Image(db.Model):
    author = db.UserProperty()
    author_nickname = db.StringProperty()
    title = db.StringProperty()
    date = db.DateTimeProperty(auto_now_add=True)
    image = db.BlobProperty()
    ext = db.StringProperty()

class ImageStore(object):
    """Add an image to the ImageStore.  Memcache.  Return image_id (url56)."""
    @staticmethod
    def add(image_data, ext, author=None, title=''):
        image = Image()

        image.image = db.Blob(image_data)
        image.ext = ext
        if author:
            image.author_nickname = author.nickname()
            image.author = author
        image.title = title
        image.put()

        image_id = to_url56(image.key().id())
        try:
            memcache.add(image_id, image)
        except ValueError:
            # too big for memcache
            pass

        return image_id
