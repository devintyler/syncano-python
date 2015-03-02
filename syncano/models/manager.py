from copy import deepcopy
from functools import wraps

import six

from syncano.connection import ConnectionMixin
from syncano.exceptions import SyncanoValueError, SyncanoRequestError
from syncano.utils import get_class_name
from .registry import registry


# The maximum number of items to display in a Manager.__repr__
REPR_OUTPUT_SIZE = 20


def clone(func):
    """Decorator which will ensure that we are working on copy of ``self``."""

    @wraps(func)
    def inner(self, *args, **kwargs):
        self = self._clone()
        return func(self, *args, **kwargs)
    return inner


class ManagerDescriptor(object):

    def __init__(self, manager):
        self.manager = manager

    def __get__(self, instance, owner=None):
        if instance is not None:
            raise AttributeError("Manager isn't accessible via {0} instances.".format(owner.__name__))
        return self.manager


class RelatedManagerDescriptor(object):

    def __init__(self, field, name, endpoint):
        self.field = field
        self.name = name
        self.endpoint = endpoint

    def __get__(self, instance, owner=None):
        if instance is None:
            raise AttributeError("RelatedManager is accessible only via {0} instances.".format(owner.__name__))

        links = getattr(instance, self.field.name)
        path = links[self.name]

        Model = registry.get_model_by_path(path)
        method = getattr(Model.please, self.endpoint, Model.please.all)

        properties = instance._meta.get_endpoint_properties('detail')
        properties = [getattr(instance, prop) for prop in properties]

        return method(*properties)


