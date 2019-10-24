__author__ = "Rick Sherman"
__credits__ = "Jeremy Schulman"

import unittest
import os
import yaml
from nose.plugins.attrib import attr

from jnpr.junos import Device
from jnpr.junos.op.phyport import PhyPortStatsTable
from jnpr.junos.op.ethport import EthPortTable
from jnpr.junos.factory.factory_loader import FactoryLoader
from jnpr.junos.factory.optable import generate_sax_parser_input

from ncclient.manager import Manager, make_device_handler
from ncclient.transport import SSHSession
from ncclient.operations.rpc import RPCReply

from lxml import etree

from mock import patch


@attr('unit')
class TestFactoryOpTable(unittest.TestCase):

    @patch('ncclient.manager.connect')
    def setUp(self, mock_connect):
        mock_connect.side_effect = self._mock_manager
        self.dev = Device(host='1.1.1.1', user='rick', password='password123',
                          gather_facts=False)
        self.dev.open()
        self.ppt = PhyPortStatsTable(self.dev)

    @patch('jnpr.junos.Device.execute')
    def test_optable_get(self, mock_execute):
        mock_execute.side_effect = self._mock_manager
        self.ppt.get()
        self.assertEqual(len(self.ppt), 2)

    @patch('jnpr.junos.Device.execute')
    def test_optable_get_key(self, mock_execute):
        mock_execute.side_effect = self._mock_manager
        self.ppt.get('ge-0/0/0')
        self.assertEqual(self.ppt.GET_KEY, 'interface_name')

    def test_optable_path(self):
        fname = 'local-get-interface-information.xml'
        path = os.path.join(os.path.dirname(__file__),
                            'rpc-reply', fname)
        lppt = PhyPortStatsTable(path=path)
        lppt.get()
        self.assertEqual(len(lppt), 2)

    def test_optable_xml(self):
        fname = 'get-interface-information.xml'
        xml = self._read_file(fname)
        lppt = PhyPortStatsTable(xml=xml)
        lppt.get()
        self.assertEqual(len(lppt), 2)

    @patch('jnpr.junos.Device.execute')
    def test_optable_view_get(self, mock_execute):
        mock_execute.side_effect = self._mock_manager
        self.ppt.get()
        v = self.ppt['ge-0/0/0']
        self.assertEqual(v['rx_packets'], 1207)

    @patch('jnpr.junos.Device.execute')
    def test_optable_view_get_astype_bool(self, mock_execute):
        mock_execute.side_effect = self._mock_manager
        et = EthPortTable(self.dev)
        et.get()
        v = et['ge-0/0/0']
        self.assertEqual(v['present'], True)

    @patch('jnpr.junos.Device.execute')
    def test_optable_view_get_astype_bool_regex(self, mock_execute):
        mock_execute.side_effect = self._mock_manager
        from jnpr.junos.op.bfd import BfdSessionTable
        bfd = BfdSessionTable(self.dev)
        bfd.get()
        v = bfd['10.92.20.4']
        self.assertEqual(v['no_absorb'], True)

    @patch('jnpr.junos.Device.execute')
    def test_optable_view_get_unknown_field(self, mock_execute):
        mock_execute.side_effect = self._mock_manager
        self.ppt.get()

        def bad(key):
            v = self.ppt['ge-0/0/0']
            return v[key]

        self.assertRaises(ValueError, bad, 'bunk')

    def test_generate_sax_parser_item_with_many_slash(self):
        yaml_data = """
---
taskmallocdetail:
    rpc: get-task-memory-information
    args:
        level: detail
    item: task-memory-malloc-usage-report/task-malloc-list/task-malloc
    key: tm-name
    view: taskmallocview

taskmallocview:
    fields:
        tmallocs: tm-allocs
        tmallocbytes: tm-alloc-bytes
        tmmaxallocs: tm-max-allocs
        tmmaxallocbytes: tm-max-alloc-bytes
        tmfunctioncalls: tm-function-calls
"""
        globals().update(FactoryLoader().load(yaml.load(yaml_data,
                                                        Loader=yaml.Loader)))
        tbl = taskmallocdetail(self.dev)
        data = generate_sax_parser_input(tbl)
        self.assertEqual(data.tag, 'task-memory-malloc-usage-report')
        self.assertEqual(len(etree.tostring(data)), len(
            b'<task-memory-malloc-usage-report><task-malloc-list><task-malloc><tm-name/><t'
            b'm-allocs/><tm-alloc-bytes/><tm-max-allocs/><tm-max-alloc-bytes/><tm-function'
            b'-calls/></task-malloc></task-malloc-list></task-memory-malloc-usage-report>'))

    def test_generate_sax_parser_same_parents_with_diff_fields(self):
        yaml_data = """
---
VtepTable:
    rpc: get-interface-information
    args:
        interface-name: "vtep"
        extensive: True
    item: physical-interface
    key: name
    view: VtepView

VtepView:
    fields:
        admin-status: admin-status
        oper-status: oper-status
        link-level-type: link-level-type
        input-bytes: traffic-statistics/input-bytes
        output-bytes: traffic-statistics/output-bytes
        input-errors: input-error-list/input-errors
        output-errors: output-error-list/output-errors
        carrier-transitions: output-error-list/carrier-transitions
        vtep-tunnel-stats: VtepTunnelTable

VtepTunnelTable:
    item: logical-interface
    key: name
    view: VtepTunnelView

VtepTunnelView:
    fields:
        vtep-type: vtep-info/vtep-type
        vtep-address: vtep-info/vtep-address
        tunnel-input-bytes: traffic-statistics/input-bytes
        tunnel-output-bytes: traffic-statistics/output-bytes
    """
        globals().update(FactoryLoader().load(yaml.load(yaml_data,
                                                        Loader=yaml.Loader)))
        tbl = VtepTable(self.dev)
        data = generate_sax_parser_input(tbl)
        self.assertEqual(data.tag, 'physical-interface')
        self.assertEqual(len(etree.tostring(data)),len(
            b'<physical-interface><name/><admin-status/><oper-status/>'
            b'<link-level-type/><traffic-statistics><input-bytes/>'
            b'<output-bytes/></traffic-statistics><input-error-list>'
            b'<input-errors/></input-error-list><output-error-list>'
            b'<output-errors/><carrier-transitions/></output-error-list>'
            b'<logical-interface><name/><vtep-info><vtep-type/><vtep-address/>'
            b'</vtep-info><traffic-statistics><input-bytes/><output-bytes/>'
            b'</traffic-statistics></logical-interface></physical-interface>')
        )

    def _read_file(self, fname):
        from ncclient.xml_ import NCElement

        fpath = os.path.join(os.path.dirname(__file__),
                             'rpc-reply', fname)
        foo = open(fpath).read()
        reply = RPCReply(foo)
        reply.parse()
        rpc_reply = NCElement(reply, self.dev._conn.
                              _device_handler.transform_reply())\
            ._NCElement__doc[0]
        return rpc_reply

    def _mock_manager(self, *args, **kwargs):
        if kwargs:
            if args and ('normalize' in kwargs or 'filter_xml' in kwargs):
                return self._read_file(args[0].tag + '.xml')
            device_params = kwargs['device_params']
            device_handler = make_device_handler(device_params)
            session = SSHSession(device_handler)
            return Manager(session, device_handler)

        if args:
            return self._read_file(args[0].tag + '.xml')
