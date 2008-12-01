# Taken from http://leahculver.com/2008/06/17/tiny-urls-based-on-pk/
url56 = '23456789abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'

def to_url56(num):
    return dec_to_anybase(num, url56)
    
def from_url56(value):
    return anybase_to_dec(value, url56)

# base 10 to any base using basestring for digits 
def dec_to_anybase(num, basestring):
    base = len(basestring)
    new = ''
    current = num
    while current >= base:
        remainder = current % base
        digit = basestring[remainder]
        new = '%s%s' % (digit, new)
        current = current / base
    if basestring[current]: # non-zero indexing
        new = '%s%s' % (basestring[current], new)
    return new

# any base defined by basestring to base 10
def anybase_to_dec(value, basestring):
    base = len(basestring)
    n = 0
    count = 0
    while value:
        last = len(value) - 1
        digit = value[last]
        digit_index = basestring.find(digit)
        if digit_index == -1:
            raise InvalidURLError
        n += digit_index * base**count
        value = value[:last]
        count += 1
    return n

class InvalidURLError(Exception):
    pass