class Manager(ConnectionMixin):
    """Base class responsible for all ORM (``please``) actions."""

    def __init__(self):
        self.name = None
        self.model = None

        self.endpoint = None
        self.properties = {}

        self.method = None
        self.query = {}
        self.data = {}

        self._limit = None
        self._serialize = True
        self._connection = None

    def __repr__(self):
        data = list(self[:REPR_OUTPUT_SIZE + 1])
        if len(data) > REPR_OUTPUT_SIZE:
            data[-1] = '...(remaining elements truncated)...'
        return repr(data)

    def __str__(self):
        return '<Manager: {0}>'.format(self.model.__name__)

    def __unicode__(self):
        return six.u(str(self))

    def __len__(self):
        return self.iterator()

    def __iter__(self):
        return iter(self.iterator())

    def __bool__(self):
        return bool(self.iterator())

    def __nonzero__(self):      # Python 2 compatibility
        return type(self).__bool__(self)

    def __getitem__(self, k):
        """
        Retrieves an item or slice from the set of results.
        """
        if not isinstance(k, (slice,) + six.integer_types):
            raise TypeError
        assert ((not isinstance(k, slice) and (k >= 0)) or
                (isinstance(k, slice) and (k.start is None or k.start >= 0) and
                 (k.stop is None or k.stop >= 0))), \
            "Negative indexing is not supported."

        manager = self._clone()

        if isinstance(k, slice):
            if k.stop is not None:
                manager.limit(int(k.stop)+1)
            return list(manager)[k.start:k.stop:k.step]

        manager.limit(k+1)
        return list(manager)[k]

    # Object actions

    def create(self, **kwargs):
        """
        A convenience method for creating an object and saving it all in one step.
        """
        attrs = kwargs.copy()
        attrs.update(self.properties)

        instance = self.model(**attrs)
        instance.save()

        return instance

    def bulk_create(self, objects):
        """
        Creates many new instances based on provided list of objects.

        .. warning::
            This method is not meant to be used with large datasets.
        """
        return [self.create(**o) for o in objects]

    @clone
    def get(self, *args, **kwargs):
        """Returns the object matching the given lookup parameters."""
        self.method = 'GET'
        self.endpoint = 'detail'
        self._filter(*args, **kwargs)
        return self.request()

    def detail(self, *args, **kwargs):
        """Wrapper around ``get`` method."""
        return self.get(*args, **kwargs)

    def get_or_create(self, *args, **kwargs):
        """A convenience method for looking up an object with the given
        lookup parameters, creating one if necessary."""
        defaults = deepcopy(kwargs.pop('defaults', {}))
        try:
            instance = self.get(*args, **kwargs)
        except self.model.DoesNotExist:
            defaults.update(kwargs)
            instance = self.create(**defaults)
        return instance

    @clone
    def delete(self, *args, **kwargs):
        """Removes single instance based on provided arguments."""
        self.method = 'DELETE'
        self.endpoint = 'detail'
        self._filter(*args, **kwargs)
        return self.request()

    @clone
    def update(self, *args, **kwargs):
        """Updates single instance based on provided arguments."""
        self.method = 'PUT'
        self.endpoint = 'detail'
        self.data = kwargs.pop('data')
        self._filter(*args, **kwargs)
        return self.request()

    def update_or_create(self, *args, **kwargs):
        """
        A convenience method for updating an object with the given parameters, creating a new one if necessary.
        The ``defaults`` is a dictionary of (field, value) pairs used to update the object.
        """
        defaults = deepcopy(kwargs.get('defaults', {}))
        try:
            instance = self.update(*args, **kwargs)
        except self.model.DoesNotExist:
            defaults.update(kwargs)
            instance = self.create(**defaults)
        return instance

    # List actions

    @clone
    def all(self, *args, **kwargs):
        """Returns a copy of the current ``Manager`` with limit removed."""
        self._limit = None
        return self.list(*args, **kwargs)

    @clone
    def list(self, *args, **kwargs):
        """Returns a copy of the current ``Manager`` containing objects that match the given lookup parameters."""
        self.method = 'GET'
        self.endpoint = 'list'
        self._filter(*args, **kwargs)
        return self

    @clone
    def first(self, *args, **kwargs):
        """Returns the first object matched by the lookup parameters or None, if there is no matching object."""
        try:
            self._limit = 1
            return self.list(*args, **kwargs)[0]
        except KeyError:
            return None

    @clone
    def page_size(self, value):
        """Sets page size."""
        if not value or not isinstance(value, six.integer_types):
            raise SyncanoValueError('page_size value needs to be an int.')

        self.query['page_size'] = value
        return self

    @clone
    def limit(self, value):
        """Sets limit of returned objects."""
        if not value or not isinstance(value, six.integer_types):
            raise SyncanoValueError('Limit value needs to be an int.')

        self._limit = value
        return self

    @clone
    def order_by(self, field):
        """Sets order of returned objects."""
        if not field or not isinstance(field, six.string_types):
            raise SyncanoValueError('Order by field needs to be a string.')

        self.query['order_by'] = field
        return self

    @clone
    def raw(self):
        """Disables serialization. ``request`` method will return raw Python types."""
        self._serialize = False
        return self

    @clone
    def using(self, connection):
        """Connection juggling."""
        # ConnectionMixin will validate this
        self.connection = connection
        return self

    # Other stuff

    def contribute_to_class(self, model, name):
        setattr(model, name, ManagerDescriptor(self))

        self.model = model
        if hasattr(model._meta, 'connection') and model._meta.connection:
            self.connection = model._meta.connection

        if not self.name:
            self.name = name

    def _filter(self, *args, **kwargs):
        if args and self.endpoint:
            properties = self.model._meta.get_endpoint_properties(self.endpoint)
            mapped_args = {k: v for k, v in zip(properties, args)}
            self.properties.update(mapped_args)
        self.properties.update(kwargs)

    def _clone(self):
        # Maybe deepcopy ?
        manager = self.__class__()
        manager.name = self.name
        manager.model = self.model
        manager._connection = self._connection
        manager.endpoint = self.endpoint
        manager.properties = deepcopy(self.properties)
        manager._limit = self._limit
        manager.method = self.method
        manager.query = deepcopy(self.query)
        manager.data = deepcopy(self.data)
        manager._serialize = self._serialize

        return manager

    def serialize(self, data, model=None):
        """Serializes passed data to related :class:`~syncano.models.base.Model` class."""
        if not isinstance(data, dict):
            return

        model = model or self.model
        properties = deepcopy(self.properties)
        properties.update(data)

        return model(**properties) if self._serialize else data

    def request(self, method=None, path=None, **request):
        """Internal method, which calls Syncano API and returns serialized data."""
        meta = self.model._meta
        method = method or self.method
        path = path or meta.resolve_endpoint(self.endpoint, self.properties)

        if 'params' not in request and self.query:
            request['params'] = self.query

        if 'data' not in request and self.data:
            request['data'] = self.data

        try:
            response = self.connection.request(method, path, **request)
        except SyncanoRequestError as e:
            if e.status_code == 404:
                raise self.model.DoesNotExist
            raise

        if 'next' not in response:
            return self.serialize(response)

        return response

    def iterator(self):
        """Pagination handler"""

        response = self.request()
        results = 0
        while True:
            objects = response.get('objects')
            next_url = response.get('next')

            for o in objects:
                if self._limit and results >= self._limit:
                    break

                results += 1
                yield self.serialize(o)

            if not objects or not next_url or (self._limit and results >= self._limit):
                break

            response = self.request(path=next_url)


class WebhookManager(Manager):
    """
    Custom :class:`~syncano.models.manager.Manager`
    class for :class:`~syncano.models.base.Webhook` model.
    """

    @clone
    def run(self, *args, **kwargs):
        self.method = 'GET'
        self.endpoint = 'run'
        self._filter(*args, **kwargs)
        self._serialize = False
        return self.request()


