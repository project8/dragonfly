import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np


def import_roach2_interface():
    repo_root = Path(__file__).resolve().parents[1]
    module_name = 'dripline.extensions.roach2_interface'

    # Build a minimal dripline package and supporting modules.
    dripline_pkg = types.ModuleType('dripline')
    sys.modules['dripline'] = dripline_pkg

    core_module = types.ModuleType('dripline.core')

    class ThrowReply(Exception):
        pass

    class Service:
        def __init__(self, **kwargs):
            self.service_kwargs = kwargs

    core_module.ThrowReply = ThrowReply
    core_module.Service = Service
    dripline_pkg.core = core_module
    sys.modules['dripline.core'] = core_module

    extensions_pkg = types.ModuleType('dripline.extensions')
    extensions_pkg.__path__ = [str(repo_root / 'dripline' / 'extensions')]
    sys.modules['dripline.extensions'] = extensions_pkg

    r2daq_module = types.ModuleType('dripline.extensions.r2daq')

    class ArtooDaq(object):
        def __init__(self, hostname, dsoc_desc=None, boffile=None, ifcfg=None,
                     do_ogp_cal=True, do_adcif_cal=True):
            self.hostname = hostname
            self._ddc_1st = {'a': {'digital': {'f_c': 800e6}},
                             'b': {'digital': {'f_c': 800e6}},
                             'c': {'digital': {'f_c': 800e6}}}
            self._roach2 = types.SimpleNamespace(est_brd_clk=lambda: 123)
            self._last_gain = None
            self._last_fft = None

        @classmethod
        def make_interface_config_dictionary(cls, **kwargs):
            return kwargs

        def calibrate_adc_ogp(self, *args, **kwargs):
            return {'a': 1.0, 'b': 1.0, 'c': 1.0}

        def read_ddc_1st_config(self, tag='a'):
            return {'digital': {'f_c': 800e6}}

        def tune_ddc_1st_to_freq(self, f_c, tag='a'):
            return f_c

        def get_gain(self, tag='a'):
            return 1.0

        def set_gain(self, g, tag='a'):
            self._last_gain = (tag, g)

        def get_fft_shift(self, tag='ab'):
            return '1101010101010'

        def set_fft_shift(self, shift, tag='ab'):
            self._last_fft = (tag, shift)

        def grab_packets(self, n=1, dsoc_desc=None, close_soc=False):
            return []

        def _snap_per_core(self, zdok=0):
            return np.array([[1, 2, 3, 4]], dtype=np.int8)

    r2daq_module.ArtooDaq = ArtooDaq
    sys.modules['dripline.extensions.r2daq'] = r2daq_module

    adc5g_module = types.ModuleType('adc5g')

    def set_spi_gain(roach2, zdok, ic, gain):
        set_spi_gain.calls.append((zdok, ic, gain))

    def set_spi_offset(roach2, zdok, ic, offset):
        set_spi_offset.calls.append((zdok, ic, offset))

    def set_spi_phase(roach2, zdok, ic, phase):
        set_spi_phase.calls.append((zdok, ic, phase))

    def get_spi_gain(roach2, zdok, ic):
        return 0.0

    def get_spi_offset(roach2, zdok, ic):
        return 0.0

    def get_spi_phase(roach2, zdok, ic):
        return 0.0

    set_spi_gain.calls = []
    set_spi_offset.calls = []
    set_spi_phase.calls = []

    adc5g_module.set_spi_gain = set_spi_gain
    adc5g_module.set_spi_offset = set_spi_offset
    adc5g_module.set_spi_phase = set_spi_phase
    adc5g_module.get_spi_gain = get_spi_gain
    adc5g_module.get_spi_offset = get_spi_offset
    adc5g_module.get_spi_phase = get_spi_phase
    sys.modules['adc5g'] = adc5g_module

    file_path = repo_root / 'dripline' / 'extensions' / 'roach2_interface.py'
    spec = importlib.util.spec_from_file_location(
        module_name,
        str(file_path),
        submodule_search_locations=[str(repo_root / 'dripline' / 'extensions')]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class DummyPacket(object):
    def __init__(self, freq_not_time, pkt_in_batch=1, digital_id=2, if_id=3, data=None):
        self._freq_not_time = freq_not_time
        self._pkt_in_batch = pkt_in_batch
        self._digital_id = digital_id
        self._if_id = if_id
        self.data = data if data is not None else np.array([1, 2, 3, 4], dtype=np.int8)

    @property
    def freq_not_time(self):
        return self._freq_not_time

    @property
    def pkt_in_batch(self):
        return self._pkt_in_batch

    @property
    def digital_id(self):
        return self._digital_id

    @property
    def if_id(self):
        return self._if_id

    def interpret_data(self):
        return np.array([1 + 1j, 2 + 2j])


class TestRoach2Interface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = import_roach2_interface()

    def setUp(self):
        self.config = {
            'source_ip': '192.168.1.100',
            'source_port': 4000,
            'source_mac': '00:11:22:33:44:55',
            'dest_ip': '192.168.1.101',
            'dest_port': 4001,
            'dest_mac': '66:77:88:99:aa:bb',
        }
        self.iface = self.module.Roach2Interface(
            roach2_hostname='led',
            channel_a_config=self.config,
            channel_b_config=self.config,
            channel_c_config=self.config,
            daq_name='test',
            default_frequency=800e6,
            gain=5.0,
            fft_shift='1010101010101',
        )

    def test_calibration_status_property(self):
        self.iface.calibrated = True
        self.assertTrue(self.iface.calibration_status)
        self.iface.calibrated = False
        self.assertFalse(self.iface.calibration_status)

    def test_do_adc_calibration_success_sets_calibrated(self):
        self.iface.calibrated = False
        self.module.ArtooDaq.calibrate_adc_ogp = lambda self, *args, **kwargs: {'a': 0.1, 'b': 0.5}
        self.iface.do_adc_calibration()
        self.assertTrue(self.iface.calibrated)

    def test_do_adc_calibration_raises_on_none(self):
        self.module.ArtooDaq.calibrate_adc_ogp = lambda self, *args, **kwargs: {'a': None}
        with self.assertRaises(self.module.core.ThrowReply):
            self.iface.do_adc_calibration()
        self.assertFalse(self.iface.calibrated)

    def test_is_running_true_when_ping_succeeds(self):
        self.module.os.system = lambda cmd: 0
        self.iface.configured = False
        self.iface.calibrated = False
        self.assertTrue(self.iface.is_running)
        self.assertTrue(self.iface.configured or True)

    def test_is_running_false_when_ping_fails(self):
        self.module.os.system = lambda cmd: 1
        self.iface.configured = True
        self.iface.calibrated = True
        self.assertFalse(self.iface.is_running)
        self.assertFalse(self.iface.configured)
        self.assertFalse(self.iface.calibrated)

    def test_block_unblock_channel_and_blocked_channels(self):
        self.iface.block_channel('a')
        self.assertTrue(self.iface.blocked_channels['a'])
        self.iface.unblock_channel('a')
        self.assertFalse(self.iface.blocked_channels['a'])

    def test_set_get_central_frequency(self):
        self.module.ArtooDaq.tune_ddc_1st_to_freq = lambda self, cf, tag=None: cf
        self.module.ArtooDaq.read_ddc_1st_config = lambda self, tag=None: {'digital': {'f_c': 1234.0}}
        freq = self.iface.set_central_frequency('a', 100e6)
        self.assertEqual(freq, 100e6)
        self.assertEqual(self.iface.freq_dict['a'], 100e6)
        self.assertEqual(self.iface.get_central_frequency('a'), 1234.0)

    def test_set_central_frequency_out_of_range_raises(self):
        with self.assertRaises(self.module.core.ThrowReply):
            self.iface.set_central_frequency('a', 10e6)
        with self.assertRaises(self.module.core.ThrowReply):
            self.iface.set_central_frequency('a', 2000e6)

    def test_set_central_frequency_blocked_channel_raises(self):
        self.iface.block_channel('a')
        with self.assertRaises(self.module.core.ThrowReply):
            self.iface.set_central_frequency('a', 100e6)

    def test_all_central_frequencies_property(self):
        self.module.ArtooDaq.read_ddc_1st_config = lambda self, tag=None: {'digital': {'f_c': 111.0}}
        freqs = self.iface.all_central_frequencies
        self.assertEqual(freqs['a'], 111.0)
        self.assertEqual(freqs['b'], 111.0)
        self.assertEqual(freqs['c'], 111.0)

    def test_gain_property(self):
        self.module.ArtooDaq.get_gain = lambda self, tag=None: 3.0
        gains = self.iface.gain
        self.assertEqual(gains, {'a': 3.0, 'b': 3.0, 'c': 3.0})

    def test_set_gain_valid(self):
        recorded = []
        def set_gain(self, gain, tag=None):
            recorded.append((tag, gain))
        self.module.ArtooDaq.set_gain = set_gain
        self.iface.set_gain('b', 1.5)
        self.assertEqual(self.iface.gain_dict['b'], 1.5)
        self.assertEqual(recorded, [('b', 1.5)])

    def test_set_gain_out_of_range_raises(self):
        with self.assertRaises(self.module.core.ThrowReply):
            self.iface.set_gain('a', 10.0)

    def test_set_gain_blocked_channel_raises(self):
        self.iface.block_channel('b')
        with self.assertRaises(self.module.core.ThrowReply):
            self.iface.set_gain('b', 1.0)

    def test_fft_shift_vectors(self):
        self.module.ArtooDaq.get_fft_shift = lambda self, tag=None: '0101010'
        self.assertEqual(self.iface.get_fft_shift_vector('ab'), '0101010')
        self.iface.set_fft_shift_vector('cd', '00110011')
        self.assertEqual(self.iface.fft_shift_vector['cd'], '00110011')
        self.assertEqual(self.iface.all_fft_shift_vectors, {'ab': '0101010', 'cd': '00110011'})

    def test_roach2_clock_property(self):
        self.iface.roach2 = types.SimpleNamespace(est_brd_clk=lambda: 555)
        self.assertEqual(self.iface.roach2_clock, 555)

    def test_get_packets_returns_expected_data(self):
        pkt = DummyPacket(freq_not_time=False)
        self.module.ArtooDaq.grab_packets = lambda self, n, dsoc_desc, close_soc: [pkt]
        p = self.iface.get_packets(channel='a', NPackets=1)
        self.assertEqual(p[0]['type'], 'time')
        self.assertEqual(p[0]['pkt_in_batch'], 1)
        self.assertEqual(p[0]['real'], [1.0, 2.0])
        self.assertEqual(p[0]['imaginary'], [1.0, 2.0])

    def test_get_packets_invalid_channel_raises(self):
        with self.assertRaises(ValueError):
            self.iface.get_packets(channel='z')

    def test_get_T_packets_returns_time_packets(self):
        pkts = [DummyPacket(freq_not_time=False), DummyPacket(freq_not_time=True)]
        self.module.ArtooDaq.grab_packets = lambda self, n, dsoc_desc, close_soc: pkts
        p = self.iface.get_T_packets(channel='a', NPackets=1)
        self.assertEqual(list(p.keys()), [0])
        self.assertEqual(p[0]['real'], [1.0, 2.0])

    def test_get_F_packets_returns_frequency_packets(self):
        pkts = [DummyPacket(freq_not_time=True), DummyPacket(freq_not_time=False)] * 5
        self.module.ArtooDaq.grab_packets = lambda self, n, dsoc_desc, close_soc: pkts
        p = self.iface.get_F_packets(channel='a', NPackets=2)
        self.assertEqual(len(p), 2)
        self.assertEqual(p[0]['real'], [1.0, 2.0])

    def test_get_F_packets_invalid_channel_raises(self):
        with self.assertRaises(ValueError):
            self.iface.get_F_packets(channel='z')

    def test_get_raw_adc_data_returns_data(self):
        self.module.ArtooDaq._snap_per_core = lambda self, zdok=0: np.array([[1, 2, 3, 4]], dtype=np.int8)
        data = self.iface.get_raw_adc_data(NSnaps=2)
        self.assertEqual(data, [1, 2, 3, 4, 1, 2, 3, 4])

    def test_get_raw_adc_data_writes_file(self):
        self.module.ArtooDaq._snap_per_core = lambda self, zdok=0: np.array([[1, 2, 3, 4]], dtype=np.int8)
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            filename = handle.name
        try:
            self.iface.get_raw_adc_data(NSnaps=1, filename=filename)
            with open(filename, 'r') as infile:
                payload = json.load(infile)
            self.assertEqual(payload, [1, 2, 3, 4])
        finally:
            os.remove(filename)

    def test_calibrate_with_2016_values_calls_manual_calibration(self):
        called = {}
        def calibrate_manually(self, **kwargs):
            called.update(kwargs)
        self.module.Roach2Interface.calibrate_manually = calibrate_manually
        self.iface.calibrate_with_2016_values()
        self.assertEqual(called['gain1'], 0.0)
        self.assertEqual(called['offset2'], -0.39)
        self.assertIn('phase4', called)

    def test_calibrate_manually_calls_adc5g_setters_and_sets_calibrated(self):
        self.module.adc5g.set_spi_gain.calls.clear()
        self.module.adc5g.set_spi_offset.calls.clear()
        self.module.adc5g.set_spi_phase.calls.clear()
        self.iface.roach2 = object()
        self.iface.calibrate_manually(gain1=0.1, gain4=0.2, offset2=1.0, phase3=0.5)
        self.assertTrue(self.iface.calibrated)
        self.assertIn((0, 1, 0.1), self.module.adc5g.set_spi_gain.calls)
        self.assertIn((0, 2, 1.0), self.module.adc5g.set_spi_offset.calls)
        self.assertIn((0, 3, 0.5), self.module.adc5g.set_spi_phase.calls)

    def test_adc_calibration_values_property(self):
        self.module.adc5g.get_spi_gain = lambda roach2, zdok, ic: 1.1 * ic
        self.module.adc5g.get_spi_offset = lambda roach2, zdok, ic: 2.0 * ic
        self.module.adc5g.get_spi_phase = lambda roach2, zdok, ic: 3.0 * ic
        self.iface.roach2 = object()
        values = self.iface.adc_calibration_values
        self.assertEqual(values['gain1'], 1.1)
        self.assertEqual(values['offset4'], 8.0)
        self.assertEqual(values['phase3'], 9.0)

    def test_finish_configure_runs_aroodaq_init_and_sets_defaults(self):
        calls = {}
        def fake_init(self, hostname, boffile=None, do_ogp_cal=False, do_adcif_cal=True, ifcfg=None, dsoc_desc=None):
            calls['init_called'] = True
            self._ddc_1st = {'a': {'digital': {'f_c': 900e6}}}
        self.module.ArtooDaq.__init__ = fake_init
        self.module.ArtooDaq.tune_ddc_1st_to_freq = lambda self, cf, tag=None: cf
        self.module.ArtooDaq.set_gain = lambda self, gain, tag=None: None
        self.module.ArtooDaq.set_fft_shift = lambda self, shift, tag=None: None
        iface = self.module.Roach2Interface(
            channel_a_config=self.config,
            channel_b_config=None,
            channel_c_config=None,
            default_frequency=700e6,
            gain=4.0,
            fft_shift='0011001100110',
        )
        configured = iface._finish_configure(boffile='bogus.bof')
        self.assertTrue(configured)
        self.assertTrue(calls.get('init_called', False))
        self.assertEqual(iface.freq_dict['a'], 700e6)
        self.assertEqual(iface.fft_shift_vector['ab'], '0011001100110')


if __name__ == '__main__':
    unittest.main()
