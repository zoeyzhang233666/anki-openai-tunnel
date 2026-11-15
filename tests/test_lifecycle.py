"""Exercise real QProcess children without importing Anki or contacting OpenAI."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PyQt6 import QtCore, QtWidgets, QtGui
    QT = True
except ImportError:
    QT = False


@unittest.skipUnless(QT, 'Install PyQt6 for QProcess lifecycle tests')
class LifecycleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        cls.tmp = tempfile.TemporaryDirectory()
        cls.fake = Path(cls.tmp.name) / 'fake_client.py'
        cls.fake.write_text('''import os, sys, time
stage = sys.argv[1]
secret = os.environ.get('CONTROL_PLANE_API_KEY', '')
if stage == 'doctor':
    sys.stdout.write(secret[:4]); sys.stdout.flush(); time.sleep(0.05)
    print(secret[4:]); sys.stdout.flush()
else:
    print('fake runtime started', flush=True)
    time.sleep(60)
''')
        class Process(QtCore.QProcess):
            def start(self, program, args):
                super().start(program, [str(cls.fake), *args])
        mw = QtWidgets.QMainWindow()
        mw.app = cls.app
        mw.form = types.SimpleNamespace(menuTools=mw.menuBar().addMenu('Tools'))
        aqt = types.ModuleType('aqt'); aqt.mw = mw
        qt = types.ModuleType('aqt.qt')
        for name in ['QDialog', 'QDialogButtonBox', 'QFileDialog', 'QFormLayout',
                     'QInputDialog', 'QLineEdit']:
            setattr(qt, name, getattr(QtWidgets, name))
        qt.QAction = QtGui.QAction
        qt.QProcess = Process
        qt.QProcessEnvironment = QtCore.QProcessEnvironment
        qt.QTimer = QtCore.QTimer
        utils = types.ModuleType('aqt.utils')
        cls.messages = []
        utils.showInfo = cls.messages.append; utils.showWarning = cls.messages.append
        cls.old_modules = {name: sys.modules.get(name) for name in ['aqt', 'aqt.qt', 'aqt.utils']}
        sys.modules.update({'aqt': aqt, 'aqt.qt': qt, 'aqt.utils': utils})
        root = Path(__file__).resolve().parents[1] / 'addon'
        spec = importlib.util.spec_from_file_location('test_addon', root / '__init__.py',
                                                     submodule_search_locations=[str(root)])
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules['test_addon'] = cls.module
        spec.loader.exec_module(cls.module)
        cls.module.STATE = Path(cls.tmp.name)
        cls.mw = mw

    @classmethod
    def tearDownClass(cls):
        cls.module.controller.shutdown()
        cls.tmp.cleanup()
        for name, old in cls.old_modules.items():
            if old is None: sys.modules.pop(name, None)
            else: sys.modules[name] = old

    def setUp(self):
        self.controller = self.module.controller
        self.controller.shutdown()
        self.controller.tail = ''
        self.controller.secret = 'synthetic-test-secret'
        self.controller.active_config = {'binary': sys.executable, 'organization_id': ''}

    def pump(self, condition):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition(): return
            time.sleep(0.01)
        self.fail('QProcess lifecycle condition timed out')

    def test_doctor_run_stop_and_chunk_redaction(self):
        self.controller.launch('doctor')
        self.pump(lambda: 'fake runtime started' in self.controller.tail)
        self.assertEqual(self.controller.stage, 'run')
        self.assertTrue(self.controller.running())
        self.assertNotIn('synthetic-test-secret', self.controller.tail)
        self.assertIn('[REDACTED]', self.controller.tail)
        process = self.controller.process
        self.controller.shutdown()
        self.assertFalse(self.controller.running())
        self.assertEqual(self.controller.secret, '')
        self.assertEqual(process.state(), QtCore.QProcess.ProcessState.NotRunning)

    def test_shutdown_during_doctor_never_starts_run(self):
        self.controller.launch('doctor')
        self.controller.shutdown()
        self.app.processEvents()
        self.assertFalse(self.controller.running())
        self.assertNotIn('fake runtime started', self.controller.tail)
        self.assertEqual(self.controller.secret, '')