class ObjectManager(Manager):
    """
    Custom :class:`~syncano.models.manager.Manager`
    class for :class:`~syncano.models.base.Object` model.
    """
    LOOKUP_SEPARATOR = '__'
    ALLOWED_LOOKUPS = [
        'gt', 'gte', 'lt', 'lte',
        'eq', 'neq', 'exists', 'in',
    ]

    def create(self, **kwargs):
        attrs = kwargs.copy()
        attrs.update(self.properties)

        model = self.get_class_model(kwargs)
        instance = model(**attrs)
        instance.save()

        return instance

    def serialize(self, data):
        model = self.get_class_model(self.properties)
        return super(ObjectManager, self).serialize(data, model)

    def get_class_model(self, properties):
        """Creates custom :class:`~syncano.models.base.Object` sub-class definition based on passed ``properties``."""
        instance_name = properties.get('instance_name', '')
        class_name = properties.get('class_name', '')
        model_name = get_class_name(instance_name, class_name, 'object')

        if self.model.__name__ == model_name:
            return self.model

        try:
            model = registry.get_model_by_name(model_name)
        except LookupError:
            schema = self.get_class_schema(properties)
            model = self.model.create_subclass(model_name, schema)
            registry.add(model_name, model)

        return model

    def get_class_schema(self, properties):
        instance_name = properties.get('instance_name', '')
        class_name = properties.get('class_name', '')
        parent = self.model._meta.parent
        class_ = parent.please.get(instance_name, class_name)
        return class_.schema

    @clone
    def filter(self, **kwargs):
        query = {}
        for key, value in six.iteritems(kwargs):
            field_name, lookup = key.split(self.LOOKUP_SEPARATOR, 1)

            if not lookup:
                lookup = 'eq'

            if field_name not in self.model.field_names:
                allowed = ', '.join(self.model.field_names)
                raise SyncanoValueError('Invalid field name {0} allowed are {1}.'.format(field_name, allowed))

            if lookup not in self.ALLOWED_LOOKUPS:
                allowed = ', '.join(self.ALLOWED_LOOKUPS)
                raise SyncanoValueError('Invalid lookup type {0} allowed are {1}.'.format(lookup, allowed))

            for field in self.model.fields:
                if field.name == field_name:
                    break

            query.setdefault(field_name, {})
            query[field_name]['_{0}'.format(lookup)] = field.to_query(value, lookup)

        self.query['query'] = query
        self.method = 'GET'
        self.endpoint = 'list'
        return self


class SchemaManager(object):
    """
    Custom :class:`~syncano.models.manager.Manager`
    class for :class:`~syncano.models.fields.SchemaFiled`.
    """

    def __init__(self, schema=None):
        self.schema = schema or []

    def __str__(self):
        return str(self.schema)

    def __repr__(self):
        return '<SchemaManager>'

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.schema[key]

        if isinstance(key, six.string_types):
            for v in self.schema:
                if v['name'] == key:
                    return v

        raise KeyError

    def __setitem__(self, key, value):
        value = deepcopy(value)
        value['name'] = key
        self.remove(key)
        self.add(value)

    def __delitem__(self, key):
        self.remove(key)

    def __iter__(self):
        return iter(self.schema)

    def __contains__(self, item):
        if not self.schema:
            return False
        return item in self.schema

    def set(self, value):
        """Sets schema value."""
        self.schema = value

    def add(self, *objects):
        """Adds multiple objects to schema."""
        self.schema.extend(objects)

    def remove(self, *names):
        """Removes selected objects based on their names."""
        values = [v for v in self.schema if v['name'] not in names]
        self.set(values)

    def clear(self):
        """Sets empty schema."""
        self.set([])

    def set_index(self, field, order=False, filter=False):
        """Sets index on selected field.

        :type field: string
        :param field: Name of schema field

        :type filter: bool
        :param filter: Sets filter index on selected field

        :type order: bool
        :param order: Sets order index on selected field
        """
        if not order and not filter:
            raise ValueError('Choose at least one index.')

        if order:
            self[field]['order_index'] = True

        if filter:
            self[field]['filter_index'] = True

    def set_order_index(self, field):
        """Shortcut for ``set_index(field, order=True)``."""
        self.set_index(field, order=True)

    def set_filter_index(self, field):
        """Shortcut for ``set_index(field, filter=True)``."""
        self.set_index(field, filter=True)

    def remove_index(self, field, order=False, filter=False):
        """Removes index from selected field.

        :type field: string
        :param field: Name of schema field

        :type filter: bool
        :param filter: Removes filter index from selected field

        :type order: bool
        :param order: Removes order index from selected field
        """
        if not order and not filter:
            raise ValueError('Choose at least one index.')

        if order and 'order_index' in self[field]:
            del self[field]['order_index']

        if filter and 'filter_index' in self[field]:
            del self[field]['filter_index']

    def remove_order_index(self, field):
        """Shortcut for ``remove_index(field, order=True)``."""
        self.remove_index(field, order=True)

    def remove_filter_index(self, field):
        """Shortcut for ``remove_index(field, filter=True)``."""
        self.remove_index(field, filter=True)
