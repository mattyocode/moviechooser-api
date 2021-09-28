import string, random
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.text import slugify

def random_string(length=8, chars = string.ascii_letters + string.digits):
    return ''.join(random.choice(chars) for n in range(length))


def unique_slug(instance, new_slug = None):
    if new_slug is not None:
        title_slug = new_slug
    else:
        title_slug = slugify(instance.title)

    ModelClass = instance.__class__
    slug_max_length = ModelClass._meta.get_field('slug').max_length
    title_slug = title_slug[:slug_max_length - 9]
    randstr = random_string()
    slug = f"{randstr}-{title_slug}"

    return slug