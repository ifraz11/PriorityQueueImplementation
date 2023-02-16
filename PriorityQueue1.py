# -*- coding: utf-8 -*-

# AudioMe App Queue Implementation 1


try:
    from collections.abc import MutableMapping as _MutableMapping
except ImportError:
    # 2.7 compatability
    from collections import MutableMapping as _MutableMapping

from six.moves import range
from operator import lt, gt


__version__ = "1.2.0"
__all__ = ["pqdict", "PQDict", "minpq", "maxpq", "nlargest", "nsmallest"]


class _Node(object):
    __slots__ = ("key", "value", "prio")

    def __init__(self, key, value, prio):
        self.key = key
        self.value = value
        self.prio = prio

    def __repr__(self):
        return self.__class__.__name__ + "(%s, %s, %s)" % (
            repr(self.key),
            repr(self.value),
            repr(self.prio),
        )


class pqdict(_MutableMapping):

    def __init__(self, data=None, key=None, reverse=False, precedes=lt):
        if reverse:
            if precedes == lt:
                precedes = gt
            else:
                raise ValueError("Got both `reverse=True` and a custom `precedes`.")

        if key is None or callable(key):
            self._keyfn = key
        else:
            raise ValueError(
                "`key` function must be a callable; got {}".format(type(key))
            )

        if callable(precedes):
            self._precedes = precedes
        else:
            raise ValueError(
                "`precedes` function must be a callable; got {}".format(type(precedes))
            )

        # The heap
        self._heap = []

        # The index
        self._position = {}

        if data is not None:
            self.update(data)

    @property
    def precedes(self):
        """Priority key precedence function"""
        return self._precedes

    @property
    def keyfn(self):
        """Priority key function"""
        return self._keyfn if self._keyfn is not None else lambda x: x

    def __repr__(self):
        things = ", ".join(
            ["%s: %s" % (repr(node.key), repr(node.value)) for node in self._heap]
        )
        return self.__class__.__name__ + "({" + things + "})"

    ############
    # dict API #
    ############
    __marker = object()
    __eq__ = _MutableMapping.__eq__
    __ne__ = _MutableMapping.__ne__
    keys = _MutableMapping.keys
    values = _MutableMapping.values
    items = _MutableMapping.items
    get = _MutableMapping.get
    clear = _MutableMapping.clear
    update = _MutableMapping.update
    setdefault = _MutableMapping.setdefault

    @classmethod
    def fromkeys(cls, iterable, value, **kwargs):
        """
        Return a new pqict mapping keys from an iterable to the same value.

        """
        return cls(((k, value) for k in iterable), **kwargs)

    def __len__(self):
        """
        Return number of items in the pqdict.

        """
        return len(self._heap)

    def __contains__(self, key):
        """
        Return ``True`` if key is in the pqdict.

        """
        return key in self._position

    def __iter__(self):
        """
        Return an iterator over the keys of the pqdict. The order of iteration
        is arbitrary! Use ``popkeys`` to iterate over keys in priority order.

        """
        for node in self._heap:
            yield node.key

    def __getitem__(self, key):
        """
        Return the priority value of ``key``. Raises a ``KeyError`` if not in
        the pqdict.

        """
        return self._heap[self._position[key]].value  # raises KeyError

    def __setitem__(self, key, value):
        """
        Assign a priority value to ``key``.

        """
        heap = self._heap
        position = self._position
        keygen = self._keyfn
        try:
            pos = position[key]
        except KeyError:
            # add
            n = len(heap)
            prio = keygen(value) if keygen is not None else value
            heap.append(_Node(key, value, prio))
            position[key] = n
            self._swim(n)
        else:
            # update
            prio = keygen(value) if keygen is not None else value
            heap[pos].value = value
            heap[pos].prio = prio
            self._reheapify(pos)

    def __delitem__(self, key):
        """
        Remove item. Raises a ``KeyError`` if key is not in the pq.

        """
        heap = self._heap
        position = self._position
        pos = position.pop(key)  # raises KeyError
        node_to_delete = heap[pos]
        # Take the very last node and place it in the vacated spot. Let it
        # sink or swim until it reaches its new resting place.
        end = heap.pop(-1)
        if end is not node_to_delete:
            heap[pos] = end
            position[end.key] = pos
            self._reheapify(pos)
        del node_to_delete

    def copy(self):
        other = self.__class__(key=self._keyfn, precedes=self._precedes)
        other._position = self._position.copy()
        other._heap = [_Node(node.key, node.value, node.prio) for node in self._heap]
        return other

    def topitem(self):
        """
        Return the item with highest priority. Raises ``KeyError`` if pqdict is
        empty.

        """
        try:
            node = self._heap[0]
        except IndexError:
            raise KeyError("pqdict is empty")
        return node.key, node.value

    def additem(self, key, value):
        """
        Add a new item. Raises ``KeyError`` 

        """
        if key in self._position:
            raise KeyError("%s is already in the queue" % repr(key))
        self[key] = value

    def pushpopitem(self, key, value):
        """
        Equivalent to inserting a new item followed by removing the top
        priority item, but faster. Raises ``KeyError`` if the new key is
        already in the pqdict.

        """
        heap = self._heap
        position = self._position
        precedes = self._precedes
        prio = self._keyfn(value) if self._keyfn else value
        node = _Node(key, value, prio)
        if key in self:
            raise KeyError("%s is already in the queue" % repr(key))
        if heap and precedes(heap[0].prio, node.prio):
            node, heap[0] = heap[0], node
            position[key] = 0
            del position[node.key]
            self._sink(0)
        return node.key, node.value

    def updateitem(self, key, new_val):
        """
        Update the priority value of an existing item. Raises ``KeyError`` if
        key is not in the pqdict.

        """
        if key not in self._position:
            raise KeyError(key)
        self[key] = new_val

    def replace_key(self, key, new_key):
        """
        Replace the key of an existing heap node in place. Raises ``KeyError``
        if the key to replace does not exist or if the new key is already in
        the pqdict.

        """
        heap = self._heap
        position = self._position
        if new_key in self:
            raise KeyError("%s is already in the queue" % repr(new_key))
        pos = position.pop(key)  # raises appropriate KeyError
        position[new_key] = pos
        heap[pos].key = new_key
