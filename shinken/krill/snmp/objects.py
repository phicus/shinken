#!/usr/bin/python
# -*- coding: utf-8 -*-

import time

from pysnmp.proto import errind

from shinken.log import logger

from client import SnmpRuntimeError

def as_tuples(properties):
    if isinstance(properties, dict):
        return [(k, v) for k, v in properties.iteritems()]
    else:
        return properties


def get_snmp_object(snmp_client, cls, subindex):

    # print 'get_snmp_object1'
    snmp_object = cls()
    cls_properties = getattr(cls, 'properties')
    try:
        for field, field_property in as_tuples(cls_properties):
            snmp_client_method = getattr(snmp_client, field_property.method)
            # print 'snmp_client_method', field, snmp_client_method, field_property.oid, subindex
            if field_property.method == 'get':
                try:
                    get_data = snmp_client.get(
                        oid=field_property.oid,
                        subindex=subindex,
                        timeout=getattr(cls, 'timeout', 3),
                        retries=getattr(cls, 'retries', 1),
                    )
                    # print 'snmp_client_method field, get_data', field, get_data
                    snmp_object.setattr(field, get_data)
                except Exception, exc:
                    logger.info("[SNMP] get_snmp_object get client=%s field=%s Exception=%s", snmp_client, field, exc)
            else:
                try:
                    walk_datas = snmp_client.walk(
                        oid=field_property.oid,
                        subindex=subindex,
                        timeout=getattr(cls, 'timeout', 3),
                        retries=getattr(cls, 'retries', 1),
                    )
                    snmp_object_data = []
                    for walk_index, walk_data in walk_datas:
                        snmp_object_data.append((tuple(list(walk_index)[len(subindex):]), walk_data.itervalues().next()))
                    snmp_object.setattr(field, snmp_object_data)
                except Exception, exc:
                    logger.info("[SNMP] get_snmp_object walk client=%s field=%s Exception=%s", snmp_client, field, exc)
    except SnmpRuntimeError, exc:
        # print 'SnmpRuntimeError', exc
        pass
    return snmp_object


def get_snmp_objects(snmp_client, cls, subindex=None):
    snmp_objects = []
    cls_properties = getattr(cls, 'properties')
    data_len = 0
    for field, field_property in as_tuples(cls_properties):
        if not field_property.oid:
            continue

        try:
            timeout = getattr(cls, 'timeout', 3)
            retries = getattr(cls, 'retries', 1)
            # walk_datas = _get_walk_data_up_to_len(snmp_client, len(snmp_objects), field_property.oid, subindex, timeout, retries, **field_property.kwargs)
            walk_datas = snmp_client.walk(field_property.oid, subindex, timeout, retries, **field_property.kwargs)
            fill_snmp_objects(snmp_objects, walk_datas, cls, field, field_property)
        except SnmpRuntimeError, exc:
            pass

    return snmp_objects


def try_snmp_objects(snmp_client, cls, subindex=None, timeout=4, retries=5):
    snmp_objects = []
    # logger.info("[SNMP-DOCSIS] try_snmp_objects1 %s", cls)
    cls_properties = getattr(cls, 'properties')
    for field, field_property in as_tuples(cls_properties):

        # logger.info("[SNMP-DOCSIS] try_snmp_objects2 %s %s", field, field_property.oid)
        if not field_property.oid:
            continue

        walk_datas = []
        try:
            walk_datas = snmp_client.walk(field_property.oid, subindex, timeout, retries, **field_property.kwargs)
        except errind.OidNotIncreasing:
            logger.info("[SNMP-DOCSIS] errind.OidNotIncreasing Exception in client=%s oid=%s ix=%s",
                        snmp_client, field_property.oid, subindex)
        except Exception, exc:
            logger.info("[SNMP-DOCSIS] try_snmp_objects Exception in client=%s oid=%s subix=%s exc=%s",
                        snmp_client, field_property.oid, subindex, exc)

        # logger.info("[SNMP-DOCSIS] try_snmp_objects3 walk_datas %d", len(walk_datas))
        fill_snmp_objects(snmp_objects, walk_datas, cls, field, field_property)
        # logger.info("[SNMP-DOCSIS] try_snmp_objects4 snmp_objects %d", len(snmp_objects))

    return snmp_objects


def fill_snmp_objects(snmp_objects, walk_datas, cls, field, field_property):
    # logger.info("[SNMP-DOCSIS] fill_snmp_objects walk_datas:%d snmp_objects:%d", len(walk_datas), len(snmp_objects))
    loop_index = 0
    for walk_index, walk_data in walk_datas:
        loop_index+=1
        # logger.info("[SNMP-DOCSIS] fill_snmp_objects loop (%d)", loop_index)
        # logger.info("[SNMP-DOCSIS] fill_snmp_objects walk_index:%s walk_data:%d snmp_objects:%d", walk_index, len(walk_data), len(snmp_objects))
        current_index = None
        current_subindex = None
        o = None
        for index, snmp_object in snmp_objects:
            # logger.info("[SNMP-DOCSIS] fill_snmp_objects snmp_object:%s", snmp_object)
            if walk_index == index:
                o = snmp_object
                current_index = index
            elif walk_index[0:len(index)] == index:
                o = snmp_object
                current_index = index
                current_subindex = walk_index[len(index):]

        if o is None:
            o = cls()
            if field_property.method == 'walk':
                o.setattr(field, [])

            snmp_objects.append((walk_index, o))
            # print 'fill_snmp_objects snmp_objects!', len(snmp_objects)

        # print 'fill_snmp_objects1', o, walk_index, walk_data, current_index, field, field_property.method
        # if current_index:
        #     o, = [o for i, o in snmp_objects if i == current_index]
        # else:
        #     o = cls()
        #     if field_property.method == 'walk':
        #         o.setattr(field, [])

        #     snmp_objects.append((walk_index, o))
        # print 'fill_snmp_objects2', o

        # logger.info("[SNMP-DOCSIS-FIXME] fill_snmp_objects and...")
        try:
            data_to_set = walk_data.itervalues().next()
        except Exception, exc:
            logger.warning("[SNMP-DOCSIS-FIXME] Exception walk_data:%s", walk_data)
            data_to_set = None

        if field_property.method == 'get':
            o.setattr(field, data_to_set)
        else:
            if current_subindex:
                o.appendattr(field, (tuple(current_subindex), data_to_set))
            else:
                logger.warning("[SNMP-DOCSIS-FIXME] no current_subindex (%s/%s/%s)...", walk_index, walk_data, data_to_set)
    # logger.info("[SNMP-DOCSIS] fill_snmp_objects!!!")


