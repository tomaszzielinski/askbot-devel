# Heavily modified copy of https://code.djangoproject.com/browser/django/tags/releases/1.2.7/django/core/management/commands/dumpdata.py
# Django license applies (https://code.djangoproject.com/browser/django/tags/releases/1.2.7/LICENSE):
#
#    Copyright (c) Django Software Foundation and individual contributors.
#    All rights reserved.
#
#    Redistribution and use in source and binary forms, with or without modification,
#    are permitted provided that the following conditions are met:
#
#    1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
#    2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
#    3. Neither the name of Django nor the names of its contributors may be used
#    to endorse or promote products derived from this software without
#    specific prior written permission.
#
#    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#    ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#    WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#    DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
#    ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#    (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#    LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
#    ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#    (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#    SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
import sys

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, router, DEFAULT_DB_ALIAS
from django.utils.datastructures import SortedDict
from django.conf import settings

from optparse import make_option

from askbot.serializers import json as json_serializer


class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = ("Output the contents of the database as a fixture of the given "
            "format (using each model's default manager).")
    args = '[appname appname.ModelName ...]'

    def handle(self, *app_labels, **options):
        from django.db.models import get_app, get_apps, get_models, get_model

        format = 'json'
        indent = 4
        using = DEFAULT_DB_ALIAS  # 'default'
        use_natural_keys = True

        settings.DEBUG = False # Just in case, we don't want queries to accumulate in connection.queries

        app_labels = ['auth', 'askbot'] # Askbot heavily depends on Django User model so we have to dump also users

        app_list = SortedDict()
        for app_label in app_labels:
            app = get_app(app_label)
            app_list[app] = None

        # Applied here this patch: https://code.djangoproject.com/ticket/5423
        # -> https://code.djangoproject.com/attachment/ticket/5423/5423.5.diff
        # TODO: Track https://code.djangoproject.com/ticket/16614
        def get_objects():
            for model in sort_dependencies(app_list.items()):
                if not model._meta.proxy and router.allow_syncdb(using, model):
                    for obj in model._default_manager.using(using).order_by(model._meta.pk.name).iterator():
                        yield obj

        try:
            json_serializer.Serializer().serialize(
                queryset=get_objects(),
                indent=indent,
                use_natural_keys=use_natural_keys,
                stream=sys.stdout
            )
        except Exception, e:
            raise CommandError("Unable to serialize database: %s" % e)


def sort_dependencies(app_list):
    """Sort a list of app,modellist pairs into a single list of models.

    The single list of models is sorted so that any model with a natural key
    is serialized before a normal model, and any model with a natural key
    dependency has it's dependencies serialized first.
    """
    from django.db.models import get_model, get_models
    # Process the list of models, and get the list of dependencies
    model_dependencies = []
    models = set()
    for app, model_list in app_list:
        if model_list is None:
            model_list = get_models(app)

        for model in model_list:
            models.add(model)
            # Add any explicitly defined dependencies
            if hasattr(model, 'natural_key'):
                deps = getattr(model.natural_key, 'dependencies', [])
                if deps:
                    deps = [get_model(*d.split('.')) for d in deps]
            else:
                deps = []

            # Now add a dependency for any FK or M2M relation with
            # a model that defines a natural key
            for field in model._meta.fields:
                if hasattr(field.rel, 'to'):
                    rel_model = field.rel.to
                    if hasattr(rel_model, 'natural_key'):
                        deps.append(rel_model)
            for field in model._meta.many_to_many:
                rel_model = field.rel.to
                if hasattr(rel_model, 'natural_key'):
                    deps.append(rel_model)
            model_dependencies.append((model, deps))

    model_dependencies.reverse()
    # Now sort the models to ensure that dependencies are met. This
    # is done by repeatedly iterating over the input list of models.
    # If all the dependencies of a given model are in the final list,
    # that model is promoted to the end of the final list. This process
    # continues until the input list is empty, or we do a full iteration
    # over the input models without promoting a model to the final list.
    # If we do a full iteration without a promotion, that means there are
    # circular dependencies in the list.
    model_list = []
    while model_dependencies:
        skipped = []
        changed = False
        while model_dependencies:
            model, deps = model_dependencies.pop()

            # If all of the models in the dependency list are either already
            # on the final model list, or not on the original serialization list,
            # then we've found another model with all it's dependencies satisfied.
            found = True
            for candidate in ((d not in models or d in model_list) for d in deps):
                if not candidate:
                    found = False
            if found:
                model_list.append(model)
                changed = True
            else:
                skipped.append((model, deps))
        if not changed:
            raise CommandError("Can't resolve dependencies for %s in serialized app list." %
                               ', '.join('%s.%s' % (model._meta.app_label, model._meta.object_name)
                                   for model, deps in sorted(skipped, key=lambda obj: obj[0].__name__))
            )
        model_dependencies = skipped

    return model_list