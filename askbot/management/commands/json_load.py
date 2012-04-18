# Heavily modified copy of https://code.djangoproject.com/browser/django/tags/releases/1.2.7/django/core/management/commands/loaddata.py
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
from optparse import make_option

from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import connections, router, transaction, DEFAULT_DB_ALIAS

from askbot.serializers import json as json_serializer

class Command(BaseCommand):
    help = 'Installs the named fixture(s) in the database.'
    args = "fixture [fixture ...]"

    option_list = BaseCommand.option_list + (
        make_option('--database', action='store', dest='database',
            default=DEFAULT_DB_ALIAS, help='Nominates a specific database to load '
                'fixtures into. Defaults to the "default" database.'),
    )

    def handle(self, *fixture_labels, **options):
        using = options.get('database', DEFAULT_DB_ALIAS)

        connection = connections[using]
        self.style = no_style()

        verbosity = int(options.get('verbosity', 1))

        # commit is a stealth option - it isn't really useful as
        # a command line option, but it can be useful when invoking
        # loaddata from within another script.
        # If commit=True, loaddata will use its own transaction;
        # if commit=False, the data load SQL will become part of
        # the transaction in place when loaddata was invoked.
        commit = options.get('commit', True)

        # Keep a count of the installed objects and fixtures
        loaded_object_count = 0
        fixture_object_count = 0
        models = set()

        # Get a cursor (even though we don't need one yet). This has
        # the side effect of initializing the test database (if
        # it isn't already initialized).
        cursor = connection.cursor()

        # Start transaction management. All fixtures are installed in a
        # single transaction to ensure that all references are resolved.
        if commit:
            transaction.commit_unless_managed(using=using)
            transaction.enter_transaction_management(using=using)
            transaction.managed(True, using=using)

        try:
            fixture = open(sys.argv[2], 'r')

            objects_in_fixture = 0
            loaded_objects_in_fixture = 0

            try:
                objects = json_serializer.Deserializer(fixture, using=using)
                for obj in objects:
                    objects_in_fixture += 1
                    if router.allow_syncdb(using, obj.object.__class__):
                        loaded_objects_in_fixture += 1
                        models.add(obj.object.__class__)
                        obj.save(using=using)
                loaded_object_count += loaded_objects_in_fixture
                fixture_object_count += objects_in_fixture
            except (SystemExit, KeyboardInterrupt):
                raise
            except Exception:
                import traceback
                fixture.close()
                if commit:
                    transaction.rollback(using=using)
                    transaction.leave_transaction_management(using=using)
                traceback.print_exc()
                return
            fixture.close()

            # If the fixture we loaded contains 0 objects, assume that an
            # error was encountered during fixture loading.
            if objects_in_fixture == 0:
                self.stderr.write(self.style.ERROR("No fixture data found! (File format may be invalid.)\n"))
                if commit:
                    transaction.rollback(using=using)
                    transaction.leave_transaction_management(using=using)
                return

        except Exception, e:
            raise

        # If we found even one object in a fixture, we need to reset the
        # database sequences.
        if loaded_object_count > 0:
            sequence_sql = connection.ops.sequence_reset_sql(self.style, models)
            if sequence_sql:
                if verbosity > 1:
                    self.stdout.write("Resetting sequences\n")
                for line in sequence_sql:
                    cursor.execute(line)

        if commit:
            transaction.commit(using=using)
            transaction.leave_transaction_management(using=using)

        if fixture_object_count == 0:
            if verbosity > 0:
                self.stdout.write("No fixtures found.\n")
        else:
            if verbosity > 0:
                if fixture_object_count == loaded_object_count:
                    self.stdout.write("Installed %d object(s)\n" % loaded_object_count)
                else:
                    self.stdout.write("Installed %d object(s) (of %d)\n" % (
                        loaded_object_count, fixture_object_count))

        # Close the DB connection. This is required as a workaround for an
        # edge case in MySQL: if the same connection is used to
        # create tables, load data, and query, the query can return
        # incorrect results. See Django #7572, MySQL #37735.
        if commit:
            connection.close()