def _get_walk_data_up_to_len(snmp_client, up_to_len, oid, subindex, timeout, retries, **kwargs):

    walk_data_len = -100
    retries_count = 0
    errind_OidNotIncreasing = False

    MAX_RETRIES = 2
    DIFF_THRESHOLD = 10
    TIME_TO_WAIT_BETWEEN_RETRIES = 5

    while walk_data_len + DIFF_THRESHOLD < up_to_len and retries_count <= MAX_RETRIES and not errind_OidNotIncreasing:
        if retries_count > 0:
            logger.warning("[SNMP] _get_walk_data_up_to_len (%s) upto=%d, but only=%d (retries=%d)" %
                           (oid, up_to_len, walk_data_len, retries_count))
            time.sleep(TIME_TO_WAIT_BETWEEN_RETRIES)

        try:
            # print 'TFLK-WALK1', oid, subindex, timeout, retries, kwargs, '...'
            walk_data = snmp_client.walk(oid, subindex, timeout, retries, **kwargs)
            # print 'TFLK-WALK2 ...', len(walk_data)
        except errind.OidNotIncreasing:
            errind_OidNotIncreasing = True
            walk_data = []
        except Exception, exc:
            print 'Exception', exc
            logger.warning("[SNMP] _get_walk_data_up_to_len (client=%s/oid=%s) Exception: %s", snmp_client, oid, exc)
            raise exc
        # except SnmpRuntimeError, exc:
        #     walk_data = []

        walk_data_len = len(walk_data)
        retries_count += 1

    if walk_data_len + DIFF_THRESHOLD < up_to_len and not errind_OidNotIncreasing:
        logger.warning("[SNMP] _get_walk_data_up_to_len (%s) upto=%d, but only=%d -> SKIP" %
                       (oid, up_to_len, walk_data_len))
    return walk_data


class SnmpObject(object):

    properties = {}
    perf_data_properties = []
    perf_properties = []

    timeout = 4
    retries = 5


    def __getattribute__(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            try:
                return self.data[name]
            except KeyError:
                return None


    def __getstate__(self):
        return self.__dict__


    def __setstate__(self, state):
        self.__dict__ = state


    def setattr(self, field, data, subindex=None):
        if subindex:
            data_to_assign = self.getattr(field)
            if not data_to_assign:
                data_to_assign = {}
            # print 'setattr1', field, data, subindex, data_to_assign
            data_to_assign['%s' % (','.join(subindex))] = data
        else:
            # print 'setattr2', field, data
            data_to_assign = data

        # setattr(self, field, data_to_assign)
        self.data[field] = data_to_assign


    def appendattr(self, field, data):
        # print 'appendattr', self, field, data
        self.data[field].append(data)


    def getattr(self, field, default=None):
        return self.data.get(field, default)


    @property
    def perf_data(self):
        cls = self.__class__

        ret = {}
        for prop in cls.perf_data_properties:
            data = getattr(self, prop, None)
            f = getattr(self, 'perf_data_%s' % prop, None)
            if f and callable(f):
                ret[prop] = f()
            else:
                ret[prop] = data

        ret.update(self.additional_perf_data())
        return ret


    def additional_perf_data(self):
        return {}


    def new_perf(self, perf, value):
        if perf not in self.perf_fields:
            self.perf_fields.append(perf)
        self.setattr(perf, value)


    @property
    def perfs(self):
        ret = {}
        for prop in self.perf_fields:
            ret[prop] = self.getattr(prop)
        return ret


class WalkObject(SnmpObject):

    def __init__(self):
        self.perf_fields = []

        self.data = dict().copy()
        for field, field_property in as_tuples(self.properties):
            if field_property.method == 'get':

                if isinstance(field_property.default, dict):
                    self.setattr(field, field_property.default.copy())
                else:
                    self.setattr(field, field_property.default)
            else:
                self.setattr(field, list())

            # if isinstance(prop_definition.default, dict):
            #     #setattr(self, prop_key, dict().copy())
            #     self.setattr(prop_key, dict().copy())
            # else:
            #     self.setattr(prop_key, prop_definition.default)


class GetObject(SnmpObject):

    def __init__(self, community, ip, port=161):
        self.perf_fields = []

        self.community = community
        self.ip = ip
        self.port = port

        self.data = dict().copy()
        for prop_key in self.properties.keys():
            self.setattr(prop_key, None)


    def consolidate(self):
        pass
