# -*- coding: utf-8 -*-
#
# This file is part of Django appschema released under the MIT license.
# See the LICENSE for more information.

from datetime import datetime

from django.conf import settings
from django.db import connection, models, transaction
from django.db.utils import DatabaseError, IntegrityError

from appschema import syncdb, migrate
from appschema.db import syncdb_apps, migrate_apps
from appschema.schema import schema_store
from appschema.south_utils import get_migration_candidates
from appschema.utils import get_apps

def new_schema(name, public_name, is_active=True, **options):
    """
    This function creates a schema and perform a syncdb on it.
    As we call some syncdb and migrate management commands, we can't rely on
    transaction support.
    We are going to catch any exception (including SystemExit).
    """
    
    try:
        schema = Schema(name=name, public_name=public_name, is_active=is_active)
        schema.save()
    except IntegrityError:
        raise Exception('Schema already exists.')
    
    try:
        cursor = connection.cursor()
        cursor.execute('CREATE SCHEMA "%s"' % name)
        transaction.commit_unless_managed()
        
        defaults = {
            'verbosity': 0,
            'traceback': None,
            'noinput': True
        }
        defaults.update(options)
        
        sync_options = options
        # We never want migration to launch with syncdb call
        sync_options['migrate'] = False
        
        _, isolated_apps = get_apps()
        
        syncdb_apps(isolated_apps, name, **sync_options)
        migrate_apps(get_migration_candidates(isolated_apps), name, **options)
        schema_store.reset_path()
        
        return schema
    except BaseException, e:
        drop_schema(name)
        raise Exception(str(e))
    

@transaction.commit_on_success
def drop_schema(name):
    Schema.objects.filter(name=name).delete()
    
    cursor = connection.cursor()
    try:
        cursor.execute('DROP SCHEMA "%s" CASCADE' % name)
    except DatabaseError:
        pass

class SchemaManager(models.Manager):
    def active(self):
        return self.filter(is_active=True)
    

class Schema(models.Model):
    created = models.DateTimeField(default=datetime.now)
    name = models.CharField(max_length=64)
    public_name = models.CharField(max_length=255, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    
    objects = SchemaManager()
    
    class Meta:
        unique_together = ('name', 'public_name')
    
    def __unicode__(self):
        return u'%s (%s)' % (self.name, self.public_name)
    